# L-CORR-001: Puntos de incidentes visibles a través del globo 3D (antípodas)

## Problema

En modo 3D (`projection: { name: 'globe' }`), los puntos de incidentes (`incidents-point`) se ven a través del globo desde la cara opuesta (antípodas). Al rotar o inclinar el globo, los puntos del lado opuesto se hacen visibles a través de la superficie semi-transparente, creando la ilusión de que los puntos "se mueven" cuando en realidad son puntos de la cara opuesta.

**Confirmado**: En modo 2D (`projection: { name: 'mercator' }`) el problema NO ocurre. Los puntos se anclan correctamente a sus coordenadas geográficas.

**Capas que SÍ funcionan en 3D**: bases, vuelos militares, buques AIS. Todas usan capas `circle` sin problemas.

**Capa que NO funciona**: `incidents-point` (y anteriormente `incidents-glow`).

## Intentos realizados (ninguno resolvió el problema)

| # | Intento | Resultado |
|---|---------|-----------|
| 1 | `circle-pitch-alignment: 'map'` en `layout` | Sin efecto |
| 2 | `circle-pitch-alignment: 'viewport'` (default) | Sin efecto |
| 3 | `circle-pitch-alignment` en `paint` (inválido) | Sin efecto |
| 4 | `fog` en `projection` con `horizon-blend: 0.8` | Sin efecto |
| 5 | `map.setFog()` vía API en `handleMapLoad` | Sin efecto |
| 6 | `renderWorldCopies={false}` | No aplica a globe |
| 7 | Eliminar capa `incidents-glow` (blur + radius 28) | Sin efecto |
| 8 | Filtrado por hemisferio visible (producto escalar 3D) con `displayViewport` del store | Sin efecto — el viewport del store no se actualiza al rotar |
| 9 | Filtrado por hemisferio visible con `globeCenter` state + `onMoveEnd` | **Sin efecto visible** |

## Diagnóstico actual

El filtrado por hemisferio visible (intento #9) DEBERÍA funcionar: se calcula el producto escalar entre el centro del globo y cada punto, y se excluyen los puntos con `dot <= -0.1` (~95° del centro). El `globeCenter` se actualiza en cada `onMoveEnd` y en cada `flyTo`.

**Hipótesis**: el problema podría no ser de código sino de:

1. **Cache del navegador**: el bundle JS compilado no se está actualizando correctamente a pesar del hard refresh. El navegador podría estar sirviendo una versión anterior del código.
2. **Cache de Vite/build**: el `npm run build` genera un bundle que no refleja los cambios más recientes. El servidor de producción sirve el bundle antiguo.
3. **HMR no aplicado**: si se usa `npm run dev`, el Hot Module Replacement podría no estar propagando los cambios al componente `IncidentMap`.
4. **React 19 concurrent rendering**: los cambios de estado en `globeCenter` podrían no estar triggerando re-renders del Source de Mapbox correctamente.
5. **Mapbox GL JS globe culling bug**: podría ser un bug conocido de Mapbox GL JS v3.9.3 donde las capas `circle` no tienen backface culling correcto en proyección globe.

## Solución aplicada (2026-05-21)

**Causa raíz confirmada**: en `mapbox-gl@3.9.3` con proyección `globe`, las capas de tipo `circle` no se recortan por la cara opuesta del planeta. Ningún `paint`/`layout` ni filtrado en CPU lo soluciona de forma robusta (durante animaciones de rotación los puntos de antípodas se siguen viendo). Las capas `symbol` con `icon-pitch-alignment: 'map'` **sí** se ocluyen correctamente — por eso la capa de buques (que ya usaba `symbol`) nunca presentó el bug.

**Fix definitivo**:

1. Sustituida la capa `incidents-point` (tipo `circle`) por una capa `symbol` con icono SDF `/icons/incident-dot.svg`, coloreado por categoría vía `icon-color`. Tamaño interpolado por severidad.
2. Sustituida la capa `incident-selected` (anillo del seleccionado) por una capa `symbol` con icono SDF `/icons/incident-ring.svg`.
3. Ambas capas usan `icon-pitch-alignment: 'map'` (clave para el culling) y `icon-rotation-alignment: 'viewport'` (mantiene los iconos de cara al usuario).
4. Eliminado el filtro hemisférico de `geojsonData`, `globeCenter` state y `handleMoveEnd` — ya no son necesarios.
5. **Excepción**: `PulseOverlay` proyecta DOM vía `map.project()` y no se beneficia del fix de la capa Mapbox. Se mantiene un dot-product check residual dentro del `update()` del overlay para no pintar pulsos en antípodas.

## Lecciones

- En proyección `globe`, **siempre preferir `symbol` sobre `circle`** para puntos de datos. El filtrado en CPU es un parche frágil.
- Los iconos SDF permiten reutilizar un único SVG y colorearlo dinámicamente con `icon-color`, evitando crear N variantes de icono.
- Cualquier overlay DOM que proyecte coordenadas geográficas a píxeles necesita su propio chequeo de visibilidad porque `map.project()` no informa de oclusión por el globo.

## Código relevante

- `frontend/src/components/map/IncidentMap.tsx` — capas `incidents-point` e `incident-selected` como `symbol`; `PulseOverlay` con dot-check residual.
- `frontend/public/icons/incident-dot.svg`, `incident-ring.svg` — iconos SDF.
