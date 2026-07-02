import { useEffect, useMemo, useState } from 'react'
import { adminService } from '../services/adminService'
import type { PermissionMatrix, PermissionRegistryEntry, UserRole } from '../types/admin'

// Cache em módulo (WS7): registry canônico com labels/descrições pt-BR
let _registryCache: PermissionRegistryEntry[] | null = null

export function usePermissions() {
  const [registry, setRegistry] = useState<PermissionRegistryEntry[] | null>(_registryCache)
  const [loading, setLoading] = useState(_registryCache === null)

  useEffect(() => {
    if (_registryCache) { setRegistry(_registryCache); setLoading(false); return }

    adminService
      .getPermissionRegistry()
      .then((d) => { _registryCache = d.permissions; setRegistry(d.permissions) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  /** Matriz permissão → roles derivada do registry (compat com consumo antigo). */
  const matrix: PermissionMatrix | null = useMemo(() => {
    if (!registry) return null
    return Object.fromEntries(registry.map((e) => [e.key, e.default_roles]))
  }, [registry])

  const can = (permission: string, role: UserRole): boolean => {
    if (!matrix) return false
    return matrix[permission]?.includes(role) ?? false
  }

  const rolesFor = (permission: string): UserRole[] => matrix?.[permission] ?? []

  /** Entrada do registry (label/descrição) para uma chave. */
  const entryFor = (permission: string): PermissionRegistryEntry | undefined =>
    registry?.find((e) => e.key === permission)

  return { registry, matrix, loading, can, rolesFor, entryFor }
}
