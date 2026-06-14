import { useEffect, useRef, useState } from 'react'
import { adminService } from '../services/adminService'
import type { WorkerInfo, WorkerStatus } from '../types/admin'

interface UseWorkerMonitorOptions {
  intervalMs?: number
  onStatusChange?: (tenantSchema: string, prev: WorkerStatus, next: WorkerStatus) => void
}

export function useWorkerMonitor({ intervalMs = 10_000, onStatusChange }: UseWorkerMonitorOptions = {}) {
  const [workers, setWorkers] = useState<WorkerInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const prevStatuses = useRef<Record<string, WorkerStatus>>({})

  useEffect(() => {
    let mounted = true

    const fetch = () =>
      adminService
        .getWorkers()
        .then((list) => {
          if (!mounted) return
          if (onStatusChange) {
            for (const w of list) {
              const prev = prevStatuses.current[w.tenant_schema]
              if (prev && prev !== w.status) onStatusChange(w.tenant_schema, prev, w.status)
              prevStatuses.current[w.tenant_schema] = w.status
            }
          }
          setWorkers(list)
          setError(null)
        })
        .catch((e) => { if (mounted) setError(e?.message ?? 'Erro ao carregar workers') })
        .finally(() => { if (mounted) setLoading(false) })

    fetch()
    const id = setInterval(fetch, intervalMs)
    return () => { mounted = false; clearInterval(id) }
  }, [intervalMs, onStatusChange])

  return { workers, loading, error }
}
