import * as s from './admin.css'
import type { UserRole } from '../types/admin'

const labels: Record<UserRole, string> = {
  superadmin: 'Superadmin',
  admin:      'Admin',
  operator:   'Operador',
  analyst:    'Analista',
  trainer:    'Treinador',
  viewer:     'Viewer',
}

export function UserRoleBadge({ role }: { role: UserRole }) {
  return <span className={s.roleBadge[role]}>{labels[role]}</span>
}
