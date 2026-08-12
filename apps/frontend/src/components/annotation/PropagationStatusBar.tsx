/**
 * PropagationStatusBar — status da propagação semeada ("buscar imagens
 * iguais") em execução/concluída/falha. OCUPA espaço no layout (filho
 * normal de um flex column) — ⛔ NUNCA position:absolute/fixed, NUNCA
 * modal (mesmo erro já corrigido uma vez no banner de contexto assumido,
 * ver fix/assumed-context-banner-layout).
 *
 * Mesmo componente é montado em dois lugares (AnnotationStudio e
 * TrainingPage) — cada instância faz seu próprio polling independente
 * enquanto o job está queued/running; para em qualquer status terminal.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { AlertTriangle, CheckCircle2, Search, ShieldCheck, X } from 'lucide-react'
import { propagationService, type PropagationJob } from '../../services/propagationService'
import { formatElapsed, formatUsd, isOnsiteProvider, mapJobToPhase } from './propagationUi'
import * as s from './PropagationStatusBar.css'

const ONSITE_LABEL = 'processando no equipamento da fábrica — as imagens não saem do site'

const POLL_INTERVAL_MS = 5000

export interface PropagationStatusBarProps {
  jobId: string
  /** CTA "Revisar" (só aparece quando `status === 'completed'`). */
  onReview: () => void
  /** Botão fechar (X) — só aparece em estados terminais. */
  onClose: () => void
}

export function PropagationStatusBar({ jobId, onReview, onClose }: PropagationStatusBarProps) {
  const [job, setJob] = useState<PropagationJob | null>(null)
  const [detailsOpen, setDetailsOpen] = useState(false)
  const jobIdRef = useRef(jobId)
  jobIdRef.current = jobId

  const fetchJob = useCallback(async () => {
    try {
      const data = await propagationService.getJob(jobIdRef.current)
      setJob(data)
    } catch {
      /* erro global já notificado pelo api.ts — mantém o último estado conhecido */
    }
  }, [])

  // Busca inicial sempre que o jobId muda (ex.: um novo job foi disparado).
  useEffect(() => {
    setJob(null)
    setDetailsOpen(false)
    void fetchJob()
  }, [jobId, fetchJob])

  // Polling 5s enquanto queued/running — cleanup no unmount E ao virar terminal.
  useEffect(() => {
    const status = job?.status
    if (status !== 'queued' && status !== 'running') return undefined
    const id = setInterval(() => void fetchJob(), POLL_INTERVAL_MS)
    return () => clearInterval(id)
  }, [job?.status, fetchJob])

  if (!job) return null

  const phase = mapJobToPhase(job)
  const onsite = isOnsiteProvider(job.gpu_provider)
  const gpuCost = job.metrics?.gpu_cost
  const costText = formatUsd(gpuCost?.actual_usd ?? gpuCost?.estimated_usd ?? null)

  // ── falha (inclui status='failed' com qualquer failure_kind, mesmo 'stopped') ──
  if (phase.failed) {
    return (
      <div className={`${s.bar} ${s.barDanger}`} role="alert">
        <AlertTriangle size={14} />
        <span className={s.label}>Busca de iguais — {phase.label}</span>
        {!onsite && <span className={s.elapsed}>custo gasto: {costText}</span>}
        {phase.detail && (
          <button
            className={s.detailsToggle}
            onClick={() => setDetailsOpen(prev => !prev)}
          >
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

  // ── concluído ──────────────────────────────────────────────────────────
  if (job.status === 'completed') {
    return (
      <div className={`${s.bar} ${s.barSuccess}`}>
        <CheckCircle2 size={14} />
        <span className={s.label}>✓ {phase.label}</span>
        <button className={s.linkButton} onClick={onReview}>
          Revisar
        </button>
        {!onsite && <span className={s.elapsed}>{costText}</span>}
        <span className={s.spacer} />
        <button className={s.closeButton} onClick={onClose} title="Fechar">
          <X size={14} />
        </button>
      </div>
    )
  }

  // ── interrompido (status='stopped' direto, sem passar por 'failed') ────
  if (job.status === 'stopped') {
    return (
      <div className={s.bar}>
        <span className={s.label}>Busca de iguais — {phase.label}</span>
        <span className={s.spacer} />
        <button className={s.closeButton} onClick={onClose} title="Fechar">
          <X size={14} />
        </button>
      </div>
    )
  }

  // ── em execução (queued/running) — sem botão fechar, sem % falso ───────
  const progressPct =
    phase.counter && phase.counter.total > 0
      ? Math.min(100, Math.round((phase.counter.done / phase.counter.total) * 100))
      : null

  return (
    <div className={s.bar} aria-live="polite">
      <Search size={14} className={s.spinIcon} />
      <span className={s.label}>
        Busca de iguais — {phase.label}
        {phase.counter ? ` · ${phase.counter.done}/${phase.counter.total}` : ''}
      </span>
      {onsite && (
        <span className={s.onsiteBadge}>
          <ShieldCheck size={12} /> {ONSITE_LABEL}
        </span>
      )}
      <div className={s.track}>
        {progressPct != null ? (
          <div className={s.fill} style={{ width: `${progressPct}%` }} />
        ) : (
          <div className={s.fillIndeterminate} />
        )}
      </div>
      <span className={s.elapsed}>
        {formatElapsed(job.started_at ?? job.created_at)}
      </span>
    </div>
  )
}
