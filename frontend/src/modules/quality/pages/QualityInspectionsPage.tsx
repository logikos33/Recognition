/**
 * Listagem de inspeções com filtros, paginação e drawer de feedback — modo demonstração.
 * Clicar na célula de Feedback abre painel lateral para confirmar/rejeitar inspeção.
 */
import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { ResultBadge, FeedbackBadge, DefectBadge } from '../components/DefectBadge'
import { table, th, td, trHover } from '../components/quality.css'
import type { QualityInspection, QualityCamera, QualityClass } from '../types/quality'

// ─── Mock data ───────────────────────────────────────────────────────────────

const MOCK_CAMERAS: QualityCamera[] = [
  { id: 'cam-a', name: 'Linha A — Frontal',   rtsp_url: '', active_module: 'quality', model_quality_id: null, is_setup_mode: false, production_order: 'ORDEM-004', product_type: null, reference_snapshot_r2_key: null, created_at: '2025-01-01T00:00:00Z' },
  { id: 'cam-b', name: 'Linha B — Lateral',   rtsp_url: '', active_module: 'quality', model_quality_id: null, is_setup_mode: false, production_order: 'ORDEM-004', product_type: null, reference_snapshot_r2_key: null, created_at: '2025-01-01T00:00:00Z' },
  { id: 'cam-c', name: 'Linha C — Embalagem', rtsp_url: '', active_module: 'quality', model_quality_id: null, is_setup_mode: false, production_order: 'ORDEM-007', product_type: null, reference_snapshot_r2_key: null, created_at: '2025-01-01T00:00:00Z' },
]

const MOCK_CLASSES: QualityClass[] = [
  { id: 1, name: 'scratch', label: 'Arranhão',      color: '#EF5350', category: 'nok' },
  { id: 2, name: 'stain',   label: 'Mancha',        color: '#FF8A65', category: 'nok' },
  { id: 3, name: 'deform',  label: 'Deformação',    color: '#FFB74D', category: 'nok' },
  { id: 4, name: 'color',   label: 'Cor incorreta', color: '#AB47BC', category: 'nok' },
  { id: 5, name: 'crack',   label: 'Trinca',        color: '#F44336', category: 'nok' },
]

type Shift = 'morning' | 'afternoon' | 'night'
type FeedbackStatus = 'pending' | 'confirmed' | 'rejected'

function makeInspections(): QualityInspection[] {
  const now = Date.now()
  const HOUR = 3_600_000
  const cameras = MOCK_CAMERAS
  const orders = ['ORDEM-001', 'ORDEM-002', 'ORDEM-003', 'ORDEM-004', 'ORDEM-005', 'ORDEM-006', 'ORDEM-007']
  const feedbacks: FeedbackStatus[] = ['pending', 'pending', 'pending', 'confirmed', 'confirmed', 'rejected']

  return Array.from({ length: 200 }, (_, i) => {
    const cam = cameras[i % cameras.length]
    const isNok = Math.random() < 0.26
    const defClass = isNok ? MOCK_CLASSES[Math.floor(Math.random() * MOCK_CLASSES.length)] : null
    const ageMs = Math.random() * 8 * HOUR
    const ts = new Date(now - ageMs)
    const h = ts.getHours()
    const shift: Shift = h >= 6 && h < 14 ? 'morning' : h >= 14 && h < 22 ? 'afternoon' : 'night'
    const nokRate = isNok ? 0.06 + Math.random() * 0.12 : 0.01 + Math.random() * 0.04

    return {
      id: `insp-${i.toString().padStart(4, '0')}`,
      camera_id: cam.id,
      camera_name: cam.name,
      result: isNok ? 'nok' : 'ok',
      defect_class: defClass?.id ?? null,
      defect_category: defClass?.category ?? null,
      confidence: 0.78 + Math.random() * 0.21,
      evidence_r2_key: null,
      production_order: orders[Math.floor(Math.random() * orders.length)] ?? null,
      product_type: null,
      shift,
      clip_status: 'pending',
      clip_r2_key: null,
      clip_start: null,
      clip_end: null,
      is_first_ok_of_order: false,
      rolling_nok_rate_1h: nokRate,
      rolling_nok_rate_8h: null,
      is_cep_alert: nokRate > 0.1,
      feedback_status: feedbacks[Math.floor(Math.random() * feedbacks.length)] as FeedbackStatus,
      feedback_by: null,
      feedback_at: null,
      feedback_notes: null,
      annotation_status: null,
      created_at: ts.toISOString(),
    } satisfies QualityInspection
  }).sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
}

const ALL_INSPECTIONS = makeInspections()

// ─── Constantes ──────────────────────────────────────────────────────────────

const SHIFT_LABELS: Record<string, string> = {
  morning: 'Manhã', afternoon: 'Tarde', night: 'Noite',
}

const PER_PAGE = 25

// ─── Componente ──────────────────────────────────────────────────────────────

export function QualityInspectionsPage() {
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [feedbackOverrides, setFeedbackOverrides] = useState<Record<string, { status: FeedbackStatus; notes: string }>>({})
  const [selected, setSelected] = useState<QualityInspection | null>(null)
  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)

  const [filters, setFilters] = useState({
    camera_id: '',
    result: '',
    feedback_status: '',
    shift: '',
    from: '',
    to: '',
    production_order: '',
  })

  function setFilter(key: string, value: string) {
    setFilters(f => ({ ...f, [key]: value }))
    setPage(1)
  }

  function getStatus(insp: QualityInspection): FeedbackStatus {
    return feedbackOverrides[insp.id]?.status ?? insp.feedback_status
  }

  function openDrawer(e: React.MouseEvent, insp: QualityInspection) {
    e.stopPropagation()
    setSelected(insp)
    setNotes(feedbackOverrides[insp.id]?.notes ?? '')
  }

  function closeDrawer() {
    if (saving) return
    setSelected(null)
  }

  function saveFeedback(status: FeedbackStatus) {
    if (!selected || saving) return
    setSaving(true)
    setTimeout(() => {
      setFeedbackOverrides(prev => ({
        ...prev,
        [selected.id]: { status, notes },
      }))
      setSaving(false)
      setSelected(null)
    }, 500)
  }

  // Filtragem client-side
  const filtered = useMemo(() => {
    return ALL_INSPECTIONS.filter(insp => {
      const effectiveStatus = feedbackOverrides[insp.id]?.status ?? insp.feedback_status
      if (filters.camera_id && insp.camera_id !== filters.camera_id) return false
      if (filters.result && insp.result !== filters.result) return false
      if (filters.feedback_status && effectiveStatus !== filters.feedback_status) return false
      if (filters.shift && insp.shift !== filters.shift) return false
      if (filters.production_order && !(insp.production_order ?? '').toLowerCase().includes(filters.production_order.toLowerCase())) return false
      if (filters.from) {
        const fromTs = new Date(filters.from).getTime()
        if (new Date(insp.created_at).getTime() < fromTs) return false
      }
      if (filters.to) {
        const toTs = new Date(filters.to).getTime() + 86_400_000
        if (new Date(insp.created_at).getTime() > toTs) return false
      }
      return true
    })
  }, [filters, feedbackOverrides])

  const totalPages = Math.ceil(filtered.length / PER_PAGE)
  const inspections = filtered.slice((page - 1) * PER_PAGE, page * PER_PAGE)

  const selectStyle: React.CSSProperties = {
    padding: '6px 10px', borderRadius: '4px', border: '1px solid #333',
    background: '#111', color: '#ccc', fontSize: '12px',
  }

  return (
    <div style={{ padding: '24px', position: 'relative' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <h2 style={{ fontSize: '18px', fontWeight: 700 }}>Inspeções</h2>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <span style={{ fontSize: '13px', color: '#888' }}>{filtered.length} registros</span>
          <span style={{ fontSize: '10px', color: '#444', fontWeight: 700, padding: '2px 8px', borderRadius: '3px', background: '#111', letterSpacing: '0.5px' }}>MODO DEMONSTRAÇÃO</span>
        </div>
      </div>

      {/* Filtros */}
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '16px' }}>
        <select id="filter-camera" name="camera_id" value={filters.camera_id} onChange={e => setFilter('camera_id', e.target.value)} style={selectStyle}>
          <option value="">Todas as câmeras</option>
          {MOCK_CAMERAS.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>

        <select id="filter-result" name="result" value={filters.result} onChange={e => setFilter('result', e.target.value)} style={selectStyle}>
          <option value="">OK + NOK</option>
          <option value="ok">Apenas OK</option>
          <option value="nok">Apenas NOK</option>
        </select>

        <select id="filter-feedback" name="feedback_status" value={filters.feedback_status} onChange={e => setFilter('feedback_status', e.target.value)} style={selectStyle}>
          <option value="">Todos feedbacks</option>
          <option value="pending">Pendente</option>
          <option value="confirmed">Confirmado</option>
          <option value="rejected">Rejeitado</option>
        </select>

        <select id="filter-shift" name="shift" value={filters.shift} onChange={e => setFilter('shift', e.target.value)} style={selectStyle}>
          <option value="">Todos turnos</option>
          <option value="morning">Manhã</option>
          <option value="afternoon">Tarde</option>
          <option value="night">Noite</option>
        </select>

        <input
          id="filter-order"
          name="production_order"
          type="text"
          placeholder="Ordem de produção"
          value={filters.production_order}
          onChange={e => setFilter('production_order', e.target.value)}
          style={{ ...selectStyle, width: '160px' }}
        />

        <input
          id="filter-date-from"
          name="from"
          type="date"
          value={filters.from}
          onChange={e => setFilter('from', e.target.value)}
          style={selectStyle}
        />
        <input
          id="filter-date-to"
          name="to"
          type="date"
          value={filters.to}
          onChange={e => setFilter('to', e.target.value)}
          style={selectStyle}
        />

        <button
          onClick={() => { setFilters({ camera_id: '', result: '', feedback_status: '', shift: '', from: '', to: '', production_order: '' }); setPage(1) }}
          style={{ ...selectStyle, cursor: 'pointer', color: '#888' }}
        >
          Limpar
        </button>
      </div>

      {/* Tabela */}
      <div style={{ overflowX: 'auto' }}>
        <table className={table}>
          <thead>
            <tr>
              <th className={th} title="Data e hora exatas em que a inspeção foi registrada pelo sistema" style={{ cursor: 'help', textDecoration: 'underline dotted #555', textUnderlineOffset: '3px' }}>Data/Hora</th>
              <th className={th} title="Câmera que capturou a imagem desta inspeção" style={{ cursor: 'help', textDecoration: 'underline dotted #555', textUnderlineOffset: '3px' }}>Câmera</th>
              <th className={th} title="Resultado da análise: OK indica produto aprovado, NOK indica defeito detectado" style={{ cursor: 'help', textDecoration: 'underline dotted #555', textUnderlineOffset: '3px' }}>Resultado</th>
              <th className={th} title="Tipo de defeito identificado pelo modelo de visão computacional (ex.: Arranhão, Mancha, Deformação)" style={{ cursor: 'help', textDecoration: 'underline dotted #555', textUnderlineOffset: '3px' }}>Defeito</th>
              <th className={th} title="Confiança do modelo na detecção — valores abaixo de 80% merecem revisão manual" style={{ cursor: 'help', textDecoration: 'underline dotted #555', textUnderlineOffset: '3px' }}>Conf.</th>
              <th className={th} title="Turno de produção em que a inspeção ocorreu: Manhã (06h–14h), Tarde (14h–22h) ou Noite (22h–06h)" style={{ cursor: 'help', textDecoration: 'underline dotted #555', textUnderlineOffset: '3px' }}>Turno</th>
              <th className={th} title="Número da ordem de produção associada ao lote inspecionado" style={{ cursor: 'help', textDecoration: 'underline dotted #555', textUnderlineOffset: '3px' }}>Lote</th>
              <th className={th} title="Status de revisão humana: Pendente aguarda análise, Confirmado valida o defeito, Falso Positivo indica detecção incorreta — clique para registrar" style={{ cursor: 'help', textDecoration: 'underline dotted #555', textUnderlineOffset: '3px' }}>Feedback ↗</th>
              <th className={th} title="Taxa de produtos NOK na última hora para esta câmera — valores acima de 10% são destacados em vermelho como alerta" style={{ cursor: 'help', textDecoration: 'underline dotted #555', textUnderlineOffset: '3px' }}>NOK/1h</th>
            </tr>
          </thead>
          <tbody>
            {inspections.length === 0 ? (
              <tr>
                <td className={td} colSpan={9} style={{ textAlign: 'center', color: '#888' }}>Nenhuma inspeção encontrada.</td>
              </tr>
            ) : (
              inspections.map(insp => {
                const cls = MOCK_CLASSES.find(c => c.id === insp.defect_class)
                const status = getStatus(insp)
                return (
                  <tr
                    key={insp.id}
                    className={trHover}
                    onClick={() => navigate(`/quality/inspections/${insp.id}`)}
                  >
                    <td className={td} style={{ fontSize: '12px', color: '#888', whiteSpace: 'nowrap' }}>
                      {new Date(insp.created_at).toLocaleString('pt-BR')}
                    </td>
                    <td className={td} style={{ fontSize: '12px' }}>{insp.camera_name ?? '—'}</td>
                    <td className={td}><ResultBadge result={insp.result} /></td>
                    <td className={td}>
                      {cls ? <DefectBadge classId={cls.id} label={cls.label} color={cls.color} /> : '—'}
                    </td>
                    <td className={td} style={{ fontSize: '12px' }}>{(insp.confidence * 100).toFixed(0)}%</td>
                    <td className={td} style={{ fontSize: '12px' }}>{SHIFT_LABELS[insp.shift] ?? insp.shift}</td>
                    <td className={td} style={{ fontSize: '12px', color: '#888' }}>{insp.production_order ?? '—'}</td>
                    {/* Feedback — clique abre drawer, não navega */}
                    <td
                      className={td}
                      onClick={e => openDrawer(e, insp)}
                      style={{ cursor: 'pointer' }}
                      title="Clique para registrar feedback"
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <FeedbackBadge status={status} />
                        {status === 'pending' && (
                          <span style={{ fontSize: '9px', color: '#555' }}>▾</span>
                        )}
                      </div>
                    </td>
                    <td className={td} style={{ fontSize: '12px', color: (insp.rolling_nok_rate_1h ?? 0) > 0.1 ? '#EF5350' : '#ccc' }}>
                      {insp.rolling_nok_rate_1h !== null ? `${((insp.rolling_nok_rate_1h ?? 0) * 100).toFixed(1)}%` : '—'}
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Paginação */}
      {totalPages > 1 && (
        <div style={{ display: 'flex', gap: '8px', justifyContent: 'center', marginTop: '16px' }}>
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            style={{ padding: '6px 14px', borderRadius: '4px', border: '1px solid #333', background: 'transparent', color: page === 1 ? '#555' : '#ccc', cursor: page === 1 ? 'not-allowed' : 'pointer', fontSize: '12px' }}
          >
            ← Anterior
          </button>
          <span style={{ padding: '6px 14px', fontSize: '12px', color: '#888' }}>
            {page} / {totalPages}
          </span>
          <button
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            style={{ padding: '6px 14px', borderRadius: '4px', border: '1px solid #333', background: 'transparent', color: page === totalPages ? '#555' : '#ccc', cursor: page === totalPages ? 'not-allowed' : 'pointer', fontSize: '12px' }}
          >
            Próxima →
          </button>
        </div>
      )}

      {/* ── Drawer de Feedback ─────────────────────────────────────────────── */}
      {selected && (
        <>
          {/* Backdrop */}
          <div
            onClick={closeDrawer}
            style={{
              position: 'fixed', inset: 0,
              background: 'rgba(0,0,0,0.5)',
              zIndex: 40,
            }}
          />

          {/* Painel */}
          <div style={{
            position: 'fixed', top: 0, right: 0,
            height: '100vh', width: '320px',
            background: '#0d0d0d',
            borderLeft: '1px solid #1e1e1e',
            zIndex: 50,
            display: 'flex', flexDirection: 'column',
            padding: '20px',
            boxShadow: '-8px 0 32px rgba(0,0,0,0.6)',
          }}>
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <span style={{ fontSize: '13px', fontWeight: 700, color: '#fff', letterSpacing: '0.3px' }}>
                Feedback de Inspeção
              </span>
              <button
                onClick={closeDrawer}
                style={{ background: 'none', border: 'none', color: '#666', cursor: 'pointer', fontSize: '20px', lineHeight: 1, padding: '0 4px' }}
              >
                ×
              </button>
            </div>

            {/* Contexto da inspeção */}
            <div style={{ background: '#111', borderRadius: '6px', padding: '14px', marginBottom: '18px', border: '1px solid #1e1e1e' }}>
              <div style={{ fontSize: '10px', color: '#444', letterSpacing: '0.8px', marginBottom: '8px' }}>INSPEÇÃO</div>
              <div style={{ fontSize: '12px', fontWeight: 600, color: '#ccc', marginBottom: '3px' }}>{selected.camera_name}</div>
              <div style={{ fontSize: '11px', color: '#666', marginBottom: '10px' }}>
                {SHIFT_LABELS[selected.shift]} · {new Date(selected.created_at).toLocaleString('pt-BR')}
              </div>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                <ResultBadge result={selected.result} />
                {(() => {
                  const cls = MOCK_CLASSES.find(c => c.id === selected.defect_class)
                  return cls ? <DefectBadge classId={cls.id} label={cls.label} color={cls.color} /> : null
                })()}
                <span style={{ fontSize: '11px', color: '#666' }}>
                  Conf. {(selected.confidence * 100).toFixed(0)}%
                </span>
              </div>
            </div>

            {/* Status atual */}
            <div style={{ marginBottom: '16px' }}>
              <div style={{ fontSize: '10px', color: '#444', letterSpacing: '0.8px', marginBottom: '6px' }}>STATUS ATUAL</div>
              <FeedbackBadge status={getStatus(selected)} />
            </div>

            {/* Notas */}
            <div style={{ marginBottom: '20px' }}>
              <div style={{ fontSize: '10px', color: '#444', letterSpacing: '0.8px', marginBottom: '6px' }}>NOTAS (OPCIONAL)</div>
              <textarea
                id="feedback-notes"
                name="notes"
                value={notes}
                onChange={e => setNotes(e.target.value)}
                placeholder="Observações sobre esta inspeção…"
                rows={3}
                style={{
                  width: '100%', boxSizing: 'border-box',
                  background: '#111', border: '1px solid #2a2a2a',
                  borderRadius: '4px', color: '#ccc',
                  fontSize: '12px', padding: '8px',
                  resize: 'vertical', outline: 'none',
                  fontFamily: 'inherit',
                }}
              />
            </div>

            <div style={{ flex: 1 }} />

            {/* Ações */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <button
                onClick={() => saveFeedback('confirmed')}
                disabled={saving}
                style={{
                  padding: '11px', borderRadius: '6px', border: 'none',
                  background: saving ? '#111' : '#0f2e1a',
                  color: saving ? '#444' : '#43D186',
                  fontWeight: 700, fontSize: '13px',
                  cursor: saving ? 'not-allowed' : 'pointer',
                  transition: 'background 0.15s',
                }}
              >
                {saving ? 'Salvando…' : '✓ Confirmar Defeito'}
              </button>
              <button
                onClick={() => saveFeedback('rejected')}
                disabled={saving}
                style={{
                  padding: '11px', borderRadius: '6px', border: 'none',
                  background: saving ? '#111' : '#2e0f0f',
                  color: saving ? '#444' : '#EF5350',
                  fontWeight: 700, fontSize: '13px',
                  cursor: saving ? 'not-allowed' : 'pointer',
                  transition: 'background 0.15s',
                }}
              >
                {saving ? 'Salvando…' : '✗ Falso Positivo'}
              </button>
              <button
                onClick={closeDrawer}
                disabled={saving}
                style={{
                  padding: '8px', borderRadius: '6px',
                  border: '1px solid #2a2a2a', background: 'none',
                  color: '#666', fontSize: '12px',
                  cursor: saving ? 'not-allowed' : 'pointer',
                }}
              >
                Cancelar
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
