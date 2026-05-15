const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

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
  aircraftType?: string | null
  aircraftModel?: string | null
  operator?: string | null
  operatorCountry?: string | null
  registration?: string | null
  origin?: string | null
  destination?: string | null
  isInteresting: boolean
  trail?: number[][] | null
  source?: string | null
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
  const response = await fetch(`${API_BASE_URL}/v1/military-flights`, {
    headers: {
      'Content-Type': 'application/json',
    },
  })

  if (!response.ok) {
    throw new Error(`Failed to fetch military flights: ${response.status}`)
  }

  return response.json()
}