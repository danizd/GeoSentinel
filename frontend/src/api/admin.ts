const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export interface JobStatus {
  job_id: string
  job: string
  status: 'running' | 'completed' | 'failed'
  started_at: string
  finished_at?: string
  duration_sec?: number
  result?: {
    events_fetched: number
    events_inserted: number
    events_quarantine: number
    incidents_created: number
    incidents_updated: number
  }
  error?: string
}

function authHeaders(): HeadersInit {
  const token = localStorage.getItem('gs_token')
  return {
    'Authorization': token ? `Bearer ${token}` : '',
    'Content-Type': 'application/json',
  }
}

export async function runJob(source: string): Promise<{ job_id: string; job: string; status: string; started_at: string }> {
  const response = await fetch(`${API_BASE_URL}/v1/admin/run/${source}`, {
    method: 'POST',
    headers: authHeaders(),
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    const err: Error & { job_id?: string; status?: number } = new Error(body.detail?.error || `HTTP ${response.status}`)
    err.job_id = body.detail?.job_id
    err.status = response.status
    throw err
  }
  return response.json()
}

export async function fetchJobStatus(jobId: string): Promise<JobStatus> {
  const response = await fetch(`${API_BASE_URL}/v1/admin/run/status/${jobId}`, {
    headers: authHeaders(),
  })
  if (!response.ok) {
    throw new Error(`Failed to fetch job status: ${response.statusText}`)
  }
  return response.json()
}