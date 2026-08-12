/**
 * SearchStatusBar — status da busca por conteúdo (job de GPU sob demanda)
 * em execução/concluída/falha. OCUPA espaço no layout (filho normal de um
 * flex column, montado acima da TrainingGallery) — ⛔ NUNCA position:
 * absolute/fixed, ⛔ NUNCA modal (mesma regra de PropagationStatusBar).
 *
 * Reaproveita os estilos de PropagationStatusBar.css.ts (barra/track/fill/
 * botões) — são tokens genéricos sem nada específico de propagação, então
 * duplicar o arquivo de CSS seria puro custo sem ganho.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { AlertTriangle, CheckCircle2, Search, X } from 'lucide-react'
import { searchService, type SearchJob } from '../../services/searchService'
import { mapSearchJobToPhase } from './searchContentUi'
import { formatElapsed, formatUsd } from './propagationUi'
import * as s from './PropagationStatusBar.css'

const POLL_INTERVAL_MS = 4000

export interface SearchStatusBarProps {
  jobId: string
  /** CTA "Ver achados" (só aparece quando `status === 'completed'`). */
  onReview: () => void
  /** Botão fechar (X) — só aparece em estados terminais. */
  onClose: () => void
}

export function SearchStatusBar({ jobId, onReview, onClose }: SearchStatusBarProps) {
  const [job, setJob] = useState<SearchJob | null>(null)
  const [detailsOpen, setDetailsOpen] = useState(false)
  const jobIdRef = useRef(jobId)
  jobIdRef.current = jobId

  const fetchJob = useCallback(async () => {
    try {
      const data = await searchService.getJob(jobIdRef.current)
      setJob(data)
    } catch {
      /* erro global já notificado pelo api.ts — mantém o último estado conhecido */
    }
  }, [])

  useEffect(() => {
    setJob(null)
    setDetailsOpen(false)
    void fetchJob()
  }, [jobId, fetchJob])

  useEffect(() => {
    const status = job?.status
    if (status !== 'queued' && status !== 'running') return undefined
    const id = setInterval(() => void fetchJob(), POLL_INTERVAL_MS)
    return () => clearInterval(id)
  }, [job?.status, fetchJob])

  if (!job) return null

  const phase = mapSearchJobToPhase(job)
  const gpuCost = job.metrics?.gpu_cost
  const costText = formatUsd(gpuCost?.actual_usd ?? gpuCost?.estimated_usd ?? null)

  // ── falha ────────────────────────────────────────────────────────────
  if (phase.failed) {
    return (
      <div className={`${s.bar} ${s.barDanger}`} role="alert">
        <AlertTriangle size={14} />
        <span className={s.label}>Busca por conteúdo — {phase.label}</span>
        <span className={s.elapsed}>custo gasto: {costText}</span>
        {phase.detail && (
          <button className={s.detailsToggle} onClick={() => setDetailsOpen(prev => !prev)}>
            {detailsOpen ? 'ocultar detalhes' : 'detalhes'}
          </button>
        )}
        {detailsOpen && phase.detail && (
          <span className={s.detailsText} title={phase.detail}>
            {phase.detail}
          </span>
        )}
        <span className={s.spacer} />
        <button className={s.closeButton} onClick={onClose} title="Fechar">
          <X size={14} />
        </button>
      </div>
    )
  }

  // ── concluído ────────────────────────────────────────────────────────
  if (job.status === 'completed') {
    return (
      <div className={`${s.bar} ${s.barSuccess}`}>
        <CheckCircle2 size={14} />
        <span className={s.label}>✓ {phase.label}</span>
        <button className={s.linkButton} onClick={onReview}>
          Ver achados
        </button>
        <span className={s.elapsed}>{costText}</span>
        <span className={s.spacer} />
        <button className={s.closeButton} onClick={onClose} title="Fechar">
          <X size={14} />
        </button>
      </div>
    )
  }

  // ── interrompido ─────────────────────────────────────────────────────
  if (job.status === 'stopped') {
    return (
      <div className={s.bar}>
        <span className={s.label}>Busca por conteúdo — {phase.label}</span>
        <span className={s.spacer} />
        <button className={s.closeButton} onClick={onClose} title="Fechar">
          <X size={14} />
        </button>
      </div>
    )
  }

  // ── em execução (queued/running) — sem botão fechar, sem % falso ──────
  const progressPct =
    phase.counter && phase.counter.total > 0
      ? Math.min(100, Math.round((phase.counter.done / phase.counter.total) * 100))
      : null

  return (
    <div className={s.bar} aria-live="polite">
      <Search size={14} className={s.spinIcon} />
      <span className={s.label}>
        Busca por conteúdo — {phase.label}
        {phase.counter ? ` · ${phase.counter.done}/${phase.counter.total}` : ''}
      </span>
      <div className={s.track}>
        {progressPct != null ? (
          <div className={s.fill} style={{ width: `${progressPct}%` }} />
        ) : (
          <div className={s.fillIndeterminate} />
        )}
      </div>
      <span className={s.elapsed}>{formatElapsed(job.created_at)}</span>
    </div>
  )
}
