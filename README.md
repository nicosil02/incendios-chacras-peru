# ¿Qué se quemó? Incendios y chacras en el Perú, octubre 2026

Sesión 14 · Ciencia de Datos con Python · Nicolás Silva Andújar (@nicosil02) · reto **C (¿qué se quemó?)**

## Pregunta

Cuando arde un incendio en el Perú, ¿qué es lo que se quema: pastizal, bosque o chacras? ¿Y cuántas chacras quedan cerca del fuego?

## Plan

1. **Focos → incendios.** Focos VIIRS de NASA FIRMS (7 días), sin confianza baja ni volcanes, agrupados en incendios (≤ 1 km y ≤ 48 h).
2. **Un incendio visto de cerca.** Par Sentinel-2 antes y después, NBR y dNBR, hectáreas quemadas y severidad.
3. **¿Qué se quemó?** Área quemada × ESA WorldCover 2021, con foco en la clase *Cultivo*, y chacras a ≤ 1 km de la cicatriz.

## Limitaciones (de partida)

- Un foco de calor no es un incendio: incluye quemas agrícolas y de pastos.
- Las nubes esconden el suelo; el área quemada depende de tener imágenes limpias.
- WorldCover es de 2021 y confunde cultivos con pastizal en la sierra.
