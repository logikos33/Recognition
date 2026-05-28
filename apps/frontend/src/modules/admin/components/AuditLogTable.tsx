import * as s from './admin.css'
import type { AuditEntry } from '../types/admin'

export function AuditLogTable({ entries }: { entries: AuditEntry[] }) {
  return (
    <div style={{ overflowX: 'auto' }}>
      <table className={s.table}>
        <thead>
          <tr>
            <th className={s.th}>Quando</th>
            <th className={s.th}>Ator</th>
            <th className={s.th}>Tenant</th>
            <th className={s.th}>Ação</th>
            <th className={s.th}>Alvo</th>
            <th className={s.th}>IP</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e) => (
            <tr key={e.id} className={s.trHover}>
              <td className={s.td}><span className={s.mono}>{new Date(e.created_at).toLocaleString('pt-BR')}</span></td>
              <td className={s.td}>
                <div>{e.actor_email ?? '—'}</div>
                <div className={s.muted}>{e.actor_role}</div>
              </td>
              <td className={s.td}>{e.tenant_name ?? '—'}</td>
              <td className={s.td}><span className={s.mono}>{e.action}</span></td>
              <td className={s.td}><span className={s.muted}>{e.target_type}{e.target_id ? ` #${e.target_id.slice(0, 8)}` : ''}</span></td>
              <td className={s.td}><span className={s.mono}>{e.ip_address ?? '—'}</span></td>
            </tr>
          ))}
          {entries.length === 0 && (
            <tr><td colSpan={6} className={s.td} style={{ textAlign: 'center' }}><span className={s.muted}>Nenhum registro</span></td></tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
