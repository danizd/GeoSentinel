# F-UI-AOI — UI de Gestión de AOI

> Cargar junto con: `E-ARCH-FRONT` + `F-API-AOI` + `F-UI-MAP`

## 1. Acceso

Ruta: `/aoi` o panel lateral secundario accesible desde topbar.
Requiere scope `aoi:manage`.

## 2. Lista de AOIs

```
┌─ AREAS OF INTEREST ──────────────── [+ NEW] ─┐
│                                               │
│  ● Europa Central          ACTIVE             │
│    conflict · wildfire  ·  SEV ≥ 3.0          │
│    [EDIT]  [VIEW ON MAP]  [DEACTIVATE]        │
│                                               │
│  ○ Medio Oriente           INACTIVE           │
│    all categories  ·  SEV ≥ 5.0              │
│    [EDIT]  [ACTIVATE]                         │
│                                               │
└───────────────────────────────────────────────┘
```

## 3. Crear / editar AOI

Flujo: formulario lateral + dibujo en mapa.

**Paso 1 — Dibujar polígono en mapa**
Usar `@mapbox/mapbox-gl-draw` para dibujo interactivo de polígonos.
El polígono se convierte a GeoJSON al confirmar.

**Paso 2 — Configurar atributos**
```
NOMBRE:      [________________]
DESCRIPCIÓN: [________________]
CATEGORÍAS:  [✓] conflict  [✓] wildfire  [ ] earthquake  [ ] all
SEV MÍNIMA:  [===●=========]  3.0
```

**Paso 3 — Guardar**
`POST /v1/aoi` con el GeoJSON generado.
Al guardar → AOI aparece en capa del mapa inmediatamente.

## 4. Validaciones en cliente

- Polígono debe tener al menos 3 vértices
- Nombre obligatorio, máx 100 chars
- `min_severity` entre 0.0 y 10.0
- Área máxima: mostrar advertencia si supera 5.000.000 km² (ver `F-API-AOI`)

## 5. Interacción AOI ↔ mapa principal

- AOI activo → visible como capa semitransparente en mapa principal (`F-UI-MAP §2 Capa 4`)
- Click en AOI en mapa → mostrar tooltip con nombre + botón "Ver incidentes"
- "Ver incidentes" → filtrar lista automáticamente por ese AOI (`aoi_id` en query)
