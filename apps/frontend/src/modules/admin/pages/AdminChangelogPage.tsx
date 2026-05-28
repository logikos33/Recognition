import { Plus } from 'lucide-react'
import { useEffect, useState } from 'react'
import { adminService } from '../services/adminService'
import * as s from '../components/admin.css'
import type { ChangeCategory, ChangeImportance, ChangelogEntry } from '../types/admin'

const PER_PAGE = 20

const IMPORTANCE_STYLE: Record<ChangeImportance, { background: string; color: string }> = {
  critical: { background: 'rgba(239,68,68,0.1)', color: '#dc2626' },
  high:     { background: 'rgba(249,115,22,0.1)', color: '#ea580c' },
  normal:   { background: 'rgba(107,114,128,0.1)', color: '#6b7280' },
  low:      { background: 'rgba(107,114,128,0.05)', color: '#9ca3af' },
}

const EMPTY_FORM = {
  title: '',
  category: '' as ChangeCategory | '',
  importance: '' as ChangeImportance | '',
  description: '',
  affected_area: '',
}

export function AdminChangelogPage() {
  const [items, setItems] = useState<ChangelogEntry[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  // Pending filter inputs (only applied when "Filtrar" is clicked)
  const [categoryInput, setCategoryInput] = useState('')
  const [importanceInput, setImportanceInput] = useState('')
  const [areaInput, setAreaInput] = useState('')

  // Applied filters (trigger load)
  const [category, setCategory] = useState('')
  const [importance, setImportance] = useState('')
  const [affectedArea, setAffectedArea] = useState('')

  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)

  const load = () => {
    setLoading(true)
    adminService.getChangelog({
      category: category || undefined,
      importance: importance || undefined,
      affected_area: affectedArea || undefined,
      page,
      per_page: PER_PAGE,
    })
      .then((r) => { setItems(r.items); setTotal(r.total) })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [category, importance, affectedArea, page])

  const applyFilters = () => {
    setCategory(categoryInput)
    setImportance(importanceInput)
    setAffectedArea(areaInput)
    setPage(1)
  }

  const handleCreate = async () => {
    if (!form.title) return
    setSaving(true)
    try {
      await adminService.createChangelogEntry({
        title: form.title,
        category: form.category || undefined,
        importance: form.importance || undefined,
        description: form.description || undefined,
        affected_area: form.affected_area || undefined,
      })
      setShowModal(false)
      setForm(EMPTY_FORM)
      load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Erro ao salvar')
    } finally {
      setSaving(false)
    }
  }

  const showing = Math.min(page * PER_PAGE, total)
  const start = Math.min((page - 1) * PER_PAGE + 1, total)

  return (
    <div className={s.pageRoot}>
      <div className={s.pageHeader}>
        <div>
          <div className={s.pageTitle}>Changelog</div>
          <div className={s.pageSubtitle}>Histórico de mudanças</div>
        </div>
        <button className={s.btnPrimary} onClick={() => { setShowModal(true); setForm(EMPTY_FORM) }}>
          <Plus size={14} /> Adicionar entrada
        </button>
      </div>

      {error && <div className={s.alertBanner.danger}>{error}</div>}

      {/* Filters */}
      <div className={s.flex} style={{ marginBottom: 16, flexWrap: 'wrap' }}>
        <select
          className={s.select}
          value={categoryInput}
          onChange={(e) => setCategoryInput(e.target.value)}
        >
          <option value="">Todas categorias</option>
          <option value="feature">feature</option>
          <option value="fix">fix</option>
          <option value="config">config</option>
          <option value="security">security</option>
          <option value="breaking">breaking</option>
          <option value="infra">infra</option>
        </select>

        <select
          className={s.select}
          value={importanceInput}
          onChange={(e) => setImportanceInput(e.target.value)}
        >
          <option value="">Todas importâncias</option>
          <option value="critical">critical</option>
          <option value="high">high</option>
          <option value="normal">normal</option>
          <option value="low">low</option>
        </select>

        <input
          className={s.input}
          placeholder="Área afetada..."
          value={areaInput}
          onChange={(e) => setAreaInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && applyFilters()}
        />

        <button className={s.btnGhost} onClick={applyFilters}>Filtrar</button>
      </div>

      <div className={s.card} style={{ padding: 0, overflow: 'hidden' }}>
        {loading ? (
          <div className={s.muted} style={{ padding: 24 }}>Carregando...</div>
        ) : (
          <table className={s.table}>
            <thead>
              <tr>
                <th className={s.th}>Importância</th>
                <th className={s.th}>Categoria</th>
                <th className={s.th}>Título</th>
                <th className={s.th}>Área</th>
                <th className={s.th}>Versão</th>
                <th className={s.th}>Data</th>
                <th className={s.th}>Por</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td className={s.td} colSpan={7} style={{ textAlign: 'center' }}>
                    <span className={s.muted}>Nenhuma entrada encontrada.</span>
                  </td>
                </tr>
              ) : items.map((entry) => {
                const isExpanded = expandedId === entry.id
                const impStyle = IMPORTANCE_STYLE[entry.importance]
                return (
                  <>
                    <tr
                      key={entry.id}
                      className={s.trHover}
                      onClick={() => setExpandedId(isExpanded ? null : entry.id)}
                    >
                      <td className={s.td}>
                        <span className={s.badge} style={impStyle}>{entry.importance}</span>
                      </td>
                      <td className={s.td}>
                        <span className={s.badge}>{entry.category}</span>
                      </td>
                      <td className={s.td}>{entry.title}</td>
                      <td className={s.td}>
                        <span className={s.muted}>{entry.affected_area ?? '—'}</span>
                      </td>
                      <td className={s.td}>
                        <span className={s.mono}>{entry.version_label ?? '—'}</span>
                      </td>
                      <td className={s.td}>
                        <span className={s.muted}>
                          {new Date(entry.created_at).toLocaleDateString('pt-BR', {
                            day: '2-digit', month: '2-digit', year: 'numeric',
                          })}
                        </span>
                      </td>
                      <td className={s.td}>
                        <span className={s.muted}>{entry.created_by_email ?? '—'}</span>
                      </td>
                    </tr>
                    {isExpanded && entry.description && (
                      <tr key={`${entry.id}-desc`}>
                        <td className={s.td} colSpan={7} style={{ background: 'rgba(107,114,128,0.04)' }}>
                          <span className={s.muted}>{entry.description}</span>
                        </td>
                      </tr>
                    )}
                  </>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      {total > 0 && (
        <div className={s.flex} style={{ marginTop: 12, justifyContent: 'space-between' }}>
          <span className={s.muted}>Mostrando {start}–{showing} de {total}</span>
          <div className={s.flex}>
            <button className={s.btnGhost} disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              Anterior
            </button>
            <button className={s.btnGhost} disabled={showing >= total} onClick={() => setPage((p) => p + 1)}>
              Próxima
            </button>
          </div>
        </div>
      )}

      {showModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div className={s.card} style={{ width: 480 }}>
            <div className={s.pageTitle} style={{ marginBottom: 16 }}>Nova Entrada de Changelog</div>

            <div style={{ marginBottom: 12 }}>
              <div className={s.muted} style={{ marginBottom: 4 }}>Título *</div>
              <input
                className={s.input}
                style={{ width: '100%', boxSizing: 'border-box' }}
                value={form.title}
                onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
              <div>
                <div className={s.muted} style={{ marginBottom: 4 }}>Categoria</div>
                <select
                  className={s.select}
                  style={{ width: '100%', boxSizing: 'border-box' }}
                  value={form.category}
                  onChange={(e) => setForm((f) => ({ ...f, category: e.target.value as ChangeCategory | '' }))}
                >
                  <option value="">— selecione —</option>
                  <option value="feature">feature</option>
                  <option value="fix">fix</option>
                  <option value="config">config</option>
                  <option value="security">security</option>
                  <option value="breaking">breaking</option>
                  <option value="infra">infra</option>
                </select>
              </div>
              <div>
                <div className={s.muted} style={{ marginBottom: 4 }}>Importância</div>
                <select
                  className={s.select}
                  style={{ width: '100%', boxSizing: 'border-box' }}
                  value={form.importance}
                  onChange={(e) => setForm((f) => ({ ...f, importance: e.target.value as ChangeImportance | '' }))}
                >
                  <option value="">— selecione —</option>
                  <option value="critical">critical</option>
                  <option value="high">high</option>
                  <option value="normal">normal</option>
                  <option value="low">low</option>
                </select>
              </div>
            </div>

            <div style={{ marginBottom: 12 }}>
              <div className={s.muted} style={{ marginBottom: 4 }}>Descrição</div>
              <textarea
                className={s.input}
                style={{ width: '100%', boxSizing: 'border-box', resize: 'vertical', minHeight: 72 }}
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              />
            </div>

            <div style={{ marginBottom: 16 }}>
              <div className={s.muted} style={{ marginBottom: 4 }}>Área afetada</div>
              <input
                className={s.input}
                style={{ width: '100%', boxSizing: 'border-box' }}
                value={form.affected_area}
                onChange={(e) => setForm((f) => ({ ...f, affected_area: e.target.value }))}
              />
            </div>

            {error && <div className={s.alertBanner.danger} style={{ marginBottom: 12 }}>{error}</div>}

            <div className={s.flex} style={{ justifyContent: 'flex-end' }}>
              <button className={s.btnGhost} onClick={() => setShowModal(false)}>Cancelar</button>
              <button className={s.btnPrimary} onClick={handleCreate} disabled={saving || !form.title}>
                {saving ? 'Salvando...' : 'Salvar'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
