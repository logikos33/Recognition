import { useState, useEffect, useCallback } from 'react'
import { qualityService } from '../services/qualityService'
import type { QualityCamera } from '../types/quality'

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
    return (
      <div style={{ padding: 24, color: '#6B7280' }}>Carregando câmeras...</div>
    )
  }

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, color: '#111827', margin: 0 }}>
          Câmeras — Módulo Qualidade
        </h1>
        <button
          onClick={load}
          style={{
            padding: '6px 14px', borderRadius: 8,
            border: '1px solid #D1D5DB', background: '#fff',
            cursor: 'pointer', fontSize: 13, color: '#374151',
          }}
        >
          ↺ Atualizar
        </button>
      </div>

      {error && (
        <div style={{
          padding: '12px 16px', background: '#FEF2F2',
          border: '1px solid #FECACA', borderRadius: 8, marginBottom: 20, color: '#DC2626',
        }}>
          {error}
        </div>
      )}

      {/* Câmeras atribuídas ao módulo Qualidade */}
      <section style={{ marginBottom: 36 }}>
        <h2 style={{ fontSize: 16, fontWeight: 600, color: '#374151', marginBottom: 14 }}>
          Atribuídas ao módulo ({assigned.length})
        </h2>

        {assigned.length === 0 && (
          <div style={{ color: '#9CA3AF', padding: '20px 0', fontSize: 14 }}>
            Nenhuma câmera atribuída. Adicione uma câmera disponível abaixo.
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 16 }}>
          {assigned.map(cam => (
            <div key={cam.id} style={{
              border: '1px solid #E5E7EB', borderRadius: 12,
              padding: 16, background: '#fff',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
                <span style={{ fontWeight: 600, fontSize: 14, color: '#111827' }}>{cam.name}</span>
                <div style={{ display: 'flex', gap: 6 }}>
                  {cam.is_setup_mode && (
                    <span style={{
                      fontSize: 11, padding: '2px 8px', borderRadius: 20,
                      background: '#FEF3C7', color: '#D97706', fontWeight: 600,
                    }}>
                      Setup
                    </span>
                  )}
                  <span style={{
                    fontSize: 11, padding: '2px 8px', borderRadius: 20,
                    background: '#ECFDF5', color: '#16A34A', fontWeight: 600,
                  }}>
                    Ativa
                  </span>
                </div>
              </div>

              {editingId === cam.id ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 10 }}>
                  <input
                    placeholder="Ordem de produção"
                    value={editForm.production_order}
                    onChange={e => setEditForm(f => ({ ...f, production_order: e.target.value }))}
                    style={{
                      padding: '7px 10px', borderRadius: 6, border: '1px solid #D1D5DB',
                      fontSize: 13,
                    }}
                  />
                  <input
                    placeholder="Tipo de peça"
                    value={editForm.product_type}
                    onChange={e => setEditForm(f => ({ ...f, product_type: e.target.value }))}
                    style={{
                      padding: '7px 10px', borderRadius: 6, border: '1px solid #D1D5DB',
                      fontSize: 13,
                    }}
                  />
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button
                      onClick={() => saveEdit(cam.id)}
                      disabled={saving}
                      style={{
                        flex: 1, padding: '7px 0', borderRadius: 6,
                        border: 'none', background: '#2563EB', color: '#fff',
                        cursor: saving ? 'not-allowed' : 'pointer', fontSize: 13,
                      }}
                    >
                      {saving ? 'Salvando...' : 'Salvar'}
                    </button>
                    <button
                      onClick={() => setEditingId(null)}
                      style={{
                        padding: '7px 14px', borderRadius: 6,
                        border: '1px solid #D1D5DB', background: '#fff',
                        cursor: 'pointer', fontSize: 13,
                      }}
                    >
                      Cancelar
                    </button>
                  </div>
                </div>
              ) : (
                <div style={{ fontSize: 13, color: '#6B7280', marginBottom: 10 }}>
                  <div>OP: {cam.production_order ?? '—'}</div>
                  <div>Peça: {cam.product_type ?? '—'}</div>
                  <div>Modelo: {cam.model_quality_id ?? '—'}</div>
                </div>
              )}

              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  onClick={() => startEdit(cam)}
                  style={{
                    flex: 1, padding: '6px 0', borderRadius: 6,
                    border: '1px solid #D1D5DB', background: '#fff',
                    cursor: 'pointer', fontSize: 12, color: '#374151',
                  }}
                >
                  Editar config
                </button>
                <button
                  onClick={() => handleUnassign(cam.id)}
                  style={{
                    padding: '6px 12px', borderRadius: 6,
                    border: '1px solid #FECACA', background: '#FEF2F2',
                    cursor: 'pointer', fontSize: 12, color: '#DC2626',
                  }}
                >
                  Remover
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Câmeras disponíveis para atribuição */}
      {available.length > 0 && (
        <section>
          <h2 style={{ fontSize: 16, fontWeight: 600, color: '#374151', marginBottom: 14 }}>
            Disponíveis para adicionar ({available.length})
          </h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 12 }}>
            {available.map(cam => (
              <div key={cam.id} style={{
                border: '1px solid #E5E7EB', borderRadius: 10,
                padding: '14px 16px', background: '#F9FAFB',
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 13, color: '#374151' }}>{cam.name}</div>
                </div>
                <button
                  onClick={() => handleAssign(cam.id)}
                  style={{
                    padding: '6px 14px', borderRadius: 6,
                    border: '1px solid #2563EB', background: '#EFF6FF',
                    cursor: 'pointer', fontSize: 12, color: '#2563EB', fontWeight: 600,
                  }}
                >
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
