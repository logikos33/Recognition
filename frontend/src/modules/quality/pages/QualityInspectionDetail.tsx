/**
 * Detalhe de inspeção de qualidade.
 * Coluna esquerda: foto evidência + clip player (sem download).
 * Coluna direita: informações + feedback + botão "Anotar frames".
 */
import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { qualityService } from '../services/qualityService'
import { ClipPlayer } from '../components/ClipPlayer'
import { ResultBadge, FeedbackBadge, DefectBadge } from '../components/DefectBadge'
import { useEvidenceUrl } from '../hooks/useClipPlayer'
import { card } from '../components/quality.css'
import type { QualityInspection, QualityClass } from '../types/quality'

export function QualityInspectionDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [inspection, setInspection] = useState<QualityInspection | null>(null)
  const [classes, setClasses] = useState<QualityClass[]>([])
  const [loading, setLoading] = useState(true)
  const [feedbackNote, setFeedbackNote] = useState('')
  const [submittingFeedback, setSubmittingFeedback] = useState<'confirmed' | 'rejected' | null>(null)
  const [preparingAnnotation, setPreparingAnnotation] = useState(false)

  const { url: evidenceUrl } = useEvidenceUrl(
    inspection?.evidence_r2_key ? id ?? null : null
  )

  useEffect(() => {
    if (!id) return
    Promise.all([
      qualityService.getInspection(id),
      qualityService.getClasses(),
    ])
      .then(([inspRes, clsRes]) => {
        setInspection(inspRes.data.inspection)
        setClasses(clsRes.data.classes)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [id])

  async function handleFeedback(status: 'confirmed' | 'rejected') {
    if (!id) return
    setSubmittingFeedback(status)
    try {
      const res = await qualityService.submitFeedback(id, { status, notes: feedbackNote })
      setInspection(res.data.inspection)
    } catch { /* silent */ }
    setSubmittingFeedback(null)
  }

  async function handlePrepareAnnotation() {
    if (!id) return
    setPreparingAnnotation(true)
    try {
      await qualityService.prepareAnnotation(id)
      navigate(`/quality/inspections/${id}/annotate`)
    } catch {
      alert('Erro ao preparar frames para anotação.')
      setPreparingAnnotation(false)
    }
  }

  if (loading) return <div style={{ padding: '32px', color: '#888' }}>Carregando inspeção…</div>
  if (!inspection) return <div style={{ padding: '32px', color: '#EF5350' }}>Inspeção não encontrada.</div>

  const defectClass = classes.find(c => c.id === inspection.defect_class)

  return (
    <div style={{ padding: '24px', display: 'grid', gridTemplateColumns: '1fr 340px', gap: '24px', maxWidth: '1100px' }}>
      {/* Coluna esquerda: media */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* Foto de evidência */}
        {evidenceUrl && (
          <div>
            <div style={{ fontSize: '12px', color: '#888', marginBottom: '6px' }}>Evidência</div>
            {/* onContextMenu previne menu de contexto com opção de download */}
            <img
              src={evidenceUrl}
              alt="Evidência da inspeção"
              onContextMenu={e => e.preventDefault()}
              style={{ width: '100%', borderRadius: '8px', display: 'block', border: '1px solid #222' }}
            />
          </div>
        )}

        {/* Clip de vídeo */}
        <div>
          <div style={{ fontSize: '12px', color: '#888', marginBottom: '6px' }}>Clip (±30s)</div>
          <ClipPlayer
            inspectionId={inspection.id}
            clipStatus={inspection.clip_status}
          />
        </div>
      </div>

      {/* Coluna direita: detalhes */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* Header */}
        <div className={card}>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '12px' }}>
            <ResultBadge result={inspection.result} />
            <FeedbackBadge status={inspection.feedback_status} />
            {inspection.is_cep_alert && (
              <span style={{ fontSize: '11px', color: '#EF5350', fontWeight: 600 }}>⚠ CEP</span>
            )}
          </div>

          {defectClass && (
            <div style={{ marginBottom: '12px' }}>
              <DefectBadge classId={defectClass.id} label={defectClass.label} color={defectClass.color} />
            </div>
          )}

          <table style={{ fontSize: '12px', width: '100%', borderCollapse: 'collapse' }}>
            <tbody>
              {[
                ['Câmera', inspection.camera_name ?? inspection.camera_id.slice(0, 8)],
                ['Confiança', `${(inspection.confidence * 100).toFixed(1)}%`],
                ['Turno', inspection.shift],
                ['Lote', inspection.production_order ?? '—'],
                ['Produto', inspection.product_type ?? '—'],
                ['Data/Hora', new Date(inspection.created_at).toLocaleString('pt-BR')],
                ['Taxa NOK 1h', inspection.rolling_nok_rate_1h !== null ? `${((inspection.rolling_nok_rate_1h ?? 0) * 100).toFixed(1)}%` : '—'],
              ].map(([k, v]) => (
                <tr key={k}>
                  <td style={{ padding: '5px 0', color: '#888', paddingRight: '12px' }}>{k}</td>
                  <td style={{ padding: '5px 0', color: '#ddd', fontWeight: 500 }}>{v}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Feedback */}
        {inspection.result === 'nok' && (
          <div className={card}>
            <div style={{ fontSize: '12px', color: '#888', marginBottom: '10px', fontWeight: 600, textTransform: 'uppercase' }}>
              Feedback
            </div>

            {inspection.feedback_status === 'pending' ? (
              <>
                <textarea
                  value={feedbackNote}
                  onChange={e => setFeedbackNote(e.target.value)}
                  placeholder="Observações (opcional)"
                  style={{
                    width: '100%', padding: '8px', borderRadius: '4px',
                    border: '1px solid #333', background: '#111', color: '#ccc',
                    fontSize: '12px', resize: 'vertical', minHeight: '60px',
                    boxSizing: 'border-box', marginBottom: '10px',
                  }}
                />
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    onClick={() => handleFeedback('confirmed')}
                    disabled={!!submittingFeedback}
                    style={{ flex: 1, padding: '8px', borderRadius: '4px', border: 'none', background: '#EF535022', color: '#EF5350', fontWeight: 600, fontSize: '12px', cursor: 'pointer' }}
                  >
                    {submittingFeedback === 'confirmed' ? '…' : '✗ Confirmar NOK'}
                  </button>
                  <button
                    onClick={() => handleFeedback('rejected')}
                    disabled={!!submittingFeedback}
                    style={{ flex: 1, padding: '8px', borderRadius: '4px', border: 'none', background: '#43D18622', color: '#43D186', fontWeight: 600, fontSize: '12px', cursor: 'pointer' }}
                  >
                    {submittingFeedback === 'rejected' ? '…' : '✓ Rejeitar Alarme'}
                  </button>
                </div>
              </>
            ) : (
              <div style={{ fontSize: '12px', color: '#888' }}>
                <FeedbackBadge status={inspection.feedback_status} />
                {inspection.feedback_notes && (
                  <p style={{ marginTop: '8px', color: '#aaa' }}>{inspection.feedback_notes}</p>
                )}
              </div>
            )}
          </div>
        )}

        {/* Anotar frames */}
        {inspection.result === 'nok' && inspection.clip_status === 'available' && (
          <div className={card}>
            <div style={{ fontSize: '12px', color: '#888', marginBottom: '10px', fontWeight: 600, textTransform: 'uppercase' }}>
              Anotação
            </div>
            {inspection.annotation_status === 'ready' || inspection.annotation_status === 'in_progress' || inspection.annotation_status === 'completed' ? (
              <button
                onClick={() => navigate(`/quality/inspections/${id}/annotate`)}
                style={{ width: '100%', padding: '8px', borderRadius: '4px', border: 'none', background: '#4FC3F722', color: '#4FC3F7', fontWeight: 600, fontSize: '12px', cursor: 'pointer' }}
              >
                Abrir Workspace
              </button>
            ) : (
              <button
                onClick={handlePrepareAnnotation}
                disabled={preparingAnnotation}
                style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid #333', background: 'transparent', color: '#aaa', fontWeight: 600, fontSize: '12px', cursor: 'pointer' }}
              >
                {preparingAnnotation ? 'Preparando frames…' : 'Extrair Frames para Anotação'}
              </button>
            )}
          </div>
        )}

        <button
          onClick={() => navigate(-1)}
          style={{ padding: '8px', borderRadius: '4px', border: '1px solid #333', background: 'transparent', color: '#888', fontSize: '12px', cursor: 'pointer' }}
        >
          ← Voltar
        </button>
      </div>
    </div>
  )
}
