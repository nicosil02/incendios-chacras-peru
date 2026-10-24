# ¿Qué se quemó en Characato? Informe sobre el incendio del 18 y 19 de octubre de 2026

Nicolás Silva Andújar · Sesión 14 y 15 · Data Science con Python

Este informe es el texto fuente del reel. Reúne los hallazgos del proyecto [incendios-chacras-peru](https://github.com/nicosil02/incendios-chacras-peru) (focos VIIRS, Sentinel-2 y ESA WorldCover, cifras en `data/processed/`) y el contexto de la temporada de incendios, con su fuente.

## 1. Contexto: una de las peores temporadas de los últimos cinco años

Octubre de 2026 fue un mes muy severo de incendios en el Perú. Del 1 al 20 de octubre se registraron 12 007 focos de calor, un 74 % por encima de la media 2012–2025. Es el segundo valor de la serie desde 2012, solo por detrás de 2020, lo que la convierte en una de las peores temporadas de incendios de los últimos cinco años. El pico fue el 16 de octubre, con 2 496 focos en un solo día. Fuente: análisis satelital independiente [av-gomez/incendios-peru-2026](https://github.com/av-gomez/incendios-peru-2026), no oficial.

El jefe del Indeci informó 12 personas fallecidas desde el inicio de la emergencia y 832 personas afectadas por quemaduras. Indeci señaló como puntos críticos Río Tambo (Junín) y Curahuasi (Apurímac). Al 23 de octubre, el Ministerio de Defensa reportó cero incendios activos tras varias semanas de emergencia. Fuente: [TV Perú](https://www.tvperu.gob.pe/noticias/nacionales/peru-registra-cero-incendios-forestales-activos-tras-semanas-de-emergencia-informa-el-mindef).

## 2. La semana analizada: del 15 al 22 de octubre

En la semana del 15 al 22 de octubre de 2026 (corte: 22 de octubre, 01:22, hora de Lima), los satélites VIIRS (S-NPP, NOAA-20 y NOAA-21, vía NASA FIRMS) registraron 8 397 focos de calor en el Perú. Tras descartar los de confianza baja (1 199) quedaron 7 198 focos limpios. Agrupando los focos que están a 1 km o menos y a 48 horas o menos entre sí, salen 2 173 incendios, 171 de ellos activos al corte. Ucayali, Junín y Huánuco concentran la mitad de los focos.

Un foco de calor no es un incendio forestal: incluye quemas agrícolas y de pastos. Y un mapa de focos no dice qué se quemó: la huella de un foco es un píxel de 375 m, no área quemada.

## 3. Por qué Characato

Para saber qué se quema hace falta una imagen limpia antes y otra después del fuego. De seis incendios de la sierra probados, cuatro (Tapo, San Juan de Jarpa, Cayna y Vilcas Huamán) no tuvieron ninguna imagen Sentinel-2 limpia después del fuego, y en Caja la mejor tenía el 27 % de la zona tapada. Characato, en la provincia de Arequipa, fue el único sin nubes: imágenes del 17 y del 20 de octubre, con el 99,9 % de la zona visible. El incendio sumó 31 focos entre el 18 y el 19 de octubre.

## 4. El método de siempre casi no lo ve

El área quemada se mide con el dNBR, la diferencia del índice de quema normalizado antes y después del fuego. Con el umbral clásico (dNBR ≥ 0,27, Key y Benson, 2006), el incendio de Characato mide menos de 2 ha (1,7 ha).

Pero en el matorral seco hay poco verde que perder, y el satélite casi no nota el cambio: el 92 % de lo quemado es de severidad baja (140,8 ha de severidad baja, 5,8 ha moderada-baja). Por eso el umbral se sacó del ruido de fondo de la propia imagen (percentil 95 del dNBR a más de 3 km de los focos = 0,109) y solo cuentan manchas continuas que tocan un foco. Medido así, ardieron 153 ha (152,5 ha), es decir, más de 70 veces más que con el umbral clásico (152,5 frente a 1,7 ha, unas 90 veces).

## 5. Qué se quemó

Cruzando el área quemada con ESA WorldCover:

| Cobertura | Quemado (ha) | % de lo quemado | A 1 km o menos, sin quemar (ha) |
|---|---|---|---|
| Matorral | 108,1 | 71 % | 674,2 |
| Pastizal | 35,3 | 23 % | 365,2 |
| Cultivo | 7,4 | 5 % | 65,3 |
| Suelo desnudo | 0,9 | 0,6 % | 19,8 |
| Construido | 0,4 | 0,3 % | 5,4 |

Lo que ardió fue sobre todo matorral, pero el fuego no se quedó en el monte: llegó al borde de las chacras, en el borde norte de la cicatriz, junto a la zona construida, y quemó hasta 7 ha de cultivo. A un kilómetro o menos quedan 65 ha de cultivo y 5 ha construidas que esta vez se salvaron.

## 6. Conclusión

Un incendio chico en el papel puede estar al lado de una chacra. Con el umbral de siempre, Characato casi no existe en las cifras; medido con un umbral adaptado al matorral seco, son 153 ha a pocos metros de cultivos y casas. Si no se mide bien lo que se quema, no se sabe qué proteger.

## Limitaciones

- En cultivo, el dNBR también sube con la cosecha o el arado, así que las 7 ha de cultivo quemado son un máximo.
- WorldCover es de 2021 y en la sierra confunde chacras con pastizal.
- El dato de la temporada (segundo valor desde 2012) proviene de un análisis independiente, no de una fuente oficial.
- Se midió un solo incendio: las nubes no dejaron medir los otros candidatos de la sierra.
