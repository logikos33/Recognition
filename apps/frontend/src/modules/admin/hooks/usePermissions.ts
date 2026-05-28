import { useEffect, useState } from 'react'
import { adminService } from '../services/adminService'
import type { PermissionMatrix, UserRole } from '../types/admin'

let _cache: PermissionMatrix | null = null

export function usePermissions() {
  const [matrix, setMatrix] = useState<PermissionMatrix | null>(_cache)
  const [loading, setLoading] = useState(_cache === null)

  useEffect(() => {
    if (_cache) { setMatrix(_cache); setLoading(false); return }

    adminService
      .getPermissionMatrix()
      .then((m) => { _cache = m; setMatrix(m) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const can = (permission: string, role: UserRole): boolean => {
    if (!matrix) return false
    return matrix[permission]?.includes(role) ?? false
  }

  const rolesFor = (permission: string): UserRole[] => matrix?.[permission] ?? []

  return { matrix, loading, can, rolesFor }
}
