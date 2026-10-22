"""Paso 2 · Un incendio visto de cerca: área quemada con dNBR.

Busca escenas Sentinel-2 L2A en Microsoft Planetary Computer alrededor del incendio elegido y escoge
la de antes y la de después por el % de píxeles válidos *dentro de la zona* (capa SCL), no por la
nubosidad de la escena completa. Calcula NBR = (B8A − B12)/(B8A + B12), dNBR = NBR antes − NBR
después, enmascara nubes, sombras, agua y nieve, y cuenta como quemado lo que tiene dNBR ≥ 0,27 y
cae a 1,5 km o menos de algún foco del incendio.

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
from scipy.ndimage import distance_transform_edt

warnings.filterwarnings("ignore")
RAIZ = Path(__file__).resolve().parent.parent
PRO, CACHE, OUT = RAIZ / "data" / "processed", RAIZ / "data" / "cache", RAIZ / "outputs"
CACHE.mkdir(parents=True, exist_ok=True)
OUT.mkdir(exist_ok=True)

UTM, RES = "EPSG:32718", 20  # B8A y B12 vienen a 20 m
MARGEN_M = 2500  # recuadro: focos del incendio + 2,5 km
VALIDO_MIN = float(sys.argv[2]) if len(sys.argv) > 2 else 0.80  # mínimo de píxeles válidos en la zona
UMBRAL, CERCA_M = 0.27, 1500
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
cerca = distance_transform_edt(~foco) * RES <= CERCA_M

quemado = (dnbr.values >= UMBRAL) & cerca
ha_pix = RES * RES / 1e4
sev = {nombre: round(float(((dnbr.values >= lo) & (dnbr.values < hi) & cerca).sum() * ha_pix), 1)
       for lo, hi, nombre in SEVERIDAD}

dnbr.rio.write_crs(UTM).rio.to_raster(CACHE / "caso_dnbr.tif")
dnbr.copy(data=np.where(cerca, 1, 0).astype("uint8")).rio.write_crs(UTM).rio.to_raster(CACHE / "caso_cerca.tif")

resumen = {
    "incendio": caso, "distrito": inc.distrito, "provincia": inc.provincia, "departamento": inc.departamento,
    "focos": int(inc.focos), "inicio": f"{inc.inicio:%Y-%m-%d %H:%M}", "fin": f"{inc.fin:%Y-%m-%d %H:%M}",
    "huella_viirs_ha": float(inc.huella_ha), "escena_antes": f_antes, "escena_despues": f_despues,
    "recuadro_km2": round(dnbr.size * ha_pix / 100, 1),
    "pct_valido_zona": round(100 * valido.mean(), 1),
    "quemado_ha_dnbr_027": round(float(quemado.sum() * ha_pix), 1),
    "quemado_ha_dnbr_010": round(float(((dnbr.values >= 0.10) & cerca).sum() * ha_pix), 1),
    "severidad_ha": sev, "bbox_wgs84": [round(v, 5) for v in bbox],
}
(PRO / "resumen_paso2.json").write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(resumen, indent=2, ensure_ascii=False))

# Mapa: dNBR por clase de severidad, con los focos encima
colores = ["#d9d9d9", "#fee391", "#fe9929", "#d7301f", "#67000d"]
fig, ax = plt.subplots(figsize=(8, 7))
ext = [xs.min(), xs.max(), ys.min(), ys.max()]
ax.imshow(dnbr.values, extent=ext, cmap=ListedColormap(colores),
          norm=BoundaryNorm([-1, 0.10, 0.27, 0.44, 0.66, 2], 5))
ax.scatter(pts.x, pts.y, s=6, c="#2b8cbe", label="Focos VIIRS")
ax.set_title(f"{inc.distrito.title()} ({inc.departamento.title()}): {resumen['quemado_ha_dnbr_010']:,.0f} ha quemadas "
             f"(dNBR ≥ 0,10), {resumen['quemado_ha_dnbr_027']:,.0f} ha con dNBR ≥ 0,27\n"
             f"Sentinel-2 {f_antes} → {f_despues}", fontsize=11)
ax.set_axis_off()
manijas = [Patch(color=c, label=nombre) for (_, _, nombre), c in zip(SEVERIDAD, colores)]
ax.legend(handles=[ax.collections[0], *manijas], loc="lower left", fontsize=8)
fig.savefig(OUT / "dnbr_caso.png", dpi=150, bbox_inches="tight")
