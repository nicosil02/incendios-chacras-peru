"""Paso 4 · Página web autocontenida con los resultados.

Rellena web/plantilla.html con las cifras de los pasos 1 a 3 y mete los mapas como imágenes
embebidas, para que la página funcione sola. El visor interactivo usa web/datos_visor.json (paso 5).

Salida: docs/index.html
"""
import base64
import json
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
PRO, OUT = RAIZ / "data" / "processed", RAIZ / "outputs"
COLOR = {"Matorral": "var(--scrub)", "Pastizal": "var(--grass)", "Cultivo": "var(--crop)"}


def leer(n):
    return json.loads((PRO / n).read_text(encoding="utf-8"))


def num(x, dec=0):
    """Número con espacio de miles y coma decimal."""
    return f"{x:,.{dec}f}".replace(",", " ").replace(".", ",")


def img(nombre):
    return "data:image/png;base64," + base64.b64encode((OUT / nombre).read_bytes()).decode()


r1, r2, r3 = leer("resumen_paso1.json"), leer("resumen_paso2.json"), leer("resumen_paso3.json")
t = pd.read_csv(PRO / "que_se_quemo.csv")
corte = pd.Timestamp(r1["corte_utc"], tz="UTC").tz_convert("America/Lima")
sev = r2["severidad_ha"]
quemado = sum(sev.values())

maximo = t.quemado_ha.max()
barras = "".join(
    f'<div class="barra" role="listitem"><span>{f.cobertura}</span>'
    f'<div class="pista"><div class="relleno" style="width:{100 * f.quemado_ha / maximo:.1f}%;'
    f'background:{COLOR.get(f.cobertura, "var(--muted)")}"></div></div>'
    f'<span class="valor">{num(f.quemado_ha, 1)} ha</span></div>'
    for f in t[t.quemado_ha >= 1].itertuples()
)
filas = "".join(
    f"<tr><td>{f.cobertura}</td><td class='n'>{num(f.quemado_ha, 1)}</td><td class='n'>{num(f.pct_quemado, 1)}</td>"
    f"<td class='n'>{num(f.a_1km_sin_quemar_ha, 1)}</td></tr>"
    for f in t.itertuples()
)
pct = t.set_index("cobertura").pct_quemado
valores = {
    "corte": corte.strftime("%d/%m/%Y %H:%M"),
    "quemado": num(r2["quemado_ha"] + 1e-9),  # 152,5 ha → 153, como en el README
    "pct_principal": num(r3["pct_cobertura_principal"]),
    "principal": r3["cobertura_principal"].lower(),
    "pct_pastizal": num(pct.get("Pastizal", 0)),
    "cult_q": num(r3["cultivo_quemado_ha"]),
    "cult_v": num(r3["cultivo_a_1km_sin_quemar_ha"]),
    "constr_v": num(r3["construido_a_1km_ha"]),
    "q027": num(r2["quemado_ha_manchas_027"], 1),
    "q_pixel": num(r2["quemado_ha_pixel_010_a_1500m"]),
    "umbral": num(r2["umbral"], 2),
    "pct_fondo": num(r2["pct_fondo_sobre_010"], 1),
    "pct_baja": num(100 * sev["Baja"] / quemado),
    "focos": num(r1["focos_limpios"]),
    "incendios": num(r1["incendios"]),
    "antes": pd.Timestamp(r2["escena_antes"]).strftime("%d/%m"),
    "despues": pd.Timestamp(r2["escena_despues"]).strftime("%d/%m"),
    "valido": num(r2["pct_valido_zona"], 1),
    "focos_caso": r2["focos"],
    "barras": barras,
    "umbral_punto": f"{r2['umbral']:.3f}",
    "datos": (RAIZ / "web" / "datos_visor.json").read_text(encoding="utf-8"),
    "filas": filas,
    "img_dnbr": img("dnbr_caso.png"),
    "img_cob": img("cobertura_caso.png"),
}
html = (RAIZ / "web" / "plantilla.html").read_text(encoding="utf-8")
for k, v in valores.items():
    html = html.replace("{{" + k + "}}", str(v))
assert "{{" not in html, "quedó un campo sin rellenar"
(RAIZ / "docs").mkdir(exist_ok=True)
(RAIZ / "web" / "artefacto.html").write_text(html, encoding="utf-8")  # para la web en Claude
# GitHub Pages necesita el documento completo
cabeza = ('<!doctype html>\n<html lang="es">\n<head>\n<meta charset="utf-8">\n'
          '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n')
pagina = cabeza + html.replace("<main", '</head>\n<body style="margin:0">\n<main', 1) + "\n</body>\n</html>\n"
(RAIZ / "docs" / "index.html").write_text(pagina, encoding="utf-8")
print(f"docs/index.html: {len(html) / 1e6:.2f} MB")
