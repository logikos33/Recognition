/**
 * UserPermissionsDrawer — "usuário customizado" (WS7).
 *
 * Gaveta de permissões por usuário aberta em AdminUsersPage e na aba Users
 * do AdminTenantDetailPage. Três camadas (Contrato de Operabilidade):
 *   1. Role base — select obrigatório (labels + descrição pt-BR)
 *   2. Role customizada — select opcional (roles do tenant + 'Nenhuma')
 *   3. Overrides — tri-state por permissão: Herdar / Permitir / Negar,
 *      com tooltip de descrição e badge do estado herdado/efetivo
 *
 * Staleness: mudanças valem no PRÓXIMO login (claim no JWT) — aviso fixo +
 * botão 'Encerrar sessões do usuário' (DELETE /v1/admin/users/<id>/sessions).
 */
import { Info, ShieldAlert } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { AppDrawer } from '../../../components/ui/AppDrawer/AppDrawer'
import { Badge } from '../../../components/ui/Badge/Badge'
import { Button } from '../../../components/ui/Button/Button'
import { ConfirmDialog } from '../../../components/ui/ConfirmDialog/ConfirmDialog'
import { Tooltip } from '../../../components/ui/Tooltip/Tooltip'
import { useToast } from '../../../components/ui/Toast/useToast'
import { usePermissions } from '../hooks/usePermissions'
import { adminService } from '../services/adminService'
import * as s from './admin.css'
import type {
  CustomRole,
  PermissionOverrideState,
  PermissionRegistryEntry,
  UserPermissionsDetail,
  UserRole,
} from '../types/admin'

export const ROLE_OPTIONS: { value: UserRole; label: string; description: string }[] = [
  { value: 'admin', label: 'Administrador', description: 'Gerencia o próprio tenant: câmeras, usuários, treinamentos e configurações.' },
  { value: 'operator', label: 'Operador', description: 'Opera câmeras, testa conexões e acompanha alertas do dia a dia.' },
  { value: 'analyst', label: 'Analista', description: 'Visualiza dashboards e relatórios; dá feedback em alertas.' },
  { value: 'trainer', label: 'Treinador', description: 'Anota frames e cria jobs de treinamento de modelo.' },
  { value: 'viewer', label: 'Visualizador', description: 'Somente visualização (read-only).' },
]

export interface DrawerUser {
  id: string
  email: string
  role: UserRole
  tenant_id: string
}

interface UserPermissionsDrawerProps {
  open: boolean
  onClose: () => void
  user: DrawerUser | null
  /** Chamado após salvar com sucesso (recarregar listagem). */
  onChanged?: () => void
}

export function UserPermissionsDrawer({ open, onClose, user, onChanged }: UserPermissionsDrawerProps) {
  const { registry } = usePermissions()
  const toast = useToast()

  const [detail, setDetail] = useState<UserPermissionsDetail | null>(null)
  const [tenantRoles, setTenantRoles] = useState<CustomRole[]>([])
  const [loading, setLoading] = useState(false)
  const [loadErr, setLoadErr] = useState<string | null>(null)

  const [baseRole, setBaseRole] = useState<UserRole>('viewer')
  const [customRoleId, setCustomRoleId] = useState<string>('')
  const [overrideState, setOverrideState] = useState<Record<string, PermissionOverrideState>>({})
  const [saving, setSaving] = useState(false)
  const [confirmSessions, setConfirmSessions] = useState(false)
  const [revoking, setRevoking] = useState(false)

  const load = useCallback(() => {
    if (!user) return
    setLoading(true)
    setLoadErr(null)
    Promise.all([
      adminService.getUserPermissions(user.id),
      adminService.getRoles(user.tenant_id).then((r) => r.roles).catch(() => [] as CustomRole[]),
    ])
      .then(([d, roles]) => {
        setDetail(d)
        setTenantRoles(roles)
        setBaseRole(d.role)
        setCustomRoleId(d.custom_role?.id ?? '')
        const initial: Record<string, PermissionOverrideState> = {}
        for (const o of d.overrides) initial[o.permission_key] = o.allow ? 'allow' : 'deny'
        setOverrideState(initial)
      })
      .catch((e: unknown) => setLoadErr(e instanceof Error ? e.message : 'Erro ao carregar permissões'))
      .finally(() => setLoading(false))
  }, [user])

  useEffect(() => { if (open) load() }, [open, load])

  const groups = useMemo(() => {
    const byGroup = new Map<string, PermissionRegistryEntry[]>()
    for (const entry of registry ?? []) {
      const list = byGroup.get(entry.group) ?? []
      list.push(entry)
      byGroup.set(entry.group, list)
    }
    return [...byGroup.entries()]
  }, [registry])

  const selectedCustomRole = tenantRoles.find((r) => r.id === customRoleId)

  /** Estado herdado (sem override): role base ∪ role customizada selecionada. */
  const inherited = useCallback((key: string): boolean => {
    if (!detail) return false
    if (detail.role_permissions.includes(key)) return true
    return Boolean(selectedCustomRole?.permissions?.[key as keyof typeof selectedCustomRole.permissions])
  }, [detail, selectedCustomRole])

  /** Preview do efetivo (evita lockout surpresa antes de salvar). */
  const effective = useCallback((key: string): boolean => {
    const state = overrideState[key] ?? 'inherit'
    if (state === 'allow') return true
    if (state === 'deny') return false
    return inherited(key)
  }, [overrideState, inherited])

  const isCustomized = customRoleId !== '' ||
    Object.values(overrideState).some((v) => v !== 'inherit')

  const handleSave = async () => {
    if (!user || !detail) return
    setSaving(true)
    try {
      if (baseRole !== detail.role) {
        await adminService.updateUser(user.id, { role: baseRole })
      }
      const originalCustomRoleId = detail.custom_role?.id ?? ''
      if (customRoleId !== originalCustomRoleId) {
        await adminService.setUserCustomRole(user.id, customRoleId || null)
      }

      const originalOverrides = new Map(detail.overrides.map((o) => [o.permission_key, o.allow]))
      const overrides: { permission_key: string; allow: boolean }[] = []
      const remove: string[] = []
      for (const [key, state] of Object.entries(overrideState)) {
        if (state === 'inherit') {
          if (originalOverrides.has(key)) remove.push(key)
        } else {
          const allow = state === 'allow'
          if (originalOverrides.get(key) !== allow) overrides.push({ permission_key: key, allow })
        }
      }
      for (const key of originalOverrides.keys()) {
        if (!(key in overrideState)) remove.push(key)
      }
      if (overrides.length > 0 || remove.length > 0) {
        await adminService.setUserPermissions(user.id, { overrides, remove })
      }

      toast.success('Permissões salvas', 'As mudanças valem no próximo login do usuário.')
      onChanged?.()
      load()
    } catch (e: unknown) {
      toast.error('Erro ao salvar permissões', e instanceof Error ? e.message : undefined)
    } finally {
      setSaving(false)
    }
  }

  const handleRevokeSessions = async () => {
    if (!user) return
    setRevoking(true)
    try {
      await adminService.revokeUserSessions(user.id)
      toast.success('Sessões encerradas', 'O usuário precisará fazer login novamente.')
      setConfirmSessions(false)
    } catch (e: unknown) {
      toast.error('Erro ao encerrar sessões', e instanceof Error ? e.message : undefined)
    } finally {
      setRevoking(false)
    }
  }

  const targetIsSuperadmin = user?.role === 'superadmin'

  return (
    <AppDrawer isOpen={open} onClose={onClose} title={`Permissões — ${user?.email ?? ''}`} size="lg">
      {loading && <div className={s.muted}>Carregando permissões...</div>}
      {loadErr && <div className={s.alertBanner.danger}>{loadErr}</div>}

      {!loading && !loadErr && detail && user && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {targetIsSuperadmin ? (
            <div className={s.alertBanner.warning} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <ShieldAlert size={15} />
              Superadmin possui todas as permissões da plataforma e é imune a restrições (anti-lockout).
            </div>
          ) : (
            <>
              {/* Role base */}
              <div>
                <label className={s.muted} style={{ display: 'block', marginBottom: 4, fontSize: 12 }}>
                  Role base (obrigatória)
                </label>
                <select
                  className={s.select}
                  style={{ width: '100%' }}
                  value={baseRole}
                  onChange={(e) => setBaseRole(e.target.value as UserRole)}
                  aria-label="Role base do usuário"
                >
                  {ROLE_OPTIONS.map((r) => (
                    <option key={r.value} value={r.value}>{r.label}</option>
                  ))}
                </select>
                <div className={s.muted} style={{ fontSize: 11, marginTop: 4 }}>
                  {ROLE_OPTIONS.find((r) => r.value === baseRole)?.description}
                </div>
              </div>

              {/* Role customizada */}
              <div>
                <label className={s.muted} style={{ display: 'block', marginBottom: 4, fontSize: 12 }}>
                  Role customizada (opcional — soma permissões à role base)
                </label>
                <select
                  className={s.select}
                  style={{ width: '100%' }}
                  value={customRoleId}
                  onChange={(e) => setCustomRoleId(e.target.value)}
                  aria-label="Role customizada do usuário"
                >
                  <option value="">Nenhuma</option>
                  {tenantRoles.map((r) => (
                    <option key={r.id} value={r.id}>{r.name}</option>
                  ))}
                </select>
              </div>

              {/* Overrides tri-state */}
              <div>
                <div className={s.cardTitle} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  Permissões individuais
                  <Tooltip label="Herdar usa a role base + role customizada. Permitir/Negar sobrescrevem só para este usuário (Negar vence).">
                    <Info size={12} style={{ opacity: 0.5, cursor: 'help' }} aria-label="Como funcionam os overrides" />
                  </Tooltip>
                  {isCustomized && <Badge variant="accent">Customizado</Badge>}
                </div>

                {groups.length === 0 && (
                  <div className={s.muted}>Registry de permissões indisponível.</div>
                )}

                {groups.map(([group, entries]) => (
                  <div key={group} className={s.card} style={{ padding: '10px 12px', marginBottom: 10 }}>
                    <div style={{ fontSize: 11, fontWeight: 700, marginBottom: 8, textTransform: 'uppercase', opacity: 0.6 }}>
                      {group}
                    </div>
                    {entries.map((entry) => {
                      const state = overrideState[entry.key] ?? 'inherit'
                      const isEffective = effective(entry.key)
                      return (
                        <div
                          key={entry.key}
                          style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0' }}
                        >
                          <span style={{ flex: 1, fontSize: 12, display: 'inline-flex', alignItems: 'center', gap: 5 }}>
                            {entry.label}
                            <Tooltip label={entry.description}>
                              <Info size={11} style={{ opacity: 0.5, cursor: 'help' }} aria-label={`Descrição: ${entry.label}`} />
                            </Tooltip>
                          </span>
                          <Badge variant={isEffective ? 'success' : 'neutral'}>
                            {isEffective ? 'Liberada' : 'Bloqueada'}
                          </Badge>
                          <select
                            className={s.select}
                            style={{ fontSize: 12, padding: '2px 6px' }}
                            value={state}
                            onChange={(e) =>
                              setOverrideState((prev) => ({
                                ...prev,
                                [entry.key]: e.target.value as PermissionOverrideState,
                              }))
                            }
                            aria-label={`Override de ${entry.label}`}
                          >
                            <option value="inherit">
                              {`Herdar (${inherited(entry.key) ? 'liberada' : 'bloqueada'})`}
                            </option>
                            <option value="allow">Permitir</option>
                            <option value="deny">Negar</option>
                          </select>
                        </div>
                      )
                    })}
                  </div>
                ))}
              </div>

              {/* Staleness + ações */}
              <div className={s.alertBanner.warning}>
                As mudanças valem no <strong>próximo login</strong> do usuário. Para aplicar
                imediatamente, encerre as sessões ativas dele.
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                <Button
                  variant="danger"
                  onClick={() => setConfirmSessions(true)}
                  disabled={saving}
                >
                  Encerrar sessões do usuário
                </Button>
                <div style={{ display: 'flex', gap: 8 }}>
                  <Button variant="ghost" onClick={onClose} disabled={saving}>Cancelar</Button>
                  <Button variant="primary" onClick={handleSave} loading={saving}>
                    Salvar permissões
                  </Button>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      <ConfirmDialog
        open={confirmSessions}
        onClose={() => setConfirmSessions(false)}
        onConfirm={handleRevokeSessions}
        title="Encerrar sessões do usuário"
        description={`Todas as sessões ativas de ${user?.email ?? ''} serão encerradas e o usuário precisará fazer login novamente. Continuar?`}
        confirmLabel="Encerrar sessões"
        loading={revoking}
      />
    </AppDrawer>
  )
}
