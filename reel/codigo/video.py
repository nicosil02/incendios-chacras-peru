"""Paso 5: arma reel.mp4 (1080x1920, 30 fps, H.264 + AAC) con subtítulos palabra por palabra.

Whisper marca cuándo se dice cada palabra; la que suena va en naranja. Pillow dibuja
cada cuadro y ffmpeg lo convierte en video. Las escenas de Characato muestran los
mapas del proyecto (dNBR y WorldCover) con un zoom lento; las cifras suben de 0 a su
valor. También exporta reel.srt y portada.png.
"""
import json
import os
import re
import subprocess
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel
from PIL import Image, ImageDraw, ImageFont

AQUI = Path(__file__).resolve().parent.parent
SALIDAS = Path(os.environ.get("SALIDAS", AQUI / "salidas"))
FFMPEG = r"C:\Users\Nicolas Silva\Documents\ffmpeg-7.1.1-essentials_build\bin\ffmpeg.exe"
W, H, FPS = 1080, 1920, 30
PAUSA_S = 0.35
FONDO, PANEL, CLARO, SUAVE, NARANJA = "#1B1A17", "#2A2824", "#F4EFE6", "#BDB5A8", "#F28C38"
F = "C:/Windows/Fonts/"
SALIDAS_MAPAS = AQUI.parent / "outputs"


def audio16k(ruta):
    """Decodifica con ffmpeg a 16 kHz mono para Whisper (evita PyAV)."""
    crudo = subprocess.run([FFMPEG, "-loglevel", "error", "-i", str(ruta), "-f", "f32le",
                            "-ac", "1", "-ar", "16000", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(crudo, dtype=np.float32)


def fuente(nombre, tam):
    return ImageFont.truetype(F + nombre, tam)


TITULO, AVISO, PIE = fuente("segoeuib.ttf", 46), fuente("segoeui.ttf", 34), fuente("segoeui.ttf", 30)
CIFRA, CIFRA_MAPA = fuente("segoeuib.ttf", 230), fuente("segoeuib.ttf", 150)
ETIQUETA, SUB, CIERRE = fuente("segoeuib.ttf", 54), fuente("segoeuib.ttf", 68), fuente("segoeuib.ttf", 64)

# Recortes de los mapas del README, sin título ni leyenda
DNBR = Image.open(SALIDAS_MAPAS / "dnbr_caso.png").convert("RGB").crop((300, 330, 720, 690))
COBERTURA = Image.open(SALIDAS_MAPAS / "cobertura_caso.png").convert("RGB").crop((230, 290, 650, 650))
MAPAS = {
    "153 ha": (DNBR, [("#FFE08A", "Severidad baja"), ("#FF9A33", "Moderada"), ("#2E86C1", "Foco VIIRS")]),
    "7 ha": (COBERTURA, [("#F29BF0", "Cultivo"), ("#FF2020", "Construido"), ("#111111", "Área quemada")]),
    "65 ha": (COBERTURA, [("#F29BF0", "Cultivo"), ("#FFB627", "Matorral"), ("#111111", "Área quemada")]),
}
MAPA_CAJA = (90, 400, 990, 1171)  # 900 x 771, misma proporción que los recortes

guion = json.loads((AQUI / "guion.json").read_text(encoding="utf-8"))
control = json.loads((SALIDAS / "control_voz.json").read_text(encoding="utf-8"))

# Inicio y fin de cada escena, según lo que duró su audio
tramos, t = [], 0.0
for c in control:
    tramos.append((t, t + c["segundos"] + PAUSA_S))
    t += c["segundos"] + PAUSA_S
duracion = t + 1.0

# Palabras con tiempos; el guion como pista para que Whisper escriba bien las cifras
whisper = WhisperModel("small", device="cpu", compute_type="int8")
pista = " ".join(e["frase"] for e in guion["escenas"])
segs, _ = whisper.transcribe(audio16k(SALIDAS / "reel.wav"), language="es",
                             word_timestamps=True, initial_prompt=pista)
palabras = [(w.start, w.end, w.word.strip()) for s in segs for w in s.words]

# Bloques de subtítulo de hasta 4 palabras, sin cruzar de una escena a otra
bloques, actual = [], []
for p in palabras:
    escena = next(i for i, (a, b) in enumerate(tramos + [(t, 1e9)]) if p[0] < b)
    if actual and (len(actual) == 4 or actual[0][3] != escena):
        bloques.append(actual)
        actual = []
    actual.append((*p, escena))
if actual:
    bloques.append(actual)


def ajustar(draw, texto, letra, ancho):
    lineas, linea = [], ""
    for palabra in texto.split():
        prueba = f"{linea} {palabra}".strip()
        if draw.textlength(prueba, font=letra) > ancho and linea:
            lineas.append(linea)
            linea = palabra
        else:
            linea = prueba
    return lineas + [linea]


def suave(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def cifra_animada(cifra, avance):
    """'153 ha' sube de 0 a 153 en el primer tramo de la escena."""
    m = re.match(r"(\d+(?: \d{3})*)(.*)", cifra)
    if not m:
        return cifra
    total = int(m.group(1).replace(" ", ""))
    n = round(total * suave(avance))
    return f"{n:,}".replace(",", " ") + m.group(2)


def cabecera(d, i):
    d.text((90, 230), guion["titulo"], font=TITULO, fill=CLARO)
    d.text((90, 296), "Voz generada con IA", font=AVISO, fill=SUAVE)


def cuadro_escena(i, seg):
    a, b = tramos[i]
    local = seg - a
    escena = guion["escenas"][i]
    img = Image.new("RGB", (W, H), FONDO)
    d = ImageDraw.Draw(img)

    if escena["cifra"] in MAPAS or i == 0:
        mapa, leyenda = MAPAS.get(escena["cifra"], (DNBR, []))
        x0, y0, x1, y1 = MAPA_CAJA
        zoom = 1.0 + 0.08 * (local / max(b - a, 1))
        cw, ch = mapa.width / zoom, mapa.height / zoom
        cx, cy = mapa.width / 2, mapa.height / 2
        vista = mapa.crop((int(cx - cw / 2), int(cy - ch / 2), int(cx + cw / 2), int(cy + ch / 2)))
        vista = vista.resize((x1 - x0, y1 - y0), Image.BILINEAR)
        if i == 0:  # portada: el mapa de fondo, oscurecido
            vista = Image.blend(vista, Image.new("RGB", vista.size, FONDO), 0.72)
        img.paste(vista, (x0, y0))
        d.rectangle(MAPA_CAJA, outline=PANEL, width=4)
        if i > 0:
            x = x0
            for color, nombre in leyenda:
                d.rectangle((x, y1 + 22, x + 30, y1 + 52), fill=color, outline=SUAVE)
                d.text((x + 42, y1 + 18), nombre, font=PIE, fill=SUAVE)
                x += 60 + d.textlength(nombre, font=PIE)
            d.text((W // 2, y1 + 160), cifra_animada(escena["cifra"], local / 0.8),
                   font=CIFRA_MAPA, fill=NARANJA, anchor="mm")
            y = y1 + 265
            for linea in ajustar(d, escena["etiqueta"], ETIQUETA, W - 220):
                d.text((W // 2, y), linea, font=ETIQUETA, fill=CLARO, anchor="mm")
                y += 66
    if escena["cifra"] and escena["cifra"] not in MAPAS:
        escala = 0.85 + 0.15 * suave(local / 0.5)
        letra = fuente("segoeuib.ttf", int(230 * escala))
        d.text((W // 2, 760), cifra_animada(escena["cifra"], local / 0.8), font=letra,
               fill=NARANJA, anchor="mm")
        y = 920
        for linea in ajustar(d, escena["etiqueta"], ETIQUETA, W - 220):
            d.text((W // 2, y), linea, font=ETIQUETA, fill=CLARO, anchor="mm")
            y += 70
    elif not escena["cifra"]:
        texto = guion["titulo"] if i == 0 else "Si no medimos bien lo que se quema, no sabremos qué proteger."
        y = 700 if i == 0 else 640
        for linea in ajustar(d, texto, CIERRE, W - 220):
            d.text((W // 2, y), linea, font=CIERRE, fill=CLARO, anchor="mm")
            y += 84
        if i > 0:
            d.text((W // 2, y + 60), escena["etiqueta"], font=AVISO, fill=SUAVE, anchor="mm")
            d.text((W // 2, y + 110), "Nicolás Silva Andújar · github.com/nicosil02",
                   font=AVISO, fill=SUAVE, anchor="mm")

    cabecera(d, i)
    # Barra de progreso del reel
    d.rectangle((90, 190, W - 90, 196), fill=PANEL)
    d.rectangle((90, 190, 90 + int((W - 180) * min(seg / duracion, 1)), 196), fill=NARANJA)
    # Entrada suave de cada escena
    if local < 0.25:
        img = Image.blend(Image.new("RGB", (W, H), FONDO), img, max(local / 0.25, 0.0))
    return img


def cuadro(seg):
    i = next((k for k, (a, b) in enumerate(tramos) if seg < b), len(tramos) - 1)
    img = cuadro_escena(i, seg)
    bloque = next((b for b in bloques if b[0][0] - 0.15 <= seg <= b[-1][1] + 0.25), None)
    if bloque:
        d = ImageDraw.Draw(img)
        texto = " ".join(p[2] for p in bloque)
        lineas = ajustar(d, texto, SUB, W - 200)
        y, k = 1500, 0
        for linea in lineas:
            n = len(linea.split())
            x = (W - d.textlength(linea, font=SUB)) / 2
            for p in bloque[k:k + n]:
                activa = p[0] <= seg <= p[1] + 0.05
                d.text((x, y), p[2], font=SUB, fill=NARANJA if activa else CLARO,
                       stroke_width=4, stroke_fill=FONDO)
                x += d.textlength(p[2] + " ", font=SUB)
            k += n
            y += 88
    return img


# Portada: la escena del área quemada, ya con la cifra completa
i_portada = next(k for k, e in enumerate(guion["escenas"]) if e["cifra"] == "153 ha")
cuadro_escena(i_portada, tramos[i_portada][0] + 2).save(AQUI / "portada.png")
if os.environ.get("SOLO_PORTADA"):
    for k in range(len(tramos)):
        cuadro(tramos[k][0] + 1.5).save(SALIDAS / f"muestra_{k + 1}.png")
    raise SystemExit

ffmpeg = subprocess.Popen(
    [FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
     "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", str(SALIDAS / "reel.wav"),
     "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p",
     "-af", "apad", "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart",
     str(AQUI / "reel.mp4")], stdin=subprocess.PIPE)
for n in range(int(duracion * FPS)):
    ffmpeg.stdin.write(cuadro(n / FPS).tobytes())
ffmpeg.stdin.close()
ffmpeg.wait()


def srt_t(s):
    ms = int(round(s * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


srt = [f"{k}\n{srt_t(b[0][0])} --> {srt_t(b[-1][1])}\n{' '.join(p[2] for p in b)}\n"
       for k, b in enumerate(bloques, 1)]
(AQUI / "reel.srt").write_text("\n".join(srt), encoding="utf-8")
print(f"Listo: reel/reel.mp4 ({duracion:.0f} s), reel.srt y portada.png")
