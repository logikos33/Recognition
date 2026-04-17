import { useEffect, useState } from 'react'
import { adminService } from '../services/adminService'
import type { AdminDashboard } from '../types/admin'

export function useAdminDashboard(intervalMs = 30_000) {
  const [data, setData] = useState<AdminDashboard | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let mounted = true

    const fetch = () =>
      adminService
        .getDashboard()
        .then((r) => { if (mounted) { setData(r); setError(null) } })
        .catch((e) => { if (mounted) setError(e?.message ?? 'Erro ao carregar dashboard') })
        .finally(() => { if (mounted) setLoading(false) })

    fetch()
    const id = setInterval(fetch, intervalMs)
    return () => { mounted = false; clearInterval(id) }
  }, [intervalMs])

  return { data, loading, error }
}
