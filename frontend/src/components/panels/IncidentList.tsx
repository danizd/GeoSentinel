import { useMapStore, useFilterStore } from '../../stores/mapStore'
import type { Incident } from '../../types/incident'
import { STATUS_COLORS } from '../../types/incident'
import { getIncidentColor, getHeadline, getSeverityColor } from '../../utils/colors'
import { formatDistanceToNow } from 'date-fns'
import { ChevronLeft, ChevronRight } from 'lucide-react'

interface IncidentListProps {
  incidents: Incident[]
  total: number
  page: number
  isLoading: boolean
}

export function IncidentList({ incidents, total, page, isLoading }: IncidentListProps) {
  const { setSelectedIncident, selectedIncident } = useMapStore()
  const { filters, setFilters } = useFilterStore()

  const handleSelect = (incident: Incident) => {
    setSelectedIncident(incident)
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
          <option value="wildfire">Incendio</option>
          <option value="disaster_natural">Desastre natural</option>
          <option value="mobility">Movilidad</option>
          <option value="humanitarian">Humanitario</option>
          <option value="thermal_anomaly">Anomalia termica</option>
          <option value="other">Otros</option>
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
            const color = getIncidentColor(incident.event_type, incident.category)
            const headline = getHeadline(incident)

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
                    className="w-2 h-2 rounded-full shrink-0"
                    style={{ backgroundColor: `rgb(${color.join(',')})` }}
                  />
                  <span className="text-sm text-text-primary font-medium leading-tight line-clamp-2">
                    {headline}
                  </span>
                  <span className={`text-xs px-1.5 py-0.5 rounded shrink-0 ${STATUS_COLORS[incident.status]}`}>
                    {incident.status}
                  </span>
                </div>
                <div className="flex items-center gap-2 mt-1.5">
                  <div className="flex-1 h-1.5 bg-bg-base rounded overflow-hidden">
                    <div
                      className="h-full"
                      style={{ width: `${(incident.severity_max / 10) * 100}%`, backgroundColor: getSeverityColor(incident.severity_max) }}
                    />
                  </div>
                  <span className="text-xs text-text-secondary font-mono shrink-0">Severidad: {incident.severity_max.toFixed(1)}</span>
                </div>
                <div className="text-xs text-gray-400 mt-1 flex gap-2">
                  <span>Fuente: {incident.sources.join(' · ')}</span>
                  <span className="ml-auto">{formatDistanceToNow(new Date(incident.last_seen), { addSuffix: true })}</span>
                </div>
              </div>
            )
          })
        )}
      </div>

      <div className="p-3 border-t border-border-glow flex items-center justify-between text-xs text-text-secondary font-mono">
        <button
          onClick={() => setFilters({ page: page - 1 })}
          disabled={page <= 1}
          className="p-1 rounded hover:bg-bg-panel disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          <ChevronLeft size={16} />
        </button>
        <span>{total} incidentes · Pág {page} de {Math.ceil(total / (filters.limit || 20))}</span>
        <button
          onClick={() => setFilters({ page: page + 1 })}
          disabled={page >= Math.ceil(total / (filters.limit || 20))}
          className="p-1 rounded hover:bg-bg-panel disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          <ChevronRight size={16} />
        </button>
      </div>
    </div>
  )
}