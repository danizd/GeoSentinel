import { useMemo, useState, useCallback, useRef, useEffect } from 'react'
import Map, { NavigationControl, Source, Layer, type MapRef } from 'react-map-gl'
import { motion, AnimatePresence } from 'framer-motion'
import { useMapStore } from '../../stores/mapStore'
import { useQuery } from '@tanstack/react-query'
import { fetchMilitaryFlights, type MilitaryFlight } from '../../api/military'
import { fetchAois } from '../../api/aois'
import { fetchAISVessels, type AISVessel } from '../../api/ais'
import type { Incident } from '../../types/incident'
import { getCategoryHex, getHeadline, getIncidentColor } from '../../utils/colors'
import { US_MILITARY_BASES, type UsMilitaryBase } from '../../data/us_bases'

function getMilitaryColor(country?: string | null): string {
  const mapping: Record<string, string> = {
    'United States': '#3B82F6',
    'United Kingdom': '#06B6D4',
    'Russia': '#EF4444',
    'China': '#EAB308',
    'France': '#A855F7',
    'Luxembourg': '#84CC16',
  }
  if (!country) return '#1E3A8A'
  return mapping[country] || '#FBBF24'
}

function getVesselColor(flag?: string | null): string {
  const mapping: Record<string, string> = {
    'US': '#3B82F6',
    'GB': '#06B6D4',
    'RU': '#EF4444',
    'CN': '#EAB308',
    'FR': '#A855F7',
    'IR': '#F97316',
    'TR': '#EAB308',
    'AU': '#22C55E',
    'IT': '#A855F7',
  }
  if (!flag) return '#94A3B8'
  return mapping[flag.toUpperCase()] || '#94A3B8'
}

function VesselsIconManager({ vessels }: { vessels: AISVessel[] }) {
  const geojson = useMemo(() => {
    if (!vessels.length) return null
    return {
      type: 'FeatureCollection' as const,
      features: vessels.map(v => ({
        type: 'Feature' as const,
        properties: {
          id: v.id,
          name: v.name,
          heading: v.heading,
          color: getVesselColor(v.flag),
          isDark: v.isDark,
        },
        geometry: {
          type: 'Point' as const,
          coordinates: [v.location.longitude, v.location.latitude],
        },
      })),
    }
  }, [vessels])

  if (!geojson) return null

  return (
    <Source id="ais-vessels-src" type="geojson" data={geojson}>
      <Layer
        id="ais-vessels-halo-dark"
        type="circle"
        source="ais-vessels-src"
        paint={{
          'circle-radius': ['case', ['get', 'isDark'], 18, 14],
          'circle-color': '#000000',
          'circle-opacity': ['case', ['get', 'isDark'], 0.4, 0.35],
          'circle-stroke-width': 0,
        }}
      />
      <Layer
        id="ais-vessels-halo-light"
        type="circle"
        source="ais-vessels-src"
        paint={{
          'circle-radius': ['case', ['get', 'isDark'], 14, 10],
          'circle-color': '#FFFFFF',
          'circle-opacity': ['case', ['get', 'isDark'], 0.4, 0.3],
          'circle-stroke-width': 0,
        }}
      />
      <Layer
        id="ais-vessels-symbol"
        type="symbol"
        source="ais-vessels-src"
        layout={{
          'icon-image': 'ship-icon',
          'icon-size': 0.35,
          'icon-allow-overlap': true,
          'icon-ignore-placement': true,
          'icon-rotate': ['get', 'heading'],
          'icon-rotation-alignment': 'map',
        }}
        paint={{
          'icon-color': ['get', 'color'],
          'icon-opacity': ['case', ['get', 'isDark'], 0.7, 0.95],
        }}
      />
    </Source>
  )
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
          'line-width': 3,
          'line-opacity': 0.8,
        }}
      />
    </Source>
  )
}

const basesGeojson: GeoJSON.FeatureCollection = {
  type: 'FeatureCollection',
  features: US_MILITARY_BASES.map((b, i) => ({
    type: 'Feature' as const,
    properties: {
      id: i,
      name: b.name,
      country: b.country,
      notes: b.notes,
    },
    geometry: {
      type: 'Point' as const,
      coordinates: [b.lon, b.lat],
    },
  })),
}

function BaseTooltip({ base, x, y }: { base: UsMilitaryBase | null; x: number; y: number }) {
  if (!base) return null
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ duration: 0.15 }}
      className="panel-glass absolute z-50 p-3 font-mono text-xs pointer-events-none shadow-xl"
      style={{ left: x + 16, top: y - 10, maxWidth: 340 }}
    >
      <div className="flex items-center gap-2 mb-1">
        <span className="w-3 h-3 rounded-full bg-accent-amber shrink-0" />
        <span className="text-text-primary font-bold text-sm">{base.name}</span>
      </div>
      <div className="text-text-secondary">{base.country}</div>
      {base.notes && (
        <div className="text-text-secondary mt-1 leading-tight">{base.notes}</div>
      )}
    </motion.div>
  )
}

function IncidentTooltip({ hover, incidents }: { hover: { x: number; y: number; incidentId: string } | null; incidents: Incident[] }) {
  if (!hover) return null
  const incident = incidents.find(i => i.incident_id === hover.incidentId)
  if (!incident) return null

  const color = getIncidentColor(incident.event_type, incident.category)
  const headline = getHeadline(incident)

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ duration: 0.15 }}
      className="panel-glass absolute z-50 p-3 font-mono text-xs pointer-events-none shadow-xl"
      style={{
        left: hover.x + 16,
        top: hover.y - 10,
        maxWidth: 280,
      }}
    >
      <div className="flex items-center gap-2 mb-1.5">
        <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: `rgb(${color.join(',')})` }} />
        <span className="text-text-primary font-bold text-xs leading-tight">{headline}</span>
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-text-secondary">
        <div>Categoría: {incident.category}</div>
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-text-secondary">
        <div>Severidad: {incident.severity_max.toFixed(1)}</div>
      </div>         
      <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-text-secondary">        
        <div>Confianza: {incident.confidence.toFixed(1)}</div>
      </div>
      <div className="text-text-secondary mt-0.5">
        Fuente: {incident.sources.join(' · ')}
      </div>
    </motion.div>
  )
}

function PulseOverlay({ incidents, mapRef }: { incidents: Incident[]; mapRef: React.RefObject<MapRef | null> }) {
  const [pixelPositions, setPixelPositions] = useState<Array<{ id: string; x: number; y: number; color: string }>>([])

  const activeIncidents = useMemo(
    () => incidents.filter(i => i.canonical_point && (i.status === 'open' || i.status === 'updated')),
    [incidents]
  )

  useEffect(() => {
    const map = mapRef.current?.getMap()
    if (!map || !activeIncidents.length) {
      setPixelPositions([])
      return
    }

    const update = () => {
      const positions: Array<{ id: string; x: number; y: number; color: string }> = []
      for (const inc of activeIncidents) {
        if (!inc.canonical_point) continue
        const px = map.project([inc.canonical_point.lon, inc.canonical_point.lat])
        if (px.x < 0 || px.y < 0 || px.x > window.innerWidth || px.y > window.innerHeight) continue
        positions.push({
          id: inc.incident_id,
          x: px.x,
          y: px.y,
          color: getCategoryHex(inc.category),
        })
      }
      setPixelPositions(positions.slice(0, 30))
    }

    update()
    map.on('move', update)
    map.on('moveend', update)
    return () => {
      map.off('move', update)
      map.off('moveend', update)
    }
  }, [activeIncidents, mapRef])

  return (
    <AnimatePresence>
      {pixelPositions.map((p) => (
        <motion.div
          key={p.id}
          initial={{ opacity: 0, scale: 0 }}
          animate={{ opacity: 0, scale: 2.5 }}
          transition={{ duration: 2.2, repeat: Infinity, ease: 'easeOut', repeatDelay: 0 }}
          className="absolute pointer-events-none rounded-full"
          style={{
            left: p.x - 12,
            top: p.y - 12,
            width: 24,
            height: 24,
            border: `2px solid ${p.color}`,
            backgroundColor: 'transparent',
          }}
        />
      ))}
    </AnimatePresence>
  )
}

export function IncidentMap({ incidents }: IncidentMapProps) {
  const mapRef = useRef<MapRef | null>(null)
  const { viewport, layers, selectedIncident } = useMapStore()
  const [is3D, setIs3D] = useState(true)
  const [selectedFlight, setSelectedFlight] = useState<MilitaryFlight | null>(null)
  const [selectedVessel, setSelectedVessel] = useState<AISVessel | null>(null)
  const [hover, setHover] = useState<{ x: number; y: number; incidentId: string } | null>(null)
  const [hoveredBase, setHoveredBase] = useState<{ base: UsMilitaryBase; x: number; y: number } | null>(null)
  const prevSelectedRef = useRef<string | null>(null)

  const { data: militaryData, isLoading: militaryLoading } = useQuery({
    queryKey: ['military-flights'],
    queryFn: fetchMilitaryFlights,
    refetchInterval: POLLING_INTERVAL_MS,
    enabled: layers.tracks,
  })

  const { data: aoiData } = useQuery({
    queryKey: ['aois'],
    queryFn: fetchAois,
    enabled: layers.aoi,
  })

  const { data: aisData, isLoading: aisLoading } = useQuery({
    queryKey: ['ais-vessels'],
    queryFn: fetchAISVessels,
    refetchInterval: POLLING_INTERVAL_MS,
    enabled: layers.vessels,
  })

  const vessels = useMemo(() => {
    if (!aisData?.vessels) return []
    return aisData.vessels.filter(v =>
      v.location &&
      typeof v.location.longitude === 'number' &&
      typeof v.location.latitude === 'number' &&
      !isNaN(v.location.longitude) &&
      !isNaN(v.location.latitude)
    )
  }, [aisData])

  const NATO_COUNTRIES = new Set([
    'Albania', 'Belgium', 'Bulgaria', 'Canada', 'Croatia', 'Czech Republic',
    'Denmark', 'Estonia', 'Finland', 'France', 'Germany', 'Greece', 'Hungary',
    'Iceland', 'Italy', 'Latvia', 'Lithuania', 'Luxembourg', 'Montenegro',
    'Netherlands', 'North Macedonia', 'Norway', 'Poland', 'Portugal', 'Romania',
    'Slovakia', 'Slovenia', 'Spain', 'Sweden', 'Turkey', 'United Kingdom', 'United States',
  ])

  const aoiGeojson = useMemo(() => {
    if (!aoiData?.aois?.length) return null
    return {
      type: 'FeatureCollection' as const,
      features: aoiData.aois.map(a => ({
        type: 'Feature' as const,
        properties: { id: a.aoi_id, name: a.name, isNato: NATO_COUNTRIES.has(a.name) },
        geometry: a.geometry,
      })),
    }
  }, [aoiData])

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
          title: incident.raw_payload?.title || incident.event_type,
          confidence: incident.confidence,
          sources: incident.sources.join(','),
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

  useEffect(() => {
    if (!selectedIncident?.canonical_point) return
    if (prevSelectedRef.current === selectedIncident.incident_id) return
    prevSelectedRef.current = selectedIncident.incident_id

    const map = mapRef.current?.getMap()
    if (map) {
      map.flyTo({
        center: [selectedIncident.canonical_point.lon, selectedIncident.canonical_point.lat],
        zoom: 6,
        duration: 1800,
        essential: true,
      })
    }
  }, [selectedIncident])

  useEffect(() => {
    if (!selectedIncident) {
      prevSelectedRef.current = null
    }
  }, [selectedIncident])

  const handleMapLoad = useCallback((e: any) => {
    const map = e.target

    const icons = [
      { url: '/icons/airplane.svg', id: 'airplane-icon' },
      { url: '/icons/ship.svg', id: 'ship-icon' },
      { url: '/icons/shield.svg', id: 'shield-icon' },
    ]

    icons.forEach(({ url, id }) => {
      if (map.hasImage(id)) return
      map.loadImage(url, (err: any, img: any) => {
        if (err) {
          console.error(`Error loading icon ${id}:`, err)
          return
        }
        if (!map.hasImage(id)) {
          map.addImage(id, img, { sdf: true })
        }
      })
    })
  }, [])

  const handleMouseMove = useCallback((e: any) => {
    const map = mapRef.current?.getMap()
    if (!map) return

    const features = map.queryRenderedFeatures(e.point, {
      layers: ['incidents-point'],
    })

    if (features.length > 0) {
      const f = features[0]
      setHover({ x: e.point.x, y: e.point.y, incidentId: f.properties?.id })
      setHoveredBase(null)
    } else {
      setHover(null)
    }

    if (!features.length && layers.bases) {
      const baseFeatures = map.queryRenderedFeatures(e.point, {
        layers: ['bases-circle'],
      })
      if (baseFeatures.length > 0) {
        const bf = baseFeatures[0]
        const idx = bf.properties?.id
        if (typeof idx === 'number' && US_MILITARY_BASES[idx]) {
          setHoveredBase({ base: US_MILITARY_BASES[idx], x: e.point.x, y: e.point.y })
        }
      } else {
        setHoveredBase(null)
      }
    }
  }, [layers.bases])

  const handleMouseLeave = useCallback(() => {
    setHover(null)
    setHoveredBase(null)
  }, [])

  const handleMapClick = (e: any) => {
    const features = e.features || []
    for (const feature of features) {
      const layerId = feature.layer?.id
      const props = feature.properties

      if (layerId === 'military-flights-symbol' || feature.source === 'military-flights-src') {
        if (props?.id) {
          const flight = flights.find(f => f.id === props.id)
          if (flight) { setSelectedFlight(flight); return }
        }
      }

      if (layerId === 'ais-vessels-symbol' || feature.source === 'ais-vessels-src') {
        if (props?.id) {
          const vessel = vessels.find(v => v.id === props.id)
          if (vessel) { setSelectedVessel(vessel); return }
        }
      }
    }
    setSelectedFlight(null)
    setSelectedVessel(null)
  }

  const INCIDENT_CATEGORY_COLORS = [
    'match', ['get', 'category'],
    'conflict', '#ef4444',
    'wildfire', '#f97316',
    'earthquake', '#a855f7',
    'disaster_natural', '#06b6d4',
    'mobility', '#38bdf8',
    'humanitarian', '#fbbf24',
    'thermal_anomaly', '#ea580c',
    'crime', '#a855f7',
    'protest', '#ec4899',
    'other', '#64748b',
    '#38bdf8',
  ]

  return (
    <div className="relative w-full h-full">
      <Map
        ref={mapRef}
        initialViewState={displayViewport}
        onLoad={handleMapLoad}
        onClick={handleMapClick}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        interactiveLayerIds={['military-flights-symbol', 'ais-vessels-symbol', 'incidents-point']}
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
                'circle-color': INCIDENT_CATEGORY_COLORS as any,
                'circle-opacity': 0.85,
                'circle-stroke-width': 1,
                'circle-stroke-color': '#ffffff',
              }}
            />
            {selectedIncident && selectedIncident.canonical_point && (
              <Layer
                id="incident-selected"
                type="circle"
                filter={['==', ['get', 'id'], selectedIncident.incident_id]}
                paint={{
                  'circle-radius': 24,
                  'circle-color': '#000000',
                  'circle-opacity': 0,
                  'circle-stroke-width': 3,
                  'circle-stroke-color': '#38bdf8',
                  'circle-stroke-opacity': 1,
                }}
              />
            )}
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

        {layers.aoi && aoiGeojson && (
          <Source id="aoi-zones" type="geojson" data={aoiGeojson}>
            <Layer
              id="aoi-fill"
              type="fill"
              source="aoi-zones"
              paint={{
                'fill-color': '#ff1100',
                'fill-opacity': 0.32,
              }}
            />
            <Layer
              id="aoi-outline"
              type="line"
              source="aoi-zones"
              paint={{
                'line-color': ['case', ['get', 'isNato'], '#000000', '#3B82F6'],
                'line-width': ['case', ['get', 'isNato'], 1.5, 2],
                'line-opacity': ['case', ['get', 'isNato'], 0.85, 0.7],
                'line-dasharray': [3, 2],
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

        {layers.vessels && vessels.length > 0 && (
          <VesselsIconManager vessels={vessels} />
        )}

        {layers.bases && (
          <Source id="bases-src" type="geojson" data={basesGeojson}>
            <Layer
              id="bases-circle"
              type="circle"
              source="bases-src"
              paint={{
                'circle-radius': 6,
                'circle-color': '#FBBF24',
                'circle-opacity': 0.85,
                'circle-stroke-width': 1.5,
                'circle-stroke-color': '#000000',
              }}
            />
          </Source>
        )}

        <NavigationControl position="top-right" />
      </Map>

      <IncidentTooltip hover={hover} incidents={incidents} />

      {hoveredBase && <BaseTooltip base={hoveredBase.base} x={hoveredBase.x} y={hoveredBase.y} />}

      <PulseOverlay incidents={incidents} mapRef={mapRef} />

      {selectedFlight && (
        <div className="absolute bottom-4 right-4 left-4 sm:left-auto sm:w-56 bg-bg-panel border border-accent-blue rounded-lg p-3 shadow-xl font-mono text-xs z-50 max-h-[70vh] overflow-y-auto">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full" style={{ backgroundColor: getMilitaryColor(selectedFlight.operatorCountry) }} />
              <span className="text-accent-blue font-bold text-sm">{selectedFlight.callsign}</span>
            </div>
            <button onClick={() => setSelectedFlight(null)} className="text-text-secondary hover:text-white text-lg leading-none">&times;</button>
          </div>
          <div className="space-y-1 text-text-secondary">
            <div className="flex justify-between"><span className="text-text-primary">Hex</span> <span className="font-mono">{selectedFlight.hexCode}</span></div>
            <div className="flex justify-between"><span className="text-text-primary">Country</span> <span>{selectedFlight.operatorCountry || '—'}</span></div>
            {selectedFlight.aircraftType && (
              <div className="flex justify-between"><span className="text-text-primary">Tipo</span> <span>{selectedFlight.aircraftType}</span></div>
            )}
            {selectedFlight.aircraftModel && (
              <div className="flex justify-between"><span className="text-text-primary">Modelo</span> <span>{selectedFlight.aircraftModel}</span></div>
            )}
            {selectedFlight.registration && (
              <div className="flex justify-between"><span className="text-text-primary">Matrícula</span> <span className="font-mono">{selectedFlight.registration}</span></div>
            )}
            {selectedFlight.operator && (
              <div className="flex justify-between"><span className="text-text-primary">Operador</span> <span>{selectedFlight.operator}</span></div>
            )}
            <div className="border-t border-border-glow pt-1 mt-1">
              <div className="flex justify-between"><span className="text-text-primary">Alt</span> <span>{selectedFlight.altitude.toLocaleString()} ft</span></div>
              <div className="flex justify-between"><span className="text-text-primary">Vel</span> <span>{selectedFlight.speed} kts</span></div>
              <div className="flex justify-between"><span className="text-text-primary">Rumbo</span> <span>{selectedFlight.heading}&deg;</span></div>
            </div>
            {(selectedFlight.origin || selectedFlight.destination || true) && (
              <div className="border-t border-border-glow pt-1 mt-1">
                <div className="flex justify-between"><span className="text-text-primary">Origen</span> <span>{selectedFlight.origin || '—'}</span></div>
                <div className="flex justify-between"><span className="text-text-primary">Destino</span> <span>{selectedFlight.destination || '—'}</span></div>
              </div>
            )}
            <div className="border-t border-border-glow pt-1 mt-1">
              <div className="flex justify-between"><span className="text-text-primary">Fuente</span> <span>{selectedFlight.source || '—'}</span></div>
            </div>
            {selectedFlight.trail && selectedFlight.trail.length > 0 && (
              <div className="border-t border-border-glow pt-1 mt-1">
                <div className="flex justify-between"><span className="text-text-primary">Ruta</span> <span>{selectedFlight.trail.length} puntos</span></div>
              </div>
            )}
            <div className="border-t border-border-glow pt-1 mt-1">
              <div className="flex justify-between"><span className="text-text-primary">Lat</span> <span className="font-mono">{selectedFlight.location.latitude.toFixed(4)}</span></div>
              <div className="flex justify-between"><span className="text-text-primary">Lon</span> <span className="font-mono">{selectedFlight.location.longitude.toFixed(4)}</span></div>
            </div>
            {selectedFlight.lastSeenAt && (
              <div className="border-t border-border-glow pt-1 mt-1">
                <div className="flex justify-between"><span className="text-text-primary">Visto</span> <span>{new Date(selectedFlight.lastSeenAt).toLocaleTimeString()}</span></div>
              </div>
            )}
          </div>
        </div>
      )}

      {selectedVessel && (
        <div className="absolute bottom-4 left-4 right-4 sm:right-auto sm:w-56 bg-bg-panel border border-accent-amber rounded-lg p-3 shadow-xl font-mono text-xs z-50 max-h-[70vh] overflow-y-auto">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full" style={{ backgroundColor: getVesselColor(selectedVessel.flag) }} />
              <span className="text-accent-amber font-bold text-sm">{selectedVessel.name || selectedVessel.callsign || selectedVessel.mmsi}</span>
            </div>
            <button onClick={() => setSelectedVessel(null)} className="text-text-secondary hover:text-white text-lg leading-none">&times;</button>
          </div>
          <div className="space-y-1 text-text-secondary">
            <div className="flex justify-between"><span className="text-text-primary">MMSI</span> <span className="font-mono">{selectedVessel.mmsi}</span></div>
            {selectedVessel.callsign && (
              <div className="flex justify-between"><span className="text-text-primary">Call</span> <span>{selectedVessel.callsign}</span></div>
            )}
            <div className="flex justify-between"><span className="text-text-primary">Bandera</span> <span>{selectedVessel.flag || '—'}</span></div>
            {selectedVessel.vesselType && (
              <div className="flex justify-between"><span className="text-text-primary">Tipo</span> <span>{selectedVessel.vesselType}</span></div>
            )}
            <div className="border-t border-border-glow pt-1 mt-1">
              <div className="flex justify-between"><span className="text-text-primary">Vel</span> <span>{selectedVessel.sog} kn</span></div>
              <div className="flex justify-between"><span className="text-text-primary">Rumbo</span> <span>{selectedVessel.cog}&deg;</span></div>
              <div className="flex justify-between"><span className="text-text-primary">Status</span> <span>{selectedVessel.navigationalStatus}</span></div>
            </div>
            {selectedVessel.destination && (
              <div className="border-t border-border-glow pt-1 mt-1">
                <div className="flex justify-between"><span className="text-text-primary">Destino</span> <span>{selectedVessel.destination}</span></div>
              </div>
            )}
            {selectedVessel.isDark && (
              <div className="border-t border-border-glow pt-1 mt-1">
                <div className="flex justify-between"><span className="text-text-primary">Estado</span> <span className="text-accent-amber">Dark ship</span></div>
              </div>
            )}
            <div className="border-t border-border-glow pt-1 mt-1">
              <div className="flex justify-between"><span className="text-text-primary">Lat</span> <span className="font-mono">{selectedVessel.location.latitude.toFixed(4)}</span></div>
              <div className="flex justify-between"><span className="text-text-primary">Lon</span> <span className="font-mono">{selectedVessel.location.longitude.toFixed(4)}</span></div>
            </div>
          </div>
        </div>
      )}

      {selectedIncident && (
        <div className="absolute bottom-4 right-4 left-4 sm:left-auto sm:w-60 bg-bg-panel border border-accent-blue rounded-lg p-3 shadow-xl font-mono text-xs z-50 max-h-[70vh] overflow-y-auto md:hidden">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full" style={{ backgroundColor: `rgb(${getIncidentColor(selectedIncident.event_type, selectedIncident.category).join(',')})` }} />
              <span className="text-accent-blue font-bold text-sm">
                {getHeadline(selectedIncident)}
              </span>
            </div>
            <button onClick={() => useMapStore.getState().setSelectedIncident(null)} className="text-text-secondary hover:text-white text-lg leading-none">&times;</button>
          </div>
          <div className="space-y-1 text-text-secondary">
            <div className="flex justify-between"><span className="text-text-primary">ID</span> <span className="font-mono text-[10px]">{selectedIncident.incident_id.slice(0, 12)}</span></div>
            <div className="flex justify-between"><span className="text-text-primary">Status</span> <span className={`px-1 rounded text-[10px] ${selectedIncident.status === 'open' ? 'bg-accent-green' : selectedIncident.status === 'updated' ? 'bg-accent-blue' : 'bg-accent-amber'}`}>{selectedIncident.status}</span></div>
            <div className="flex justify-between"><span className="text-text-primary">Severidad</span> <span>{selectedIncident.severity_max.toFixed(1)}</span></div>
            <div className="flex justify-between"><span className="text-text-primary">Confianza</span> <span>{selectedIncident.confidence.toFixed(1)}</span></div>
            {selectedIncident.actors && selectedIncident.actors.length > 0 && (
              <div className="border-t border-border-glow pt-1 mt-1">
                <div className="text-text-primary text-[10px] mb-0.5">ACTORES</div>
                {selectedIncident.actors.map((actor, i) => (
                  <div key={i} className="text-[10px] leading-tight">
                    <span className="text-accent-amber">{actor.name || '?'}</span>
                    {actor.role && <span className="text-text-secondary"> ({actor.role})</span>}
                    {actor.country && <span className="text-text-secondary"> · {actor.country}</span>}
                  </div>
                ))}
              </div>
            )}
            {selectedIncident.raw_payload?.url && (
              <div className="border-t border-border-glow pt-1 mt-1">
                <div className="text-text-primary text-[10px] mb-0.5">FUENTE</div>
                <a
                  href={selectedIncident.raw_payload.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-accent-blue hover:underline text-[10px] leading-tight break-all"
                >
                  {selectedIncident.raw_payload.url.length > 45
                    ? selectedIncident.raw_payload.url.slice(0, 45) + '...'
                    : selectedIncident.raw_payload.url}
                </a>
              </div>
            )}
            <div className="border-t border-border-glow pt-1 mt-1">
              <div className="flex justify-between"><span className="text-text-primary">Fuentes</span> <span>{selectedIncident.sources.join(', ')}</span></div>
            </div>
            <div className="border-t border-border-glow pt-1 mt-1">
              <div className="flex justify-between"><span className="text-text-primary">Lat</span> <span className="font-mono">{selectedIncident.canonical_point?.lat.toFixed(4)}&deg;</span></div>
              <div className="flex justify-between"><span className="text-text-primary">Lon</span> <span className="font-mono">{selectedIncident.canonical_point?.lon.toFixed(4)}&deg;</span></div>
            </div>
            <div className="border-t border-border-glow pt-1 mt-1">
              <div className="flex justify-between"><span className="text-text-primary">Observaciones</span> <span>{selectedIncident.observation_count}</span></div>
            </div>
            {selectedIncident.fatalities_total > 0 && (
              <div className="border-t border-border-glow pt-1 mt-1">
                <div className="flex justify-between"><span className="text-text-primary">Fatalidades</span> <span className="text-accent-red">{selectedIncident.fatalities_total}</span></div>
              </div>
            )}
            <div className="border-t border-border-glow pt-1 mt-1">
              <div className="flex justify-between"><span className="text-text-primary">1&ordf; detecci&oacute;n</span> <span>{new Date(selectedIncident.first_seen).toLocaleDateString()}</span></div>
              <div className="flex justify-between"><span className="text-text-primary">&Uacute;ltima</span> <span>{new Date(selectedIncident.last_seen).toLocaleDateString()}</span></div>
            </div>
          </div>
        </div>
      )}

      <button
        onClick={() => setIs3D(!is3D)}
        className="absolute top-16 sm:top-18 right-2 bg-accent-blue text-white px-2 sm:px-3 py-2 text-xs sm:text-sm font-bold rounded shadow-lg hover:bg-accent-blue/80 transition-colors"
      >
        {is3D ? '2D' : '3D'}
      </button>

      {layers.tracks && militaryLoading && (
        <div className="absolute top-2 left-1/2 -translate-x-1/2 bg-accent-blue text-white text-sm font-mono px-4 py-2 rounded shadow-lg animate-pulse z-50">
          Cargando vuelos...
        </div>
      )}

      {layers.vessels && aisLoading && (
        <div className="absolute top-2 left-1/2 -translate-x-1/2 bg-accent-amber text-bg-base text-sm font-mono px-4 py-2 rounded shadow-lg animate-pulse z-50">
          Cargando buques...
        </div>
      )}

      {layers.vessels && aisData?.isStale && (
        <div className="absolute top-16 right-2 bg-yellow-600 text-white text-xs px-2 py-1 rounded z-50">
          Datos AIS simulados
        </div>
      )}

      {layers.tracks && militaryData?.isStale && (
        <div className="absolute top-10 right-2 bg-yellow-600 text-white text-xs px-2 py-1 rounded z-50">
          Stale data
        </div>
      )}

      <div className="absolute bottom-4 left-4 font-mono text-[10px] sm:text-xs text-text-secondary bg-bg-glass px-2 py-1 rounded">
        {displayViewport.latitude.toFixed(4)}&deg; {displayViewport.longitude.toFixed(4)}&deg; &middot; ZOOM {displayViewport.zoom.toFixed(1)}
      </div>
    </div>
  )
}
