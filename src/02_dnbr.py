"""Paso 2 · Un incendio visto de cerca: área quemada con dNBR.

Busca escenas Sentinel-2 L2A en Microsoft Planetary Computer alrededor del incendio elegido y escoge
la de antes y la de después por el % de píxeles válidos *dentro de la zona* (capa SCL), no por la
nubosidad de la escena completa. Calcula NBR = (B8A − B12)/(B8A + B12), dNBR = NBR antes − NBR
después y enmascara nubes, sombras, agua y nieve. Para no contar ruido, el umbral de quemado es el
mayor entre 0,10 y el percentil 95 del dNBR lejos del fuego (a más de 3 km de los focos), se suaviza
con una mediana de 3×3 y solo cuentan las manchas de 1 ha o más que tocan un foco (a ≤ 375 m).

Uso:      python src/02_dnbr.py <id_incendio>
Entradas: data/processed/incendios.csv, data/processed/focos.csv
Salidas:  data/cache/caso_*.tif (no se sube), data/processed/escenas_caso.csv,
          data/processed/resumen_paso2.json, outputs/dnbr_caso.png
"""
import json
import sys
import warnings
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import odc.stac
import pandas as pd
import planetary_computer as pc
import pystac_client
import rioxarray  # noqa: F401  (activa .rio en xarray)
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch
from scipy.ndimage import distance_transform_edt, label, median_filter

warnings.filterwarnings("ignore")
RAIZ = Path(__file__).resolve().parent.parent
PRO, CACHE, OUT = RAIZ / "data" / "processed", RAIZ / "data" / "cache", RAIZ / "outputs"
CACHE.mkdir(parents=True, exist_ok=True)
OUT.mkdir(exist_ok=True)

UTM, RES = "EPSG:32718", 20  # B8A y B12 vienen a 20 m
MARGEN_M = 2500  # recuadro: focos del incendio + 2,5 km
VALIDO_MIN = float(sys.argv[2]) if len(sys.argv) > 2 else 0.80  # mínimo de píxeles válidos en la zona
UMBRAL_MIN, LEJOS_M, TOCA_M, MANCHA_MIN_HA = 0.10, 3000, 375, 1.0
SCL_INVALIDO = [0, 1, 3, 6, 8, 9, 10, 11]  # sin dato, saturado, sombra, agua, nubes, cirros, nieve
SEVERIDAD = [(-1, 0.10, "No quemado"), (0.10, 0.27, "Baja"), (0.27, 0.44, "Moderada-baja"),
             (0.44, 0.66, "Moderada-alta"), (0.66, 2, "Alta")]  # Key y Benson (2006)

caso = int(sys.argv[1])
inc = pd.read_csv(PRO / "incendios.csv", index_col="incendio", parse_dates=["inicio", "fin"]).loc[caso]
focos = pd.read_csv(PRO / "focos.csv")
focos = focos[focos.incendio == caso]
pts = gpd.GeoSeries(gpd.points_from_xy(focos.longitude, focos.latitude), crs=4326).to_crs(UTM)
x0, y0, x1, y1 = pts.total_bounds
recuadro = gpd.GeoSeries.from_xy([x0 - MARGEN_M, x1 + MARGEN_M], [y0 - MARGEN_M, y1 + MARGEN_M], crs=UTM)
bbox = list(recuadro.to_crs(4326).total_bounds)
print(f"Incendio {caso}: {inc.distrito}, {inc.provincia} ({inc.departamento}), {inc.focos} focos, "
      f"{inc.inicio:%d %b %H:%M} → {inc.fin:%d %b %H:%M}")

cat = pystac_client.Client.open("https://planetarycomputer.microsoft.com/api/stac/v1", modifier=pc.sign_inplace)


def cargar(desde, hasta):
    """Escenas del periodo sobre el recuadro, una por día, con su % válido en la zona."""
    items = list(cat.search(collections=["sentinel-2-l2a"], bbox=bbox, datetime=f"{desde}/{hasta}").items())
    if not items:
        return None, pd.DataFrame()
    ds = odc.stac.load(items, bands=["B8A", "B12", "SCL"], bbox=bbox, crs=UTM, resolution=RES,
                       groupby="solar_day", chunks={})
    valido = (~ds.SCL.isin(SCL_INVALIDO)).mean(("x", "y")).compute().values
    nubes = {str(i.datetime.date()): i.properties.get("eo:cloud_cover") for i in items}
    base = {str(i.datetime.date()): float(i.properties.get("s2:processing_baseline", "0")) for i in items}
    tabla = pd.DataFrame({"fecha": [str(t)[:10] for t in ds.time.values], "valido_zona_pct": (100 * valido).round(1)})
    tabla["nubes_escena_pct"] = tabla.fecha.map(nubes).round(1)
    tabla["baseline"] = tabla.fecha.map(base)
    return ds, tabla


antes_ds, antes_t = cargar((inc.inicio - pd.Timedelta(days=45)).strftime("%Y-%m-%d"),
                           (inc.inicio - pd.Timedelta(days=1)).strftime("%Y-%m-%d"))
despues_ds, despues_t = cargar((inc.fin + pd.Timedelta(hours=12)).strftime("%Y-%m-%d"), "2026-10-22")
escenas = pd.concat([antes_t.assign(momento="antes"), despues_t.assign(momento="después")])
escenas.to_csv(PRO / "escenas_caso.csv", index=False)
print(escenas.to_string(index=False))

ok_a = antes_t[antes_t.valido_zona_pct >= 100 * VALIDO_MIN]
ok_d = despues_t[despues_t.valido_zona_pct >= 100 * VALIDO_MIN]
if ok_a.empty or ok_d.empty:
    sys.exit("No hay par de escenas con suficientes píxeles válidos en la zona: probar otro incendio.")
f_antes = ok_a.fecha.iloc[-1]  # la más cercana antes del fuego
f_despues = ok_d.fecha.iloc[0]  # la primera limpia después del fuego
print(f"\nPar elegido: antes {f_antes}, después {f_despues}")


def nbr(ds, fecha, baseline):
    """NBR en reflectancia. Desde la baseline 04.00 (ene 2022) L2A suma +1000 a los números digitales."""
    e = ds.sel(time=fecha).squeeze().compute()
    off = 1000 if baseline >= 4 else 0
    b8a = (e.B8A.astype("float32") - off) / 1e4
    b12 = (e.B12.astype("float32") - off) / 1e4
    return (b8a - b12) / (b8a + b12), ~e.SCL.isin(SCL_INVALIDO)


nbr_a, ok_pa = nbr(antes_ds, f_antes, antes_t.set_index("fecha").baseline[f_antes])
nbr_d, ok_pd = nbr(despues_ds, f_despues, despues_t.set_index("fecha").baseline[f_despues])
valido = (ok_pa & ok_pd).values
dnbr = (nbr_a - nbr_d).where(valido)

# Cerca de los focos: distancia de cada píxel al foco más cercano
xs, ys = dnbr.x.values, dnbr.y.values
foco = np.zeros(dnbr.shape, bool)
fi = np.clip(np.searchsorted(-ys, -pts.y.values), 0, len(ys) - 1)
fj = np.clip(np.searchsorted(xs, pts.x.values), 0, len(xs) - 1)
foco[fi, fj] = True
dist = distance_transform_edt(~foco) * RES
v = dnbr.values
ha_pix = RES * RES / 1e4

# Ruido de fondo: cuánto "cambia" el dNBR donde no hubo fuego (secado, diferencias entre fechas)
fondo = v[(dist > LEJOS_M) & np.isfinite(v)]
p95_fondo = float(np.percentile(fondo, 95))
umbral = max(UMBRAL_MIN, p95_fondo)


def manchas(u):
    """Píxeles de las manchas continuas con dNBR ≥ u (mediana 3×3) de ≥ 1 ha que tocan un foco."""
    m = median_filter(np.where(np.isfinite(v), v, -1), 3) >= u
    lab, _ = label(m, structure=np.ones((3, 3)))
    tam = np.bincount(lab.ravel()) * ha_pix
    toca = np.unique(lab[m & (dist <= TOCA_M)])
    return np.isin(lab, [k for k in toca if k > 0 and tam[k] >= MANCHA_MIN_HA])


quemado = manchas(umbral)
sev = {nombre: round(float((quemado & (v >= lo) & (v < hi)).sum() * ha_pix), 1)
       for lo, hi, nombre in SEVERIDAD if nombre != "No quemado"}

dnbr.rio.write_crs(UTM).rio.to_raster(CACHE / "caso_dnbr.tif")
dnbr.copy(data=quemado.astype("uint8")).rio.write_crs(UTM).rio.to_raster(CACHE / "caso_quemado.tif")

resumen = {
    "incendio": caso, "distrito": inc.distrito, "provincia": inc.provincia, "departamento": inc.departamento,
    "focos": int(inc.focos), "inicio": f"{inc.inicio:%Y-%m-%d %H:%M}", "fin": f"{inc.fin:%Y-%m-%d %H:%M}",
    "huella_viirs_ha": float(inc.huella_ha), "escena_antes": f_antes, "escena_despues": f_despues,
    "recuadro_km2": round(dnbr.size * ha_pix / 100, 1),
    "pct_valido_zona": round(100 * valido.mean(), 1),
    "dnbr_fondo_p95": round(p95_fondo, 3), "pct_fondo_sobre_010": round(100 * float((fondo >= 0.10).mean()), 1),
    "umbral": round(umbral, 3),
    "quemado_ha": round(float(quemado.sum() * ha_pix), 1),
    "quemado_ha_manchas_027": round(float(manchas(0.27).sum() * ha_pix), 1),
    "quemado_ha_pixel_010_a_1500m": round(float(((v >= 0.10) & (dist <= 1500)).sum() * ha_pix), 1),
    "severidad_ha": sev, "bbox_wgs84": [round(v, 5) for v in bbox],
}
(PRO / "resumen_paso2.json").write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(resumen, indent=2, ensure_ascii=False))

# Mapa: dNBR por clase de severidad, con los focos encima
colores = ["#d9d9d9", "#fee391", "#fe9929", "#d7301f", "#67000d"]
fig, ax = plt.subplots(figsize=(8, 7))
ext = [xs.min(), xs.max(), ys.min(), ys.max()]
ax.imshow(np.where(quemado, v, -0.5), extent=ext, cmap=ListedColormap(colores),
          norm=BoundaryNorm([-1, 0.10, 0.27, 0.44, 0.66, 2], 5))
ax.scatter(pts.x, pts.y, s=6, c="#2b8cbe", label="Focos VIIRS")
ax.set_title(f"{inc.distrito.title()} ({inc.departamento.title()}): {resumen['quemado_ha']:,.0f} ha quemadas "
             f"(dNBR ≥ {umbral:.2f}, manchas que tocan un foco)\nSentinel-2 {f_antes} → {f_despues}", fontsize=11)
ax.set_axis_off()
manijas = [Patch(color=c, label=nombre) for (_, _, nombre), c in zip(SEVERIDAD, colores)]
ax.legend(handles=[ax.collections[0], *manijas], loc="lower left", fontsize=8)
fig.savefig(OUT / "dnbr_caso.png", dpi=150, bbox_inches="tight")
