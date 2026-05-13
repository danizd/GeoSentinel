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