const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export interface VesselLocation {
  latitude: number
  longitude: number
}

export interface AISVessel {
  id: string
  mmsi: string
  name?: string | null
  callsign?: string | null
  location: VesselLocation
  sog: number
  cog: number
  heading: number
  navigationalStatus: string
  vesselType?: string | null
  flag?: string | null
  destination?: string | null
  isDark: boolean
  lastAisUpdate: string
  source: string
}

export interface AISVesselCluster {
  center: VesselLocation
  count: number
  activityType: string
}

export interface AISVesselsResponse {
  vessels: AISVessel[]
  clusters: AISVesselCluster[]
  isStale: boolean
}

export async function fetchAISVessels(): Promise<AISVesselsResponse> {
  const response = await fetch(`${API_BASE_URL}/v1/ais-vessels`, {
    headers: { 'Content-Type': 'application/json' },
  })
  if (!response.ok) {
    throw new Error(`Failed to fetch AIS vessels: ${response.status}`)
  }
  return response.json()
}
