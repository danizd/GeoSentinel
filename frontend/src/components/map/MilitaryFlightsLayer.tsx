import { useMemo } from 'react'
import { ScatterplotLayer, PathLayer } from '@deck.gl/layers'
import type { Layer } from '@deck.gl/core'
import type { MilitaryFlight, MilitaryFlightCluster } from '../../api/military'

interface MilitaryFlightsLayerProps {
  flights: MilitaryFlight[]
  clusters: MilitaryFlightCluster[]
  visible: boolean
}

const OPERATOR_COLORS: Record<string, number[]> = {
  US: [0, 120, 255],
  RU: [255, 0, 0],
  CN: [255, 180, 0],
  IR: [0, 150, 0],
  IL: [100, 100, 100],
  UK: [0, 100, 150],
  FR: [0, 85, 180],
  DE: [200, 180, 0],
}

function getOperatorColor(country?: string | null): number[] {
  if (!country) return [255, 255, 255]
  return OPERATOR_COLORS[country.toUpperCase()] || [255, 255, 255]
}

export function useMilitaryFlightsLayer({
  flights,
  clusters,
  visible,
}: MilitaryFlightsLayerProps): Layer[] {
  const layers = useMemo(() => {
    if (!visible) return []
    if (flights.length === 0) return []

    const scatterLayer = new ScatterplotLayer({
      id: 'military-flights-layer',
      data: flights,
      getPosition: (d: MilitaryFlight) => [d.location.longitude, d.location.latitude],
      getRadius: 8000,
      getFillColor: (d: MilitaryFlight) => {
        const baseColor = getOperatorColor(d.operatorCountry)
        if (d.isInteresting) {
          return [baseColor[0], baseColor[1], baseColor[2], 255]
        }
        return [baseColor[0], baseColor[1], baseColor[2], 200]
      },
      getLineColor: [255, 255, 255, 180],
      lineWidthMinPixels: 1,
      stroked: true,
      pickable: true,
      radiusMinPixels: 4,
      radiusMaxPixels: 20,
      updateTriggers: {
        getFillColor: [flights],
      },
    })

    const trailsWithData = flights.filter(f => f.trail && f.trail.length > 1)
    const pathLayer = new PathLayer({
      id: 'military-trails-layer',
      data: trailsWithData as any,
      getPath: (d: any) => d.trail || [],
      getColor: (d: any) => {
        const baseColor = getOperatorColor(d.operatorCountry)
        return [baseColor[0], baseColor[1], baseColor[2], 120]
      },
      getWidth: 3,
      widthMinPixels: 2,
      widthMaxPixels: 5,
      jointRounded: true,
      capRounded: true,
      updateTriggers: {
        getPath: [flights],
      },
    })

    const clusterLayer = new ScatterplotLayer({
      id: 'military-clusters-layer',
      data: clusters.filter(c => c.count >= 3),
      getPosition: (d: MilitaryFlightCluster) => [d.center.longitude, d.center.latitude],
      getRadius: (d: MilitaryFlightCluster) => Math.min(d.count * 5000, 50000),
      getFillColor: [255, 100, 0, 60],
      getLineColor: [255, 100, 0, 200],
      lineWidthMinPixels: 2,
      stroked: true,
      pickable: false,
    })

    return [pathLayer, scatterLayer, clusterLayer]
  }, [flights, clusters, visible])

  return layers
}