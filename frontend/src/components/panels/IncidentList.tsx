import { useMapStore, useFilterStore } from '../../stores/mapStore'
import type { Incident } from '../../types/incident'
import { CATEGORY_COLORS, STATUS_COLORS } from '../../types/incident'
import { formatDistanceToNow } from 'date-fns'

interface IncidentListProps {
  incidents: Incident[]
  total: number
  page: number
  isLoading: boolean
}

export function IncidentList({ incidents, total, page, isLoading }: IncidentListProps) {
  const { setSelectedIncident, setViewport, selectedIncident } = useMapStore()
  const { filters, setFilters } = useFilterStore()

  const handleSelect = (incident: Incident) => {
    setSelectedIncident(incident)
    if (incident.canonical_point) {
      setViewport({
        longitude: incident.canonical_point.lon,
        latitude: incident.canonical_point.lat,
        zoom: 6,
      })
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex gap-2 p-3 border-b border-border-glow">
        <select
          value={filters.category || ''}
          onChange={(e) => setFilters({ category: e.target.value || undefined })}
          className="bg-bg-panel text-text-primary text-sm px-2 py-1 rounded border border-border-glow"
        >
          <option value="">Todas</option>
          <option value="conflict">Conflicto</option>
          <option value="disaster_natural">Desastre natural</option>
          <option value="wildfire">Incendio</option>
          <option value="crime">Crimen</option>
          <option value="protest">Protesta</option>
        </select>
        <select
          value={filters.status || ''}
          onChange={(e) => setFilters({ status: e.target.value || undefined })}
          className="bg-bg-panel text-text-primary text-sm px-2 py-1 rounded border border-border-glow"
        >
          <option value="open,updated">Activos</option>
          <option value="stale">Inactivos</option>
          <option value="closed">Cerrados</option>
          <option value="">Todos</option>
        </select>
      </div>

      <div className="flex-1 overflow-auto">
        {isLoading ? (
          <div className="flex items-center justify-center h-32">
            <div className="animate-spin h-6 w-6 border-2 border-accent-blue border-t-transparent rounded-full" />
          </div>
        ) : incidents.length === 0 ? (
          <div className="text-center text-text-secondary p-4">Sin incidentes con los filtros actuales</div>
        ) : (
          incidents.map((incident) => {
            const isSelected = selectedIncident?.incident_id === incident.incident_id
            const color = CATEGORY_COLORS[incident.category] || CATEGORY_COLORS.default
            return (
              <div
                key={incident.incident_id}
                onClick={() => handleSelect(incident)}
                className={`p-3 border-b border-border-glow cursor-pointer transition-colors ${
                  isSelected ? 'bg-bg-glass' : 'hover:bg-bg-panel'
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span
                    className="w-2 h-2 rounded-full"
                    style={{ backgroundColor: `rgb(${color.join(',')})` }}
                  />
                  <span className="font-mono text-sm text-text-primary">
                    {incident.event_type.toUpperCase()}
                  </span>
                  <span className={`text-xs px-1.5 py-0.5 rounded ${STATUS_COLORS[incident.status]}`}>
                    {incident.status}
                  </span>
                </div>
                <div className="text-xs text-text-secondary font-mono">
                  SEV {incident.severity_max.toFixed(1)} · {incident.sources.join(', ')}
                </div>
                <div className="text-xs text-text-secondary mt-1">
                  {formatDistanceToNow(new Date(incident.last_seen), { addSuffix: true })}
                </div>
              </div>
            )
          })
        )}
      </div>

      <div className="p-3 border-t border-border-glow text-xs text-text-secondary font-mono">
        {total} incidentes · Pág {page} de {Math.ceil(total / (filters.limit || 20))}
      </div>
    </div>
  )
}