import { Plus, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { adminService } from '../services/adminService'
import * as s from '../components/admin.css'
import type { Announcement, AnnouncementType } from '../types/admin'
import { vars } from '../../../styles/theme.css'

const TYPES: AnnouncementType[] = ['info', 'maintenance', 'feature', 'security']

const emptyForm: Partial<Announcement> = { title: '', content: '', type: 'info', target: 'all' }

export function AdminAnnouncementsPage() {
  const [items, setItems] = useState<Announcement[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState<Partial<Announcement>>(emptyForm)
  const [saving, setSaving] = useState(false)

  const load = () => {
    setLoading(true)
    adminService.getAnnouncements()
      .then(setItems)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const handleCreate = async () => {
    setSaving(true); setError(null)
    try {
      await adminService.createAnnouncement(form)
      setShowModal(false); setForm(emptyForm); load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Erro ao criar comunicado')
    } finally { setSaving(false) }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Arquivar este comunicado?')) return
    try { await adminService.deleteAnnouncement(id); load() }
    catch (e: unknown) { alert(e instanceof Error ? e.message : 'Erro') }
  }

  return (
    <div className={s.pageRoot}>
      <div className={s.pageHeader}>
        <div>
          <div className={s.pageTitle}>Comunicados</div>
          <div className={s.pageSubtitle}>{items.length} comunicados ativos</div>
        </div>
        <button className={s.btnPrimary} onClick={() => setShowModal(true)}><Plus size={14} /> Novo Comunicado</button>
      </div>

      {error && <div className={s.alertBanner.danger}>{error}</div>}

      <div className={s.card}>
        {loading ? <div className={s.muted}>Carregando...</div> : (
          <table className={s.table}>
            <thead>
              <tr>
                <th className={s.th}>Tipo</th>
                <th className={s.th}>Título</th>
                <th className={s.th}>Alvo</th>
                <th className={s.th}>Publicado</th>
                <th className={s.th}>Expira</th>
                <th className={s.th}></th>
              </tr>
            </thead>
            <tbody>
              {items.map((a) => (
                <tr key={a.id} className={s.trHover}>
                  <td className={s.td}><span className={s.badge} style={{ background: 'rgba(59,130,246,0.1)', color: vars.color.primary }}>{a.type}</span></td>
                  <td className={s.td}><strong>{a.title}</strong><div className={s.muted}>{a.content?.slice(0, 60)}</div></td>
                  <td className={s.td}><span className={s.muted}>{a.target}</span></td>
                  <td className={s.td}><span className={s.muted}>{a.published_at ? new Date(a.published_at).toLocaleDateString('pt-BR') : '—'}</span></td>
                  <td className={s.td}><span className={s.muted}>{a.expires_at ? new Date(a.expires_at).toLocaleDateString('pt-BR') : '—'}</span></td>
                  <td className={s.td}>
                    <button className={s.btnGhost} style={{ padding: '3px 8px', fontSize: 11 }} onClick={() => handleDelete(a.id)}>
                      <Trash2 size={11} />
                    </button>
                  </td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr><td colSpan={6} className={s.td} style={{ textAlign: 'center' }}><span className={s.muted}>Nenhum comunicado</span></td></tr>
              )}
            </tbody>
          </table>
        )}
      </div>

      {showModal && (
        <div style={{ position: 'fixed', inset: 0, background: vars.color.overlay /* TODO-WS1: converter para Modal do kit */, display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div className={s.card} style={{ width: 480 }}>
            <div className={s.pageTitle} style={{ marginBottom: 16 }}>Novo Comunicado</div>
            <div style={{ marginBottom: 12 }}>
              <div className={s.muted} style={{ marginBottom: 4 }}>Título</div>
              <input className={s.input} style={{ width: '100%', boxSizing: 'border-box' }} value={form.title ?? ''} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} />
            </div>
            <div style={{ marginBottom: 12 }}>
              <div className={s.muted} style={{ marginBottom: 4 }}>Conteúdo</div>
              <textarea className={s.input} style={{ width: '100%', boxSizing: 'border-box', minHeight: 80, resize: 'vertical' }} value={form.content ?? ''} onChange={(e) => setForm((f) => ({ ...f, content: e.target.value }))} />
            </div>
            <div style={{ marginBottom: 12 }}>
              <div className={s.muted} style={{ marginBottom: 4 }}>Tipo</div>
              <select className={s.select} style={{ width: '100%', boxSizing: 'border-box' }} value={form.type ?? 'info'} onChange={(e) => setForm((f) => ({ ...f, type: e.target.value as AnnouncementType }))}>
                {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div style={{ marginBottom: 16 }}>
              <div className={s.muted} style={{ marginBottom: 4 }}>Alvo (all / tenant:uuid)</div>
              <input className={s.input} style={{ width: '100%', boxSizing: 'border-box' }} value={form.target ?? 'all'} onChange={(e) => setForm((f) => ({ ...f, target: e.target.value }))} />
            </div>
            {error && <div className={s.alertBanner.danger}>{error}</div>}
            <div className={s.flex} style={{ justifyContent: 'flex-end' }}>
              <button className={s.btnGhost} onClick={() => setShowModal(false)}>Cancelar</button>
              <button className={s.btnPrimary} onClick={handleCreate} disabled={saving || !form.title}>{saving ? 'Criando...' : 'Publicar'}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
