# F-UI-REFRESH — Actualización Manual de Datos (Botones de Interfaz)

> Cargar junto con: `E-ARCH` + `E-ARCH-FRONT` + `E-SEC` + `F-UI-DASH`

---

## 1. Propósito

Permitir al operador disparar manualmente la ingesta de cada fuente
y el procesamiento posterior (clustering + ciclo de vida) desde la UI,
sin acceder al terminal ni ejecutar scripts directamente.

---

## 2. Backend — endpoints de control requeridos

Antes de implementar la UI, el backend debe exponer un endpoint
por cada script existente. Estos endpoints ejecutan los mismos scripts
de forma asíncrona y devuelven el resultado.

| Endpoint | Método | Script equivalente | Scope requerido |
|----------|--------|--------------------|-----------------|
| `/v1/admin/run/usgs` | POST | `scripts/run_usgs.py` | `admin:run` |
| `/v1/admin/run/firms` | POST | `scripts/run_firms.py` | `admin:run` |
| `/v1/admin/run/gdelt` | POST | `scripts/run_gdelt.py` | `admin:run` |
| `/v1/admin/run/acled` | POST | `scripts/run_acled.py` | `admin:run` |
| `/v1/admin/run/clustering` | POST | `scripts/run_clustering.py` | `admin:run` |
| `/v1/admin/run/lifecycle` | POST | `jobs/incident_lifecycle.py` | `admin:run` |
| `/v1/admin/run/all` | POST | Secuencia completa (ver §4) | `admin:run` |

### Contrato de respuesta (todos los endpoints)

```json
{
  "job":        "usgs",
  "status":     "running",
  "started_at": "2026-05-14T10:23:00Z",
  "job_id":     "uuid"
}
```

Los jobs corren en background (FastAPI `BackgroundTasks`).
El endpoint devuelve `202 Accepted` inmediatamente, no espera a que termine.

### Endpoint de estado del job

```
GET /v1/admin/run/status/{job_id}
```

```json
{
  "job_id":       "uuid",
  "job":          "usgs",
  "status":       "completed",
  "started_at":   "2026-05-14T10:23:00Z",
  "finished_at":  "2026-05-14T10:23:45Z",
  "duration_sec": 45,
  "result": {
    "events_fetched":   120,
    "events_inserted":  118,
    "events_quarantine": 2,
    "incidents_created": 8,
    "incidents_updated": 3
  },
  "error": null
}
```

Si el job falla: `"status": "failed"` con `"error": "mensaje"`.

---

## 3. Nuevo scope de autenticación

Añadir a `E-SEC §1`:

| Scope | Descripción |
|-------|-------------|
| `admin:run` | Permite disparar jobs de ingesta y procesamiento |

Solo usuarios con este scope ven y pueden usar los controles de refresh.
Ver `F-UI-AUTH §5` para patrón de ocultación por scope.

---

## 4. Secuencia del job "Run All"

El endpoint `/v1/admin/run/all` ejecuta en este orden estricto:

```
1. USGS      ┐
2. FIRMS     ├── en paralelo (no dependen entre sí)
3. GDELT     │
4. ACLED     ┘
      ↓ esperar a que todos terminen
5. Clustering  (necesita los eventos ya insertados)
      ↓
6. Lifecycle   (necesita los incidentes ya agrupados)
```

Los pasos 1–4 corren en paralelo. Los pasos 5 y 6 son secuenciales
y dependen de los anteriores.

---

## 5. UI — Panel de control de refresh

Componente: `components/panels/RefreshPanel.tsx`

Visible solo si `hasScope('admin:run')`.
Accesible desde el topbar mediante botón `[SYNC]` o icono `RefreshCw` de Lucide.
Se muestra como panel lateral o modal glassmorphism.

### Layout del panel

```
┌─ DATA SYNC ──────────────────────────────────────────┐
│                                                       │
│  SOURCES                              LAST RUN        │
│  ─────────────────────────────────────────────────    │
│  ◉ USGS     Terremotos ≥ 4.0    hace 12 min  [RUN]   │
│  ◉ FIRMS    Incendios activos   hace 1 h     [RUN]   │
│  ◉ GDELT    Conflictos media    hace 45 min  [RUN]   │
│  ◉ ACLED    Conflictos batch    hace 6 h     [RUN]   │
│                                                       │
│  PROCESSING                                           │
│  ─────────────────────────────────────────────────    │
│  ◉ Clustering   Agrupa eventos     hace 8 min  [RUN] │
│  ◉ Lifecycle    Actualiza estados  hace 8 min  [RUN] │
│                                                       │
│  ───────────────────────────────────────────────────  │
│                              [  RUN ALL  ]            │
└───────────────────────────────────────────────────────┘
```

---

## 6. Estados visuales de cada botón

Cada botón `[RUN]` tiene cuatro estados:

| Estado | Visual | Descripción |
|--------|--------|-------------|
| `idle` | Botón activo, color acento | Listo para ejecutar |
| `running` | Spinner + `RUNNING...` deshabilitado | Job en curso |
| `success` | Check verde + `DONE` durante 3s | Completado sin errores |
| `error` | X rojo + `FAILED` durante 5s | Completado con errores |

Tras `success` o `error`, el botón vuelve a `idle` automáticamente.

---

## 7. Indicador de progreso y resultado

Al completar un job, mostrar bajo el botón correspondiente:

```
✓ USGS completado en 45s
  Events: 120 fetched · 118 inserted · 2 quarantine
  Incidents: 8 created · 3 updated
```

Si hay errores:
```
✗ GDELT fallido (timeout después de 30s)
  [VER LOG]
```

El botón `[VER LOG]` abre un modal con el mensaje de error completo
devuelto por el campo `error` del endpoint de estado.

---

## 8. Polling de estado del job en frontend

Al disparar un job, el frontend:

1. Hace `POST /v1/admin/run/{source}` → recibe `job_id`
2. Inicia polling a `GET /v1/admin/run/status/{job_id}` cada 2 segundos
3. Cuando `status` es `completed` o `failed` → detiene el polling
4. Muestra resultado según §7
5. Invalida la query de incidentes en TanStack Query para refrescar el mapa

```typescript
// Usando TanStack Query para el polling de estado
useQuery({
  queryKey: ['job-status', jobId],
  queryFn: () => fetchJobStatus(jobId),
  refetchInterval: (data) =>
    data?.status === 'running' ? 2000 : false,  // para cuando termina
  enabled: !!jobId,
})
```

---

## 9. Comportamiento del botón "RUN ALL"

- Muestra un spinner global en el panel mientras corre
- Deshabilita todos los botones individuales durante la ejecución
- Muestra progreso por fase:

```
[1/3] Ingesta en curso...   USGS ✓  FIRMS ✓  GDELT ✓  ACLED ✓
[2/3] Clustering...
[3/3] Lifecycle...
✓ Completado en 2m 14s — 847 eventos · 42 incidentes actualizados
```

- Al completar: invalida queries de incidentes y fuentes en TanStack Query

---

## 10. Protección contra ejecuciones simultáneas

El backend debe rechazar una segunda ejecución del mismo job
si ya hay uno corriendo:

```json
HTTP 409 Conflict
{
  "error": "job_already_running",
  "job": "usgs",
  "running_since": "2026-05-14T10:23:00Z"
}
```

La UI muestra el botón en estado `running` si recibe un 409,
adoptando el `job_id` del job ya en curso para hacer polling de su estado.

---

## 11. Integración con statusbar

Tras cada ejecución exitosa, actualizar en el statusbar (`F-UI-DASH §5`)
el indicador de latencia de la fuente correspondiente a verde,
sin esperar al ciclo de polling habitual de `useSourceStatus`.

---

## 12. Tests obligatorios

| Test | Descripción |
|------|-------------|
| Auth | Botones no visibles sin scope `admin:run` |
| Disparo individual | POST a `/v1/admin/run/usgs` devuelve 202 + job_id |
| Polling de estado | Frontend detecta `completed` y detiene el polling |
| 409 simultáneo | Segundo click en `[RUN]` mientras corre adopta el job en curso |
| Run All secuencia | Clustering no empieza hasta que los 4 ingestores terminan |
| Invalidación | Mapa se refresca con nuevos incidentes al completar job |
| Error handling | Job fallido muestra estado `error` y mensaje legible |