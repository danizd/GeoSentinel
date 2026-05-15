import { X } from 'lucide-react'
import { useMapStore } from '../../stores/mapStore'
import type { Incident } from '../../types/incident'
import { STATUS_COLORS } from '../../types/incident'
import { getIncidentColor, getHeadline } from '../../utils/colors'
import { formatDistanceToNow } from 'date-fns'

interface IncidentDetailProps {
  incident: Incident
}

export function IncidentDetail({ incident }: IncidentDetailProps) {
  const { setSelectedIncident } = useMapStore()
  const color = getIncidentColor(incident.event_type, incident.category)
  const headline = getHeadline(incident)

  return (
    <div className="bg-bg-panel border-l border-border-glow h-full flex flex-col w-full">
      <div className="p-4 border-b border-border-glow flex items-center justify-between">
        <h2 className="font-mono text-sm text-accent-blue">DETALLE</h2>
        <button
          onClick={() => setSelectedIncident(null)}
          className="text-text-secondary hover:text-text-primary"
        >
          <X size={18} />
        </button>
      </div>

      <div className="flex-1 overflow-auto p-4 space-y-4">
        <div>
          <div className="font-mono text-xs text-text-secondary mb-1">ID</div>
          <div className="font-mono text-sm text-text-primary break-all">{incident.incident_id}</div>
        </div>

        <div className="flex items-center gap-3">
          <span
            className="w-3 h-3 rounded-full shrink-0"
            style={{ backgroundColor: `rgb(${color.join(',')})` }}
          />
          <span className="text-lg font-bold text-text-primary leading-tight">{headline}</span>
          <span className={`text-xs px-2 py-1 rounded shrink-0 ${STATUS_COLORS[incident.status]}`}>
            {incident.status}
          </span>
        </div>

        <div>
          <div className="font-mono text-xs text-text-secondary mb-1">Categoría</div>
          <div className="text-text-primary">{incident.category}</div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="font-mono text-xs text-text-secondary mb-1">Severidad</div>
            <div className="flex items-center gap-2">
              <div className="flex-1 h-2 bg-bg-base rounded overflow-hidden">
                <div
                  className="h-full bg-accent-amber"
                  style={{ width: `${(incident.severity_max / 10) * 100}%` }}
                />
              </div>
              <span className="font-mono text-sm text-text-primary">{incident.severity_max.toFixed(1)}</span>
            </div>
          </div>
          <div>
            <div className="font-mono text-xs text-text-secondary mb-1">Confianza</div>
            <div className="flex items-center gap-2">
              <div className="flex-1 h-2 bg-bg-base rounded overflow-hidden">
                <div
                  className="h-full bg-accent-blue"
                  style={{ width: `${(incident.confidence / 10) * 100}%` }}
                />
              </div>
              <span className="font-mono text-sm text-text-primary">{incident.confidence.toFixed(1)}</span>
            </div>
          </div>
        </div>

        {incident.canonical_point && (
          <div>
            <div className="font-mono text-xs text-text-secondary mb-1">Ubicación</div>
            <div className="font-mono text-sm text-text-primary">
              {incident.canonical_point.lat.toFixed(4)}° {incident.canonical_point.lon.toFixed(4)}°
            </div>
          </div>
        )}

        <div>
          <div className="font-mono text-xs text-text-secondary mb-1">Fuentes</div>
          <div className="flex gap-1">
            {incident.sources.map((source) => (
              <span
                key={source}
                className="text-xs px-2 py-0.5 rounded bg-bg-base text-text-primary border border-border-glow"
              >
                {source}
              </span>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <div className="font-mono text-xs text-text-secondary mb-1">1ª detección</div>
            <div className="font-mono text-sm text-text-primary">
              {formatDistanceToNow(new Date(incident.first_seen), { addSuffix: true })}
            </div>
          </div>
          <div>
            <div className="font-mono text-xs text-text-secondary mb-1">Última detección</div>
            <div className="font-mono text-sm text-text-primary">
              {formatDistanceToNow(new Date(incident.last_seen), { addSuffix: true })}
            </div>
          </div>
        </div>

        <div>
          <div className="font-mono text-xs text-text-secondary mb-1">Observaciones</div>
          <div className="text-text-primary">{incident.observation_count}</div>
        </div>
      </div>
    </div>
  )
}