import { useState, useCallback, useEffect, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { RefreshCw, Check, X, Loader2 } from 'lucide-react'
import { runJob, fetchJobStatus } from '../../api/admin'
import type { JobStatus } from '../../api/admin'
import { useAuthStore } from '../../stores/authStore'

type ButtonState = 'idle' | 'running' | 'success' | 'error'

interface SourceConfig {
  key: string
  label: string
  description: string
}

const SOURCE_JOBS: SourceConfig[] = [
  { key: 'usgs', label: 'USGS', description: 'Terremotos >= 4.0' },
  { key: 'firms', label: 'FIRMS', description: 'Incendios activos' },
  { key: 'gdelt', label: 'GDELT', description: 'Conflictos media' },
  { key: 'acled', label: 'ACLED', description: 'Conflictos batch' },
]

const PROCESSING_JOBS: SourceConfig[] = [
  { key: 'clustering', label: 'Clustering', description: 'Agrupa eventos' },
  { key: 'lifecycle', label: 'Lifecycle', description: 'Actualiza estados' },
]

interface JobResult {
  events_fetched: number
  events_inserted: number
  events_quarantine: number
  incidents_created: number
  incidents_updated: number
}

interface JobEntry {
  state: ButtonState
  jobId: string | null
  result: JobResult | null
  error: string | null
}

function parseResult(status: JobStatus): JobResult | null {
  return (status.result as JobResult) || null
}

function JobButton({
  config,
  entry,
  onTrigger,
  disabled,
}: {
  config: SourceConfig
  entry: JobEntry
  onTrigger: (key: string) => void
  disabled: boolean
}) {
  let icon = <RefreshCw className="w-3 h-3" />
  let label = 'RUN'
  let btnClass =
    'border border-border-glow text-text-primary hover:bg-accent-blue hover:text-bg-base disabled:opacity-40'

  if (entry.state === 'running') {
    icon = <Loader2 className="w-3 h-3 animate-spin" />
    label = 'RUNNING...'
    btnClass = 'border border-accent-blue text-accent-blue cursor-not-allowed'
  } else if (entry.state === 'success') {
    icon = <Check className="w-3 h-3 text-accent-green" />
    label = 'DONE'
    btnClass = 'border border-accent-green text-accent-green'
  } else if (entry.state === 'error') {
    icon = <X className="w-3 h-3 text-accent-red" />
    label = 'FAILED'
    btnClass = 'border border-accent-red text-accent-red'
  }

  return (
    <div className="flex flex-col gap-0.5">
      <button
        onClick={() => onTrigger(config.key)}
        disabled={disabled || entry.state === 'running'}
        className={`flex items-center gap-1.5 px-3 py-1 rounded text-xs font-mono font-bold transition-colors ${btnClass}`}
      >
        {icon}
        <span>{label}</span>
      </button>

      {entry.state === 'success' && entry.result && (
        <div className="text-[10px] font-mono text-text-secondary pl-1 leading-tight">
          <span>
            Ev: {entry.result.events_fetched} fet · {entry.result.events_inserted} ins · {entry.result.events_quarantine} q
          </span>
          <br />
          <span>
            Inc: {entry.result.incidents_created} cr · {entry.result.incidents_updated} up
          </span>
        </div>
      )}

      {entry.state === 'error' && entry.error && (
        <div className="text-[10px] font-mono text-accent-red pl-1 leading-tight max-w-[140px] truncate" title={entry.error}>
          {entry.error}
        </div>
      )}
    </div>
  )
}

export function RefreshPanel() {
  const hasAdminScope = useAuthStore((s) => s.hasScope('admin:run'))
  const queryClient = useQueryClient()

  const [entries, setEntries] = useState<Record<string, JobEntry>>(
    Object.fromEntries(
      [...SOURCE_JOBS, ...PROCESSING_JOBS].map((j) => [j.key, { state: 'idle', jobId: null, result: null, error: null }])
    )
  )

  const [runAllState, setRunAllState] = useState<ButtonState>('idle')
  const [runAllProgress, setRunAllProgress] = useState<string>('')
  const [runAllResult, setRunAllResult] = useState<JobResult | null>(null)
  const pollingTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({})

  const clearPollTimer = useCallback((key: string) => {
    if (pollingTimers.current[key]) {
      clearTimeout(pollingTimers.current[key])
      delete pollingTimers.current[key]
    }
  }, [])

  const schedulePoll = useCallback(
    (key: string, jobId: string) => {
      clearPollTimer(key)
      pollingTimers.current[key] = setTimeout(async () => {
        try {
          const status = await fetchJobStatus(jobId)
          if (status.status === 'running') {
            pollingTimers.current[key] = setTimeout(() => schedulePoll(key, jobId), 2000)
          } else {
            delete pollingTimers.current[key]
            const newState: ButtonState = status.status === 'completed' ? 'success' : 'error'

            setEntries((prev) => ({
              ...prev,
              [key]: {
                state: newState,
                jobId: prev[key].jobId,
                result: parseResult(status),
                error: status.error || null,
              },
            }))

            if (status.status === 'completed') {
              queryClient.invalidateQueries({ queryKey: ['incidents'] })
            }

            const resetDelay = newState === 'success' ? 3000 : 5000
            pollingTimers.current[key + '_reset'] = setTimeout(() => {
              setEntries((prev) => {
                if (prev[key].state !== newState) return prev
                return { ...prev, [key]: { ...prev[key], state: 'idle' } }
              })
            }, resetDelay)
          }
        } catch {
          delete pollingTimers.current[key]
          setEntries((prev) => ({
            ...prev,
            [key]: { state: 'error', jobId: null, result: null, error: 'Poll failed' },
          }))
        }
      }, 2000)
    },
    [clearPollTimer, queryClient]
  )

  const startJob = useCallback(
    (key: string, jobId: string) => {
      setEntries((prev) => ({ ...prev, [key]: { state: 'running', jobId, result: null, error: null } }))
      schedulePoll(key, jobId)
    },
    [schedulePoll]
  )

  const triggerSingle = useCallback(
    (key: string) => {
      runJob(key)
        .then((res) => {
          startJob(key, res.job_id)
        })
        .catch((err: any) => {
          if (err.status === 409 && err.job_id) {
            startJob(key, err.job_id)
          } else {
            const msg = err.message || 'Unknown error'
            setEntries((prev) => ({
              ...prev,
              [key]: { state: 'error', jobId: null, result: null, error: msg },
            }))
            pollingTimers.current[key + '_reset'] = setTimeout(() => {
              setEntries((prev) => ({ ...prev, [key]: { state: 'idle', jobId: null, result: null, error: null } }))
            }, 5000)
          }
        })
    },
    [startJob]
  )

  const pollRunAll = useCallback(
    (jobId: string) => {
      pollingTimers.current['runall'] = setTimeout(async () => {
        try {
          const status = await fetchJobStatus(jobId)
          if (status.status === 'running') {
            const details = (status.result as any)?.details
            if (details) {
              const doneSources = Object.entries(details)
                .filter(([, v]: any) => v && typeof v === 'object' && v.events_inserted !== undefined)
                .map(([k]) => k.toUpperCase())
              if (doneSources.length > 0) {
                setRunAllProgress(`[1/3] Ingesta ${doneSources.join(' ')} ✓`)
              }
            }
            pollingTimers.current['runall'] = setTimeout(() => pollRunAll(jobId), 2000)
          } else {
            if (status.status === 'completed') {
              setRunAllResult(status.result as JobResult)
              setRunAllState('success')
              queryClient.invalidateQueries({ queryKey: ['incidents'] })
            } else {
              setRunAllState('error')
            }
            pollingTimers.current['runall_reset'] = setTimeout(() => {
              setRunAllState('idle')
              setRunAllProgress('')
            }, 5000)
          }
        } catch {
          setRunAllState('error')
          pollingTimers.current['runall_reset'] = setTimeout(() => {
            setRunAllState('idle')
            setRunAllProgress('')
          }, 5000)
        }
      }, 2000)
    },
    [queryClient]
  )

  const triggerRunAll = useCallback(async () => {
    setRunAllState('running')
    setRunAllProgress('[1/3] Ingestando USGS FIRMS GDELT ACLED...')
    setRunAllResult(null)

    try {
      const res = await runJob('all')
      setRunAllProgress('[2/3] Clustering + Lifecycle...')
      pollRunAll(res.job_id)
    } catch (err: any) {
      if (err.status === 409 && err.job_id) {
        setRunAllProgress('[2/3] Clustering + Lifecycle...')
        pollRunAll(err.job_id)
      } else {
        setRunAllState('error')
        pollingTimers.current['runall_reset'] = setTimeout(() => {
          setRunAllState('idle')
          setRunAllProgress('')
        }, 5000)
      }
    }
  }, [pollRunAll])

useEffect(() => {
    return () => {
      Object.values(pollingTimers.current).forEach(clearTimeout)
    }
  }, [clearPollTimer])

  if (!hasAdminScope) return null

  return (
    <div className="bg-bg-glass backdrop-blur-xl border border-border-glow rounded-xl p-4 w-80 shrink-0">
      <div className="flex items-center gap-2 mb-4">
        <RefreshCw className="text-accent-blue" size={16} />
        <h2 className="font-mono text-sm text-accent-blue font-bold tracking-widest">DATA SYNC</h2>
      </div>

      <div className="text-[10px] font-mono text-text-secondary mb-2 tracking-widest uppercase">Sources</div>
      <div className="space-y-2 mb-4">
        {SOURCE_JOBS.map((src) => (
          <div key={src.key} className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-accent-blue shrink-0" />
              <div>
                <div className="text-text-primary font-mono text-xs">{src.label}</div>
                <div className="text-text-secondary text-[10px]">{src.description}</div>
              </div>
            </div>
            <JobButton config={src} entry={entries[src.key]} onTrigger={triggerSingle} disabled={runAllState === 'running'} />
          </div>
        ))}
      </div>

      <div className="text-[10px] font-mono text-text-secondary mb-2 tracking-widest uppercase">Processing</div>
      <div className="space-y-2 mb-4">
        {PROCESSING_JOBS.map((proc) => (
          <div key={proc.key} className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-accent-amber shrink-0" />
              <div>
                <div className="text-text-primary font-mono text-xs">{proc.label}</div>
                <div className="text-text-secondary text-[10px]">{proc.description}</div>
              </div>
            </div>
            <JobButton config={proc} entry={entries[proc.key]} onTrigger={triggerSingle} disabled={runAllState === 'running'} />
          </div>
        ))}
      </div>

      {runAllProgress && (
        <div className="text-xs font-mono text-accent-blue mb-3 animate-pulse">{runAllProgress}</div>
      )}

      {runAllResult && runAllState === 'success' && (
        <div className="text-xs font-mono text-text-secondary mb-3">
          <div className="text-accent-green">Completado</div>
          <div>
            {runAllResult.events_fetched} eventos · {runAllResult.incidents_created} inc · {runAllResult.incidents_updated} up
          </div>
        </div>
      )}

      <div className="border-t border-border-glow pt-3 mt-2">
        <button
          onClick={triggerRunAll}
          disabled={runAllState === 'running'}
          className={`w-full py-2 rounded font-mono text-sm font-bold tracking-widest transition-colors ${
            runAllState === 'running'
              ? 'bg-accent-blue/20 text-accent-blue cursor-not-allowed'
              : runAllState === 'success'
              ? 'bg-accent-green/20 text-accent-green'
              : runAllState === 'error'
              ? 'bg-accent-red/20 text-accent-red'
              : 'bg-accent-blue text-bg-base hover:bg-accent-blue/80'
          }`}
        >
          {runAllState === 'running' ? (
            <span className="flex items-center justify-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin" /> RUNNING ALL...
            </span>
          ) : runAllState === 'success' ? (
            <span className="flex items-center justify-center gap-2">
              <Check className="w-4 h-4" /> DONE
            </span>
          ) : runAllState === 'error' ? (
            <span className="flex items-center justify-center gap-2">
              <X className="w-4 h-4" /> FAILED
            </span>
          ) : (
            'RUN ALL'
          )}
        </button>
      </div>
    </div>
  )
}