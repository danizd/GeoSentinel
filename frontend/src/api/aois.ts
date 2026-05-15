const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

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
  const response = await fetch(`${API_BASE_URL}/v1/aoi?limit=100`, {
    headers: { 'Content-Type': 'application/json' },
  })
  if (!response.ok) {
    throw new Error(`Failed to fetch AOIs: ${response.status}`)
  }
  return response.json()
}
