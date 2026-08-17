/**
 * SearchContentPanel — configuração da "busca por conteúdo" nas imagens de
 * treino selecionadas: termos de EPI prontos + termos livres, custo
 * estimado ANTES de disparar o job de GPU. Painel ANCORADO (drawer fixo no
 * canto — mesmo padrão de SimilarSearchPanel) — ⛔ NUNCA modal, ⛔ NUNCA
 * overlay de tela inteira.
 *
 * Achados NÃO são propostas — a promoção manual acontece depois, em
 * SearchFindingsPanel, quando o job termina (ver SearchStatusBar "Ver
 * achados"). Este painel só configura e dispara.
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Search, X } from 'lucide-react'
import { ApiError } from '../../services/api'
import { searchService, type SearchJob } from '../../services/searchService'
import { useToast } from '../ui/Toast/useToast'
import { Skeleton } from '../ui/Skeleton/Skeleton'
import {
  MAX_TERMS_PER_JOB,
  READY_TERMS,
  buildSearchTerms,
  searchSubmitDisabledReason,
  summarizeIneligible,
} from './searchContentUi'
import { formatUsd } from './propagationUi'
import * as s from './SearchContentPanel.css'

export interface SearchContentPanelProps {
  frameIds: string[]
  onClose: () => void
  onStarted: (job: SearchJob) => void
}

export function SearchContentPanel({ frameIds, onClose, onStarted }: SearchContentPanelProps) {
  const toast = useToast()
  const [selectedReady, setSelectedReady] = useState<Set<string>>(new Set())
  const [freeTerms, setFreeTerms] = useState<string[]>([])
  const [freeInput, setFreeInput] = useState('')

  const [preflight, setPreflight] = useState<Awaited<ReturnType<typeof searchService.getPreflight>> | null>(null)
  const [preflightLoading, setPreflightLoading] = useState(false)
  const [loadError, setLoadError] = useState(false)
  const [cloudDisabled, setCloudDisabled] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const terms = useMemo(() => buildSearchTerms(selectedReady, freeTerms), [selectedReady, freeTerms])
  const termsKey = useMemo(() => terms.map(t => t.query).join('|'), [terms])

  const loadPreflight = useCallback(async () => {
    // search_handlers.py::_parse_terms rejeita `terms` vazio com 400 — sem
    // termo nenhum marcado ainda nem vale a pena chamar o preflight (o
    // botão "Buscar" já fica desabilitado com o motivo certo, ver
    // searchSubmitDisabledReason).
    if (frameIds.length === 0 || terms.length === 0) {
      setPreflight(null)
      setPreflightLoading(false)
      setLoadError(false)
      setCloudDisabled(null)
      return
    }
    setPreflightLoading(true)
    setLoadError(false)
    setCloudDisabled(null)
    try {
      const data = await searchService.getPreflight(frameIds, terms)
      setPreflight(data)
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 409) {
        setCloudDisabled(err.message || 'busca em nuvem desabilitada neste tenant')
      } else {
        setLoadError(true)
      }
    } finally {
      setPreflightLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [frameIds, termsKey])

  useEffect(() => {
    void loadPreflight()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [termsKey])

  // _MAX_TERMS de search_handlers.py::_parse_terms — acima disso o preflight
  // e o create rejeitam com 400; a UI trava a adição antes de chegar lá.
  const atTermsCap = terms.length >= MAX_TERMS_PER_JOB

  const toggleReady = useCallback(
    (key: string) => {
      setSelectedReady(prev => {
        const next = new Set(prev)
        if (next.has(key)) {
          next.delete(key)
        } else {
          if (atTermsCap) {
            toast.warning(`Máximo de ${MAX_TERMS_PER_JOB} termos por busca`)
            return prev
          }
          next.add(key)
        }
        return next
      })
    },
    [atTermsCap, toast],
  )

  const addFreeTerm = useCallback(() => {
    const term = freeInput.trim()
    if (!term) return
    if (atTermsCap) {
      toast.warning(`Máximo de ${MAX_TERMS_PER_JOB} termos por busca`)
      return
    }
    setFreeTerms(prev => [...prev, term])
    setFreeInput('')
  }, [freeInput, atTermsCap, toast])

  const removeFreeTerm = useCallback((index: number) => {
    setFreeTerms(prev => prev.filter((_, i) => i !== index))
  }, [])

  const eligibleFrameIds = useMemo(() => {
    if (!preflight) return frameIds
    const ineligible = new Set(preflight.ineligible.map(i => i.frame_id))
    return frameIds.filter(id => !ineligible.has(id))
  }, [frameIds, preflight])

  const ineligibleSummary = useMemo(
    () => (preflight ? summarizeIneligible(preflight.ineligible) : []),
    [preflight],
  )

  const disabledReason = searchSubmitDisabledReason(terms.length, preflight, cloudDisabled != null)

  const start = useCallback(async () => {
    if (submitting || disabledReason) return
    setSubmitting(true)
    try {
      const job = await searchService.createJob(eligibleFrameIds, terms)
      toast.success('Busca por conteúdo iniciada')
      onStarted(job)
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Erro ao iniciar a busca')
    } finally {
      setSubmitting(false)
    }
  }, [submitting, disabledReason, eligibleFrameIds, terms, toast, onStarted])

  return (
    <div className={s.panel} role="dialog" aria-label="Buscar por conteúdo">
      <div className={s.header}>
        <span className={s.title}>
          <Search size={14} /> Buscar nestas imagens
        </span>
        <button className={s.closeButton} onClick={onClose} title="Fechar">
          <X size={14} />
        </button>
      </div>

      <div className={s.body}>
        <p className={s.infoLine}>
          {frameIds.length} imagem{frameIds.length === 1 ? '' : 'ns'} selecionada{frameIds.length === 1 ? '' : 's'}
        </p>

        {cloudDisabled ? (
          <div className={s.errorBox}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <AlertTriangle size={14} /> Busca em nuvem desabilitada
            </span>
            <span>{cloudDisabled}</span>
          </div>
        ) : (
          <>
            <span className={s.sectionLabel}>Termos prontos de EPI</span>
            <div className={s.termsGroup}>
              {READY_TERMS.map(t => (
                <label key={t.key} className={s.termRow}>
                  <input
                    type="checkbox"
                    checked={selectedReady.has(t.key)}
                    disabled={atTermsCap && !selectedReady.has(t.key)}
                    onChange={() => toggleReady(t.key)}
                  />
                  <span className={s.termLabel}>{t.labelPt}</span>
                  <span className={s.termQuery}>{t.query}</span>
                </label>
              ))}
            </div>

            <span className={s.sectionLabel}>Outros termos</span>
            <div className={s.freeTermRow}>
              <input
                className={s.freeTermInput}
                placeholder={
                  atTermsCap
                    ? `máximo de ${MAX_TERMS_PER_JOB} termos atingido`
                    : "termos em inglês funcionam melhor — ex.: 'forklift', 'ladder'"
                }
                value={freeInput}
                disabled={atTermsCap}
                onChange={e => setFreeInput(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    addFreeTerm()
                  }
                }}
              />
            </div>
            {freeTerms.length > 0 && (
              <div className={s.chipsRow}>
                {freeTerms.map((term, i) => (
                  <span key={`${term}-${i}`} className={s.chip}>
                    {term}
                    <button className={s.chipRemove} onClick={() => removeFreeTerm(i)} title="Remover">
                      <X size={11} />
                    </button>
                  </span>
                ))}
              </div>
            )}

            {preflightLoading ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <Skeleton variant="rect" width="100%" height={56} />
              </div>
            ) : loadError ? (
              <div className={s.errorBox}>
                <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <AlertTriangle size={14} /> Erro ao calcular o custo.
                </span>
                <button className={s.retryButton} onClick={() => void loadPreflight()}>
                  Tentar de novo
                </button>
              </div>
            ) : preflight ? (
              <>
                <div className={s.costBox}>
                  <span className={s.infoLine}>
                    {preflight.eligible_count} de {preflight.selected_count} imagens elegíveis
                  </span>
                  <span className={s.costValue}>
                    {preflight.gpu.price_error
                      ? 'preço indisponível'
                      : `Custo estimado: ${formatUsd(preflight.gpu.estimated_cost_usd)}`}
                  </span>
                  {!preflight.gpu.price_error && (
                    <span className={s.infoLine}>teto: {formatUsd(preflight.gpu.max_usd)}</span>
                  )}
                </div>
                {ineligibleSummary.length > 0 && (
                  <div className={s.warningBox}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <AlertTriangle size={13} />
                      {preflight.selected_count - preflight.eligible_count} imagem(ns) fora da busca:
                    </span>
                    {ineligibleSummary.map(item => (
                      <span key={item.reason}>
                        • {item.count}× {item.reason}
                      </span>
                    ))}
                  </div>
                )}
              </>
            ) : null}
          </>
        )}
      </div>

      {!cloudDisabled && (
        <div className={s.footer}>
          <button className={s.cta} disabled={!!disabledReason || submitting} onClick={() => void start()}>
            {submitting ? 'Iniciando…' : 'Buscar'}
          </button>
          {disabledReason && <p className={s.reasonText}>{disabledReason}</p>}
        </div>
      )}
    </div>
  )
}
