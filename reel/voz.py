"""Paso 4: narra el guion revisado con mi voz clonada (Qwen3-TTS 0.6B, CPU).

Whisper transcribe la muestra de voz (Qwen la necesita como texto de referencia)
y vuelve a escuchar cada escena: si entiende mal más del 25 % de las palabras,
la escena se genera de nuevo.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import re

import jiwer
from num2words import num2words
import numpy as np
import soundfile as sf
import torch
from faster_whisper import WhisperModel
from qwen_tts import Qwen3TTSModel

AQUI = Path(__file__).resolve().parent
SALIDAS = AQUI / "salidas"
SALIDAS.mkdir(exist_ok=True)
FFMPEG = r"C:\Users\Nicolas Silva\Documents\ffmpeg-7.1.1-essentials_build\bin\ffmpeg.exe"
TTS = "Qwen/Qwen3-TTS-12Hz-0.6B-Base"
MAX_WER = 0.25
INTENTOS = 2
PAUSA_S = 0.35


def audio16k(ruta):
    """Decodifica con ffmpeg a 16 kHz mono para Whisper (evita PyAV)."""
    crudo = subprocess.run([FFMPEG, "-loglevel", "error", "-i", str(ruta), "-f", "f32le",
                            "-ac", "1", "-ar", "16000", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(crudo, dtype=np.float32)

guion = json.loads((AQUI / "guion.json").read_text(encoding="utf-8"))

# 1. Muestra de voz: a WAV mono 24 kHz y transcrita por Whisper
muestra = SALIDAS / "mi_voz.wav"
subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(AQUI / "mi_voz.ogg"),
                "-ac", "1", "-ar", "24000", str(muestra)], check=True)
whisper = WhisperModel("small", device="cpu", compute_type="int8")
segs, _ = whisper.transcribe(audio16k(muestra), language="es", vad_filter=True)
ref_text = " ".join(s.text.strip() for s in segs)
print("Texto de la muestra:", ref_text, flush=True)


def normalizar(t):
    """Minúsculas, sin puntuación y con las cifras en palabras, como en el guion."""
    t = t.lower().replace("%", " por ciento")
    t = re.sub(r"(?<=\d)[.\s](?=\d{3})", "", t)
    t = re.sub(r"\d+", lambda m: num2words(int(m.group()), lang="es"), t)
    return jiwer.RemovePunctuation()(t).strip()


def escuchar(audio, sr):
    tmp = SALIDAS / "_control.wav"
    sf.write(tmp, audio, sr)
    segs, _ = whisper.transcribe(audio16k(tmp), language="es")
    return " ".join(s.text.strip() for s in segs)


# 2. Clonar la voz una sola vez y narrar escena por escena
torch.manual_seed(0)
modelo = Qwen3TTSModel.from_pretrained(TTS, device_map="cpu", dtype=torch.float32)
prompt = modelo.create_voice_clone_prompt(ref_audio=str(muestra), ref_text=ref_text)

# SOLO="4" regenera solo esas escenas y conserva las demás
solo = {int(x) for x in os.environ.get("SOLO", "").split(",") if x}
partes, control = [], []
previo = {c["escena"]: c for c in json.loads((SALIDAS / "control_voz.json").read_text())} if solo else {}
for i, escena in enumerate(guion["escenas"], 1):
    if solo and i not in solo:
        control.append(previo[i])
        continue
    for intento in range(1, INTENTOS + 1):
        wavs, sr = modelo.generate_voice_clone(text=escena["frase"], language="Spanish",
                                               voice_clone_prompt=prompt)
        oido = escuchar(wavs[0], sr)
        wer = jiwer.wer(normalizar(escena["frase"]), normalizar(oido))
        print(f"Escena {i}, intento {intento}: WER {wer:.0%} | {oido}", flush=True)
        if wer <= MAX_WER:
            break
    sf.write(SALIDAS / f"escena_{i:02d}.wav", wavs[0], sr)
    control.append({"escena": i, "intentos": intento, "wer": round(wer, 3),
                    "segundos": round(len(wavs[0]) / sr, 2)})
    partes += [wavs[0], np.zeros(int(PAUSA_S * sr), dtype=wavs[0].dtype)]

(SALIDAS / "control_voz.json").write_text(json.dumps(control, indent=2), encoding="utf-8")
sf.write(SALIDAS / "voz_cruda.wav", np.concatenate(partes), sr)

# 3. Volumen de redes sociales: -14 LUFS
subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(SALIDAS / "voz_cruda.wav"),
                "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000", str(SALIDAS / "reel.wav")],
               check=True)
total = sum(c["segundos"] for c in control) + PAUSA_S * len(control)
print(f"Listo: salidas/reel.wav, unos {total:.0f} s", file=sys.stderr)
