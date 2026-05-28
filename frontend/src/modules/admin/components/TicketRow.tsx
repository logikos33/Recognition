import { useNavigate } from 'react-router-dom'
import * as s from './admin.css'
import { SlaIndicator } from './SlaIndicator'
import type { SupportTicket } from '../types/admin'

const categoryLabel: Record<string, string> = {
  bug: 'Bug', question: 'Dúvida', retrain: 'Retreino',
  new_module: 'Novo módulo', billing: 'Financeiro', other: 'Outro',
}

export function TicketRow({ ticket }: { ticket: SupportTicket }) {
  const nav = useNavigate()
  return (
    <tr className={s.trHover} onClick={() => nav(`/admin/tickets/${ticket.id}`)}>
      <td className={s.td}><span className={s.mono}>#{ticket.id.slice(0, 8)}</span></td>
      <td className={s.td}>
        <div>{ticket.subject}</div>
        <div className={s.muted}>{ticket.tenant_name}</div>
      </td>
      <td className={s.td}>{categoryLabel[ticket.category] ?? ticket.category}</td>
      <td className={s.td}><span className={s.priorityBadge[ticket.priority]}>{ticket.priority}</span></td>
      <td className={s.td}><span className={s.statusBadge[ticket.status]}>{ticket.status.replace('_', ' ')}</span></td>
      <td className={s.td}>
        <SlaIndicator priority={ticket.priority} createdAt={ticket.created_at} firstRespondedAt={ticket.first_responded_at} />
      </td>
      <td className={s.td}><span className={s.muted}>{new Date(ticket.created_at).toLocaleDateString('pt-BR')}</span></td>
    </tr>
  )
}
