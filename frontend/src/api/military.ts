const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/v1'

export interface Location {
  latitude: number
  longitude: number
}

export interface MilitaryFlight {
  id: string
  callsign: string
  hexCode: string
  location: Location
  altitude: number
  heading: number
  speed: number
  lastSeenAt: string
  aircraftType?: string
  operator?: string
  operatorCountry?: string
  isInteresting: boolean
  trail?: number[][]
}

export interface MilitaryFlightCluster {
  center: Location
  count: number
  avgAltitude: number
  avgSpeed: number
}

export interface MilitaryFlightsResponse {
  flights: MilitaryFlight[]
  clusters: MilitaryFlightCluster[]
  isStale: boolean
}

export async function fetchMilitaryFlights(): Promise<MilitaryFlightsResponse> {
  const response = await fetch(`${API_BASE}/military-flights`, {
    headers: {
      'Content-Type': 'application/json',
    },
  })

  if (!response.ok) {
    throw new Error(`Failed to fetch military flights: ${response.status}`)
  }

  return response.json()
}