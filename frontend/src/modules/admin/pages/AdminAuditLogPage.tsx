import { Download } from 'lucide-react'
import { useEffect, useState } from 'react'
import { adminService } from '../services/adminService'
import { AuditLogTable } from '../components/AuditLogTable'
import * as s from '../components/admin.css'
import type { AuditEntry } from '../types/admin'

export function AdminAuditLogPage() {
  const [items, setItems] = useState<AuditEntry[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [action, setAction] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [page, setPage] = useState(1)
  const [exporting, setExporting] = useState(false)

  const load = () => {
    setLoading(true)
    adminService.getAuditLog({
      action: action || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      page,
    })
      .then((r) => { setItems(r.items); setTotal(r.total) })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [action, dateFrom, dateTo, page])

  const handleExport = async () => {
    setExporting(true)
    try {
      const blob = await adminService.exportAuditLog({ action: action || undefined })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = `audit-log-${new Date().toISOString().slice(0, 10)}.csv`
      a.click(); URL.revokeObjectURL(url)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Erro ao exportar')
    } finally { setExporting(false) }
  }

  return (
    <div className={s.pageRoot}>
      <div className={s.pageHeader}>
        <div>
          <div className={s.pageTitle}>Audit Log</div>
          <div className={s.pageSubtitle}>{total} registros</div>
        </div>
        <button className={s.btnGhost} onClick={handleExport} disabled={exporting}>
          <Download size={14} /> {exporting ? 'Exportando...' : 'Exportar CSV'}
        </button>
      </div>

      {error && <div className={s.alertBanner.danger}>{error}</div>}

      <div className={s.flex} style={{ marginBottom: 16, flexWrap: 'wrap' }}>
        <input className={s.input} placeholder="Filtrar por ação..." value={action} onChange={(e) => { setAction(e.target.value); setPage(1) }} />
        <input className={s.input} type="date" value={dateFrom} onChange={(e) => { setDateFrom(e.target.value); setPage(1) }} />
        <input className={s.input} type="date" value={dateTo} onChange={(e) => { setDateTo(e.target.value); setPage(1) }} />
      </div>

      <div className={s.card}>
        {loading ? <div className={s.muted}>Carregando...</div> : <AuditLogTable entries={items} />}
      </div>

      {total > 50 && (
        <div className={s.flex} style={{ marginTop: 12, justifyContent: 'center' }}>
          <button className={s.btnGhost} disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Anterior</button>
          <span className={s.muted}>Pág {page}</span>
          <button className={s.btnGhost} disabled={page * 50 >= total} onClick={() => setPage((p) => p + 1)}>Próxima</button>
        </div>
      )}
    </div>
  )
}
