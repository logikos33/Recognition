import { Info } from 'lucide-react'
import * as s from './admin.css'
import { Tooltip } from '../../../components/ui/Tooltip/Tooltip'
import type { PermissionRegistryEntry, UserRole } from '../types/admin'

const ROLES: UserRole[] = ['superadmin', 'admin', 'operator', 'analyst', 'trainer', 'viewer']

/**
 * Matriz de permissões dirigida pelo registry canônico (WS7).
 * Nomenclatura: SEMPRE label pt-BR do registry; chave técnica só no tooltip.
 */
export function PermissionMatrixTable({ entries }: { entries: PermissionRegistryEntry[] }) {
  const groups = new Map<string, PermissionRegistryEntry[]>()
  for (const entry of entries) {
    const list = groups.get(entry.group) ?? []
    list.push(entry)
    groups.set(entry.group, list)
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table className={s.table}>
        <thead>
          <tr>
            <th className={s.th}>Permissão</th>
            {ROLES.map((r) => <th key={r} className={s.th}>{r}</th>)}
          </tr>
        </thead>
        <tbody>
          {[...groups.entries()].map(([group, perms]) => (
            <GroupRows key={group} group={group} perms={perms} />
          ))}
        </tbody>
      </table>
    </div>
  )
}

function GroupRows({ group, perms }: { group: string; perms: PermissionRegistryEntry[] }) {
  return (
    <>
      <tr>
        <td className={s.td} colSpan={ROLES.length + 1}>
          <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', opacity: 0.6 }}>
            {group}
          </span>
        </td>
      </tr>
      {perms.map((perm) => (
        <tr key={perm.key}>
          <td className={s.td}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              {perm.label}
              <Tooltip label={`${perm.description} (${perm.key})`}>
                <Info size={12} style={{ opacity: 0.5, cursor: 'help' }} aria-label={`Descrição: ${perm.label}`} />
              </Tooltip>
            </span>
          </td>
          {ROLES.map((r) => (
            <td key={r} className={s.td} style={{ textAlign: 'center' }}>
              {perm.default_roles.includes(r) ? '✓' : <span className={s.muted}>–</span>}
            </td>
          ))}
        </tr>
      ))}
    </>
  )
}
