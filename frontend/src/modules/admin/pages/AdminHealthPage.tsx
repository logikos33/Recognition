import { RefreshCw } from 'lucide-react'
import { useEffect, useState } from 'react'
import { adminService } from '../services/adminService'
import { PlatformHealthCard } from '../components/PlatformHealthCard'
import * as s from '../components/admin.css'
import type { PlatformHealth } from '../types/admin'

export function AdminHealthPage() {
  const [health, setHealth] = useState<PlatformHealth | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  const load = () => {
    setLoading(true)
    adminService.getPlatformHealth()
      .then((r) => { setHealth(r); setLastUpdated(new Date()); setError(null) })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
    const id = setInterval(load, 30_000)
    return () => clearInterval(id)
  }, [])

  return (
    <div className={s.pageRoot}>
      <div className={s.pageHeader}>
        <div>
          <div className={s.pageTitle}>Saúde da Plataforma</div>
          <div className={s.pageSubtitle}>
            Atualizado a cada 30s
            {lastUpdated && ` · Última verificação: ${lastUpdated.toLocaleTimeString('pt-BR')}`}
          </div>
        </div>
        <button className={s.btnGhost} onClick={load} disabled={loading}>
          <RefreshCw size={14} /> Atualizar
        </button>
      </div>

      {error && <div className={s.alertBanner.danger}>{error}</div>}

      {loading && !health ? (
        <div className={s.muted}>Carregando...</div>
      ) : health ? (
        <PlatformHealthCard health={health} />
      ) : null}
    </div>
  )
}
