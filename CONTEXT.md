# Glosario del dominio — GeoSentinel

Glosario de términos canónicos. Sin detalles de implementación.

## Términos

| Término | Definición |
|---------|-----------|
| **Incidente** | Entidad del sistema propio (dashboard) que agrega observaciones de varias fuentes sobre un mismo hecho. Tiene estado y severidad. |
| **Zona (AOI)** | Polígono de interés definido por el sistema propio (países OTAN, regiones de conflicto). Delimita dónde se buscan datos. Distinto de **región**. |
| **Radar** | Página `/radar` del frontend: mapa dedicado que muestra solo los datos de CR360 (eventos, carreteras comprometidas y regiones) de los países configurados. |
| **Evento (CR360)** | Punto reportado por CR360 con título, descripción, fecha y país. Puede ser un ataque, protesta, incendio, etc. |
| **Carretera comprometida** | Tramo (LineString) de CR360 marcado como afectado, con severidad (CRÍTICA / ALTA / MEDIA / BAJA), amenaza y conflicto asociado. |
| **Región** | Polígono de CR360 que representa una zona de control, conflicto o actividad (p. ej. un óblast, un área criminal). Identificada por `popupTitle` y asociada a un conflicto, grupo o fuerza. Distinta de **zona (AOI)**. |
| **Conflicto** | Marco de referencia de CR360 que agrupa regiones y carreteras (p. ej. "Guerra contra el Narco en México"). |
| **Fuerza / Grupo criminal** | Actor de CR360 (ejército regular, grupo criminal) asociado a eventos, regiones y carreteras. |
| **País de interés** | Subconjunto configurable de países (ISO-3) que delimita qué eventos, carreteras y regiones muestra el **radar**. |
| **Frontera nacional** | Borde administrativo de un país (p. ej. Ucrania) remarcado en el **radar** como línea destacada. Dato estático derivado de Natural Earth (dominio público), distinto de las **regiones** (polígonos dinámicos de CR360). |
| **Distintivo de país** | Indicador visual de la nacionalidad de un **evento** en el radar: anillo de color alrededor del icono (o punto de color si el evento no tiene icono). Permite identificar el país de cada evento de un vistazo, complementado por la bandera en tooltip y modal. |
