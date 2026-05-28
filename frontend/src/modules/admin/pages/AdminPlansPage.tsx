import { Plus } from 'lucide-react'
import { useEffect, useState } from 'react'
import { adminService } from '../services/adminService'
import * as s from '../components/admin.css'
import type { Plan } from '../types/admin'

export function AdminPlansPage() {
  const [plans, setPlans] = useState<Plan[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState<Plan | null>(null)
  const [saving, setSaving] = useState(false)

  const load = () => {
    setLoading(true)
    adminService.getPlans()
      .then(setPlans)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const handleSave = async () => {
    if (!editing) return
    setSaving(true)
    try {
      if (editing.id) {
        await adminService.updatePlan(editing.id, editing)
      } else {
        await adminService.createPlan(editing)
      }
      setEditing(null)
      load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Erro ao salvar plano')
    } finally { setSaving(false) }
  }

  const emptyPlan: Plan = { id: '', slug: '', name: '', modules_allowed: [], max_cameras: 10, video_retention_days: 30, requires_training_approval: false, price_per_camera: {}, active: true }

  return (
    <div className={s.pageRoot}>
      <div className={s.pageHeader}>
        <div>
          <div className={s.pageTitle}>Planos</div>
          <div className={s.pageSubtitle}>{plans.length} planos cadastrados</div>
        </div>
        <button className={s.btnPrimary} onClick={() => setEditing(emptyPlan)}><Plus size={14} /> Novo Plano</button>
      </div>

      {error && <div className={s.alertBanner.danger}>{error}</div>}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 16 }}>
        {loading ? <div className={s.muted}>Carregando...</div> : plans.map((p) => (
          <div key={p.id} className={s.card} style={{ cursor: 'pointer' }} onClick={() => setEditing({ ...p })}>
            <div className={s.flex}>
              <span style={{ fontWeight: 700, flex: 1 }}>{p.name}</span>
              <span className={s.planBadge[p.slug as keyof typeof s.planBadge] ?? s.badge}>{p.slug}</span>
            </div>
            <div className={s.muted} style={{ marginTop: 8 }}>Máx câmeras: {p.max_cameras}</div>
            <div className={s.muted}>Retenção: {p.video_retention_days} dias</div>
            <div className={s.muted}>Aprovação de treino: {p.requires_training_approval ? 'Sim' : 'Não'}</div>
            <div style={{ marginTop: 8 }}>
              {(p.modules_allowed ?? []).map((m) => (
                <span key={m} className={s.badge} style={{ background: 'rgba(59,130,246,0.1)', color: '#2563eb', marginRight: 4 }}>{m}</span>
              ))}
            </div>
          </div>
        ))}
      </div>

      {editing !== null && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div className={s.card} style={{ width: 480 }}>
            <div className={s.pageTitle} style={{ marginBottom: 16 }}>{editing.id ? 'Editar Plano' : 'Novo Plano'}</div>
            {[
              ['Nome', 'name', 'text'],
              ['Slug', 'slug', 'text'],
              ['Máx câmeras', 'max_cameras', 'number'],
              ['Retenção (dias)', 'video_retention_days', 'number'],
            ].map(([label, key, type]) => (
              <div key={key} style={{ marginBottom: 12 }}>
                <div className={s.muted} style={{ marginBottom: 4 }}>{label}</div>
                <input className={s.input} type={type} style={{ width: '100%', boxSizing: 'border-box' }}
                  value={(editing as unknown as Record<string, unknown>)[key] as string ?? ''}
                  onChange={(e) => setEditing((prev) => prev ? { ...prev, [key]: type === 'number' ? Number(e.target.value) : e.target.value } : prev)}
                />
              </div>
            ))}
            <div style={{ marginBottom: 16 }}>
              <div className={s.muted} style={{ marginBottom: 4 }}>Módulos permitidos (separados por vírgula)</div>
              <input className={s.input} style={{ width: '100%', boxSizing: 'border-box' }}
                value={(editing.modules_allowed ?? []).join(', ')}
                onChange={(e) => setEditing((prev) => prev ? { ...prev, modules_allowed: e.target.value.split(',').map((m) => m.trim()).filter(Boolean) } : prev)}
              />
            </div>
            <div className={s.flex} style={{ marginBottom: 16 }}>
              <input type="checkbox" checked={editing.requires_training_approval}
                onChange={(e) => setEditing((prev) => prev ? { ...prev, requires_training_approval: e.target.checked } : prev)} />
              <span>Requer aprovação de treinamento</span>
            </div>
            {error && <div className={s.alertBanner.danger}>{error}</div>}
            <div className={s.flex} style={{ justifyContent: 'flex-end' }}>
              <button className={s.btnGhost} onClick={() => setEditing(null)}>Cancelar</button>
              <button className={s.btnPrimary} onClick={handleSave} disabled={saving}>{saving ? 'Salvando...' : 'Salvar'}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
