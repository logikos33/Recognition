/**
 * Página de câmeras do módulo de qualidade — modo demonstração.
 * Dados mockados com interatividade local (assign, config, setup mode).
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { card, cardTitle, cardHeader } from '../components/quality.css'
import type { QualityCamera } from '../types/quality'

// ─── Mock data ───────────────────────────────────────────────────────────────

interface MockCameraStats {
  nokRate: number
  totalToday: number
  cepAlerts: number
  model: string | null
}

type AssignedCamera = QualityCamera & MockCameraStats

const INITIAL_ASSIGNED: AssignedCamera[] = [
  {
    id: 'cam-a', name: 'Linha A — Frontal', rtsp_url: 'rtsp://192.168.1.101:554/stream1',
    active_module: 'quality', model_quality_id: 'mdl-v3', is_setup_mode: false,
    production_order: 'ORDEM-004', product_type: 'Peça Frontal', reference_snapshot_r2_key: 'snapshots/cam-a.jpg',
    created_at: '2025-01-10T08:00:00Z',
    nokRate: 0.034, totalToday: 1247, cepAlerts: 0, model: 'quality-v3.pt',
  },
  {
    id: 'cam-b', name: 'Linha B — Lateral', rtsp_url: 'rtsp://192.168.1.102:554/stream1',
    active_module: 'quality', model_quality_id: 'mdl-v3', is_setup_mode: false,
    production_order: 'ORDEM-004', product_type: 'Peça Lateral', reference_snapshot_r2_key: null,
    created_at: '2025-01-10T08:00:00Z',
    nokRate: 0.087, totalToday: 892, cepAlerts: 3, model: 'quality-v3.pt',
  },
  {
    id: 'cam-c', name: 'Linha C — Embalagem', rtsp_url: 'rtsp://192.168.1.103:554/stream1',
    active_module: 'quality', model_quality_id: null, is_setup_mode: true,
    production_order: 'ORDEM-007', product_type: null, reference_snapshot_r2_key: null,
    created_at: '2025-02-05T09:30:00Z',
    nokRate: 0.012, totalToday: 2103, cepAlerts: 0, model: null,
  },
]

const INITIAL_AVAILABLE: (QualityCamera & { location: string })[] = [
  {
    id: 'cam-d', name: 'Linha D — Topo', rtsp_url: 'rtsp://192.168.1.104:554/stream1',
    active_module: '', model_quality_id: null, is_setup_mode: false,
    production_order: null, product_type: null, reference_snapshot_r2_key: null,
    created_at: '2025-03-01T10:00:00Z', location: 'Célula 4 — Topo',
  },
  {
    id: 'cam-e', name: 'Saída — Final de Linha', rtsp_url: 'rtsp://192.168.1.105:554/stream1',
    active_module: '', model_quality_id: null, is_setup_mode: false,
    production_order: null, product_type: null, reference_snapshot_r2_key: null,
    created_at: '2025-03-15T14:00:00Z', location: 'Corredor B — Saída',
  },
]

// ─── Componente ──────────────────────────────────────────────────────────────

export function QualityCamerasPage() {
  const navigate = useNavigate()
  const [assigned, setAssigned] = useState<AssignedCamera[]>(INITIAL_ASSIGNED)
  const [available, setAvailable] = useState(INITIAL_AVAILABLE)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editForm, setEditForm] = useState({ production_order: '', product_type: '' })
  const [saving, setSaving] = useState(false)

  function handleAssign(camId: string) {
    const cam = available.find(c => c.id === camId)
    if (!cam) return
    const newAssigned: AssignedCamera = {
      ...cam,
      active_module: 'quality',
      nokRate: 0,
      totalToday: 0,
      cepAlerts: 0,
      model: null,
    }
    setAssigned(prev => [...prev, newAssigned])
    setAvailable(prev => prev.filter(c => c.id !== camId))
  }

  function handleUnassign(camId: string) {
    const cam = assigned.find(c => c.id === camId)
    if (!cam) return
    setAssigned(prev => prev.filter(c => c.id !== camId))
    setAvailable(prev => [...prev, {
      id: cam.id, name: cam.name, rtsp_url: cam.rtsp_url,
      active_module: '', model_quality_id: cam.model_quality_id,
      is_setup_mode: false, production_order: cam.production_order,
      product_type: cam.product_type, reference_snapshot_r2_key: cam.reference_snapshot_r2_key,
      created_at: cam.created_at, location: '',
    }])
    if (editingId === camId) setEditingId(null)
  }

  function handleToggleSetup(camId: string) {
    setAssigned(prev =>
      prev.map(c => c.id === camId ? { ...c, is_setup_mode: !c.is_setup_mode } : c)
    )
  }

  function openEdit(cam: AssignedCamera) {
    setEditingId(cam.id)
    setEditForm({ production_order: cam.production_order ?? '', product_type: cam.product_type ?? '' })
  }

  function handleSaveConfig(camId: string) {
    setSaving(true)
    setTimeout(() => {
      setAssigned(prev =>
        prev.map(c => c.id === camId
          ? { ...c, production_order: editForm.production_order || null, product_type: editForm.product_type || null }
          : c
        )
      )
      setSaving(false)
      setEditingId(null)
    }, 400)
  }

  const inputStyle: React.CSSProperties = {
    padding: '6px 10px', borderRadius: '4px', border: '1px solid #333',
    background: '#0d0d0d', color: '#e0e0e0', fontSize: '13px', width: '160px', outline: 'none',
  }

  return (
    <div style={{ padding: '24px', maxWidth: '960px' }}>

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h2 style={{ fontSize: '18px', fontWeight: 700, marginBottom: '4px' }}>Câmeras de Qualidade</h2>
          <p style={{ fontSize: '12px', color: '#555' }}>Gerencie câmeras atribuídas ao módulo, configure ordens de produção e modelos de inspeção.</p>
        </div>
        <span style={{ fontSize: '10px', color: '#444', fontWeight: 700, padding: '2px 8px', borderRadius: '3px', background: '#111', letterSpacing: '0.5px' }}>
          MODO DEMONSTRAÇÃO
        </span>
      </div>

      {/* Câmeras atribuídas */}
      <section style={{ marginBottom: '32px' }}>
        <div className={cardHeader} style={{ marginBottom: '12px' }}>
          <span className={cardTitle}>Câmeras Ativas ({assigned.length})</span>
        </div>

        {assigned.length === 0 && (
          <div style={{ color: '#555', fontSize: '13px', padding: '24px', textAlign: 'center', border: '1px dashed #222', borderRadius: '6px' }}>
            Nenhuma câmera atribuída ao módulo de qualidade.
          </div>
        )}

        <div style={{ display: 'grid', gap: '12px' }}>
          {assigned.map(cam => {
            const nokColor = cam.nokRate > 0.05 ? '#EF5350' : cam.nokRate > 0.02 ? '#FFB74D' : '#43D186'

            return (
              <div key={cam.id} className={card} style={{ borderLeft: `3px solid ${cam.is_setup_mode ? '#FFB74D' : cam.cepAlerts > 0 ? '#EF5350' : '#1a1a1a'}` }}>
                {/* Linha principal */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px' }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                      <span style={{ fontWeight: 600, fontSize: '14px' }}>{cam.name}</span>
                      {cam.is_setup_mode && (
                        <span style={{ fontSize: '9px', fontWeight: 700, padding: '2px 6px', borderRadius: '2px', background: '#3a2500', color: '#FFB74D', letterSpacing: '0.5px' }}>SETUP</span>
                      )}
                      {cam.cepAlerts > 0 && (
                        <span style={{ fontSize: '9px', fontWeight: 700, padding: '2px 6px', borderRadius: '2px', background: '#3d0f0f', color: '#EF5350', letterSpacing: '0.5px' }}>⚠ {cam.cepAlerts} CEP</span>
                      )}
                    </div>
                    <div style={{ fontSize: '11px', color: '#555', marginBottom: '8px', fontFamily: 'monospace' }}>
                      {cam.rtsp_url}
                    </div>

                    {/* Stats */}
                    <div style={{ display: 'flex', gap: '20px', flexWrap: 'wrap' }}>
                      <div>
                        <span style={{ fontSize: '10px', color: '#444', letterSpacing: '0.5px' }}>TAXA NOK</span>
                        <div style={{ fontSize: '15px', fontWeight: 700, color: nokColor, fontVariantNumeric: 'tabular-nums' }}>
                          {(cam.nokRate * 100).toFixed(1)}%
                        </div>
                      </div>
                      <div>
                        <span style={{ fontSize: '10px', color: '#444', letterSpacing: '0.5px' }}>INSP. HOJE</span>
                        <div style={{ fontSize: '15px', fontWeight: 700, color: '#bbb', fontVariantNumeric: 'tabular-nums' }}>
                          {cam.totalToday.toLocaleString('pt-BR')}
                        </div>
                      </div>
                      <div>
                        <span style={{ fontSize: '10px', color: '#444', letterSpacing: '0.5px' }}>MODELO</span>
                        <div style={{ fontSize: '12px', fontWeight: 600, color: cam.model ? '#4FC3F7' : '#444', marginTop: '2px' }}>
                          {cam.model ?? '— não configurado'}
                        </div>
                      </div>
                      <div>
                        <span style={{ fontSize: '10px', color: '#444', letterSpacing: '0.5px' }}>LOTE / PRODUTO</span>
                        <div style={{ fontSize: '12px', color: '#888', marginTop: '2px' }}>
                          {cam.production_order ?? '—'} · {cam.product_type ?? '—'}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Ações */}
                  <div style={{ display: 'flex', gap: '6px', flexShrink: 0, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                    <button
                      onClick={() => navigate(`/quality/inspections?camera_id=${cam.id}&result=nok`)}
                      title="Ver inspeções NOK desta câmera"
                      style={{ fontSize: '11px', padding: '5px 10px', borderRadius: '4px', border: '1px solid #1a3a5c', background: '#0d1929', color: '#4FC3F7', cursor: 'pointer' }}
                    >
                      ↗ Inspeções
                    </button>
                    <button
                      onClick={() => openEdit(cam)}
                      style={{ fontSize: '11px', padding: '5px 10px', borderRadius: '4px', border: '1px solid #333', background: 'transparent', color: '#ccc', cursor: 'pointer' }}
                    >
                      Config
                    </button>
                    <button
                      onClick={() => handleToggleSetup(cam.id)}
                      style={{ fontSize: '11px', padding: '5px 10px', borderRadius: '4px', border: `1px solid #FFB74D44`, background: cam.is_setup_mode ? '#3a250022' : 'transparent', color: '#FFB74D', cursor: 'pointer' }}
                    >
                      {cam.is_setup_mode ? 'Sair Setup' : 'Setup'}
                    </button>
                    <button
                      onClick={() => handleUnassign(cam.id)}
                      style={{ fontSize: '11px', padding: '5px 10px', borderRadius: '4px', border: '1px solid #EF535044', background: 'transparent', color: '#EF5350', cursor: 'pointer' }}
                    >
                      Remover
                    </button>
                  </div>
                </div>

                {/* Formulário de config inline */}
                {editingId === cam.id && (
                  <div style={{ marginTop: '14px', paddingTop: '14px', borderTop: '1px solid #1e1e1e', display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'flex-end' }}>
                    <div>
                      <label style={{ fontSize: '11px', color: '#555', display: 'block', marginBottom: '4px' }}>Ordem de Produção</label>
                      <input
                        value={editForm.production_order}
                        onChange={e => setEditForm(f => ({ ...f, production_order: e.target.value }))}
                        placeholder="ex: ORDEM-001"
                        style={inputStyle}
                      />
                    </div>
                    <div>
                      <label style={{ fontSize: '11px', color: '#555', display: 'block', marginBottom: '4px' }}>Tipo de Produto</label>
                      <input
                        value={editForm.product_type}
                        onChange={e => setEditForm(f => ({ ...f, product_type: e.target.value }))}
                        placeholder="ex: Peça Frontal"
                        style={inputStyle}
                      />
                    </div>
                    <button
                      onClick={() => handleSaveConfig(cam.id)}
                      disabled={saving}
                      style={{ padding: '7px 14px', borderRadius: '4px', border: 'none', background: saving ? '#111' : '#4FC3F7', color: saving ? '#444' : '#000', fontWeight: 700, fontSize: '12px', cursor: saving ? 'not-allowed' : 'pointer' }}
                    >
                      {saving ? 'Salvando…' : 'Salvar'}
                    </button>
                    <button
                      onClick={() => setEditingId(null)}
                      style={{ padding: '7px 10px', borderRadius: '4px', border: '1px solid #333', background: 'transparent', color: '#666', fontSize: '12px', cursor: 'pointer' }}
                    >
                      Cancelar
                    </button>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </section>

      {/* Câmeras disponíveis */}
      {available.length > 0 && (
        <section>
          <div className={cardHeader} style={{ marginBottom: '12px' }}>
            <span className={cardTitle}>Câmeras Disponíveis ({available.length})</span>
          </div>
          <p style={{ fontSize: '12px', color: '#555', marginBottom: '12px' }}>
            Câmeras da rede disponíveis para adicionar ao módulo de qualidade.
          </p>
          <div style={{ display: 'grid', gap: '8px' }}>
            {available.map(cam => (
              <div
                key={cam.id}
                className={card}
                style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px' }}
              >
                <div>
                  <div style={{ fontWeight: 500, fontSize: '13px', marginBottom: '2px' }}>{cam.name}</div>
                  <div style={{ fontSize: '11px', color: '#555', fontFamily: 'monospace' }}>{cam.rtsp_url}</div>
                </div>
                <button
                  onClick={() => handleAssign(cam.id)}
                  style={{ fontSize: '12px', padding: '5px 14px', borderRadius: '4px', border: 'none', background: '#43D18622', color: '#43D186', fontWeight: 700, cursor: 'pointer', flexShrink: 0 }}
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
