/**
 * AdminRoute — Guard para rotas /admin/*.
 * Permite acesso apenas a usuários com role 'superadmin'.
 * Redireciona para / caso contrário, sem loop.
 */
import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'

export function AdminRoute() {
  const { isSuperAdmin } = useAuth()

  if (!isSuperAdmin) {
    return <Navigate to="/" replace />
  }

  return <Outlet />
}
