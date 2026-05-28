import * as s from './admin.css'
import type { PermissionMatrix, UserRole } from '../types/admin'

const ROLES: UserRole[] = ['superadmin', 'admin', 'operator', 'analyst', 'trainer', 'viewer']

export function PermissionMatrixTable({ matrix }: { matrix: PermissionMatrix }) {
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
          {Object.entries(matrix).map(([perm, roles]) => (
            <tr key={perm}>
              <td className={s.td}><span className={s.mono}>{perm}</span></td>
              {ROLES.map((r) => (
                <td key={r} className={s.td} style={{ textAlign: 'center' }}>
                  {roles.includes(r) ? '✓' : <span className={s.muted}>–</span>}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
