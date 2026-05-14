import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { fetchIncidents } from '../api/incidents'
import { useFilterStore, useMapStore } from '../stores/mapStore'
import { IncidentMap } from '../components/map/IncidentMap'
import { IncidentList } from '../components/panels/IncidentList'
import { IncidentDetail } from '../components/panels/IncidentDetail'
import { RefreshPanel } from '../components/panels/RefreshPanel'
import { AlertTriangle, Activity, Database, ChevronDown, RefreshCw } from 'lucide-react'
import { useState } from 'react'

const ACTIVE_SOURCES = [
  { name: 'USGS', label: 'USGS', desc: 'Terremotos >= 4.0M' },
  { name: 'FIRMS', label: 'NASA FIRMS', desc: 'Incendios activos (VIIRS/MODIS)' },
  { name: 'GDELT', label: 'GDELT Cloud v2', desc: 'Conflictos globales' },
  { name: 'ACLED', label: 'ACLED', desc: 'Conflictos estructurados' },
  { name: 'OPENSKY', label: 'OpenSky Network', desc: 'Vuelos militares (relay)' },
]

const PENDING_SOURCES = [
  { name: 'MT', label: 'MarineTraffic', desc: 'Tráfico naval AIS (comercial)' },
  { name: 'LUM', label: 'Liveuamap', desc: 'Conflictos geolocalizados (sin API)' },
]

export function Dashboard() {
  const { filters } = useFilterStore()
  const { selectedIncident, layers, toggleLayer } = useMapStore()
  const [showSources, setShowSources] = useState(false)
  const [showRefresh, setShowRefresh] = useState(false)

  const { data, isLoading, isFetching, dataUpdatedAt } = useQuery({
    queryKey: ['incidents', filters],
    queryFn: () => fetchIncidents(filters),
    refetchInterval: 30000,
    staleTime: 15000,
  })

  return (
    <div className="flex flex-col h-screen bg-bg-base text-text-primary">
      <div className="flex items-center justify-between px-4 py-2 bg-bg-panel border-b border-border-glow">
        <div className="flex items-center gap-2">
          <Activity className="text-accent-blue" size={20} />
          <span className="font-mono text-lg font-bold tracking-wider">GeoSentinel</span>
        </div>
        <Link
          to="/info"
          className="text-xs text-white hover:text-white transition-colors font-medium"
        >
          INFORMACIÓN
        </Link>
        <div className="flex items-center gap-4">
          <div className="flex gap-1">
            <button
              onClick={() => toggleLayer('scatter')}
              className={`px-2 py-1 text-xs font-mono rounded border ${
                layers.scatter ? 'bg-accent-blue text-bg-base' : 'border-border-glow text-text-secondary'
              }`}
            >
              PUNTOS
            </button>
            <button
              onClick={() => toggleLayer('heat')}
              className={`px-2 py-1 text-xs font-mono rounded border ${
                layers.heat ? 'bg-accent-blue text-bg-base' : 'border-border-glow text-text-secondary'
              }`}
            >
              CALOR
            </button>
            <button
              onClick={() => toggleLayer('aoi')}
              className={`px-2 py-1 text-xs font-mono rounded border ${
                layers.aoi ? 'bg-accent-blue text-bg-base' : 'border-border-glow text-text-secondary'
              }`}
            >
              ZONAS
            </button>
            <button
              onClick={() => toggleLayer('tracks')}
              className={`px-2 py-1 text-xs font-mono rounded border ${
                layers.tracks ? 'bg-accent-blue text-bg-base' : 'border-border-glow text-text-secondary'
              }`}
            >
              VUELOS
            </button>
            <button
              onClick={() => toggleLayer('vessels')}
              className={`px-2 py-1 text-xs font-mono rounded border ${
                layers.vessels ? 'bg-accent-blue text-bg-base' : 'border-border-glow text-text-secondary'
              }`}
            >
              BUQUES
            </button>
          </div>
          {isFetching && (
            <div className="flex items-center gap-2 text-xs text-text-secondary">
              <div className="animate-spin h-3 w-3 border border-accent-blue border-t-transparent rounded-full" />
              <span className="font-mono">
                UPDATED → {dataUpdatedAt ? 'hace ' + Math.floor((Date.now() - dataUpdatedAt) / 1000) + 's' : ''}
              </span>
            </div>
          )}
          <button
            onClick={() => setShowRefresh(!showRefresh)}
            className="text-text-secondary hover:text-accent-blue transition-colors"
            title="Data Sync"
          >
            <RefreshCw size={16} />
          </button>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {showRefresh && (
          <div className="shrink-0">
            <RefreshPanel />
          </div>
        )}
        <div className="w-[30%] min-w-[300px] border-r border-border-glow">
          <IncidentList
            incidents={data?.incidents || []}
            total={data?.total || 0}
            page={data?.page || 1}
            isLoading={isLoading}
          />
        </div>

        <div className="flex-1 relative">
          <IncidentMap
            incidents={data?.incidents || []}
          />
        </div>

        {selectedIncident && (
          <div className="w-[350px]">
            <IncidentDetail incident={selectedIncident} />
          </div>
        )}
      </div>

      <div className="flex items-center justify-between px-4 py-1 bg-bg-panel border-t border-border-glow text-xs font-mono text-text-secondary">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <AlertTriangle size={12} className="text-accent-amber" />
            <span>Sin novedades</span>
          </div>
          <div className="relative">
            <button
              onClick={() => setShowSources(!showSources)}
              className="flex items-center gap-1 hover:text-text-primary transition-colors"
            >
              <Database size={12} />
              <span>{ACTIVE_SOURCES.length} fuentes activas</span>
              <ChevronDown size={10} className={`transition-transform ${showSources ? 'rotate-180' : ''}`} />
            </button>
            {showSources && (
              <div className="absolute bottom-full left-0 mb-1 w-64 bg-bg-panel border border-border-glow rounded shadow-lg p-2 z-50">
                <div className="text-xs font-bold text-accent-blue mb-1">ACTIVAS</div>
                {ACTIVE_SOURCES.map(s => (
                  <div key={s.name} className="flex items-center gap-2 py-0.5">
                    <span className="w-2 h-2 rounded-full bg-green-500" />
                    <span className="text-text-primary font-semibold text-[11px]">{s.label}</span>
                    <span className="text-text-secondary text-[10px]">{s.desc}</span>
                  </div>
                ))}
                <div className="text-xs font-bold text-text-secondary mt-2 mb-1">PENDIENTES</div>
                {PENDING_SOURCES.map(s => (
                  <div key={s.name} className="flex items-center gap-2 py-0.5">
                    <span className="w-2 h-2 rounded-full bg-gray-600" />
                    <span className="text-text-secondary font-semibold text-[11px]">{s.label}</span>
                    <span className="text-text-secondary text-[10px]">{s.desc}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
        <div>
          {data?.total || 0} incidentes activos
        </div>
      </div>
    </div>
  )
}