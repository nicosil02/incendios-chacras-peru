"""Paso 3 · ¿Qué se quemó?

Cruza el área quemada del paso 2 con ESA WorldCover 2021 (10 m, leído a la grilla de 20 m con la
clase más frecuente) y cuenta, por clase de cobertura, las hectáreas quemadas y las que quedan a
1 km o menos de la cicatriz sin quemar. Pone el foco en la clase 40, *Cultivo*.

Entradas: data/cache/caso_dnbr.tif, data/cache/caso_quemado.tif, data/processed/resumen_paso2.json
Salidas:  data/processed/que_se_quemo.csv, data/processed/resumen_paso3.json, outputs/cobertura_caso.png
"""
import json
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import odc.stac
import pandas as pd
import planetary_computer as pc
import pystac_client
import rioxarray
from scipy.ndimage import distance_transform_edt

warnings.filterwarnings("ignore")
RAIZ = Path(__file__).resolve().parent.parent
PRO, CACHE, OUT = RAIZ / "data" / "processed", RAIZ / "data" / "cache", RAIZ / "outputs"
RES, VECINDAD_M = 20, 1000
CLASES = {10: "Árboles", 20: "Matorral", 30: "Pastizal", 40: "Cultivo", 50: "Construido",
          60: "Suelo desnudo", 70: "Nieve", 80: "Agua", 90: "Humedal", 95: "Manglar", 100: "Musgo y liquen"}
COLORES = {10: "#006400", 20: "#ffbb22", 30: "#ffff4c", 40: "#f096ff", 50: "#fa0000", 60: "#b4b4b4",
           70: "#f0f0f0", 80: "#0064c8", 90: "#0096a0", 95: "#00cf75", 100: "#fae6a0"}

r2 = json.loads((PRO / "resumen_paso2.json").read_text(encoding="utf-8"))
dnbr = rioxarray.open_rasterio(CACHE / "caso_dnbr.tif").squeeze()
quemado = rioxarray.open_rasterio(CACHE / "caso_quemado.tif").squeeze().values == 1

cat = pystac_client.Client.open("https://planetarycomputer.microsoft.com/api/stac/v1", modifier=pc.sign_inplace)
items = list(cat.search(collections=["esa-worldcover"], bbox=r2["bbox_wgs84"]).items())
wc = odc.stac.load(items, bands=["map"], like=dnbr.to_dataset(name="d").odc.geobox, resampling="mode")
wc = wc["map"].isel(time=-1).values  # versión 2021 (la más reciente)

d = dnbr.values
vecindad = (distance_transform_edt(~quemado) * RES <= VECINDAD_M) & ~quemado & np.isfinite(d)
ha = RES * RES / 1e4

filas = []
for c, nombre in CLASES.items():
    q, v = (quemado & (wc == c)).sum() * ha, (vecindad & (wc == c)).sum() * ha
    if q or v:
        filas.append({"clase": c, "cobertura": nombre, "quemado_ha": round(q, 1), "a_1km_sin_quemar_ha": round(v, 1)})
t = pd.DataFrame(filas)
t["pct_quemado"] = (100 * t.quemado_ha / t.quemado_ha.sum()).round(1)
t = t.sort_values("quemado_ha", ascending=False)
t.to_csv(PRO / "que_se_quemo.csv", index=False)

cult = t.set_index("clase").reindex([40]).fillna(0).iloc[0]
resumen = {
    "incendio": f"{r2['distrito'].title()}, {r2['provincia'].title()} ({r2['departamento'].title()})",
    "umbral_dnbr": r2["umbral"], "quemado_ha": round(float(t.quemado_ha.sum()), 1),
    "cobertura_principal": t.cobertura.iat[0], "pct_cobertura_principal": float(t.pct_quemado.iat[0]),
    "cultivo_quemado_ha": float(cult.quemado_ha), "cultivo_a_1km_sin_quemar_ha": float(cult.a_1km_sin_quemar_ha),
    "construido_a_1km_ha": float(t.set_index("clase").a_1km_sin_quemar_ha.get(50, 0)),
}
(PRO / "resumen_paso3.json").write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
print(t.to_string(index=False))
print(json.dumps(resumen, indent=2, ensure_ascii=False))

# Mapa: WorldCover con el contorno de lo quemado
xs, ys = dnbr.x.values, dnbr.y.values
rgb = np.ones((*wc.shape, 3))
for c, col in COLORES.items():
    rgb[wc == c] = [int(col[i:i + 2], 16) / 255 for i in (1, 3, 5)]
fig, ax = plt.subplots(figsize=(8, 7))
ext = [xs.min(), xs.max(), ys.min(), ys.max()]
ax.imshow(rgb, extent=ext)
ax.contour(xs, ys, quemado.astype(int), levels=[0.5], colors="black", linewidths=0.8)
ax.set_title(f"¿Qué se quemó en {r2['distrito'].title()}? {resumen['pct_cobertura_principal']:.0f} % "
             f"{resumen['cobertura_principal'].lower()}; {resumen['cultivo_a_1km_sin_quemar_ha']:,.0f} ha de "
             f"cultivo a ≤ 1 km\nESA WorldCover 2021, contorno negro = área quemada (dNBR ≥ {r2['umbral']:.2f})", fontsize=10)
ax.set_axis_off()
from matplotlib.patches import Patch  # noqa: E402
presentes = [c for c in CLASES if (wc == c).any()]
ax.legend(handles=[Patch(color=COLORES[c], label=CLASES[c]) for c in presentes], loc="lower left", fontsize=8)
fig.savefig(OUT / "cobertura_caso.png", dpi=150, bbox_inches="tight")
