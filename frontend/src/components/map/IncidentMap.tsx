import { useMemo, useState, useCallback } from 'react'
import Map, { NavigationControl, Source, Layer } from 'react-map-gl'
import { useMapStore } from '../../stores/mapStore'
import { useQuery } from '@tanstack/react-query'
import { fetchMilitaryFlights, type MilitaryFlight } from '../../api/military'
import type { Incident } from '../../types/incident'

function getMilitaryColor(country?: string): string {
  const mapping: Record<string, string> = {
    'United States': '#3B82F6',
    'United Kingdom': '#06B6D4',
    'Russia': '#EF4444',
    'China': '#EAB308',
    'France': '#A855F7',
    'Luxembourg': '#84CC16',
  }
  if (!country) return '#FFFFFF'
  return mapping[country] || '#FBBF24'
}

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN || ''
const MAP_STYLE_3D = 'mapbox://styles/mapbox/satellite-streets-v12'
const MAP_STYLE_2D = 'mapbox://styles/mapbox/streets-v12'

const POLLING_INTERVAL_MS = 30000

const DEFAULT_VIEWPORT = {
  longitude: 20,
  latitude: 20,
  zoom: 2.5,
  pitch: 0,
  bearing: 0,
}

function isValidViewport(vp: Partial<typeof DEFAULT_VIEWPORT>): boolean {
  return (
    typeof vp.longitude === 'number' && !isNaN(vp.longitude) &&
    typeof vp.latitude === 'number' && !isNaN(vp.latitude) &&
    typeof vp.zoom === 'number' && !isNaN(vp.zoom)
  )
}

interface IncidentMapProps {
  incidents: Incident[]
}

function AircraftIconManager({ flights }: { flights: MilitaryFlight[] }) {
  const geojson = useMemo(() => {
    if (!flights.length) return null
    return {
      type: 'FeatureCollection' as const,
      features: flights.map(f => ({
        type: 'Feature' as const,
        properties: {
          id: f.id,
          callsign: f.callsign,
          heading: f.heading,
          color: getMilitaryColor(f.operatorCountry),
        },
        geometry: {
          type: 'Point' as const,
          coordinates: [f.location.longitude, f.location.latitude],
        },
      })),
    }
  }, [flights])

  if (!geojson) return null

  return (
    <Source id="military-flights-src" type="geojson" data={geojson}>
      <Layer
        id="military-flights-halo-dark"
        type="circle"
        source="military-flights-src"
        paint={{
          'circle-radius': 14,
          'circle-color': '#000000',
          'circle-opacity': 0.35,
          'circle-stroke-width': 0,
        }}
      />
      <Layer
        id="military-flights-halo-light"
        type="circle"
        source="military-flights-src"
        paint={{
          'circle-radius': 10,
          'circle-color': '#FFFFFF',
          'circle-opacity': 0.6,
          'circle-stroke-width': 0,
        }}
      />
      <Layer
        id="military-flights-symbol"
        type="symbol"
        source="military-flights-src"
        layout={{
          'icon-image': 'airplane-icon',
          'icon-size': 0.45,
          'icon-allow-overlap': true,
          'icon-ignore-placement': true,
          'icon-rotate': ['get', 'heading'],
          'icon-rotation-alignment': 'map',
        }}
        paint={{
          'icon-color': ['get', 'color'],
          'icon-opacity': 0.95,
        }}
      />
    </Source>
  )
}

function MilitaryTrailsLayer({ flights }: { flights: MilitaryFlight[] }) {
  const geojson = useMemo(() => {
    const features = flights
      .filter(f => f.trail && f.trail.length > 1)
      .map(f => ({
        type: 'Feature' as const,
        properties: {
          color: getMilitaryColor(f.operatorCountry),
        },
        geometry: {
          type: 'LineString' as const,
          coordinates: f.trail!,
        },
      }))
    if (!features.length) return null
    return { type: 'FeatureCollection' as const, features }
  }, [flights])

  if (!geojson) return null

  return (
    <Source id="military-trails-src" type="geojson" data={geojson}>
      <Layer
        id="military-trails-line"
        type="line"
        source="military-trails-src"
        paint={{
          'line-color': ['get', 'color'],
          'line-width': 2,
          'line-opacity': 0.5,
        }}
      />
    </Source>
  )
}

export function IncidentMap({ incidents }: IncidentMapProps) {
  const { viewport, layers } = useMapStore()
  const [is3D, setIs3D] = useState(true)
  const [selectedFlight, setSelectedFlight] = useState<MilitaryFlight | null>(null)

  const { data: militaryData, isLoading: militaryLoading } = useQuery({
    queryKey: ['military-flights'],
    queryFn: fetchMilitaryFlights,
    refetchInterval: POLLING_INTERVAL_MS,
    enabled: layers.tracks,
  })

  const flights = useMemo(() => {
    if (!militaryData?.flights) return []
    return militaryData.flights.filter(f =>
      f.location &&
      typeof f.location.longitude === 'number' &&
      typeof f.location.latitude === 'number' &&
      !isNaN(f.location.longitude) &&
      !isNaN(f.location.latitude)
    )
  }, [militaryData])

  const geojsonData = useMemo(() => ({
    type: 'FeatureCollection' as const,
    features: incidents
      .filter(i => i.canonical_point)
      .map((incident) => ({
        type: 'Feature' as const,
        properties: {
          id: incident.incident_id,
          category: incident.category,
          severity: incident.severity_max,
          status: incident.status,
        },
        geometry: {
          type: 'Point' as const,
          coordinates: [incident.canonical_point!.lon, incident.canonical_point!.lat],
        },
      })),
  }), [incidents])

  const displayViewport = useMemo(() => {
    const vp = isValidViewport(viewport) ? viewport : DEFAULT_VIEWPORT
    return {
      longitude: vp.longitude!,
      latitude: vp.latitude!,
      zoom: vp.zoom!,
      pitch: vp.pitch ?? 0,
      bearing: vp.bearing ?? 0,
    }
  }, [viewport])

  const handleMapLoad = useCallback((e: any) => {
    const map = e.target
    const size = 48
    const canvas = document.createElement('canvas')
    canvas.width = size
    canvas.height = size
    const ctx = canvas.getContext('2d')!
    ctx.font = 'bold 36px sans-serif'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillStyle = '#FFFFFF'
    ctx.fillText('\u2708', size / 2, size / 2)

    const img = new Image()
    img.onload = () => {
      if (!map.hasImage('airplane-icon')) {
        map.addImage('airplane-icon', img, { sdf: true })
      }
    }
    img.src = canvas.toDataURL()
  }, [])

  const handleFlightClick = (e: any) => {
    const features = e.features || []
    for (const feature of features) {
      if (feature.layer?.id === 'military-flights-symbol' || feature.source === 'military-flights-src') {
        const props = feature.properties
        if (props?.id) {
          const flight = flights.find(f => f.id === props.id)
          if (flight) {
            setSelectedFlight(flight)
            return
          }
        }
      }
    }
    setSelectedFlight(null)
  }

  return (
    <div className="relative w-full h-full">
      <Map
        initialViewState={displayViewport}
        onLoad={handleMapLoad}
        onClick={handleFlightClick}
        interactiveLayerIds={['military-flights-symbol']}
        style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%' } as any}
        mapStyle={is3D ? MAP_STYLE_3D : MAP_STYLE_2D}
        mapboxAccessToken={MAPBOX_TOKEN}
        reuseMaps
        projection={is3D ? { name: 'globe' } : { name: 'mercator' }}
      >
        {layers.scatter && (
          <Source id="incidents" type="geojson" data={geojsonData}>
            <Layer
              id="incidents-point"
              type="circle"
              paint={{
                'circle-radius': ['interpolate', ['linear'], ['get', 'severity'], 0, 4, 10, 20],
                'circle-color': [
                  'match', ['get', 'category'],
                  'conflict', '#ef4444',
                  'disaster_natural', '#fbbf24',
                  'wildfire', '#f97316',
                  '#38bdf8'
                ],
                'circle-opacity': 0.85,
                'circle-stroke-width': 1,
                'circle-stroke-color': '#ffffff',
              }}
            />
          </Source>
        )}

        {layers.heat && (
          <Source id="incidents-heat" type="geojson" data={geojsonData}>
            <Layer
              id="incidents-heat"
              type="heatmap"
              paint={{
                'heatmap-weight': ['interpolate', ['linear'], ['get', 'severity'], 0, 0, 10, 1],
                'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 0, 1, 15, 3],
                'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 0, 2, 15, 20],
                'heatmap-opacity': 0.6,
                'heatmap-color': [
                  'interpolate', ['linear'], ['heatmap-density'],
                  0, 'rgba(0,0,0,0)',
                  0.2, '#ffffb2',
                  0.4, '#fed976',
                  0.6, '#feb24c',
                  0.8, '#f03b20',
                  1, '#bd0026'
                ],
              }}
            />
          </Source>
        )}

        {layers.tracks && flights.length > 0 && (
          <>
            <AircraftIconManager flights={flights} />
            <MilitaryTrailsLayer flights={flights} />
          </>
        )}

        <NavigationControl position="top-right" />
      </Map>

      {selectedFlight && (
        <div className="absolute bottom-4 right-4 bg-bg-panel border border-accent-blue rounded-lg p-3 shadow-xl font-mono text-xs w-52 z-50">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full" style={{ backgroundColor: getMilitaryColor(selectedFlight.operatorCountry) }} />
              <span className="text-accent-blue font-bold text-sm">{selectedFlight.callsign}</span>
            </div>
            <button onClick={() => setSelectedFlight(null)} className="text-text-secondary hover:text-white text-lg leading-none">&times;</button>
          </div>
          <div className="space-y-1 text-text-secondary">
            <div className="flex justify-between"><span className="text-text-primary">Hex</span> <span>{selectedFlight.hexCode}</span></div>
            <div className="flex justify-between"><span className="text-text-primary">Alt</span> <span>{selectedFlight.altitude.toLocaleString()} ft</span></div>
            <div className="flex justify-between"><span className="text-text-primary">Spd</span> <span>{selectedFlight.speed} kts</span></div>
            <div className="flex justify-between"><span className="text-text-primary">Hdg</span> <span>{selectedFlight.heading}&deg;</span></div>
            {selectedFlight.operatorCountry && (
              <div className="flex justify-between"><span className="text-text-primary">Country</span> <span>{selectedFlight.operatorCountry}</span></div>
            )}
            {selectedFlight.aircraftType && (
              <div className="flex justify-between"><span className="text-text-primary">Type</span> <span>{selectedFlight.aircraftType}</span></div>
            )}
            {selectedFlight.operator && (
              <div className="flex justify-between"><span className="text-text-primary">Op</span> <span>{selectedFlight.operator}</span></div>
            )}
            <div className="flex justify-between pt-1 border-t border-border-glow">
              <span className="text-text-primary">Lat</span> <span>{selectedFlight.location.latitude.toFixed(4)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-primary">Lon</span> <span>{selectedFlight.location.longitude.toFixed(4)}</span>
            </div>
          </div>
        </div>
      )}

      <button
        onClick={() => setIs3D(!is3D)}
        className="absolute top-14 right-2 bg-accent-blue text-white px-3 py-2 text-sm font-bold rounded shadow-lg hover:bg-accent-blue/80 transition-colors"
      >
        {is3D ? '2D' : '3D'}
      </button>

      {layers.tracks && militaryLoading && (
        <div className="absolute top-2 left-1/2 -translate-x-1/2 bg-accent-blue text-white text-sm font-mono px-4 py-2 rounded shadow-lg animate-pulse z-50">
          Loading tracks...
        </div>
      )}

      {layers.tracks && militaryData?.isStale && (
        <div className="absolute top-14 right-2 bg-yellow-600 text-white text-xs px-2 py-1 rounded z-50">
          Stale data
        </div>
      )}

      <div className="absolute bottom-4 left-4 font-mono text-xs text-text-secondary bg-bg-glass px-2 py-1 rounded">
        {displayViewport.latitude.toFixed(4)}&deg; {displayViewport.longitude.toFixed(4)}&deg; &middot; ZOOM {displayViewport.zoom.toFixed(1)}
      </div>
    </div>
  )
}
