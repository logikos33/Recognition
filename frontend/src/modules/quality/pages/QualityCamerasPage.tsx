/**
 * Página de câmeras do módulo de qualidade.
 * Exibe câmeras atribuídas com config rápida + câmeras disponíveis para adicionar.
 */
import { useState, useEffect } from 'react'
import { qualityService } from '../services/qualityService'
import { card, cardTitle, cardHeader } from '../components/quality.css'
import type { QualityCamera } from '../types/quality'

export function QualityCamerasPage() {
  const [assigned, setAssigned] = useState<QualityCamera[]>([])
  const [available, setAvailable] = useState<QualityCamera[]>([])
  const [loading, setLoading] = useState(true)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editForm, setEditForm] = useState<{ production_order: string; product_type: string }>({
    production_order: '',
    product_type: '',
  })

  useEffect(() => {
    async function load() {
      try {
        const [assignedRes, availableRes] = await Promise.all([
          qualityService.getCameras(),
          qualityService.getAvailableCameras(),
        ])
        setAssigned(assignedRes.data.cameras)
        setAvailable(availableRes.data.cameras)
      } catch {
        // silent — tela vazia
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  async function handleAssign(cameraId: string) {
    try {
      const res = await qualityService.assignCamera(cameraId)
      setAssigned(prev => [...prev, res.data.camera])
      setAvailable(prev => prev.filter(c => c.id !== cameraId))
    } catch { /* silent */ }
  }

  async function handleUnassign(cameraId: string) {
    try {
      await qualityService.unassignCamera(cameraId)
      const removed = assigned.find(c => c.id === cameraId)
      setAssigned(prev => prev.filter(c => c.id !== cameraId))
      if (removed) setAvailable(prev => [...prev, removed])
    } catch { /* silent */ }
  }

  async function handleToggleSetup(cameraId: string) {
    try {
      const res = await qualityService.toggleSetupMode(cameraId)
      setAssigned(prev =>
        prev.map(c => c.id === cameraId ? { ...c, is_setup_mode: res.data.is_setup_mode } : c)
      )
    } catch { /* silent */ }
  }

  async function handleSaveConfig(cameraId: string) {
    try {
      await qualityService.updateCameraConfig(cameraId, editForm)
      setAssigned(prev =>
        prev.map(c => c.id === cameraId
          ? { ...c, production_order: editForm.production_order, product_type: editForm.product_type }
          : c
        )
      )
      setEditingId(null)
    } catch { /* silent */ }
  }

  if (loading) return <div style={{ padding: '32px', color: '#888' }}>Carregando câmeras…</div>

  return (
    <div style={{ padding: '24px', maxWidth: '900px' }}>
      <h2 style={{ marginBottom: '20px', fontSize: '18px', fontWeight: 700 }}>Câmeras de Qualidade</h2>

      {/* Câmeras atribuídas */}
      <section style={{ marginBottom: '32px' }}>
        <div className={cardHeader}>
          <span className={cardTitle}>Câmeras Ativas ({assigned.length})</span>
        </div>

        {assigned.length === 0 && (
          <div style={{ color: '#888', fontSize: '13px', padding: '16px 0' }}>
            Nenhuma câmera atribuída ao módulo de qualidade.
          </div>
        )}

        <div style={{ display: 'grid', gap: '12px' }}>
          {assigned.map(cam => (
            <div key={cam.id} className={card}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <div style={{ fontWeight: 600, marginBottom: '4px' }}>{cam.name}</div>
                  <div style={{ fontSize: '12px', color: '#888' }}>
                    Lote: {cam.production_order || '—'} · Produto: {cam.product_type || '—'}
                  </div>
                  {cam.is_setup_mode && (
                    <div style={{ fontSize: '11px', color: '#FFB74D', marginTop: '4px', fontWeight: 600 }}>
                      MODO CONFIGURAÇÃO ATIVO
                    </div>
                  )}
                </div>
                <div style={{ display: 'flex', gap: '8px', flexShrink: 0 }}>
                  <button
                    onClick={() => {
                      setEditingId(cam.id)
                      setEditForm({ production_order: cam.production_order ?? '', product_type: cam.product_type ?? '' })
                    }}
                    style={{ fontSize: '12px', padding: '4px 10px', borderRadius: '4px', border: '1px solid #444', background: 'transparent', color: '#ccc', cursor: 'pointer' }}
                  >
                    Config
                  </button>
                  <button
                    onClick={() => handleToggleSetup(cam.id)}
                    style={{ fontSize: '12px', padding: '4px 10px', borderRadius: '4px', border: '1px solid #444', background: cam.is_setup_mode ? '#FFB74D22' : 'transparent', color: '#FFB74D', cursor: 'pointer' }}
                  >
                    {cam.is_setup_mode ? 'Sair Setup' : 'Setup'}
                  </button>
                  <button
                    onClick={() => handleUnassign(cam.id)}
                    style={{ fontSize: '12px', padding: '4px 10px', borderRadius: '4px', border: '1px solid #EF535044', background: 'transparent', color: '#EF5350', cursor: 'pointer' }}
                  >
                    Remover
                  </button>
                </div>
              </div>

              {editingId === cam.id && (
                <div style={{ marginTop: '12px', display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'flex-end' }}>
                  <div>
                    <label style={{ fontSize: '11px', color: '#888', display: 'block', marginBottom: '4px' }}>Ordem de Produção</label>
                    <input
                      value={editForm.production_order}
                      onChange={e => setEditForm(f => ({ ...f, production_order: e.target.value }))}
                      style={{ padding: '6px 10px', borderRadius: '4px', border: '1px solid #444', background: '#111', color: '#fff', fontSize: '13px', width: '160px' }}
                      placeholder="ex: OP-2024-001"
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: '11px', color: '#888', display: 'block', marginBottom: '4px' }}>Tipo de Produto</label>
                    <input
                      value={editForm.product_type}
                      onChange={e => setEditForm(f => ({ ...f, product_type: e.target.value }))}
                      style={{ padding: '6px 10px', borderRadius: '4px', border: '1px solid #444', background: '#111', color: '#fff', fontSize: '13px', width: '160px' }}
                      placeholder="ex: Peça A"
                    />
                  </div>
                  <button
                    onClick={() => handleSaveConfig(cam.id)}
                    style={{ padding: '6px 12px', borderRadius: '4px', border: 'none', background: '#4FC3F7', color: '#000', fontWeight: 600, fontSize: '12px', cursor: 'pointer' }}
                  >
                    Salvar
                  </button>
                  <button
                    onClick={() => setEditingId(null)}
                    style={{ padding: '6px 10px', borderRadius: '4px', border: '1px solid #444', background: 'transparent', color: '#888', fontSize: '12px', cursor: 'pointer' }}
                  >
                    Cancelar
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* Câmeras disponíveis */}
      {available.length > 0 && (
        <section>
          <div className={cardHeader}>
            <span className={cardTitle}>Câmeras Disponíveis ({available.length})</span>
          </div>
          <div style={{ display: 'grid', gap: '8px' }}>
            {available.map(cam => (
              <div
                key={cam.id}
                className={card}
                style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
              >
                <span style={{ fontWeight: 500, fontSize: '14px' }}>{cam.name}</span>
                <button
                  onClick={() => handleAssign(cam.id)}
                  style={{ fontSize: '12px', padding: '4px 12px', borderRadius: '4px', border: 'none', background: '#43D18622', color: '#43D186', fontWeight: 600, cursor: 'pointer' }}
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
