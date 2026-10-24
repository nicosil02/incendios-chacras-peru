# Reel · ¿Qué se quemó en Characato?

Sesión 15 · Nicolás Silva Andújar

**▶ El video: [`reel.mp4`](reel.mp4)** · 54 s, vertical 1080×1920, voz generada con IA

## Qué hay en esta carpeta

| Archivo | Qué es |
|---|---|
| [`reel.mp4`](reel.mp4) | El reel final |
| [`posts.md`](posts.md) | Los tres posts para X, LinkedIn y Facebook |
| [`informe.md`](informe.md) | El texto fuente del reel, con los datos y sus fuentes |
| [`guion.json`](guion.json) | El guion revisado, escena por escena |
| [`reel.srt`](reel.srt) | Subtítulos para subir aparte |
| [`portada.png`](portada.png) | Portada del reel |
| [`codigo/`](codigo/) | Los scripts de cada paso |
| `salidas/` | Datos intermedios del control de voz |

## Cómo se hizo

1. **Texto largo:** [`informe.md`](informe.md), los hallazgos del proyecto más el contexto de la temporada de incendios.
2. **Guion:** un LLM lo escribe como JSON con frase, cifra y etiqueta por escena.
3. **Revisión:** [`codigo/verificar_guion.py`](codigo/verificar_guion.py) marca con ¡¡ toda cifra que no esté en el informe. Las frases las revisé yo; lo que corregí está en el [README principal](../README.md#qué-corregí-del-guion-y-por-qué).
4. **Voz:** [`codigo/voz.py`](codigo/voz.py) clona mi voz con Qwen3-TTS 0.6B a partir de una nota de 19 s. Whisper vuelve a escuchar cada escena y la regenera si entiende mal más del 25 % de las palabras. [`codigo/unir.py`](codigo/unir.py) recorta los silencios y deja el audio a −14 LUFS.
5. **Video:** [`codigo/video.py`](codigo/video.py) dibuja cada cuadro con Pillow, con los mapas dNBR y WorldCover del proyecto, y ffmpeg lo convierte en video.

Para repetirlo, desde la raíz del repo:

```bash
python reel/codigo/verificar_guion.py
python reel/codigo/voz.py      # necesita reel/mi_voz.ogg, que no está en el repo
python reel/codigo/unir.py
python reel/codigo/video.py
```
