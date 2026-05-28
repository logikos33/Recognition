import { useEffect, useState } from 'react'
import { adminService } from '../services/adminService'
import { TrainingApprovalCard } from '../components/TrainingApprovalCard'
import * as s from '../components/admin.css'
import type { TrainingApproval } from '../types/admin'

export function AdminTrainingApprovalsPage() {
  const [items, setItems] = useState<TrainingApproval[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState('pending')
  const [page, setPage] = useState(1)

  const load = () => {
    setLoading(true)
    adminService.getTrainingApprovals({ status: statusFilter || undefined, page })
      .then((r) => { setItems(r.items); setTotal(r.total) })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [statusFilter, page])

  const handleApprove = async (id: string) => {
    const notes = prompt('Notas de aprovação (opcional):') ?? undefined
    try {
      await adminService.approveTraining(id, notes)
      load()
    } catch (e: unknown) { alert(e instanceof Error ? e.message : 'Erro') }
  }

  const handleReject = async (id: string) => {
    const reason = prompt('Motivo da rejeição (obrigatório):')
    if (!reason) return
    try {
      await adminService.rejectTraining(id, reason)
      load()
    } catch (e: unknown) { alert(e instanceof Error ? e.message : 'Erro') }
  }

  return (
    <div className={s.pageRoot}>
      <div className={s.pageHeader}>
        <div>
          <div className={s.pageTitle}>Aprovações de Treinamento</div>
          <div className={s.pageSubtitle}>{total} registros</div>
        </div>
      </div>

      {error && <div className={s.alertBanner.danger}>{error}</div>}

      <div className={s.flex} style={{ marginBottom: 16 }}>
        {['pending', 'approved', 'rejected', 'auto_approved', ''].map((st) => (
          <button
            key={st}
            className={statusFilter === st ? s.btnPrimary : s.btnGhost}
            onClick={() => { setStatusFilter(st); setPage(1) }}
          >
            {st || 'Todos'}
          </button>
        ))}
      </div>

      {loading ? (
        <div className={s.muted}>Carregando...</div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 16 }}>
          {items.map((a) => (
            <TrainingApprovalCard
              key={a.id}
              approval={a}
              onApprove={handleApprove}
              onReject={handleReject}
            />
          ))}
          {items.length === 0 && (
            <div className={s.card}><span className={s.muted}>Nenhuma aprovação encontrada</span></div>
          )}
        </div>
      )}

      {total > 20 && (
        <div className={s.flex} style={{ marginTop: 16, justifyContent: 'center' }}>
          <button className={s.btnGhost} disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Anterior</button>
          <span className={s.muted}>Pág {page}</span>
          <button className={s.btnGhost} disabled={page * 20 >= total} onClick={() => setPage((p) => p + 1)}>Próxima</button>
        </div>
      )}
    </div>
  )
}
