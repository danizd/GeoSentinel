import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { fetchIncidents } from '../api/incidents'
import { useFilterStore, useMapStore } from '../stores/mapStore'
import { IncidentMap } from '../components/map/IncidentMap'
import { IncidentList } from '../components/panels/IncidentList'
import { IncidentDetail } from '../components/panels/IncidentDetail'
import { RefreshPanel } from '../components/panels/RefreshPanel'
import { AlertTriangle, Activity, Database, ChevronDown, RefreshCw, List, X } from 'lucide-react'
import { useState, useEffect } from 'react'
import { RADAR_TITLE } from '../api/cr360'

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

const LAYER_BUTTONS = [
  { key: 'scatter' as const, label: 'PUNTOS' },
  { key: 'heat' as const, label: 'CALOR' },
  { key: 'aoi' as const, label: 'ZONAS' },
  { key: 'tracks' as const, label: 'VUELOS MILITARES' },
  { key: 'vessels' as const, label: 'BUQUES MILITARES' },
  { key: 'bases' as const, label: 'BASES DE EEUU' },
]

export function Dashboard() {
  const { filters } = useFilterStore()
  const { selectedIncident, layers, toggleLayer, setSelectedIncident } = useMapStore()
  const [showSources, setShowSources] = useState(false)
  const [showLayers, setShowLayers] = useState(false)
  const [showRefresh, setShowRefresh] = useState(false)
  const [showSidebar, setShowSidebar] = useState(false)

  const { data, isLoading, isFetching, dataUpdatedAt } = useQuery({
    queryKey: ['incidents', filters],
    queryFn: () => fetchIncidents(filters),
    refetchInterval: 30000,
    staleTime: 15000,
  })

  useEffect(() => {
    if (selectedIncident) {
      setShowSidebar(false)
    }
  }, [selectedIncident])

  return (
    <div className="flex flex-col h-screen bg-bg-base text-text-primary">
      <div className="flex items-center justify-between px-3 py-2 bg-bg-panel border-b border-border-glow">
        <div className="flex items-center gap-2">
          <button
            className="md:hidden p-1 rounded hover:bg-bg-glass"
            onClick={() => setShowSidebar(!showSidebar)}
          >
            <List size={20} />
          </button>
          <Activity className="text-accent-blue" size={20} />
          <span className="font-mono text-lg font-bold tracking-wider hidden sm:inline">GeoSentinel</span>
          <span className="font-mono text-lg font-bold tracking-wider sm:hidden">GS</span>
        </div>

        <div className="flex items-center gap-2">
          <Link
            to="/radar"
            className="text-xs text-white hover:text-white transition-colors font-medium border border-accent-blue/30 rounded px-2 py-1 bg-accent-blue/10 hover:bg-accent-blue/20"
          >
            {RADAR_TITLE}
          </Link>
          <Link
            to="/info"
            className="text-xs text-white hover:text-white transition-colors font-medium"
          >
            INFO
          </Link>
        </div>

        <div className="flex items-center gap-2 md:gap-4">
          <div className="hidden lg:flex gap-1">
            {LAYER_BUTTONS.map((btn) => (
              <button
                key={btn.key}
                onClick={() => toggleLayer(btn.key)}
                className={`px-2 py-1 text-xs font-mono rounded border ${
                  layers[btn.key] ? 'bg-accent-blue text-bg-base' : 'border-border-glow text-text-secondary'
                }`}
              >
                {btn.label}
              </button>
            ))}
          </div>

          <div className="lg:hidden relative">
            <button
              onClick={() => setShowLayers(!showLayers)}
              className={`px-2 py-1 text-xs font-mono rounded border ${
                showLayers ? 'bg-accent-blue text-bg-base border-accent-blue' : 'border-border-glow text-text-secondary'
              }`}
            >
              CAPAS {Object.values(layers).filter(Boolean).length}
            </button>
            {showLayers && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setShowLayers(false)} />
                <div className="absolute right-0 top-full mt-1 bg-bg-panel border border-border-glow rounded shadow-lg p-2 z-50 flex flex-col gap-1">
                  {LAYER_BUTTONS.map((btn) => (
                    <button
                      key={btn.key}
                      onClick={() => { toggleLayer(btn.key); setShowLayers(false) }}
                      className={`px-3 py-1.5 text-xs font-mono rounded border text-left ${
                        layers[btn.key] ? 'bg-accent-blue text-bg-base border-accent-blue' : 'border-border-glow text-text-secondary'
                      }`}
                    >
                      {btn.label}
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>

          {isFetching && (
            <div className="flex items-center gap-1 text-xs text-text-secondary">
              <div className="animate-spin h-3 w-3 border border-accent-blue border-t-transparent rounded-full" />
              <span className="font-mono hidden sm:inline">
                UPDATED → {dataUpdatedAt ? 'hace ' + Math.floor((Date.now() - dataUpdatedAt) / 1000) + 's' : ''}
              </span>
            </div>
          )}

          <button
            onClick={() => setShowRefresh(!showRefresh)}
            className="flex items-center gap-1 md:gap-2 px-2 md:px-4 py-1.5 md:py-2 bg-accent-blue/10 text-accent-blue border border-accent-blue/20 rounded-lg hover:bg-accent-blue hover:text-white transition-all duration-300 shadow-sm active:scale-95"
            title="Sincroniza datos"
          >
            <RefreshCw size={16} className={showRefresh ? "animate-spin" : ""} />
            <span className="font-medium text-xs md:text-sm hidden sm:inline">Sincronizar</span>
          </button>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden relative">
        {showRefresh && (
          <>
            <div className="fixed inset-0 bg-black/40 z-30 md:hidden" onClick={() => setShowRefresh(false)} />
            <div className="absolute left-0 top-0 bottom-0 z-40 md:relative refresh-overlay
              w-full max-w-80 md:w-80 md:shrink-0 md:border-r md:border-border-glow">
              <div className="flex md:hidden justify-end p-2">
                <button onClick={() => setShowRefresh(false)} className="text-text-secondary hover:text-text-primary">
                  <X size={20} />
                </button>
              </div>
              <RefreshPanel />
            </div>
          </>
        )}

        <div className="hidden md:block w-[25%] min-w-[200px] lg:min-w-[260px] border-r border-border-glow">
          <IncidentList
            incidents={data?.incidents || []}
            total={data?.total || 0}
            page={data?.page || 1}
            isLoading={isLoading}
          />
        </div>

        {showSidebar && (
          <>
            <div className="fixed inset-0 bg-black/40 z-30 md:hidden" onClick={() => setShowSidebar(false)} />
            <div className="absolute left-0 top-0 bottom-0 z-40 w-[85vw] max-w-[320px] bg-bg-panel sidebar-drawer open md:hidden">
              <div className="flex justify-between items-center p-3 border-b border-border-glow">
                <span className="font-mono text-sm text-accent-blue font-bold">INCIDENTES</span>
                <button onClick={() => setShowSidebar(false)} className="text-text-secondary hover:text-text-primary">
                  <X size={20} />
                </button>
              </div>
              <IncidentList
                incidents={data?.incidents || []}
                total={data?.total || 0}
                page={data?.page || 1}
                isLoading={isLoading}
              />
            </div>
          </>
        )}

        <div className="flex-1 relative">
          <IncidentMap
            incidents={data?.incidents || []}
          />
          {!showSidebar && !selectedIncident && (
            <div className="md:hidden absolute bottom-4 left-4 z-20">
              <button
                onClick={() => setShowSidebar(true)}
                className="bg-bg-panel border border-border-glow rounded-lg px-3 py-2 text-xs font-mono text-text-primary hover:bg-bg-glass transition-colors shadow-lg"
              >
                <div className="flex items-center gap-2">
                  <List size={16} />
                  <span>{data?.total || 0} incidentes</span>
                </div>
              </button>
            </div>
          )}
        </div>

        {selectedIncident && (
          <>
            <div className="fixed inset-0 bg-black/40 z-30 lg:hidden" onClick={() => setSelectedIncident(null)} />
            <div className="fixed right-0 top-0 bottom-0 z-40 w-[90vw] max-w-[400px] lg:relative lg:max-w-none lg:w-[350px] detail-overlay">
              <IncidentDetail incident={selectedIncident} />
            </div>
          </>
        )}
      </div>

      <div className="flex items-center justify-between px-3 md:px-4 py-1 bg-bg-panel border-t border-border-glow text-xs font-mono text-text-secondary">
        <div className="flex items-center gap-3 md:gap-4">
          <div className="flex items-center gap-2">
            <AlertTriangle size={12} className="text-accent-amber" />
            <span className="hidden sm:inline">Sin novedades</span>
          </div>
          <div className="relative">
            <button
              onClick={() => setShowSources(!showSources)}
              className="flex items-center gap-1 hover:text-text-primary transition-colors"
            >
              <Database size={12} />
              <span className="hidden sm:inline">{ACTIVE_SOURCES.length} fuentes</span>
              <span className="sm:hidden">{ACTIVE_SOURCES.length}F</span>
              <ChevronDown size={10} className={`transition-transform ${showSources ? 'rotate-180' : ''}`} />
            </button>
            {showSources && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setShowSources(false)} />
                <div className="absolute bottom-full left-0 mb-1 w-56 sm:w-64 bg-bg-panel border border-border-glow rounded shadow-lg p-2 z-50">
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
              </>
            )}
          </div>
        </div>
        <div>
          {data?.total || 0} incidentes
        </div>
      </div>
    </div>
  )
}