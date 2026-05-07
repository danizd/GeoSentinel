# F-LC — Ciclo de Vida del Incidente (Máquina de Estados)

> **Spec funcional** — Obligatoria junto con `E-MODEL` para cualquier tarea
> que modifique el estado de incidentes.

---

## 1. Estados y definiciones

| Estado | Descripción |
|--------|-------------|
| `open` | Incidente activo con actividad reciente (`now - last_seen < STALE_HOURS`) |
| `updated` | Recibió nuevas observaciones en los últimos 15 min (estado transitorio) |
| `stale` | Sin nuevas observaciones durante `INCIDENT_STALE_HOURS` (default: 72h) |
| `closed` | Confirmado como terminado (manual o por regla de negocio) |
| `false_positive` | Marcado por operador humano; excluido de conteos y API por defecto |

---

## 2. Diagrama de transiciones

```
             nueva observación
   ┌─────────────────────────────────────────┐
   │                                         │
[open] ──nueva obs──► [updated] ──15min──► [open]
   │                                         │
   │  > STALE_HOURS sin obs                  │  > STALE_HOURS sin obs
   ▼                                         ▼
[stale] ◄────────────────────────────────────┘
   │
   ├──── nueva observación ──► [open]   (reactivación)
   │
   └──── cierre manual ──────► [closed]

[open | updated | stale] ──operador──► [false_positive]
[false_positive] ──operador──► [open]  (reversión)
[closed] ──operador──► [open]          (reapertura)
```

## 3. Reglas de transición

### 3.1 `* → updated`
- **Trigger**: nuevo `event_canonical` se asocia a este incidente
- **Acción**: actualizar `last_seen`, `observation_count`, `sources`,
  recalcular `severity_latest` y `confidence`

### 3.2 `updated → open`
- **Trigger**: han pasado 15 minutos desde la última actualización
- **Implementación**: job periódico que resetea `updated → open`

### 3.3 `open | updated → stale`
- **Trigger**: `now() - last_seen > INCIDENT_STALE_HOURS`
- **No eliminar**: el incidente permanece en BD, solo cambia status

### 3.4 `stale → open` (reactivación)
- **Trigger**: nueva observación entra al cluster del incidente
- **Condición**: la observación tiene `event_time` dentro de la ventana activa
- **Log**: registrar reactivación con `reason='new_observation'`

### 3.5 `* → false_positive`
- **Trigger**: operador humano via `POST /v1/corrections`
- **Obligatorio**: crear registro en `corrections_audit`
- **Efecto**: incidente excluido de API pública por defecto
  (incluir solo si query param `include_fp=true`)

### 3.6 `* → closed`
- **Trigger**: operador humano o regla de negocio configurable
- **Diferencia con `false_positive`**: el incidente sí ocurrió pero terminó

## 4. Reglas de purga y archivado

- Incidentes con `status IN ('closed','false_positive')` y
  `last_updated < now() - WINDOW_DAYS` → mover a tabla `incidents_archive`
- Incidentes `stale` con `last_seen < now() - WINDOW_DAYS * 2` → idem
- La purga es **MOVE**, nunca DELETE de la tabla principal

## 5. Transiciones inválidas (deben lanzar excepción)

```python
INVALID_TRANSITIONS = {
    'closed': ['open', 'updated', 'stale'],      # solo manual puede reabrir
    'false_positive': ['updated', 'stale'],       # solo puede ir a open
}
```
