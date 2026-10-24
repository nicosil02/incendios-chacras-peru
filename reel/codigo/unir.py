"""Entre el paso 4 y el 5: recorta cada escena donde termina la voz y arma reel.wav.

Qwen a veces deja silencio o un ruido al final de la escena. Whisper marca la
primera y la última palabra, y se corta ahí (con un margen pequeño).
"""
import json
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel

AQUI = Path(__file__).resolve().parent.parent
SALIDAS = AQUI / "salidas"
FFMPEG = r"C:\Users\Nicolas Silva\Documents\ffmpeg-7.1.1-essentials_build\bin\ffmpeg.exe"
PAUSA_S = 0.35


def audio16k(ruta):
    crudo = subprocess.run([FFMPEG, "-loglevel", "error", "-i", str(ruta), "-f", "f32le",
                            "-ac", "1", "-ar", "16000", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(crudo, dtype=np.float32)


whisper = WhisperModel("small", device="cpu", compute_type="int8")
control = json.loads((SALIDAS / "control_voz.json").read_text(encoding="utf-8"))
partes = []
for c in control:
    ruta = SALIDAS / f"escena_{c['escena']:02d}.wav"
    audio, sr = sf.read(ruta)
    segs, _ = whisper.transcribe(audio16k(ruta), language="es", word_timestamps=True)
    palabras = [w for s in segs for w in s.words]
    ini = max(0.0, palabras[0].start - 0.1)
    fin = min(len(audio) / sr, palabras[-1].end + 0.25)
    recorte = audio[int(ini * sr):int(fin * sr)]
    print(f"Escena {c['escena']}: {len(audio) / sr:.1f} s -> {len(recorte) / sr:.1f} s")
    c["segundos"] = round(len(recorte) / sr, 2)
    partes += [recorte, np.zeros(int(PAUSA_S * sr))]

(SALIDAS / "control_voz.json").write_text(json.dumps(control, indent=2), encoding="utf-8")
sf.write(SALIDAS / "voz_cruda.wav", np.concatenate(partes), sr)
subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(SALIDAS / "voz_cruda.wav"),
                "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000", str(SALIDAS / "reel.wav")],
               check=True)
print(f"Listo: reel.wav de {sum(c['segundos'] + PAUSA_S for c in control):.0f} s")
