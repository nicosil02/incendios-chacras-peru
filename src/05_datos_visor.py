"""Paso 5 · Datos para el visor interactivo de la página web.

Exporta, sobre la misma grilla de 20 m del paso 2: el dNBR (cuantizado a un byte), la cobertura de
WorldCover, los píxeles a ≤ 375 m de un foco y la imagen en falso color (SWIR) de antes y después. Suma el
contexto nacional: focos por día y los incendios más grandes de la semana.

Entradas: data/cache/caso_dnbr.tif, data/processed/*.csv y *.json
Salida:   web/datos_visor.json
"""
import base64
import io
import json
import warnings
from pathlib import Path

import numpy as np
import odc.stac
import pandas as pd
import planetary_computer as pc
import pystac_client
import rioxarray
from PIL import Image
from scipy.ndimage import distance_transform_edt

warnings.filterwarnings("ignore")
RAIZ = Path(__file__).resolve().parent.parent
PRO, CACHE = RAIZ / "data" / "processed", RAIZ / "data" / "cache"
RES, TOCA_M = 20, 375

r2 = json.loads((PRO / "resumen_paso2.json").read_text(encoding="utf-8"))
dnbr = rioxarray.open_rasterio(CACHE / "caso_dnbr.tif").squeeze()
geobox = dnbr.to_dataset(name="d").odc.geobox
v = dnbr.values
alto, ancho = v.shape


def b64(arr, tipo=np.uint8):
    return base64.b64encode(np.ascontiguousarray(arr, dtype=tipo).tobytes()).decode()


# dNBR en dos bytes: 0 = sin dato, si no dNBR = (q − 32768) / 10 000
q = np.where(np.isfinite(v), np.clip(np.round(v * 1e4) + 32768, 1, 65535), 0)

# Píxeles a ≤ 375 m de un foco del incendio
focos = pd.read_csv(PRO / "focos.csv")
f = focos[focos.incendio == r2["incendio"]]
import geopandas as gpd  # noqa: E402

pts = gpd.GeoSeries(gpd.points_from_xy(f.longitude, f.latitude), crs=4326).to_crs(dnbr.rio.crs)
xs, ys = dnbr.x.values, dnbr.y.values
marca = np.zeros(v.shape, bool)
fi = np.clip(np.searchsorted(-ys, -pts.y.values), 0, alto - 1)
fj = np.clip(np.searchsorted(xs, pts.x.values), 0, ancho - 1)
marca[fi, fj] = True
toca = distance_transform_edt(~marca) * RES <= TOCA_M
focos_px = [[int(i), int(j)] for i, j in zip(fi, fj)]

# WorldCover y color real de antes y después, en la misma grilla
cat = pystac_client.Client.open("https://planetarycomputer.microsoft.com/api/stac/v1", modifier=pc.sign_inplace)
wc_items = list(cat.search(collections=["esa-worldcover"], bbox=r2["bbox_wgs84"]).items())
wc = odc.stac.load(wc_items, bands=["map"], like=geobox, resampling="mode")["map"].isel(time=-1).values


# Falso color B12/B8A/B04: el 20/10 tiene una bruma delgada que SCL no marca y que en color real
# tapa todo; en el infrarrojo de onda corta casi no se nota y la cicatriz sale oscura.
BANDAS = ["B12", "B8A", "B04"]


def cargar(fecha):
    items = list(cat.search(collections=["sentinel-2-l2a"], bbox=r2["bbox_wgs84"], datetime=fecha).items())
    e = odc.stac.load(items, bands=BANDAS, like=geobox, groupby="solar_day").isel(time=0)
    return np.dstack([(e[b].values.astype("float32") - 1000) / 1e4 for b in BANDAS])


antes_rgb, despues_rgb = cargar(r2["escena_antes"]), cargar(r2["escena_despues"])
lo, hi = np.percentile(antes_rgb, [1, 99], axis=(0, 1))  # mismo estiramiento para las dos fechas


def falso_color(rgb):
    rgb = np.clip((rgb - lo) / (hi - lo), 0, 1) ** 0.9
    buf = io.BytesIO()
    Image.fromarray((rgb * 255).astype("uint8")).save(buf, "JPEG", quality=82)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


# Contexto nacional
focos["dia"] = pd.to_datetime(focos.hora_lima.str[:10])
por_dia = focos.groupby("dia").size()
inc = pd.read_csv(PRO / "incendios.csv")
top = inc.head(10)[["incendio", "distrito", "provincia", "departamento", "focos", "huella_ha", "activo"]]
if r2["incendio"] not in top.incendio.values:
    top = pd.concat([top, inc[inc.incendio == r2["incendio"]][top.columns]])

datos = {
    "ancho": ancho, "alto": alto, "res": RES, "umbral": r2["umbral"], "p95_fondo": r2["dnbr_fondo_p95"],
    "dnbr": b64(q, "<u2"), "wc": b64(wc), "toca": b64(toca), "focos_px": focos_px,
    "antes": falso_color(antes_rgb), "despues": falso_color(despues_rgb),
    "fecha_antes": r2["escena_antes"], "fecha_despues": r2["escena_despues"],
    "por_dia": [{"dia": d.strftime("%Y-%m-%d"), "focos": int(n)} for d, n in por_dia.items()],
    "top": top.assign(caso=top.incendio == r2["incendio"]).to_dict("records"),
    "caso": r2["incendio"],
}
(RAIZ / "web" / "datos_visor.json").write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
print(f"web/datos_visor.json: {len(json.dumps(datos)) / 1e6:.2f} MB · grilla {ancho}×{alto}")
