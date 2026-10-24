# ¿Qué se quemó? Incendios y chacras en el Perú, octubre 2026

Sesión 14 · Python Intermedio · Nicolás Silva Andújar (@nicosil02) · reto **C (¿qué se quemó?)**

**Página web:** https://claude.ai/artifact/QQcz7dxPZ7NF5BUwVzEYPF (copia en [`docs/index.html`](docs/index.html))

![Área quemada en Characato sobre ESA WorldCover](outputs/cobertura_caso.png)

## Pregunta

Cuando arde un incendio en el Perú, ¿qué es lo que se quema: pastizal, matorral o chacras? ¿Y cuántas chacras quedan cerca del fuego? Lo respondo para el incendio de **Characato (Arequipa)** del 18 y 19 de octubre de 2026.

## Tres hallazgos

1. **Lo que ardió fue sobre todo matorral, pero el fuego llegó al borde de las chacras.** Se quemaron **153 ha**: 71 % matorral, 23 % pastizal y **7 ha de cultivo (5 %)**, en el borde norte de la cicatriz, junto a la zona construida. A 1 km o menos quedan **65 ha de cultivo** y 5 ha construidas sin quemar.
2. **El umbral de siempre casi no ve este incendio, y uno más bajo cuenta ruido.** Con dNBR ≥ 0,27 salen menos de **2 ha**: el 92 % de lo quemado es de severidad baja (Key y Benson, 2006), porque en el matorral seco hay poca vegetación que perder. Pero bajar a 0,10 sin más tampoco sirve: a más de 3 km del fuego, el **6,1 % de los píxeles ya pasa de 0,10** por el secado. Por eso el umbral sale del propio fondo (percentil 95 = 0,109) y solo cuentan manchas continuas que tocan un foco. Contando píxel por píxel a 1,5 km de los focos habrían salido 196 ha, un 29 % más.
3. **Las nubes deciden qué incendios se pueden medir.** De seis incendios de la sierra probados, cuatro (Tapo, San Juan de Jarpa, Cayna y Vilcas Huamán) no tuvieron ninguna imagen Sentinel-2 limpia después del fuego, y en Caja la mejor tenía el 27 % de la zona tapada ([`candidatos_caso.csv`](data/processed/candidatos_caso.csv)). Characato se pudo medir porque Arequipa sigue despejada en octubre.

En todo el Perú hubo **7 198 focos** limpios y **2 173 incendios** en la semana (171 activos al corte); Ucayali, Junín y Huánuco concentran la mitad de los focos.

![dNBR de Characato](outputs/dnbr_caso.png)

## Datos y fechas

| Dato | Fuente | Fechas |
|---|---|---|
| Focos de calor VIIRS (S-NPP, NOAA-20, NOAA-21) | NASA FIRMS, CSV «South America 7d» | 15 al 22 oct 2026, corte 22 oct 01:22 (Lima) |
| Imágenes | Sentinel-2 L2A, Microsoft Planetary Computer | antes 17 oct, después 20 oct 2026 (99,9 % válido en la zona) |
| Cobertura del suelo | ESA WorldCover 2021, 10 m, Planetary Computer | 2021 |
| Límites distritales | [juaneladio/peru-geojson](https://github.com/juaneladio/peru-geojson) | — |

## Método

1. **Focos → incendios** (`src/01_incendios.py`): focos del Perú sin confianza baja ni volcanes (Sabancaya, Ubinas, Misti); los que están a ≤ 1 km y ≤ 48 h forman un incendio. Huella = unión de píxeles de 375 m (no es área quemada).
2. **Área quemada** (`src/02_dnbr.py`): escenas elegidas por el % de píxeles válidos en la zona según la capa SCL, no por la nubosidad de la escena. NBR = (B8A − B12)/(B8A + B12) en reflectancia (restando el +1000 de la baseline ≥ 04.00), dNBR = NBR antes − NBR después, máscara de nubes, sombra, agua y nieve. **Umbral** = el mayor entre 0,10 y el percentil 95 del dNBR a más de 3 km de los focos (el ruido de fondo); mediana de 3×3 y solo manchas continuas de ≥ 1 ha que tocan un foco (a ≤ 375 m), como en los trabajos de Luis Guevara y Josué Soria.
3. **¿Qué se quemó?** (`src/03_que_se_quemo.py`): área quemada × WorldCover (clase más frecuente a 20 m) y cobertura a ≤ 1 km de la cicatriz.
4. **Página web** (`src/04_web.py`): rellena `web/plantilla.html` con las cifras y genera `docs/index.html`.

Reproducir:

```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
# bajar a data/raw/ los tres CSV de 7 días de FIRMS y distritos.geojson
python src/01_incendios.py
python src/02_dnbr.py 971          # id del incendio de Characato
python src/03_que_se_quemo.py
python src/04_web.py
```

## Limitaciones

- **Un foco de calor no es un incendio forestal**: incluye quemas agrícolas y de pastos.
- **En cultivo, el dNBR también sube con la cosecha o el arado**, así que las 7 ha de cultivo quemado son un máximo (aunque entre las dos imágenes hay solo 3 días).
- **WorldCover es de 2021** y en la sierra confunde chacras con pastizal.
- **Umbral bajo**: dentro de las manchas puede quedar algo de secado; lo acotan el umbral sacado del fondo y que la imagen de antes es de un día antes del fuego.
- **Un solo incendio**: las nubes no dejaron medir los otros candidatos de la sierra.

## Reel (sesión 15): del informe a un video con mi voz

**▶ El video: [`reel/reel.mp4`](reel/reel.mp4)**. Todo lo del reel está en [`reel/`](reel/): el texto fuente [`reel/informe.md`](reel/informe.md), el guion, los posts [`reel/posts.md`](reel/posts.md) y el código de cada paso. Cómo se hizo, en [`reel/README.md`](reel/README.md).

### Qué corregí del guion y por qué

| Decía | Quedó | Por qué |
|---|---|---|
| «casi todo matorral» | «sobre todo matorral» | El matorral es el 71 %, no casi todo |
| «nadie te dice qué se quemó» | «un mapa de focos no dice qué se quemó» | Exageraba; lo que sí sostiene el README es que la huella de un foco no es área quemada |
| «la peor temporada de incendios desde 2020» | «una de las peores temporadas de los últimos cinco años» | El dato viene de un análisis independiente, no oficial; la frase nueva es la que los datos sostienen |
| «fue el único con cielo limpio» | «fue el único sin nubes» | No era un error del texto: Whisper escuchó «consuelo limpio» dos veces, así que la voz clonada no lo pronunciaba bien |
| «a 1 km del fuego» | «a un kilómetro o menos» | El README mide desde la cicatriz quemada, no desde el fuego |

Además reescribí el guion completo: el primero contaba lo que hice (focos, nubes, método) y el final cuenta lo que pasó en Characato, que con el umbral clásico casi no aparece (menos de 2 ha) y medido bien son 153 ha junto a las chacras. «Más de setenta veces más» es un cálculo mío (152,5 ha frente a 1,7 ha, unas 90 veces); está explicado en el informe fuente.
