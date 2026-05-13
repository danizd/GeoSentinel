import type { Incident, IncidentListResponse, IncidentFilters } from '../types/incident'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

function buildQueryString(filters: IncidentFilters): string {
  const params = new URLSearchParams()
  if (filters.category) params.set('category', filters.category)
  if (filters.status) params.set('status', filters.status)
  if (filters.min_severity) params.set('min_severity', filters.min_severity.toString())
  if (filters.min_confidence) params.set('min_confidence', filters.min_confidence.toString())
  if (filters.sources) params.set('sources', filters.sources)
  if (filters.aoi_id) params.set('aoi_id', filters.aoi_id)
  if (filters.page) params.set('page', filters.page.toString())
  if (filters.limit) params.set('limit', filters.limit.toString())
  return params.toString()
}

export async function fetchIncidents(filters: IncidentFilters): Promise<IncidentListResponse> {
  const query = buildQueryString(filters)
  const response = await fetch(`${API_BASE_URL}/v1/incidents?${query}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch incidents: ${response.statusText}`)
  }
  return response.json()
}

export async function fetchIncident(id: string): Promise<Incident> {
  const response = await fetch(`${API_BASE_URL}/v1/incidents/${id}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch incident: ${response.statusText}`)
  }
  return response.json()
}