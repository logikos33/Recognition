import { useEffect, useState } from 'react'
import { adminService } from '../services/adminService'
import { TicketRow } from '../components/TicketRow'
import * as s from '../components/admin.css'
import type { SupportTicket, TicketPriority, TicketStatus } from '../types/admin'

export function AdminTicketsPage() {
  const [items, setItems] = useState<SupportTicket[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState('')
  const [priority, setPriority] = useState('')
  const [page, setPage] = useState(1)

  const load = () => {
    setLoading(true)
    adminService.getTickets({ status: status || undefined, priority: priority || undefined, page })
      .then((r) => { setItems(r.items); setTotal(r.total) })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [status, priority, page])

  const statuses: TicketStatus[] = ['open', 'in_progress', 'waiting_client', 'resolved', 'closed']
  const priorities: TicketPriority[] = ['low', 'normal', 'high', 'critical']

  return (
    <div className={s.pageRoot}>
      <div className={s.pageHeader}>
        <div>
          <div className={s.pageTitle}>Tickets de Suporte</div>
          <div className={s.pageSubtitle}>{total} tickets</div>
        </div>
      </div>

      {error && <div className={s.alertBanner.danger}>{error}</div>}

      <div className={s.flex} style={{ marginBottom: 16 }}>
        <select className={s.select} value={status} onChange={(e) => { setStatus(e.target.value); setPage(1) }}>
          <option value="">Todos os status</option>
          {statuses.map((st) => <option key={st} value={st}>{st.replace('_', ' ')}</option>)}
        </select>
        <select className={s.select} value={priority} onChange={(e) => { setPriority(e.target.value); setPage(1) }}>
          <option value="">Todas as prioridades</option>
          {priorities.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
      </div>

      <div className={s.card}>
        {loading ? <div className={s.muted}>Carregando...</div> : (
          <table className={s.table}>
            <thead>
              <tr>
                <th className={s.th}>#</th>
                <th className={s.th}>Assunto</th>
                <th className={s.th}>Categoria</th>
                <th className={s.th}>Prioridade</th>
                <th className={s.th}>Status</th>
                <th className={s.th}>SLA</th>
                <th className={s.th}>Criado</th>
              </tr>
            </thead>
            <tbody>
              {items.map((t) => <TicketRow key={t.id} ticket={t} />)}
              {items.length === 0 && (
                <tr><td colSpan={7} className={s.td} style={{ textAlign: 'center' }}><span className={s.muted}>Nenhum ticket encontrado</span></td></tr>
              )}
            </tbody>
          </table>
        )}
      </div>

      {total > 20 && (
        <div className={s.flex} style={{ marginTop: 12, justifyContent: 'center' }}>
          <button className={s.btnGhost} disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Anterior</button>
          <span className={s.muted}>Pág {page}</span>
          <button className={s.btnGhost} disabled={page * 20 >= total} onClick={() => setPage((p) => p + 1)}>Próxima</button>
        </div>
      )}
    </div>
  )
}
