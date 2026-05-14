const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/v1'

export interface AoiGeometry {
  type: string
  coordinates: number[][][]
}

export interface Aoi {
  aoi_id: string
  name: string
  description: string
  geometry: AoiGeometry
  categories: string[]
  min_severity: number
  is_active: boolean
  created_by: string
  created_at: string
}

export interface AoiListResponse {
  total: number
  aois: Aoi[]
}

export async function fetchAois(): Promise<AoiListResponse> {
  const response = await fetch(`${API_BASE}/aoi?limit=100`, {
    headers: { 'Content-Type': 'application/json' },
  })
  if (!response.ok) {
    throw new Error(`Failed to fetch AOIs: ${response.status}`)
  }
  return response.json()
}
