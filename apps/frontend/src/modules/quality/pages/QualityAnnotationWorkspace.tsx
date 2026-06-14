/**
 * Workspace de anotação de frames NOK.
 * Canvas drag-to-bbox, seleção via hit-test matemático, auto-save, tira de thumbnails.
 *
 * REGRAS DO CANVAS:
 * - Todas bboxes com pointerEvents:'none'
 * - Seleção via handleMouseDown (hit-test matemático)
 * - Auto-save ao trocar frame
 * - Atalhos: A/← anterior, D/→ próximo, S pular, Del remover selecionado
 */
import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { qualityService } from '../services/qualityService'
import { useQualityAnnotation } from '../hooks/useQualityAnnotation'
import { AnnotationCanvas } from '../components/AnnotationCanvas'
import { thumbStrip, thumbItem } from '../components/quality.css'
import type { QualityClass } from '../types/quality'

const CLASS_COLORS: Record<number, string> = {
  0: '#43D186', 1: '#EF5350', 2: '#FF8A65', 3: '#FFB74D',
  4: '#F06292', 5: '#CE93D8', 6: '#4FC3F7', 7: '#E57373', 8: '#FFD54F',
}

export function QualityAnnotationWorkspace() {
  const { inspectionId } = useParams<{ inspectionId: string }>()
  const navigate = useNavigate()
  const [classes, setClasses] = useState<QualityClass[]>([])
  const [frameUrls, setFrameUrls] = useState<Record<string, string>>({})
  const [progress, setProgress] = useState<{ annotated: number; total: number; can_create_job: boolean } | null>(null)
  const [creatingJob, setCreatingJob] = useState(false)

  const annotation = useQualityAnnotation(inspectionId ?? '')

  // Carregar classes YOLO
  useEffect(() => {
    qualityService.getClasses().then(res => setClasses(res.data.classes)).catch(() => {})
  }, [])

  // Carregar URL do frame atual
  useEffect(() => {
    const frame = annotation.currentFrame
    if (!frame || frameUrls[frame.id]) return

    qualityService.getFrameUrl(frame.id)
      .then(res => setFrameUrls(prev => ({ ...prev, [frame.id]: res.data.url })))
      .catch(() => {})
  }, [annotation.currentFrame, frameUrls])

  // Polling de progresso a cada troca de frame
  useEffect(() => {
    if (!inspectionId) return
    qualityService.getAnnotationProgress(inspectionId)
      .then(res => setProgress(res.data))
      .catch(() => {})
  }, [inspectionId, annotation.currentIndex])

  async function handleCreateJob() {
    setCreatingJob(true)
    try {
      await qualityService.createTrainingJob()
      navigate('/quality/training')
    } catch {
      alert('Erro ao criar job de treinamento.')
    }
    setCreatingJob(false)
  }

  if (!inspectionId) return null

  if (annotation.loading) {
    return <div style={{ padding: '32px', color: '#888' }}>Carregando frames…</div>
  }

  if (annotation.error) {
    return <div style={{ padding: '32px', color: '#EF5350' }}>{annotation.error}</div>
  }

  if (annotation.frames.length === 0) {
    return (
      <div style={{ padding: '32px', color: '#888' }}>
        <p>Nenhum frame disponível para anotação.</p>
        <p style={{ fontSize: '13px', marginTop: '8px' }}>
          Verifique se o clip foi gerado e o processo de extração foi concluído.
        </p>
      </div>
    )
  }

  const currentUrl = annotation.currentFrame ? frameUrls[annotation.currentFrame.id] ?? null : null

  // Enriquecer bboxes com label e color das classes
  const enrichedBboxes = annotation.bboxes.map(b => ({
    ...b,
    label: classes.find(c => c.id === b.class_id)?.name ?? `c${b.class_id}`,
    color: CLASS_COLORS[b.class_id] ?? '#888',
  }))

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 120px)', overflow: 'hidden' }}>
      {/* Coluna esquerda: canvas */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '16px', gap: '12px', minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ fontSize: '13px', color: '#888' }}>
            Frame {annotation.currentIndex + 1} / {annotation.frames.length}
            {annotation.saving && <span style={{ marginLeft: '8px', color: '#FFB74D' }}>Salvando…</span>}
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              onClick={annotation.goPrev}
              disabled={annotation.currentIndex === 0}
              style={btnStyle}
            >
              ← Anterior
            </button>
            <button onClick={annotation.skipFrame} style={{ ...btnStyle, color: '#888' }}>
              Pular (S)
            </button>
            <button
              onClick={annotation.goNext}
              disabled={annotation.currentIndex === annotation.frames.length - 1}
              style={btnStyle}
            >
              Próximo →
            </button>
          </div>
        </div>

        <AnnotationCanvas
          imageUrl={currentUrl}
          bboxes={enrichedBboxes}
          previewBox={annotation.previewBox}
          selectedId={annotation.selectedId}
          onMouseDown={annotation.handleMouseDown}
          onMouseMove={annotation.handleMouseMove}
          onMouseUp={annotation.handleMouseUp}
        />

        {/* Tira de thumbnails */}
        <div className={thumbStrip}>
          {annotation.frames.map((frame, i) => {
            const isActive = i === annotation.currentIndex
            const variant = isActive ? 'active' : frame.status === 'annotated' ? 'annotated' : frame.status === 'skipped' ? 'skipped' : 'pending'
            return (
              <div
                key={frame.id}
                className={thumbItem[variant]}
                onClick={() => annotation.goToFrame(i)}
                title={`Frame ${i + 1}: ${frame.status}`}
              />
            )
          })}
        </div>
      </div>

      {/* Coluna direita: controles */}
      <div style={{ width: '220px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '16px', borderLeft: '1px solid #222', overflow: 'auto' }}>
        {/* Classe ativa */}
        <div>
          <div style={{ fontSize: '11px', color: '#888', textTransform: 'uppercase', marginBottom: '8px' }}>Classe Ativa</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {classes.filter(c => c.category === 'nok').map(c => (
              <button
                key={c.id}
                onClick={() => annotation.setActiveClass(c.id)}
                style={{
                  padding: '6px 10px',
                  borderRadius: '4px',
                  border: `1px solid ${annotation.activeClassId === c.id ? c.color : '#333'}`,
                  background: annotation.activeClassId === c.id ? `${c.color}22` : 'transparent',
                  color: annotation.activeClassId === c.id ? c.color : '#888',
                  fontSize: '11px',
                  fontWeight: annotation.activeClassId === c.id ? 700 : 400,
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
              >
                {c.label}
              </button>
            ))}
          </div>
        </div>

        {/* Ações na bbox selecionada */}
        {annotation.selectedId && (
          <div>
            <div style={{ fontSize: '11px', color: '#888', textTransform: 'uppercase', marginBottom: '8px' }}>BBox Selecionada</div>
            <button
              onClick={annotation.removeSelected}
              style={{ ...btnStyle, color: '#EF5350', borderColor: '#EF535044', width: '100%', justifyContent: 'center' }}
            >
              Remover (Del)
            </button>
          </div>
        )}

        {/* Progresso */}
        {progress && (
          <div style={{ fontSize: '12px', color: '#888' }}>
            <div style={{ marginBottom: '4px' }}>
              Anotados: <strong style={{ color: '#43D186' }}>{progress.annotated}</strong> / {progress.total}
            </div>
            <div
              style={{
                height: '4px',
                background: '#222',
                borderRadius: '2px',
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  height: '100%',
                  width: `${(progress.annotated / Math.max(progress.total, 1)) * 100}%`,
                  background: '#43D186',
                  borderRadius: '2px',
                }}
              />
            </div>
          </div>
        )}

        {/* Criar job */}
        <button
          onClick={handleCreateJob}
          disabled={creatingJob || !(progress?.can_create_job)}
          style={{
            padding: '10px',
            borderRadius: '6px',
            border: 'none',
            background: progress?.can_create_job ? '#4FC3F7' : '#222',
            color: progress?.can_create_job ? '#000' : '#555',
            fontWeight: 700,
            fontSize: '13px',
            cursor: progress?.can_create_job ? 'pointer' : 'not-allowed',
            marginTop: 'auto',
          }}
        >
          {creatingJob ? 'Criando…' : 'Criar Job Treino'}
        </button>

        {!progress?.can_create_job && (
          <div style={{ fontSize: '11px', color: '#555', textAlign: 'center' }}>
            Anote ao menos 10 frames para habilitar
          </div>
        )}

        {/* Atalhos */}
        <div style={{ fontSize: '10px', color: '#444', lineHeight: 1.8 }}>
          A / ← anterior<br />
          D / → próximo<br />
          S — pular<br />
          Del — remover bbox<br />
          Esc — desselecionar
        </div>
      </div>
    </div>
  )
}

const btnStyle: React.CSSProperties = {
  padding: '6px 12px',
  borderRadius: '4px',
  border: '1px solid #333',
  background: 'transparent',
  color: '#ccc',
  fontSize: '12px',
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
  gap: '4px',
}
