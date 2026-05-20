# F-UI-CORR — UI de Correcciones Humanas

> Cargar junto con: `E-ARCH-FRONT` + `F-API-CORR` + `F-UI-AUTH`

## 1. Acceso

Visible solo si `hasScope('corrections:write')`.
Accesible desde el panel de detalle del incidente (ver `F-UI-DASH §4`).

## 2. Acciones disponibles y UI

### Marcar como falso positivo
Botón: `[MARK FALSE POSITIVE]` — color rojo, requiere confirmación.

```
┌─ CONFIRMAR ──────────────────────────────┐
│ ¿Marcar incidente d47e34fc como          │
│ falso positivo?                          │
│                                          │
│ RAZÓN (obligatorio):                     │
│ ┌────────────────────────────────────┐   │
│ │                                    │   │
│ └────────────────────────────────────┘   │
│                                          │
│ [CANCELAR]          [CONFIRMAR]          │
└──────────────────────────────────────────┘
```

### Cerrar incidente
Botón: `[CLOSE INCIDENT]` — color gris, mismo flujo de confirmación con campo razón.

### Reclasificar
Dropdown de `category` + `event_type`. Sin confirmación modal — botón `[SAVE]` inline.

### Reubicar
Click en mapa para seleccionar nueva coordenada canónica.
Flujo: `[RELOCATE]` → cursor en modo selección → click en mapa → preview → `[CONFIRM]`

## 3. Feedback tras corrección

- Éxito → toast verde: `"Correction saved"` + invalidar query de incidentes
- Error → toast rojo con mensaje de error de la API
- El incidente se actualiza en lista y mapa **sin recargar la página**

## 4. Historial de correcciones (opcional en v1)

Sección colapsable en panel de detalle: "CORRECTION LOG"
Lista las entradas de `corrections_audit` para ese incidente.

```
2026-05-09 10:23 UTC  |  analyst@org.com  |  reclassify
  before: conflict  →  after: disaster_natural
  reason: "Confirmed gas explosion, not armed attack"
```
