"""Paso 3 (parte automática): marca con ¡¡ toda cifra del guion que no aparece tal cual en el informe fuente.

Las afirmaciones no se verifican con código: eso lo hace una persona leyendo el guion contra la fuente.
"""
import json
import re
from pathlib import Path

REEL = Path(__file__).resolve().parent.parent
fuente = (REEL / "informe.md").read_text(encoding="utf-8")
guion = json.loads((REEL / "guion.json").read_text(encoding="utf-8"))

# En el informe las cifras usan espacio fino o normal como separador de miles
fuente_norm = re.sub(r"[  ]", " ", fuente)

palabras = 0
for i, escena in enumerate(guion["escenas"], 1):
    textos = [escena["cifra"]] * bool(escena["cifra"]) + re.findall(r"\d[\d ,.]*\d|\d", escena["etiqueta"])
    marcas = [t for t in textos if t.strip() not in fuente_norm]
    estado = "ok" if not marcas else "¡¡ " + ", ".join(marcas)
    n = len(escena["frase"].split())
    palabras += n
    print(f"{i}. [{escena['cifra']:>6}] {estado:<12} ({n} palabras) {escena['frase']}")

print(f"\nTotal: {palabras} palabras, unos {palabras / 2.6:.0f} segundos a ritmo de reel")
