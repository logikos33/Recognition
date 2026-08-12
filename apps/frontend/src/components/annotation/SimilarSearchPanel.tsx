/**
 * SimilarSearchPanel — configuração da propagação semeada ("buscar
 * imagens iguais"): painel compacto ANCORADO abaixo da topBar do Estúdio
 * (mesmo padrão visual do floatPanel de brilho/contraste) — ⛔ NUNCA modal,
 * ⛔ NUNCA overlay de tela inteira.
 *
 * Mostra o preflight (pool/sementes/custo) ANTES de disparar o job — o
 * Vitor precisa ver o número do custo estimado antes de qualquer chamada
 * de GPU paga; sem preço estimado (price_error), o CTA fica bloqueado.
 */
import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle, ShieldCheck, Sparkles, X } from 'lucide-react'
import { useToast } from '../ui/Toast/useToast'
import { Skeleton } from '../ui/Skeleton/Skeleton'
import {
  propagationService,
  type PropagationJob,
  type PropagationPreflight,
} from '../../services/propagationService'
import { disabledReason, formatUsd, isOnsiteProvider } from './propagationUi'
import * as s from './SimilarSearchPanel.css'

const ONSITE_LABEL = 'processando no equipamento da fábrica — as imagens não saem do site'

interface QuantityOption {
  key: string
  label: string
  validationOnly: boolean
  maxResults?: number
}

const QUANTITY_OPTIONS: QuantityOption[] = [
  { key: 'validation', label: 'Validação — 5 frames (recomendado primeiro)', validationOnly: true },
  { key: '10', label: '10 imagens', validationOnly: false, maxResults: 10 },
  { key: '25', label: '25 imagens', validationOnly: false, maxResults: 25 },
  { key: '50', label: '50 imagens', validationOnly: false, maxResults: 50 },
  { key: '100', label: '100 imagens', validationOnly: false, maxResults: 100 },
]

/** YYYY-MM-DD → DD/MM/AAAA (exibição pt-BR). Volta a string original se
 * não bater o formato esperado — nunca quebra o painel por causa disso. */
function formatDateBr(iso: string): string {
  const parts = iso.split('-')
  return parts.length === 3 ? `${parts[2]}/${parts[1]}/${parts[0]}` : iso
}

export interface SimilarSearchPanelProps {
  cameraId: string | null
  /** Nome de exibição da câmera (StudioFrame.cameraName) — só rótulo, o
   * critério de fato é `cameraId`. */
  cameraLabel?: string | null
  /** YYYY-MM-DD — mesmo dia usado como date_from E date_to (frame único). */
  date: string | null
  hasBoxes: boolean
  onClose: () => void
  onStarted: (job: PropagationJob) => void
}

export function SimilarSearchPanel({
  cameraId,
  cameraLabel,
  date,
  hasBoxes,
  onClose,
  onStarted,
}: SimilarSearchPanelProps) {
  const toast = useToast()
  const [selected, setSelected] = useState<QuantityOption>(QUANTITY_OPTIONS[0])
  const [preflight, setPreflight] = useState<PropagationPreflight | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const identified = !!cameraId && !!date

  const loadPreflight = useCallback(async () => {
    if (!cameraId || !date) return
    setLoading(true)
    setLoadError(false)
    try {
      const data = await propagationService.getPreflight({
        camera_id: cameraId,
        date_from: date,
        date_to: date,
        validation_only: selected.validationOnly,
      })
      setPreflight(data)
    } catch {
      setLoadError(true)
    } finally {
      setLoading(false)
    }
  }, [cameraId, date, selected.validationOnly])

  useEffect(() => {
    void loadPreflight()
  }, [loadPreflight])

  const onsite = isOnsiteProvider(preflight?.gpu_provider)

  // Onsite: sem chamada RunPod nenhuma (preflight nem tenta estimar preço,
  // ver preflight_propagation_handler) — price_error nunca se aplica aqui.
  const priceReason =
    !onsite && preflight && !loading && !loadError && preflight.gpu.price_error
      ? 'não foi possível estimar o custo — tente de novo'
      : null
  const reason = preflight ? disabledReason(hasBoxes, preflight) ?? priceReason : null

  const canSubmit = identified && !loading && !loadError && !submitting && !!preflight && reason == null

  const start = useCallback(async () => {
    if (!cameraId || !date || !canSubmit) return
    setSubmitting(true)
    try {
      const job = await propagationService.createJob({
        camera_ids: [cameraId],
        date_from: date,
        date_to: date,
        validation_only: selected.validationOnly,
        ...(selected.maxResults != null ? { max_results: selected.maxResults } : {}),
      })
      toast.success('Busca de imagens iguais iniciada')
      onStarted(job)
      onClose()
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Erro ao iniciar a busca')
    } finally {
      setSubmitting(false)
    }
  }, [cameraId, date, canSubmit, selected, toast, onStarted, onClose])

  return (
    <div className={s.panel} role="dialog" aria-label="Buscar imagens iguais">
      <div className={s.header}>
        <span className={s.title}>
          <Sparkles size={14} /> Buscar imagens iguais
        </span>
        <button className={s.closeButton} onClick={onClose} title="Fechar">
          <X size={14} />
        </button>
      </div>

      {!identified ? (
        <p className={s.muted}>
          Não foi possível identificar a câmera/data deste frame — busca indisponível.
        </p>
      ) : loading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <Skeleton variant="text" width="85%" />
          <Skeleton variant="text" width="60%" />
          <Skeleton variant="rect" width="100%" height={64} />
        </div>
      ) : loadError ? (
        <div className={s.errorBox}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <AlertTriangle size={14} /> Erro ao carregar dados da busca.
          </span>
          <button className={s.retryButton} onClick={() => void loadPreflight()}>
            Tentar de novo
          </button>
        </div>
      ) : preflight ? (
        <>
          <p className={s.infoLine}>
            Disponíveis no pool: <strong>{preflight.pool_effective}</strong>
            {preflight.pool_effective !== preflight.pool_total ? ` de ${preflight.pool_total}` : ''}
            {' '}({cameraLabel || 'Câmera'} — {date ? formatDateBr(date) : '—'})
          </p>
          <p className={s.infoLine}>
            Sementes: {preflight.seed_box_count} caixa{preflight.seed_box_count === 1 ? '' : 's'} em{' '}
            {preflight.seed_frame_count} frame{preflight.seed_frame_count === 1 ? '' : 's'}
          </p>

          <div className={s.quantityGroup} role="radiogroup" aria-label="Quantidade de imagens">
            {QUANTITY_OPTIONS.map(opt => (
              <label key={opt.key} className={s.quantityRow}>
                <input
                  type="radio"
                  name="propagation-quantity"
                  checked={selected.key === opt.key}
                  onChange={() => setSelected(opt)}
                />
                {opt.label}
              </label>
            ))}
          </div>

          {onsite ? (
            <p className={s.infoLine}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <ShieldCheck size={14} /> {ONSITE_LABEL}
              </span>
            </p>
          ) : (
            <p className={s.infoLine}>
              {preflight.gpu.price_error
                ? 'preço indisponível no momento'
                : `Custo estimado: ${formatUsd(preflight.gpu.estimated_cost_usd)} (teto ${formatUsd(preflight.gpu.max_usd)})`}
            </p>
          )}

          <button className={s.cta} disabled={!canSubmit} onClick={() => void start()}>
            {submitting ? 'Iniciando…' : 'Iniciar busca'}
          </button>
          {reason && <p className={s.reasonText}>{reason}</p>}
        </>
      ) : null}
    </div>
  )
}
