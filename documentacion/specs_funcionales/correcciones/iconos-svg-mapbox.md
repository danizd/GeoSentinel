# F-CORR-001 — Iconos SVG en capas de vuelos y buques

> Cargar junto con: `E-ARCH-FRONT` + `F-UI-MAP` + `F-ING-MIL` + `F-ING-AIS`

## 1. Problema

Los iconos de vuelos militares y buques en el mapa usan caracteres Unicode
(`✈` U+2708, `⛵` U+26F5, `⛨` U+26E8) renderizados en un `<canvas>` y
registrados como imagen SDF con `map.addImage()`. Esto presenta varios
problemas:

1. **Renderizado inconsistente por SO**: el glifo `✈` se dibuja distinto en
   Windows, macOS y Linux según la fuente del sistema. La silueta no es
   predecible.
2. **Calidad visual limitada**: los glifos Unicode no fueron diseñados como
   iconos de mapa. Carecen de proporciones óptimas para tamaños pequeños y
   rotación.
3. **Código innecesariamente complejo**: se crea un `<canvas>` por icono, se
   dibuja el carácter con `fillText`, se convierte a data URL, se carga como
   `Image`, y luego se registra — 5 pasos para lo que Mapbox puede hacer en 1.
4. **Archivo huérfano**: `frontend/public/avion.png` es un remanente del
   intento 1 (IconLayer con PNG externo) que ya no se usa.
5. **Código muerto**: `MilitaryFlightsLayer.tsx` exporta un hook
   `useMilitaryFlightsLayer` con layers Deck.gl que nunca se importa.

## 2. Solución

Sustituir la generación de iconos vía canvas+Unicode por carga directa de
archivos SVG de silueta con `map.loadImage()`, manteniendo el registro SDF
para conservar el coloreado dinámico por país/operador.

### 2.1 Flujo actual (a eliminar)

```
handleMapLoad → document.createElement('canvas')
             → ctx.fillText('\u2708')
             → canvas.toDataURL()
             → new Image() + img.onload
             → map.addImage('airplane-icon', img, { sdf: true })
```

### 2.2 Flujo nuevo

```
handleMapLoad → map.loadImage('/icons/airplane.svg', callback)
             → map.addImage('airplane-icon', img, { sdf: true })
```

Un paso en lugar de cinco. Misma API, mismo resultado SDF, mejor calidad
visual.

## 3. Especificación técnica

### 3.1 Archivos SVG nuevos

Ubicación: `frontend/public/icons/`

| Archivo | Icono | Descripción | Tamaño viewBox |
|---------|-------|-------------|----------------|
| `airplane.svg` | Silueta de avión militar vista superior | Fuselaje, alas en flecha, estabilizadores. Relleno blanco (`#FFFFFF`) sobre fondo transparente. | 24×24 |
| `ship.svg` | Silueta de buque vista superior | Casco, superestructura central. Relleno blanco sobre transparente. | 24×24 |
| `shield.svg` | Escudo militar | Forma de escudo heráldico. Relleno `#FBBF24` (ámbar) sobre transparente. | 24×24 |

**Requisitos de diseño del SVG**:

- `<svg>` con `viewBox="0 0 24 24"`, sin atributos `width`/`height`
  fijos (Mapbox escala con `icon-size`).
- Relleno blanco (`#FFFFFF`) sobre fondo transparente. El coloreado en
  runtime lo gestiona `icon-color` con SDF.
- Sin trazos (`stroke`), solo relleno (`fill`). Los trazos no se comportan
  bien con SDF.
- Path centrado en el viewBox — el centro del icono (0,0 en coordenadas
  de la capa) debe coincidir con el centro del viewBox (12,12 en un
  viewBox de 24×24).
- Para el avión, la nariz apunta hacia arriba (0° = norte). Mapbox rota
  con `icon-rotate: ['get', 'heading']` en sentido horario respecto al
  norte, que es el estándar de heading aeronáutico.
- Sin texto, sin gradientes, sin filtros — solo `<path>` con `fill`.

### 3.2 Registro de iconos — nuevo handleMapLoad

Reemplazar el bloque actual de generación de canvas en `handleMapLoad`
(`IncidentMap.tsx`, líneas 512-566) por:

```typescript
const handleMapLoad = useCallback((e: any) => {
  const map = e.target

  const icons = [
    { url: '/icons/airplane.svg', id: 'airplane-icon' },
    { url: '/icons/ship.svg', id: 'ship-icon' },
    { url: '/icons/shield.svg', id: 'shield-icon' },
  ]

  icons.forEach(({ url, id }) => {
    if (map.hasImage(id)) return
    map.loadImage(url, (err: any, img: any) => {
      if (err) {
        console.error(`Error loading icon ${id}:`, err)
        return
      }
      if (!map.hasImage(id)) {
        map.addImage(id, img, { sdf: true })
      }
    })
  })
}, [])
```

**Cambios respecto al código actual**:

- Se elimina: `document.createElement('canvas')`, `getContext('2d')`,
  `fillText`, `toDataURL()`, `new Image()`, `img.onload`.
- Se mantiene: `{ sdf: true }` en `addImage` (necesario para coloreado
  dinámico con `icon-color`).
- Se añade: `map.hasImage(id)` antes de cargar (evita doble registro).
- Se añade: manejo de error explícito con `console.error`.
- Se añade: iteración sobre array de iconos en lugar de tres bloques
  repetidos.

### 3.3 Capas de renderizado — sin cambios

Las capas `symbol` y `circle` (halos) **no cambian**. Los IDs de imagen
(`'airplane-icon'`, `'ship-icon'`, `'shield-icon'`) se mantienen idénticos.
Las propiedades `icon-color: ['get', 'color']`, `icon-rotate: ['get', 'heading']`
y `icon-rotation-alignment: 'map'` funcionan exactamente igual con iconos
SVG+SDF que con Unicode+SDF.

### 3.4 Limpieza de código muerto

| Archivo | Acción |
|---------|--------|
| `frontend/public/avion.png` | **Eliminar** — remanente del intento 1, nunca referenciado |
| `frontend/src/components/map/MilitaryFlightsLayer.tsx` | **Eliminar** — hook Deck.gl nunca importado, obsoleto desde la migración a capas nativas |

### 3.5 Actualización de specs existentes

Las siguientes specs contienen secciones desactualizadas que deben
actualizarse como parte de esta corrección:

| Spec | Sección | Cambio |
|------|---------|--------|
| `F-ING-MIL` §9.2 | "Solución final: Mapbox SDF con ✈ renderizado en canvas" | Actualizar a "Mapbox SDF con iconos SVG cargados vía loadImage". Eliminar código de canvas. Documentar el nuevo flujo `map.loadImage()` + SDF. |
| `F-ING-AIS` §12 | "ScatterplotLayer 'vessels-layer'" | Reemplazar por las capas nativas Mapbox (doble halo + symbol SDF) que es lo que realmente está implementado. |
| `F-UI-MAP` §2 | Deck.gl como controller | Actualizar: vuelos y buques usan capas nativas Mapbox, no Deck.gl. Deck.gl se mantiene para scatterplot de incidentes y heatmap. |
| `E-SOURCES` §2.5 | "icono SDF ✈ generado en onLoad" | Cambiar a "icono SVG cargado con loadImage, registrado como SDF". |
| `E-SOURCES` §2.6 | "ScatterplotLayer para buques" | Cambiar a "capas nativas Mapbox (symbol SDF + doble halo)". |

## 4. Historial de intentos anteriores (no modificar)

La sección 9.1 de `F-ING-MIL` ("Historial de intentos fallidos") se conserva
íntegra. Los 5 intentos documentados siguen siendo válidos como referencia.
Esta corrección no modifica ese historial — solo cambia la sección 9.2
(solución final).

## 5. Tests obligatorios

| Test | Descripción |
|------|-------------|
| Renderizado SVG | Los 3 iconos (airplane, ship, shield) se cargan y renderizan en el mapa sin errores de consola |
| Coloreado dinámico | `icon-color` data-driven funciona: avión USA azul, Rusia rojo, etc. |
| Rotación por heading | `icon-rotate` rota el icono correctamente respecto al norte geográfico |
| Anclaje en globe | Iconos permanecen anclados al mapa con `pitch > 0` y `projection: 'globe'` |
| Contraste con halos | Doble halo (oscuro + claro) visible contra fondos de satélite claros y oscuros |
| Escalado | `icon-size` escala sin pixelación a zoom alto (≥12) |
| Fallback por error | Si un SVG falla al cargar, el icono no se registra pero la app no crashea |
| Limpieza | `avion.png` eliminado de `public/` y `MilitaryFlightsLayer.tsx` eliminado de `src/` |
| Sin regresión | Las capas de incidentes (scatterplot), AOI (polygon) y heatmap funcionan igual |

## 6. No incluir en esta corrección

- No cambiar los colores del mapa de `getMilitaryColor` / `getVesselColor`.
- No cambiar el sistema de doble halo.
- No cambiar las capas Deck.gl de incidentes, heatmap o AOI.
- No añadir nuevos iconos (bases militares, dark ships, etc.) — eso es
  extensión futura.
- No migrar las capas de incidentes de Deck.gl a Mapbox nativo — es un
  cambio ortogonal.