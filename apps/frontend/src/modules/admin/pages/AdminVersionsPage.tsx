import { ChevronDown, ChevronRight, RotateCcw, Tag } from 'lucide-react'
import { useEffect, useState } from 'react'
import { adminService } from '../services/adminService'
import * as s from '../components/admin.css'
import type { SystemVersion, VersionType } from '../types/admin'

const VERSION_TYPE_STYLE: Record<VersionType, { background: string; color: string }> = {
  major: { background: 'rgba(239,68,68,0.1)', color: '#dc2626' },
  minor: { background: 'rgba(59,130,246,0.1)', color: '#2563eb' },
  patch: { background: 'rgba(107,114,128,0.1)', color: '#6b7280' },
}

const EMPTY_FORM = { version: '', version_type: 'patch' as VersionType, title: '', description: '' }

export function AdminVersionsPage() {
  const [versions, setVersions] = useState<SystemVersion[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [rolling, setRolling] = useState<string | null>(null)

  const load = () => {
    setLoading(true)
    adminService.getVersions()
      .then(setVersions)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const handleRollback = async (v: SystemVersion) => {
    const ok = window.confirm(
      `Restaurar configuração para versão ${v.version}? Esta ação modifica módulos e planos de todos os tenants.`
    )
    if (!ok) return
    setRolling(v.id)
    try {
      await adminService.rollbackVersion(v.id)
      load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Erro ao fazer rollback')
    } finally {
      setRolling(null)
    }
  }

  const handleCreate = async () => {
    if (!form.version || !form.title) return
    setSaving(true)
    try {
      await adminService.createVersion(form)
      setShowModal(false)
      setForm(EMPTY_FORM)
      load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Erro ao criar versão')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className={s.pageRoot}>
      <div className={s.pageHeader}>
        <div>
          <div className={s.pageTitle}>Versões do Sistema</div>
          <div className={s.pageSubtitle}>Checkpoints de configuração</div>
        </div>
        <button className={s.btnPrimary} onClick={() => { setShowModal(true); setForm(EMPTY_FORM) }}>
          <Tag size={14} /> Nova Versão
        </button>
      </div>

      {error && <div className={s.alertBanner.danger}>{error}</div>}

      {loading ? (
        <div className={s.muted}>Carregando...</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {versions.map((v) => {
            const isExpanded = expandedId === v.id
            const typeStyle = VERSION_TYPE_STYLE[v.version_type]
            return (
              <div key={v.id} className={s.card}>
                <div className={s.flex} style={{ justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
                  <div className={s.flex} style={{ flexWrap: 'wrap', gap: 8 }}>
                    <span className={s.badge} style={typeStyle}>v{v.version}</span>
                    {v.is_current && (
                      <span className={s.flex} style={{ gap: 4 }}>
                        <span className={s.dot.healthy} />
                        <span className={s.muted}>Atual</span>
                      </span>
                    )}
                    <span style={{ fontWeight: 700 }}>{v.title}</span>
                  </div>

                  <div className={s.flex}>
                    {typeof v.changelog_count === 'number' && (
                      <span className={s.badge}>{v.changelog_count} entradas</span>
                    )}
                    <button
                      className={s.btnGhost}
                      onClick={() => setExpandedId(isExpanded ? null : v.id)}
                      title="Detalhes"
                    >
                      {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                      Detalhes
                    </button>
                    {!v.is_current && !v.rolled_back_at && (
                      <button
                        className={s.btnDanger}
                        onClick={() => handleRollback(v)}
                        disabled={rolling === v.id}
                        title="Rollback"
                      >
                        <RotateCcw size={14} />
                        {rolling === v.id ? 'Restaurando...' : 'Rollback'}
                      </button>
                    )}
                  </div>
                </div>

                <div className={s.flex} style={{ marginTop: 8, gap: 16, flexWrap: 'wrap' }}>
                  <span className={s.muted}>
                    {new Date(v.created_at).toLocaleDateString('pt-BR', {
                      day: '2-digit', month: '2-digit', year: 'numeric',
                      hour: '2-digit', minute: '2-digit',
                    })}
                  </span>
                  {v.created_by_email && (
                    <span className={s.muted}>{v.created_by_email}</span>
                  )}
                  {v.rolled_back_at && (
                    <span className={s.muted} style={{ color: '#dc2626' }}>
                      Revertida em {new Date(v.rolled_back_at).toLocaleDateString('pt-BR')}
                      {v.rolled_back_by_email && ` por ${v.rolled_back_by_email}`}
                    </span>
                  )}
                </div>

                {isExpanded && (
                  <div style={{ marginTop: 16, borderTop: '1px solid rgba(107,114,128,0.2)', paddingTop: 16 }}>
                    {v.description && (
                      <p className={s.muted} style={{ marginBottom: 12 }}>{v.description}</p>
                    )}
                    {v.changelog && v.changelog.length > 0 ? (
                      <table className={s.table}>
                        <thead>
                          <tr>
                            <th className={s.th}>Importância</th>
                            <th className={s.th}>Categoria</th>
                            <th className={s.th}>Título</th>
                            <th className={s.th}>Área</th>
                          </tr>
                        </thead>
                        <tbody>
                          {v.changelog.map((entry) => (
                            <tr key={entry.id}>
                              <td className={s.td}><span className={s.badge}>{entry.importance}</span></td>
                              <td className={s.td}><span className={s.badge}>{entry.category}</span></td>
                              <td className={s.td}>{entry.title}</td>
                              <td className={s.td}><span className={s.muted}>{entry.affected_area ?? '—'}</span></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    ) : (
                      <span className={s.muted}>Nenhuma entrada de changelog vinculada.</span>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {showModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div className={s.card} style={{ width: 480 }}>
            <div className={s.pageTitle} style={{ marginBottom: 16 }}>Nova Versão</div>

            <div style={{ marginBottom: 12 }}>
              <div className={s.muted} style={{ marginBottom: 4 }}>Versão</div>
              <input
                className={s.input}
                placeholder="1.2.0"
                style={{ width: '100%', boxSizing: 'border-box' }}
                value={form.version}
                onChange={(e) => setForm((f) => ({ ...f, version: e.target.value }))}
              />
            </div>

            <div style={{ marginBottom: 12 }}>
              <div className={s.muted} style={{ marginBottom: 4 }}>Tipo</div>
              <select
                className={s.select}
                style={{ width: '100%', boxSizing: 'border-box' }}
                value={form.version_type}
                onChange={(e) => setForm((f) => ({ ...f, version_type: e.target.value as VersionType }))}
              >
                <option value="major">major</option>
                <option value="minor">minor</option>
                <option value="patch">patch</option>
              </select>
            </div>

            <div style={{ marginBottom: 12 }}>
              <div className={s.muted} style={{ marginBottom: 4 }}>Título</div>
              <input
                className={s.input}
                style={{ width: '100%', boxSizing: 'border-box' }}
                value={form.title}
                onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              />
            </div>

            <div style={{ marginBottom: 16 }}>
              <div className={s.muted} style={{ marginBottom: 4 }}>Descrição (opcional)</div>
              <textarea
                className={s.input}
                style={{ width: '100%', boxSizing: 'border-box', resize: 'vertical', minHeight: 72 }}
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              />
            </div>

            {error && <div className={s.alertBanner.danger} style={{ marginBottom: 12 }}>{error}</div>}

            <div className={s.flex} style={{ justifyContent: 'flex-end' }}>
              <button className={s.btnGhost} onClick={() => setShowModal(false)}>Cancelar</button>
              <button className={s.btnPrimary} onClick={handleCreate} disabled={saving || !form.version || !form.title}>
                {saving ? 'Criando...' : 'Criar Versão'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
