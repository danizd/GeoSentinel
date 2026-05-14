import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { RefreshPanel } from '../../src/components/panels/RefreshPanel'
import * as admin from '../../src/api/admin'
import * as authStore from '../../src/stores/authStore'

vi.mock('../../src/api/admin', () => ({
  runJob: vi.fn(),
  fetchJobStatus: vi.fn(),
}))

vi.mock('../../src/stores/authStore', () => ({
  useAuthStore: vi.fn(),
}))

const mockRunJob = vi.mocked(admin.runJob)
const mockFetchJobStatus = vi.mocked(admin.fetchJobStatus)
const mockUseAuthStore = vi.mocked(authStore.useAuthStore)

describe('RefreshPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('Auth visibility', () => {
    it('should not render when user lacks admin:run scope', () => {
      mockUseAuthStore.mockReturnValue({
        token: 'token',
        scopes: ['incidents:read'],
        setAuth: vi.fn(),
        clearAuth: vi.fn(),
        hasScope: (scope: string) => scope === 'admin:run',
      })

      const { container } = render(<RefreshPanel />)
      expect(container).toBeEmptyDOMElement()
    })

    it('should render when user has admin:run scope', () => {
      mockUseAuthStore.mockReturnValue({
        token: 'token',
        scopes: ['admin:run'],
        setAuth: vi.fn(),
        clearAuth: vi.fn(),
        hasScope: (scope: string) => scope === 'admin:run',
      })

      const { getByText } = render(<RefreshPanel />)
      expect(getByText('DATA SYNC')).toBeTruthy()
      expect(getByText('USGS')).toBeTruthy()
      expect(getByText('FIRMS')).toBeTruthy()
      expect(getByText('GDELT')).toBeTruthy()
      expect(getByText('ACLED')).toBeTruthy()
      expect(getByText('Clustering')).toBeTruthy()
      expect(getByText('Lifecycle')).toBeTruthy()
    })
  })

  describe('Single job trigger', () => {
    beforeEach(() => {
      mockUseAuthStore.mockReturnValue({
        token: 'token',
        scopes: ['admin:run'],
        setAuth: vi.fn(),
        clearAuth: vi.fn(),
        hasScope: () => true,
      })
    })

    it('should show running state after POST returns 202', async () => {
      const jobId = 'job-123'
      mockRunJob.mockResolvedValue({
        job: 'usgs',
        status: 'running',
        started_at: '2026-05-14T10:00:00Z',
        job_id: jobId,
      })
      mockFetchJobStatus.mockResolvedValue({
        job_id: jobId,
        job: 'usgs',
        status: 'completed',
        started_at: '2026-05-14T10:00:00Z',
        finished_at: '2026-05-14T10:00:30Z',
        duration_sec: 30,
        result: {
          events_fetched: 120,
          events_inserted: 118,
          events_quarantine: 2,
          incidents_created: 8,
          incidents_updated: 3,
        },
        error: null,
      })

      const { getByText } = render(<RefreshPanel />)
      const usgsButton = getByText('RUN').closest('button')

      fireEvent.click(usgsButton!)

      await waitFor(() => {
        expect(getByText('RUNNING...')).toBeTruthy()
      })
    })

    it('should show success state after polling detects completed', async () => {
      const jobId = 'job-456'
      mockRunJob.mockResolvedValue({
        job: 'usgs',
        status: 'running',
        started_at: '2026-05-14T10:00:00Z',
        job_id: jobId,
      })

      let callCount = 0
      mockFetchJobStatus.mockImplementation(() => {
        callCount++
        if (callCount === 1) {
          return Promise.resolve({
            job_id: jobId,
            job: 'usgs',
            status: 'running',
            started_at: '2026-05-14T10:00:00Z',
          })
        }
        return Promise.resolve({
          job_id: jobId,
          job: 'usgs',
          status: 'completed',
          started_at: '2026-05-14T10:00:00Z',
          finished_at: '2026-05-14T10:00:30Z',
          duration_sec: 30,
          result: {
            events_fetched: 120,
            events_inserted: 118,
            events_quarantine: 2,
            incidents_created: 8,
            incidents_updated: 3,
          },
          error: null,
        })
      })

      const { getByText } = render(<RefreshPanel />)
      const usgsButton = getByText('RUN').closest('button')

      fireEvent.click(usgsButton!)

      await waitFor(() => expect(getByText('DONE')).toBeTruthy(), { timeout: 5000 })
    })

    it('should show error state when job fails', async () => {
      const jobId = 'job-789'
      mockRunJob.mockResolvedValue({
        job: 'usgs',
        status: 'running',
        started_at: '2026-05-14T10:00:00Z',
        job_id: jobId,
      })
      mockFetchJobStatus.mockResolvedValue({
        job_id: jobId,
        job: 'usgs',
        status: 'failed',
        started_at: '2026-05-14T10:00:00Z',
        finished_at: '2026-05-14T10:00:30Z',
        duration_sec: 30,
        result: null,
        error: 'Connection timeout after 30s',
      })

      const { getByText } = render(<RefreshPanel />)
      const usgsButton = getByText('RUN').closest('button')

      fireEvent.click(usgsButton!)

      await waitFor(() => {
        expect(getByText('FAILED')).toBeTruthy()
        expect(getByText('Connection timeout after 30s')).toBeTruthy()
      }, { timeout: 5000 })
    })

    it('should adopt existing job_id on 409 conflict and poll it', async () => {
      const existingJobId = 'existing-job-id'
      const err: any = new Error('job already running')
      err.status = 409
      err.job_id = existingJobId

      mockRunJob.mockRejectedValue(err)

      mockFetchJobStatus.mockResolvedValue({
        job_id: existingJobId,
        job: 'usgs',
        status: 'completed',
        started_at: '2026-05-14T10:00:00Z',
        finished_at: '2026-05-14T10:00:30Z',
        duration_sec: 30,
        result: {
          events_fetched: 50,
          events_inserted: 48,
          events_quarantine: 2,
          incidents_created: 4,
          incidents_updated: 1,
        },
        error: null,
      })

      const { getByText } = render(<RefreshPanel />)
      const usgsButton = getByText('RUN').closest('button')

      fireEvent.click(usgsButton!)

      await waitFor(() => {
        expect(mockFetchJobStatus).toHaveBeenCalledWith(existingJobId)
        expect(getByText('DONE')).toBeTruthy()
      }, { timeout: 5000 })
    })
  })

  describe('RUN ALL button', () => {
    beforeEach(() => {
      mockUseAuthStore.mockReturnValue({
        token: 'token',
        scopes: ['admin:run'],
        setAuth: vi.fn(),
        clearAuth: vi.fn(),
        hasScope: () => true,
      })
    })

    it('should disable all individual buttons while RUN ALL is in progress', async () => {
      const allJobId = 'all-job-id'
      mockRunJob.mockResolvedValue({
        job: 'all',
        status: 'running',
        started_at: '2026-05-14T10:00:00Z',
        job_id: allJobId,
      })

      let pollCount = 0
      mockFetchJobStatus.mockImplementation(() => {
        pollCount++
        return Promise.resolve({
          job_id: allJobId,
          job: 'all',
          status: pollCount < 3 ? 'running' : 'completed',
          started_at: '2026-05-14T10:00:00Z',
          finished_at: '2026-05-14T10:02:00Z',
          duration_sec: 120,
          result: {
            events_fetched: 500,
            events_inserted: 480,
            events_quarantine: 20,
            incidents_created: 42,
            incidents_updated: 10,
            details: {},
          },
          error: null,
        })
      })

      const { getByText } = render(<RefreshPanel />)
      const runAllButton = getByText('RUN ALL').closest('button')

      fireEvent.click(runAllButton!)

      const usgsButton = getByText('RUNNING...').closest('button')
      expect(usgsButton).toBeTruthy()
    })
  })
})