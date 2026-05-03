import { useState, useEffect, useCallback } from 'react'
import { qualityService } from '../services/qualityService'
import type { QualityCamera } from '../types/quality'
import * as s from './QualityCamerasPage.css'

export function QualityCamerasPage() {
  const [assigned, setAssigned] = useState<QualityCamera[]>([])
  const [available, setAvailable] = useState<QualityCamera[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editForm, setEditForm] = useState({ production_order: '', product_type: '' })
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [assignedRes, availableRes] = await Promise.all([
        qualityService.getCameras(),
        qualityService.getAvailableCameras(),
      ])
      setAssigned(assignedRes.data?.cameras ?? [])
      setAvailable(availableRes.data?.cameras ?? [])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao carregar câmeras')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  async function handleAssign(cameraId: string) {
    try {
      await qualityService.assignCamera(cameraId)
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao atribuir câmera')
    }
  }

  async function handleUnassign(cameraId: string) {
    try {
      await qualityService.unassignCamera(cameraId)
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao remover câmera')
    }
  }

  function startEdit(cam: QualityCamera) {
    setEditingId(cam.id)
    setEditForm({
      production_order: cam.production_order ?? '',
      product_type: cam.product_type ?? '',
    })
  }

  async function saveEdit(cameraId: string) {
    setSaving(true)
    try {
      await qualityService.updateCameraConfig(cameraId, editForm)
      setEditingId(null)
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao salvar configuração')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <div className={s.loadingText}>Carregando câmeras...</div>
  }

  return (
    <div className={s.pageWrapper}>
      <div className={s.pageHeader}>
        <h1 className={s.pageTitle}>Câmeras — Módulo Qualidade</h1>
        <button onClick={load} className={s.refreshBtn}>↺ Atualizar</button>
      </div>

      {error && <div className={s.errorBanner}>{error}</div>}

      {/* Câmeras atribuídas ao módulo Qualidade */}
      <section className={s.section}>
        <h2 className={s.sectionTitle}>Atribuídas ao módulo ({assigned.length})</h2>

        {assigned.length === 0 && (
          <div className={s.emptyText}>
            Nenhuma câmera atribuída. Adicione uma câmera disponível abaixo.
          </div>
        )}

        <div className={s.grid}>
          {assigned.map(cam => (
            <div key={cam.id} className={s.cameraCard}>
              <div className={s.cameraCardHeader}>
                <span className={s.cameraName}>{cam.name}</span>
                <div className={s.badgeRow}>
                  {cam.is_setup_mode && <span className={s.badgeSetup}>Setup</span>}
                  <span className={s.badgeActive}>Ativa</span>
                </div>
              </div>

              {editingId === cam.id ? (
                <div className={s.editStack}>
                  <input
                    id={`edit-op-${cam.id}`}
                    name="production_order"
                    className={s.editInput}
                    placeholder="Ordem de produção"
                    value={editForm.production_order}
                    onChange={e => setEditForm(f => ({ ...f, production_order: e.target.value }))}
                  />
                  <input
                    id={`edit-type-${cam.id}`}
                    name="product_type"
                    className={s.editInput}
                    placeholder="Tipo de peça"
                    value={editForm.product_type}
                    onChange={e => setEditForm(f => ({ ...f, product_type: e.target.value }))}
                  />
                  <div className={s.editActions}>
                    <button onClick={() => saveEdit(cam.id)} disabled={saving} className={s.saveBtn}>
                      {saving ? 'Salvando...' : 'Salvar'}
                    </button>
                    <button onClick={() => setEditingId(null)} className={s.cancelBtn}>
                      Cancelar
                    </button>
                  </div>
                </div>
              ) : (
                <div className={s.metaText}>
                  <div>OP: {cam.production_order ?? '—'}</div>
                  <div>Peça: {cam.product_type ?? '—'}</div>
                  <div>Modelo: {cam.model_quality_id ?? '—'}</div>
                </div>
              )}

              <div className={s.cardActions}>
                <button onClick={() => startEdit(cam)} className={s.editConfigBtn}>
                  Editar config
                </button>
                <button onClick={() => handleUnassign(cam.id)} className={s.removeBtn}>
                  Remover
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Câmeras disponíveis para atribuição */}
      {available.length > 0 && (
        <section className={s.section}>
          <h2 className={s.sectionTitle}>Disponíveis para adicionar ({available.length})</h2>
          <div className={s.availableGrid}>
            {available.map(cam => (
              <div key={cam.id} className={s.availableCard}>
                <div className={s.availableName}>{cam.name}</div>
                <button onClick={() => handleAssign(cam.id)} className={s.addBtn}>
                  + Adicionar
                </button>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
