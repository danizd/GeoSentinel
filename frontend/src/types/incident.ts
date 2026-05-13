export interface IncidentPoint {
  lon: number
  lat: number
}

export interface Incident {
  incident_id: string
  status: 'open' | 'updated' | 'stale' | 'closed' | 'false_positive'
  category: string
  event_type: string
  canonical_point: IncidentPoint | null
  first_seen: string
  last_seen: string
  severity_max: number
  severity_latest: number
  confidence: number
  fatalities_total: number
  sources: string[]
  observation_count: number
}

export interface IncidentListResponse {
  total: number
  page: number
  incidents: Incident[]
}

export interface IncidentFilters {
  category?: string
  status?: string
  min_severity?: number
  min_confidence?: number
  sources?: string
  aoi_id?: string
  page?: number
  limit?: number
}

export const CATEGORY_COLORS: Record<string, [number, number, number]> = {
  conflict: [239, 68, 68],
  disaster_natural: [251, 191, 36],
  wildfire: [249, 115, 22],
  crime: [168, 85, 247],
  protest: [236, 72, 153],
  default: [56, 189, 248],
}

export const STATUS_COLORS: Record<Incident['status'], string> = {
  open: 'bg-accent-green',
  updated: 'bg-accent-blue',
  stale: 'bg-accent-amber',
  closed: 'bg-text-secondary',
  false_positive: 'bg-accent-red',
}