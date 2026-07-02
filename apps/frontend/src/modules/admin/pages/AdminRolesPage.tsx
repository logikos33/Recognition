/**
 * AdminRolesPage — Gerenciamento de permissões customizáveis por tenant.
 *
 * Features:
 *   - Lista de roles com contagem de usuários
 *   - Modal criar/editar role com checkboxes por área funcional
 *   - Deletar role (bloqueado se há usuários vinculados)
 */
import { Edit2, Plus, Shield, Trash2, X } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import * as s from '../components/admin.css'
import { adminService } from '../services/adminService'
import type { CustomRole, PermissionKey } from '../types/admin'
import { PERMISSION_GROUPS } from '../types/admin'

// ── Role Editor Modal ─────────────────────────────────────────────────────────

interface RoleModalProps {
  role?: CustomRole
  onSave: () => void
  onClose: () => void
}

function RoleModal({ role, onSave, onClose }: RoleModalProps) {
  const isEdit = Boolean(role)
  const [name, setName] = useState(role?.name ?? '')
  const [permissions, setPermissions] = useState<Record<string, boolean>>(
    role?.permissions ?? {}
  )
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const toggle = (key: PermissionKey) => {
    setPermissions((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  const handleSave = async () => {
    if (!name.trim()) { setErr('Nome é obrigatório'); return }
    setSaving(true); setErr(null)
    try {
      const perms = permissions as Record<PermissionKey, boolean>
      if (isEdit && role) {
        await adminService.updateRole(role.id, { name, permissions: perms })
      } else {
        await adminService.createRole({ name, permissions: perms })
      }
      onSave()
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : 'Erro ao salvar')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={overlayStyle}>
      <div className={s.card} style={modalBoxStyle}>
        {/* Header */}
        <div className={s.pageHeader} style={{ marginBottom: 16 }}>
          <div className={s.pageTitle}>{isEdit ? 'Editar Role' : 'Nova Role'}</div>
          <button
            className={s.btnGhost}
            onClick={onClose}
            aria-label="Fechar"
            style={{ padding: '4px 8px' }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Name */}
        <label style={fieldLabelStyle}>Nome da role</label>
        <input
          className={s.input}
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Ex.: Operador de câmeras"
          style={{ width: '100%', marginBottom: 20, boxSizing: 'border-box' }}
        />

        {/* Permission groups */}
        <div className={s.cardTitle}>Permissões</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 20 }}>
          {PERMISSION_GROUPS.map((group) => (
            <div key={group.label} className={s.card} style={{ padding: '10px 12px' }}>
              <div style={{ fontSize: 11, fontWeight: 700, marginBottom: 8, textTransform: 'uppercase', opacity: 0.6 }}>
                {group.label}
              </div>
              {group.permissions.map((perm) => (
                <label key={perm} style={checkRowStyle}>
                  <input
                    type="checkbox"
                    checked={Boolean(permissions[perm])}
                    onChange={() => toggle(perm)}
                    style={{ marginRight: 7, cursor: 'pointer' }}
                  />
                  <span style={{ fontSize: 12 }}>{perm}</span>
                </label>
              ))}
            </div>
          ))}
        </div>

        {err && <div className={s.alertBanner.danger} style={{ marginBottom: 12 }}>{err}</div>}

        {/* Actions */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button className={s.btnGhost} onClick={onClose} disabled={saving}>
            Cancelar
          </button>
          <button className={s.btnPrimary} onClick={handleSave} disabled={saving}>
            {saving ? 'Salvando...' : 'Salvar'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Badge helpers (inline since `badge` has no variants) ──────────────────────

function PermBadge({ label }: { label: string }) {
  return (
    <span
      className={s.badge}
      style={{ background: 'rgba(59,130,246,0.12)', color: '#2563eb', fontSize: 11 }}
    >
      {label}
    </span>
  )
}

function CountBadge({ count }: { count: number }) {
  return (
    <span
      className={s.badge}
      style={
        count > 0
          ? { background: 'rgba(34,197,94,0.12)', color: '#16a34a' }
          : { background: 'rgba(107,114,128,0.12)', color: '#6b7280' }
      }
    >
      {count}
    </span>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function AdminRolesPage() {
  const [roles, setRoles] = useState<CustomRole[]>([])
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState<string | null>(null)
  const [modal, setModal] = useState<{ open: boolean; role?: CustomRole }>({ open: false })
  const [deleting, setDeleting] = useState<string | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    adminService.getRoles()
      .then((r) => setRoles(r.roles))
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : 'Erro ao carregar roles'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  const handleDelete = async (role: CustomRole) => {
    if (role.user_count > 0) {
      alert(
        `A role "${role.name}" possui ${role.user_count} usuário(s) vinculado(s).\n` +
        'Remova a role de todos os usuários antes de deletar.'
      )
      return
    }
    if (!confirm(`Deletar a role "${role.name}"? Esta ação não pode ser desfeita.`)) return
    setDeleting(role.id)
    try {
      await adminService.deleteRole(role.id)
      load()
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : 'Erro ao deletar')
    } finally {
      setDeleting(null)
    }
  }

  return (
    <div className={s.pageRoot}>
      {/* Header */}
      <div className={s.pageHeader}>
        <div>
          <div className={s.pageTitle}>Permissões</div>
          <div className={s.pageSubtitle}>{roles.length} role(s) customizada(s) neste tenant</div>
        </div>
        <button className={s.btnPrimary} onClick={() => setModal({ open: true })}>
          <Plus size={14} /> Nova Role
        </button>
      </div>

      {err && <div className={s.alertBanner.danger}>{err}</div>}

      {/* Role list */}
      <div className={s.card}>
        {loading ? (
          <div className={s.muted}>Carregando...</div>
        ) : roles.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 20px' }}>
            <Shield size={36} style={{ opacity: 0.25, marginBottom: 10, display: 'block', margin: '0 auto 10px' }} />
            <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>Nenhuma role customizada</div>
            <div className={s.muted}>
              Crie roles para atribuir permissões granulares a usuários deste tenant.
            </div>
          </div>
        ) : (
          <table className={s.table}>
            <thead>
              <tr>
                <th>Nome</th>
                <th>Permissões ativas</th>
                <th>Usuários</th>
                <th>Criada em</th>
                <th style={{ width: 88 }}>Ações</th>
              </tr>
            </thead>
            <tbody>
              {roles.map((r) => {
                const activePerms = Object.entries(r.permissions)
                  .filter(([, v]) => v)
                  .map(([k]) => k)
                return (
                  <tr key={r.id}>
                    <td style={{ fontWeight: 500 }}>{r.name}</td>
                    <td>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                        {activePerms.length === 0 ? (
                          <span className={s.badge} style={{ background: 'rgba(107,114,128,0.1)', color: '#6b7280' }}>
                            Sem permissões
                          </span>
                        ) : (
                          <>
                            {activePerms.slice(0, 4).map((p) => <PermBadge key={p} label={p} />)}
                            {activePerms.length > 4 && (
                              <span className={s.badge} style={{ background: 'rgba(107,114,128,0.1)', color: '#6b7280' }}>
                                +{activePerms.length - 4}
                              </span>
                            )}
                          </>
                        )}
                      </div>
                    </td>
                    <td><CountBadge count={r.user_count} /></td>
                    <td className={s.muted}>
                      {new Date(r.created_at).toLocaleDateString('pt-BR')}
                    </td>
                    <td>
                      <div className={s.flex}>
                        <button
                          className={s.btnGhost}
                          style={{ padding: '4px 8px' }}
                          onClick={() => setModal({ open: true, role: r })}
                          title="Editar"
                        >
                          <Edit2 size={14} />
                        </button>
                        <button
                          className={s.btnDanger}
                          style={{ padding: '4px 8px' }}
                          onClick={() => handleDelete(r)}
                          disabled={deleting === r.id || r.user_count > 0}
                          title={r.user_count > 0 ? 'Role possui usuários vinculados' : 'Deletar'}
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Modal */}
      {modal.open && (
        <RoleModal
          role={modal.role}
          onSave={() => { setModal({ open: false }); load() }}
          onClose={() => setModal({ open: false })}
        />
      )}
    </div>
  )
}

// ── Inline styles ─────────────────────────────────────────────────────────────

const overlayStyle: React.CSSProperties = {
  position: 'fixed',
  inset: 0,
  background: 'rgba(0,0,0,0.6)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  zIndex: 9999,
}

const modalBoxStyle: React.CSSProperties = {
  width: '100%',
  maxWidth: 680,
  maxHeight: '90vh',
  overflowY: 'auto',
}

const fieldLabelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: 12,
  fontWeight: 600,
  marginBottom: 6,
  opacity: 0.7,
}

const checkRowStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  marginBottom: 5,
  cursor: 'pointer',
}
