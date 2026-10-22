"""Paso 1 · De focos de calor a incendios.

Lee los focos VIIRS de NASA FIRMS (S-NPP, NOAA-20 y NOAA-21, últimos 7 días), se queda con los
del Perú, quita los de confianza baja y los que caen junto a volcanes activos, y une en un mismo
incendio los focos que están a 1 km o menos y a 48 horas o menos entre sí.

Entradas: data/raw/*_South_America_7d.csv, data/raw/distritos.geojson
Salidas:  data/processed/focos.csv, data/processed/incendios.csv, data/processed/resumen_paso1.json
"""
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

RAIZ = Path(__file__).resolve().parent.parent
RAW, SAL = RAIZ / "data" / "raw", RAIZ / "data" / "processed"
SAL.mkdir(parents=True, exist_ok=True)
UTM = 32718  # UTM 18S: sirve para medir distancias en todo el Perú con error chico

# Volcanes que FIRMS detecta como "fuego" todo el año (lat, lon)
VOLCANES = {"Sabancaya": (-15.787, -71.857), "Ubinas": (-16.355, -70.903), "Misti": (-16.294, -71.409)}
RADIO_KM, VENTANA_H = 1.0, 48

# 1. Focos de los tres satélites
archivos = {"S-NPP": "SUOMI_VIIRS_C2", "NOAA-20": "J1_VIIRS_C2", "NOAA-21": "J2_VIIRS_C2"}
focos = pd.concat(
    [pd.read_csv(RAW / f"{a}_South_America_7d.csv").assign(sat=s) for s, a in archivos.items()],
    ignore_index=True,
)
n_crudos = len(focos)
hhmm = focos.acq_time.astype(str).str.zfill(4)
focos["hora_utc"] = pd.to_datetime(focos.acq_date + " " + hhmm.str[:2] + ":" + hhmm.str[2:], utc=True)
focos["hora_lima"] = focos.hora_utc.dt.tz_convert("America/Lima")

# 2. Solo Perú, con su distrito
dist = gpd.read_file(RAW / "distritos.geojson")[["NOMBDEP", "NOMBPROV", "NOMBDIST", "geometry"]]
g = gpd.GeoDataFrame(focos, geometry=gpd.points_from_xy(focos.longitude, focos.latitude), crs=4326)
g = gpd.sjoin(g, dist, predicate="within", how="inner").drop(columns="index_right")
n_peru = len(g)

# 3. Limpieza: confianza baja y volcanes (3 km)
g = g[~g.confidence.isin(["l", "low"])]
n_sin_baja = len(g)
g = g.to_crs(UTM)
volc = gpd.GeoSeries(gpd.points_from_xy([v[1] for v in VOLCANES.values()], [v[0] for v in VOLCANES.values()]), crs=4326)
g = g[~g.intersects(volc.to_crs(UTM).buffer(3000).union_all())].reset_index(drop=True)
n_limpios = len(g)

# 4. Incendios: pares de focos a ≤ 1 km y ≤ 48 h, y componentes conectadas
xy = np.c_[g.geometry.x, g.geometry.y]
pares = cKDTree(xy).query_pairs(RADIO_KM * 1000, output_type="ndarray")
t = g.hora_utc.astype("int64").to_numpy() / 3.6e12  # horas
pares = pares[np.abs(t[pares[:, 0]] - t[pares[:, 1]]) <= VENTANA_H]
n = len(g)
grafo = coo_matrix((np.ones(len(pares)), (pares[:, 0], pares[:, 1])), shape=(n, n))
_, g["incendio"] = connected_components(grafo, directed=False)

# 5. Tabla de incendios. Huella = unión de los píxeles VIIRS de 375 m (no es área quemada)
corte = g.hora_utc.max()
g["pixel"] = g.geometry.buffer(187.5, cap_style="square")
huella = g.set_geometry("pixel").dissolve("incendio").area / 1e4
inc = g.groupby("incendio").agg(
    focos=("frp", "size"),
    frp_total_mw=("frp", "sum"),
    inicio=("hora_lima", "min"),
    fin=("hora_lima", "max"),
    x=("geometry", lambda s: s.x.mean()),
    y=("geometry", lambda s: s.y.mean()),
    departamento=("NOMBDEP", lambda s: s.mode().iat[0]),
    provincia=("NOMBPROV", lambda s: s.mode().iat[0]),
    distrito=("NOMBDIST", lambda s: s.mode().iat[0]),
)
inc["huella_ha"] = huella.round(1)
inc["activo"] = (corte - g.groupby("incendio").hora_utc.max()) <= pd.Timedelta(hours=24)
centro = gpd.GeoSeries(gpd.points_from_xy(inc.x, inc.y), crs=UTM).to_crs(4326)
inc["lat"], inc["lon"] = centro.y.round(5).values, centro.x.round(5).values
inc = inc.drop(columns=["x", "y"]).sort_values("focos", ascending=False)
inc["frp_total_mw"] = inc.frp_total_mw.round(1)

g.drop(columns=["geometry", "pixel"]).to_csv(SAL / "focos.csv", index=False)
inc.to_csv(SAL / "incendios.csv")

resumen = {
    "corte_utc": corte.strftime("%Y-%m-%d %H:%M"),
    "desde_utc": g.hora_utc.min().strftime("%Y-%m-%d %H:%M"),
    "focos_sudamerica": n_crudos,
    "focos_peru": n_peru,
    "descartados_confianza_baja": n_peru - n_sin_baja,
    "descartados_volcanes": n_sin_baja - n_limpios,
    "focos_limpios": n_limpios,
    "incendios": len(inc),
    "incendios_3_focos_o_mas": int((inc.focos >= 3).sum()),
    "incendios_activos_24h": int(inc.activo.sum()),
}
(SAL / "resumen_paso1.json").write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(resumen, indent=2, ensure_ascii=False))
print(inc.head(15).to_string())
