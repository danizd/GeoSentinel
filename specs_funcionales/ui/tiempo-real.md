# F-UI-TIEMPO-REAL — Datos en Tiempo Real (Polling)

> Cargar junto con: `E-ARCH-FRONT` + `F-UI-DASH`

## 1. Estrategia: polling con TanStack Query

No se usan WebSockets en esta versión. El polling con TanStack Query
cubre el caso de uso de nowcasting con suficiente frescura de datos.

## 2. Hooks de datos

```typescript
// api/incidents.ts
export function useIncidents(filters: IncidentFilters) {
  return useQuery({
    queryKey: ['incidents', filters],
    queryFn: () => fetchIncidents(filters),
    refetchInterval: POLL_INCIDENTS,       // 30s desde E-ARCH-FRONT §7
    staleTime: POLL_INCIDENTS / 2,         // 15s — datos "frescos"
    refetchIntervalInBackground: false,    // parar polling si tab oculto
    refetchOnWindowFocus: true,            // refetch al volver al tab
  })
}

export function useSourceStatus() {
  return useQuery({
    queryKey: ['source-status'],
    queryFn: () => fetchSourceStatus(),
    refetchInterval: POLL_STATS,           // 60s
  })
}
```

## 3. Invalidación manual

Cuando el usuario aplica un filtro nuevo → refetch inmediato sin esperar el intervalo:

```typescript
const { invalidateQueries } = useQueryClient()

// En filterStore, al cambiar filtros:
onChange: (newFilters) => {
  set({ filters: newFilters })
  invalidateQueries({ queryKey: ['incidents'] })
}
```

## 4. Indicador visual de actualización

```typescript
const { isFetching, dataUpdatedAt } = useIncidents(filters)

// En Topbar:
// isFetching → spinner suave (no bloqueante)
// dataUpdatedAt → "UPDATED 23s AGO"
```

El indicador de tiempo usa `formatDistanceToNow` de `date-fns`.
**No usar** `new Date()` directamente — genera re-renders innecesarios.

## 5. Manejo de errores de red

```typescript
useQuery({
  // ...
  retry: 3,
  retryDelay: attemptIndex => Math.min(1000 * 2 ** attemptIndex, 30000),
  onError: (error) => {
    // Mostrar banner no intrusivo: "Conexión perdida — reintentando..."
    // NO modal bloqueante
  }
})
```

Si tras 3 reintentos sigue fallando → badge rojo en statusbar "API OFFLINE".
Los datos anteriores permanecen visibles (stale data) con indicador visual de edad.

## 6. Estados de carga

| Estado | UI |
|--------|----|
| Primera carga | Skeleton en lista + spinner en mapa |
| Refetch en background | Spinner pequeño en topbar (no bloquea) |
| Error de red | Banner inferior no intrusivo |
| Sin datos (filtros muy restrictivos) | Mensaje "No incidents match current filters" en panel |

**Nunca** mostrar pantalla de carga completa en refetches — el usuario pierde contexto.
