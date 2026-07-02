import { vars } from '../../../styles/theme.css'
import { Plus, Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import { adminService } from '../services/adminService'
import { UserRoleBadge } from '../components/UserRoleBadge'
import * as s from '../components/admin.css'
import type { AdminUser, UserRole } from '../types/admin'

const ROLES: UserRole[] = ['admin', 'operator', 'analyst', 'trainer', 'viewer']

export function AdminUsersPage() {
  const [items, setItems] = useState<AdminUser[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [page, setPage] = useState(1)
  const [showModal, setShowModal] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState({ email: '', role: 'operator', tenant_id: '' })

  const load = () => {
    setLoading(true)
    adminService.getUsers({ search: search || undefined, role: roleFilter || undefined, page })
      .then((r) => { setItems(r.items); setTotal(r.total) })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [search, roleFilter, page])

  const handleCreate = async () => {
    setSaving(true); setError(null)
    try {
      const res = await adminService.createUser({ email: form.email, role: form.role, tenant_id: form.tenant_id })
      alert(`Usuário criado!\nSenha temporária: ${res.temp_password}`)
      setShowModal(false)
      setForm({ email: '', role: 'operator', tenant_id: '' })
      load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Erro ao criar usuário')
    } finally { setSaving(false) }
  }

  const handleDeactivate = async (u: AdminUser) => {
    if (!confirm(`Desativar ${u.email}?`)) return
    try {
      await (u.is_active ? adminService.deactivateUser(u.id) : adminService.reactivateUser(u.id))
      load()
    } catch (e: unknown) { alert(e instanceof Error ? e.message : 'Erro') }
  }

  return (
    <div className={s.pageRoot}>
      <div className={s.pageHeader}>
        <div>
          <div className={s.pageTitle}>Usuários</div>
          <div className={s.pageSubtitle}>{total} usuários cadastrados</div>
        </div>
        <button className={s.btnPrimary} onClick={() => setShowModal(true)}><Plus size={14} /> Novo Usuário</button>
      </div>

      {error && <div className={s.alertBanner.danger}>{error}</div>}

      <div className={s.flex} style={{ marginBottom: 16 }}>
        <div className={s.flex} style={{ flex: 1 }}>
          <Search size={15} />
          <input className={s.input} style={{ flex: 1 }} placeholder="Buscar por email..." value={search} onChange={(e) => { setSearch(e.target.value); setPage(1) }} />
        </div>
        <select className={s.select} value={roleFilter} onChange={(e) => { setRoleFilter(e.target.value); setPage(1) }}>
          <option value="">Todas as roles</option>
          {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
        </select>
      </div>

      <div className={s.card}>
        {loading ? <div className={s.muted}>Carregando...</div> : (
          <table className={s.table}>
            <thead>
              <tr>
                <th className={s.th}>Email</th>
                <th className={s.th}>Role</th>
                <th className={s.th}>Tenant</th>
                <th className={s.th}>Último login</th>
                <th className={s.th}>Logins</th>
                <th className={s.th}>Status</th>
                <th className={s.th}></th>
              </tr>
            </thead>
            <tbody>
              {items.map((u) => (
                <tr key={u.id} className={s.trHover}>
                  <td className={s.td}>{u.email}</td>
                  <td className={s.td}><UserRoleBadge role={u.role} /></td>
                  <td className={s.td}><span className={s.muted}>{u.tenant_name ?? u.tenant_id.slice(0, 8)}</span></td>
                  <td className={s.td}><span className={s.muted}>{u.last_login_at ? new Date(u.last_login_at).toLocaleDateString('pt-BR') : '—'}</span></td>
                  <td className={s.td}>{u.login_count}</td>
                  <td className={s.td}><span className={s.dot[u.is_active ? 'healthy' : 'critical']} /></td>
                  <td className={s.td}>
                    <button className={s.btnGhost} style={{ fontSize: 11, padding: '3px 8px' }} onClick={() => handleDeactivate(u)}>
                      {u.is_active ? 'Desativar' : 'Reativar'}
                    </button>
                  </td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr><td colSpan={7} className={s.td} style={{ textAlign: 'center' }}><span className={s.muted}>Nenhum usuário encontrado</span></td></tr>
              )}
            </tbody>
          </table>
        )}
      </div>

      {total > 20 && (
        <div className={s.flex} style={{ marginTop: 12, justifyContent: 'center' }}>
          <button className={s.btnGhost} disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Anterior</button>
          <span className={s.muted}>Pág {page}</span>
          <button className={s.btnGhost} disabled={page * 20 >= total} onClick={() => setPage((p) => p + 1)}>Próxima</button>
        </div>
      )}

      {showModal && (
        <div style={{ position: 'fixed', inset: 0, background: vars.color.overlay /* TODO-WS1: converter para Modal do kit */, display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div className={s.card} style={{ width: 420 }}>
            <div className={s.pageTitle} style={{ marginBottom: 16 }}>Novo Usuário</div>
            <div style={{ marginBottom: 12 }}>
              <div className={s.muted} style={{ marginBottom: 4 }}>Email</div>
              <input className={s.input} style={{ width: '100%', boxSizing: 'border-box' }} value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} />
            </div>
            <div style={{ marginBottom: 12 }}>
              <div className={s.muted} style={{ marginBottom: 4 }}>Role</div>
              <select className={s.select} style={{ width: '100%', boxSizing: 'border-box' }} value={form.role} onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}>
                {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
            <div style={{ marginBottom: 16 }}>
              <div className={s.muted} style={{ marginBottom: 4 }}>Tenant ID</div>
              <input className={s.input} style={{ width: '100%', boxSizing: 'border-box' }} placeholder="UUID do tenant" value={form.tenant_id} onChange={(e) => setForm((f) => ({ ...f, tenant_id: e.target.value }))} />
            </div>
            {error && <div className={s.alertBanner.danger}>{error}</div>}
            <div className={s.flex} style={{ justifyContent: 'flex-end' }}>
              <button className={s.btnGhost} onClick={() => setShowModal(false)}>Cancelar</button>
              <button className={s.btnPrimary} onClick={handleCreate} disabled={saving || !form.email || !form.tenant_id}>
                {saving ? 'Criando...' : 'Criar Usuário'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
