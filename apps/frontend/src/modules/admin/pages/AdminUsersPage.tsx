import { Plus, Search, KeyRound, Copy, Check } from 'lucide-react'
import { useEffect, useState } from 'react'
import { vars } from '../../../styles/theme.css'
import { adminService } from '../services/adminService'
import { CreateUserWizard } from '../components/CreateUserWizard'
import { UserRoleBadge } from '../components/UserRoleBadge'
import * as s from '../components/admin.css'
import type { AdminUser, UserRole } from '../types/admin'
import { PAPEL_LABEL } from '../papeis'

// Filtro da lista — mesmo vocabulário pt-BR das telas de criação; a chave
// técnica (`operator`) fica no `value`, nunca no texto que o dono lê.
const ROLES: UserRole[] = ['admin', 'operator', 'analyst', 'trainer', 'viewer']

export function AdminUsersPage() {
  const [items, setItems] = useState<AdminUser[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [page, setPage] = useState(1)
  const [showModal, setShowModal] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [resetResult, setResetResult] = useState<{ email: string; temp_password: string } | null>(null)
  const [copied, setCopied] = useState(false)

  const load = () => {
    setLoading(true)
    adminService.getUsers({ search: search || undefined, role: roleFilter || undefined, page })
      .then((r) => { setItems(r.items); setTotal(r.total) })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [search, roleFilter, page])

  const handleDeactivate = async (u: AdminUser) => {
    if (!confirm(`Desativar ${u.email}?`)) return
    try {
      await (u.is_active ? adminService.deactivateUser(u.id) : adminService.reactivateUser(u.id))
      load()
    } catch (e: unknown) { alert(e instanceof Error ? e.message : 'Erro') }
  }

  const handleResetPassword = async (u: AdminUser) => {
    if (!confirm(`Resetar a senha de ${u.email}?\n\nA senha atual deixará de funcionar imediatamente e uma senha temporária será gerada.`)) return
    try {
      const res = await adminService.resetPassword(u.id)
      setCopied(false)
      setResetResult(res)
      load()
    } catch (e: unknown) { alert(e instanceof Error ? e.message : 'Erro ao resetar senha') }
  }

  const copyTemp = async () => {
    if (!resetResult) return
    try {
      await navigator.clipboard.writeText(resetResult.temp_password)
      setCopied(true)
    } catch { /* clipboard indisponível — usuário copia manualmente */ }
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
          {ROLES.map((r) => <option key={r} value={r}>{PAPEL_LABEL[r]}</option>)}
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
                  <td className={s.td}><span className={s.muted}>{u.tenant_name ?? (u.tenant_id ? u.tenant_id.slice(0, 8) : '—')}</span></td>
                  <td className={s.td}><span className={s.muted}>{u.last_login_at ? new Date(u.last_login_at).toLocaleDateString('pt-BR') : '—'}</span></td>
                  <td className={s.td}>{u.login_count}</td>
                  <td className={s.td}><span className={s.dot[u.is_active ? 'healthy' : 'critical']} /></td>
                  <td className={s.td}>
                    <div className={s.flex} style={{ gap: 6, justifyContent: 'flex-end' }}>
                      <button className={s.btnGhost} style={{ fontSize: 11, padding: '3px 8px' }} onClick={() => handleResetPassword(u)} title="Gerar nova senha temporária">
                        <KeyRound size={12} /> Resetar senha
                      </button>
                      <button className={s.btnGhost} style={{ fontSize: 11, padding: '3px 8px' }} onClick={() => handleDeactivate(u)}>
                        {u.is_active ? 'Desativar' : 'Reativar'}
                      </button>
                    </div>
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

      {resetResult && (
        <div style={{ position: 'fixed', inset: 0, background: vars.color.overlay /* TODO-WS1: converter para Modal do kit */, display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div className={s.card} style={{ width: 440 }}>
            <div className={s.flex} style={{ gap: 8, marginBottom: 8 }}>
              <KeyRound size={18} color={vars.color.primary} />
              <div className={s.pageTitle}>Senha temporária gerada</div>
            </div>
            <div className={s.muted} style={{ marginBottom: 16, fontSize: 13 }}>
              Repasse esta senha a <strong>{resetResult.email}</strong>. Ela é exibida <strong>uma única vez</strong> — não é recuperável depois. O usuário deverá defini-la novamente no primeiro acesso.
            </div>
            <div className={s.flex} style={{ gap: 8, marginBottom: 16 }}>
              <code style={{ flex: 1, padding: '10px 12px', borderRadius: 8, background: vars.color.bgCard, border: `1px solid ${vars.color.borderDefault}`, fontFamily: vars.font.mono, fontSize: 14, wordBreak: 'break-all' }}>
                {resetResult.temp_password}
              </code>
              <button className={s.btnGhost} onClick={copyTemp} title="Copiar" style={{ padding: '8px 10px' }}>
                {copied ? <Check size={15} /> : <Copy size={15} />}
              </button>
            </div>
            <div className={s.flex} style={{ justifyContent: 'flex-end' }}>
              <button className={s.btnPrimary} onClick={() => setResetResult(null)}>Fechar</button>
            </div>
          </div>
        </div>
      )}

      <CreateUserWizard
        open={showModal}
        onClose={() => setShowModal(false)}
        onCreated={load}
      />
    </div>
  )
}
