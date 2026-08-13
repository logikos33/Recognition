/**
 * ProposalTriageGrid — grade de triagem em massa de propostas de IA
 * (propagação semeada / pré-anotação, migration 118).
 *
 * Muitos tiles por tela (grade responsiva), teclado-first:
 *   A = aprovar (aceita, com a caixa corrigida se houver)
 *   R = rejeitar
 *   C = alterna modo de correção da caixa da proposta focada
 *   → / Espaço = próximo tile · ← = tile anterior
 *
 * Ações individuais (A/R) são otimistas: o tile some da grade na hora;
 * erro de rede devolve o tile ao lugar + toast. Ações em lote (barra de
 * baixo) sempre confirmam (barra inline, nunca confirm() nativo — bloqueia
 * automação de navegador) e sempre re-buscam a página 1 no final.
 */
import { useCallback, useEffect, useRef, useState, type CSSProperties } from 'react'
import { AlertTriangle, ImageOff, X } from 'lucide-react'
import { Button } from '../ui/Button/Button'
import { Skeleton } from '../ui/Skeleton/Skeleton'
import { useToast } from '../ui/Toast/useToast'
import { useStudioKeyboard } from './useStudioKeyboard'
import { clamp, moveBox, resizeBox, HANDLES, type HandleId } from './boxGeometry'
import type { Box } from './studioTypes'
import {
  proposalService,
  type ListProposalsParams,
  type Proposal,
  type ProposalBbox,
  type ProposalFacets,
  type ProposalSortField,
  type ProposalSortOrder,
  type RejectBatchBody,
} from '../../services/proposalService'
import * as s from './ProposalTriageGrid.css'

const PAGE_SIZE = 60
const DEFAULT_CONFIDENCE_THRESHOLD = 0.8

const HANDLE_POSITIONS: Record<HandleId, CSSProperties> = {
  nw: { left: -4, top: -4, cursor: 'nwse-resize' },
  n: { left: '50%', top: -4, transform: 'translateX(-50%)', cursor: 'ns-resize' },
  ne: { right: -4, top: -4, cursor: 'nesw-resize' },
  e: { right: -4, top: '50%', transform: 'translateY(-50%)', cursor: 'ew-resize' },
  se: { right: -4, bottom: -4, cursor: 'nwse-resize' },
  s: { left: '50%', bottom: -4, transform: 'translateX(-50%)', cursor: 'ns-resize' },
  sw: { left: -4, bottom: -4, cursor: 'nesw-resize' },
  w: { left: -4, top: '50%', transform: 'translateY(-50%)', cursor: 'ew-resize' },
}

function bboxToBox(bbox: ProposalBbox, id: string): Box {
  return { id, classId: 0, xCenter: bbox[0], yCenter: bbox[1], width: bbox[2], height: bbox[3] }
}

function boxToBbox(box: Box): ProposalBbox {
  return [box.xCenter, box.yCenter, box.width, box.height]
}

function parseConfidenceInput(text: string): number | undefined {
  const trimmed = text.trim()
  if (trimmed === '') return undefined
  const value = Number(trimmed)
  return Number.isFinite(value) ? value : undefined
}

interface DragState {
  proposalId: string
  mode: 'move' | 'resize'
  handle?: HandleId
  startBox: Box
  offsetX?: number
  offsetY?: number
}

interface PendingBulkAction {
  label: string
  run: () => Promise<void>
}

export interface ProposalTriageGridProps {
  /** Job de propagação recém-concluído (vindo do "Revisar" da barra de
   * status) — pré-filtra a grade. `null`/ausente = todas as propostas
   * pendentes do tenant, sem filtro de job. */
  initialJobId?: string | null
}

export function ProposalTriageGrid({ initialJobId = null }: ProposalTriageGridProps) {
  const toast = useToast()

  // ── filtros / paginação ───────────────────────────────────────────────────
  const [jobId, setJobId] = useState<string | null>(initialJobId)
  const [classFilter, setClassFilter] = useState<Set<string>>(new Set())
  const [confMinText, setConfMinText] = useState('')
  const [confMaxText, setConfMaxText] = useState('')
  const [confidenceMin, setConfidenceMin] = useState<number | undefined>(undefined)
  const [confidenceMax, setConfidenceMax] = useState<number | undefined>(undefined)
  const [sortField, setSortField] = useState<ProposalSortField>('confidence')
  const [sortOrder, setSortOrder] = useState<ProposalSortOrder>('asc')
  const [page, setPage] = useState(1)
  const [reloadNonce, setReloadNonce] = useState(0)

  const [proposals, setProposals] = useState<Proposal[]>([])
  const [facets, setFacets] = useState<ProposalFacets | null>(null)
  const [total, setTotal] = useState(0)
  const [totalPages, setTotalPages] = useState(1)
  const [loading, setLoading] = useState(false)
  const [brokenImages, setBrokenImages] = useState<Set<string>>(new Set())

  // ── seleção múltipla ──────────────────────────────────────────────────────
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const lastClickIndexRef = useRef<number | null>(null)

  // ── foco/teclado + correção de caixa ────────────────────────────────────
  const [focusedIndex, setFocusedIndex] = useState<number | null>(null)
  const [correctMode, setCorrectMode] = useState(false)
  const [correctedBboxes, setCorrectedBboxes] = useState<Record<string, ProposalBbox>>({})

  // ── ações em lote ─────────────────────────────────────────────────────────
  const [confidenceThreshold, setConfidenceThreshold] = useState(DEFAULT_CONFIDENCE_THRESHOLD)
  const [pendingBulk, setPendingBulk] = useState<PendingBulkAction | null>(null)
  const [bulkBusy, setBulkBusy] = useState(false)

  const loadSeqRef = useRef(0)

  // ── busca ─────────────────────────────────────────────────────────────────
  const buildParams = useCallback(
    (): ListProposalsParams => ({
      status: 'pending',
      job_id: jobId ?? undefined,
      class_name: classFilter.size > 0 ? Array.from(classFilter) : undefined,
      confidence_min: confidenceMin,
      confidence_max: confidenceMax,
      sort: sortField,
      order: sortOrder,
      page,
      page_size: PAGE_SIZE,
    }),
    [jobId, classFilter, confidenceMin, confidenceMax, sortField, sortOrder, page],
  )

  const load = useCallback(async () => {
    const seq = ++loadSeqRef.current
    setLoading(true)
    try {
      const data = await proposalService.listProposals(buildParams())
      if (seq !== loadSeqRef.current) return
      setProposals(data.proposals)
      setTotal(data.total)
      setTotalPages(Math.max(1, data.total_pages))
      setFacets(data.facets)
      setFocusedIndex(data.proposals.length > 0 ? 0 : null)
      setCorrectMode(false)
    } catch {
      /* erro global já notificado pelo api.ts */
    } finally {
      if (seq === loadSeqRef.current) setLoading(false)
    }
  }, [buildParams])

  useEffect(() => {
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load, reloadNonce])

  // Array encolheu (rejeição/aprovação otimista) — mantém o foco válido sem
  // forçar de volta pro início (fluxo de teclado rápido).
  useEffect(() => {
    setFocusedIndex(prev => {
      if (prev == null) return null
      if (proposals.length === 0) return null
      return Math.min(prev, proposals.length - 1)
    })
  }, [proposals.length])

  const resetPageAnd = useCallback((fn: () => void) => {
    fn()
    setPage(1)
    setSelected(new Set())
    lastClickIndexRef.current = null
  }, [])

  const forceReload = useCallback(() => {
    setPage(1)
    setSelected(new Set())
    setReloadNonce(n => n + 1)
  }, [])

  // ── filtros ───────────────────────────────────────────────────────────────
  const toggleClassFilter = useCallback(
    (className: string) => {
      resetPageAnd(() => {
        setClassFilter(prev => {
          const next = new Set(prev)
          if (next.has(className)) next.delete(className)
          else next.add(className)
          return next
        })
      })
    },
    [resetPageAnd],
  )

  const applyConfidenceRange = useCallback(() => {
    const min = parseConfidenceInput(confMinText)
    const max = parseConfidenceInput(confMaxText)
    resetPageAnd(() => {
      setConfidenceMin(min)
      setConfidenceMax(max)
    })
  }, [confMinText, confMaxText, resetPageAnd])

  const clearJobFilter = useCallback(() => {
    resetPageAnd(() => setJobId(null))
  }, [resetPageAnd])

  const setSort = useCallback(
    (field: ProposalSortField) => {
      const nextOrder: ProposalSortOrder =
        sortField === field ? (sortOrder === 'asc' ? 'desc' : 'asc') : 'asc'
      resetPageAnd(() => {
        setSortField(field)
        setSortOrder(nextOrder)
      })
    },
    [sortField, sortOrder, resetPageAnd],
  )

  // ── seleção ───────────────────────────────────────────────────────────────
  const toggleSelect = useCallback((id: string, index: number) => {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
    lastClickIndexRef.current = index
  }, [])

  const selectRange = useCallback(
    (from: number, to: number) => {
      const [lo, hi] = from <= to ? [from, to] : [to, from]
      setSelected(prev => {
        const next = new Set(prev)
        for (let i = lo; i <= hi; i++) {
          const p = proposals[i]
          if (p) next.add(p.id)
        }
        return next
      })
      lastClickIndexRef.current = to
    },
    [proposals],
  )

  const onTileClick = useCallback(
    (event: React.MouseEvent, index: number) => {
      const proposal = proposals[index]
      if (!proposal) return
      if (event.shiftKey && lastClickIndexRef.current != null) {
        event.preventDefault()
        selectRange(lastClickIndexRef.current, index)
        return
      }
      if (event.ctrlKey || event.metaKey) {
        toggleSelect(proposal.id, index)
        return
      }
      if (selected.size > 0) {
        toggleSelect(proposal.id, index)
        return
      }
      setFocusedIndex(index)
      setCorrectMode(false)
    },
    [proposals, selected, selectRange, toggleSelect],
  )

  // ── ações otimistas individuais (A / R) ─────────────────────────────────
  const removeAndAdjust = useCallback((id: string, className: string) => {
    setProposals(prev => prev.filter(p => p.id !== id))
    setTotal(prev => Math.max(0, prev - 1))
    setFacets(prev =>
      prev
        ? {
            by_class: prev.by_class.map(f =>
              f.class_name === className ? { ...f, count: Math.max(0, f.count - 1) } : f,
            ),
          }
        : prev,
    )
    setSelected(prev => {
      if (!prev.has(id)) return prev
      const next = new Set(prev)
      next.delete(id)
      return next
    })
    setCorrectedBboxes(prev => {
      if (!(id in prev)) return prev
      const next = { ...prev }
      delete next[id]
      return next
    })
    setCorrectMode(false)
  }, [])

  const restoreProposal = useCallback((proposal: Proposal, index: number) => {
    setProposals(prev => {
      const next = [...prev]
      next.splice(Math.min(index, next.length), 0, proposal)
      return next
    })
    setTotal(prev => prev + 1)
    setFacets(prev =>
      prev
        ? {
            by_class: prev.by_class.map(f =>
              f.class_name === proposal.class_name ? { ...f, count: f.count + 1 } : f,
            ),
          }
        : prev,
    )
  }, [])

  const rejectOne = useCallback(
    async (proposal: Proposal, index: number) => {
      removeAndAdjust(proposal.id, proposal.class_name)
      try {
        await proposalService.rejectProposal(proposal.id)
      } catch {
        restoreProposal(proposal, index)
        toast.error('Erro ao rejeitar proposta — restaurada')
      }
    },
    [removeAndAdjust, restoreProposal, toast],
  )

  const acceptOne = useCallback(
    async (proposal: Proposal, index: number, bbox?: ProposalBbox) => {
      removeAndAdjust(proposal.id, proposal.class_name)
      try {
        await proposalService.acceptProposal(proposal.id, bbox)
      } catch {
        restoreProposal(proposal, index)
        toast.error('Erro ao aprovar proposta — restaurada')
      }
    },
    [removeAndAdjust, restoreProposal, toast],
  )

  // ── ações em lote (sempre re-busca no final) ────────────────────────────
  const clearSelection = useCallback(() => setSelected(new Set()), [])

  const runRejectBatch = useCallback(
    async (body: RejectBatchBody, emptyMessage: string) => {
      const result = await proposalService.rejectBatch(body)
      toast.success(
        result.rejected_count > 0
          ? `${result.rejected_count} proposta${result.rejected_count === 1 ? '' : 's'} rejeitada${result.rejected_count === 1 ? '' : 's'}`
          : emptyMessage,
      )
      clearSelection()
      forceReload()
    },
    [toast, clearSelection, forceReload],
  )

  const selectedClass = classFilter.size === 1 ? Array.from(classFilter)[0] : null
  const selectedClassCount = selectedClass
    ? (facets?.by_class.find(f => f.class_name === selectedClass)?.count ?? 0)
    : 0

  const requestRejectJob = useCallback(() => {
    if (!jobId) return
    setPendingBulk({
      label: 'Rejeitar TODAS as propostas pendentes deste job?',
      run: async () => {
        const result = await proposalService.rejectJob(jobId)
        toast.success(
          `${result.rejected_count} proposta${result.rejected_count === 1 ? '' : 's'} rejeitada${result.rejected_count === 1 ? '' : 's'} do job`,
        )
        clearSelection()
        forceReload()
      },
    })
  }, [jobId, toast, clearSelection, forceReload])

  const requestRejectClass = useCallback(() => {
    if (!selectedClass) return
    const className = selectedClass
    const count = selectedClassCount
    setPendingBulk({
      label: `Rejeitar todas as propostas da classe "${className}" (${count})?`,
      run: () =>
        runRejectBatch(
          { job_id: jobId ?? undefined, class_names: [className] },
          'Nenhuma proposta encontrada para essa classe.',
        ),
    })
  }, [selectedClass, selectedClassCount, jobId, runRejectBatch])

  const requestRejectByConfidence = useCallback(() => {
    const threshold = confidenceThreshold
    setPendingBulk({
      label: `Rejeitar todas as propostas pendentes com confiança abaixo de ${threshold.toFixed(2)}?`,
      run: () =>
        runRejectBatch(
          {
            job_id: jobId ?? undefined,
            class_names: classFilter.size > 0 ? Array.from(classFilter) : undefined,
            confidence_lt: threshold,
          },
          'Nenhuma proposta abaixo desse limiar.',
        ),
    })
  }, [confidenceThreshold, jobId, classFilter, runRejectBatch])

  const requestRejectSelection = useCallback(() => {
    if (selected.size === 0) return
    const ids = Array.from(selected)
    setPendingBulk({
      label: `Rejeitar ${ids.length} proposta${ids.length === 1 ? '' : 's'} selecionada${ids.length === 1 ? '' : 's'}?`,
      run: () => runRejectBatch({ proposal_ids: ids }, 'Nenhuma proposta rejeitada.'),
    })
  }, [selected, runRejectBatch])

  const confirmBulk = useCallback(async () => {
    if (!pendingBulk) return
    setBulkBusy(true)
    try {
      await pendingBulk.run()
    } catch {
      toast.error('Erro ao executar a ação em lote — nada foi alterado')
    } finally {
      setBulkBusy(false)
      setPendingBulk(null)
    }
  }, [pendingBulk, toast])

  // ── correção de caixa (arrastar/redimensionar o tile focado) ───────────
  const activeImgRef = useRef<HTMLImageElement | null>(null)
  const dragRef = useRef<DragState | null>(null)

  const currentBboxFor = useCallback(
    (proposal: Proposal): ProposalBbox => correctedBboxes[proposal.id] ?? proposal.bbox,
    [correctedBboxes],
  )

  const normFromEvent = useCallback(
    (event: MouseEvent | React.MouseEvent): { x: number; y: number } | null => {
      const img = activeImgRef.current
      if (!img) return null
      const rect = img.getBoundingClientRect()
      if (rect.width === 0 || rect.height === 0) return null
      return {
        x: clamp((event.clientX - rect.left) / rect.width, 0, 1),
        y: clamp((event.clientY - rect.top) / rect.height, 0, 1),
      }
    },
    [],
  )

  const onWindowMouseMove = useCallback(
    (event: MouseEvent) => {
      const drag = dragRef.current
      if (!drag) return
      const pos = normFromEvent(event)
      if (!pos) return
      const nextBox =
        drag.mode === 'move'
          ? moveBox(drag.startBox, pos.x - (drag.offsetX ?? 0), pos.y - (drag.offsetY ?? 0))
          : resizeBox(drag.startBox, drag.handle ?? 'se', pos.x, pos.y)
      setCorrectedBboxes(prev => ({ ...prev, [drag.proposalId]: boxToBbox(nextBox) }))
    },
    [normFromEvent],
  )

  const onWindowMouseUp = useCallback(() => {
    dragRef.current = null
    window.removeEventListener('mousemove', onWindowMouseMove)
    window.removeEventListener('mouseup', onWindowMouseUp)
  }, [onWindowMouseMove])

  const beginDrag = useCallback(
    (drag: DragState) => {
      dragRef.current = drag
      window.addEventListener('mousemove', onWindowMouseMove)
      window.addEventListener('mouseup', onWindowMouseUp)
    },
    [onWindowMouseMove, onWindowMouseUp],
  )

  useEffect(
    () => () => {
      window.removeEventListener('mousemove', onWindowMouseMove)
      window.removeEventListener('mouseup', onWindowMouseUp)
    },
    [onWindowMouseMove, onWindowMouseUp],
  )

  const handleBoxMouseDown = useCallback(
    (event: React.MouseEvent, proposal: Proposal) => {
      if (event.button !== 0) return
      event.stopPropagation()
      const pos = normFromEvent(event)
      if (!pos) return
      const box = bboxToBox(currentBboxFor(proposal), proposal.id)
      beginDrag({
        proposalId: proposal.id,
        mode: 'move',
        startBox: box,
        offsetX: pos.x - box.xCenter,
        offsetY: pos.y - box.yCenter,
      })
    },
    [normFromEvent, currentBboxFor, beginDrag],
  )

  const handleHandleMouseDown = useCallback(
    (event: React.MouseEvent, proposal: Proposal, handle: HandleId) => {
      if (event.button !== 0) return
      event.stopPropagation()
      const box = bboxToBox(currentBboxFor(proposal), proposal.id)
      beginDrag({ proposalId: proposal.id, mode: 'resize', handle, startBox: box })
    },
    [currentBboxFor, beginDrag],
  )

  // ── teclado ───────────────────────────────────────────────────────────────
  const handleKeydown = useCallback(
    (event: KeyboardEvent) => {
      if (proposals.length === 0) return
      if (event.key === 'ArrowRight' || event.key === ' ') {
        event.preventDefault()
        setCorrectMode(false)
        setFocusedIndex(prev => (prev == null ? 0 : Math.min(prev + 1, proposals.length - 1)))
        return
      }
      if (event.key === 'ArrowLeft') {
        event.preventDefault()
        setCorrectMode(false)
        setFocusedIndex(prev => (prev == null ? 0 : Math.max(prev - 1, 0)))
        return
      }
      if (focusedIndex == null) return
      const proposal = proposals[focusedIndex]
      if (!proposal) return
      const key = event.key.toLowerCase()
      if (key === 'c') {
        event.preventDefault()
        setCorrectMode(m => !m)
        return
      }
      if (key === 'a') {
        event.preventDefault()
        void acceptOne(proposal, focusedIndex, correctedBboxes[proposal.id])
        return
      }
      if (key === 'r') {
        event.preventDefault()
        void rejectOne(proposal, focusedIndex)
      }
    },
    [proposals, focusedIndex, correctedBboxes, acceptOne, rejectOne],
  )

  useStudioKeyboard(handleKeydown)

  // ── render ────────────────────────────────────────────────────────────────
  return (
    <div className={s.root}>
      <div className={s.filterBar}>
        <div className={s.filterRow}>
          {jobId && (
            <span className={s.jobChip}>
              Job: {jobId.slice(0, 8)}
              <button className={s.jobChipClose} onClick={clearJobFilter} title="Ver todas as propostas pendentes">
                <X size={12} />
              </button>
            </span>
          )}
          <span className={s.filterLabel}>Classe:</span>
          {(facets?.by_class ?? []).map(f => (
            <button
              key={f.class_name}
              className={`${s.chip}${classFilter.has(f.class_name) ? ` ${s.chipActive}` : ''}`}
              onClick={() => toggleClassFilter(f.class_name)}
            >
              {f.class_name} <span className={s.chipCount}>({f.count})</span>
            </button>
          ))}
        </div>
        <div className={s.filterRow}>
          <span className={s.filterLabel}>Ordenar:</span>
          <button
            className={`${s.sortButton}${sortField === 'confidence' ? ` ${s.sortButtonActive}` : ''}`}
            onClick={() => setSort('confidence')}
          >
            Confiança {sortField === 'confidence' ? (sortOrder === 'asc' ? '↑' : '↓') : ''}
          </button>
          <button
            className={`${s.sortButton}${sortField === 'class_name' ? ` ${s.sortButtonActive}` : ''}`}
            onClick={() => setSort('class_name')}
          >
            Classe {sortField === 'class_name' ? (sortOrder === 'asc' ? '↑' : '↓') : ''}
          </button>
          <span className={s.filterLabel}>Confiança entre</span>
          <input
            type="number"
            min={0}
            max={1}
            step={0.05}
            value={confMinText}
            onChange={e => setConfMinText(e.target.value)}
            placeholder="0.0"
            className={s.confidenceInput}
          />
          <span className={s.filterLabel}>e</span>
          <input
            type="number"
            min={0}
            max={1}
            step={0.05}
            value={confMaxText}
            onChange={e => setConfMaxText(e.target.value)}
            placeholder="1.0"
            className={s.confidenceInput}
          />
          <Button size="sm" variant="secondary" onClick={applyConfidenceRange}>
            Aplicar
          </Button>
        </div>
        <div className={s.filterRow}>
          <span className={s.resultLine}>
            {total} proposta{total === 1 ? '' : 's'} pendente{total === 1 ? '' : 's'}
          </span>
          <div style={{ flex: 1 }} />
          <span className={s.hint}>A aprovar · R rejeitar · C corrigir caixa · ←/→ navegar</span>
        </div>
      </div>

      <div className={s.bulkBar}>
        <div className={s.bulkGroup}>
          <Button size="sm" variant="danger" onClick={requestRejectJob} disabled={!jobId}>
            Rejeitar job inteiro
          </Button>
        </div>
        <div className={s.bulkGroup}>
          <Button size="sm" variant="danger" onClick={requestRejectClass} disabled={!selectedClass}>
            {selectedClass
              ? `Rejeitar classe ${selectedClass} (${selectedClassCount})`
              : 'Rejeitar classe (selecione 1 classe)'}
          </Button>
        </div>
        <div className={s.bulkGroup}>
          <Button size="sm" variant="danger" onClick={requestRejectByConfidence}>
            Rejeitar confiança &lt;
          </Button>
          <input
            type="number"
            min={0}
            max={1}
            step={0.05}
            value={confidenceThreshold}
            onChange={e => setConfidenceThreshold(clamp(Number(e.target.value) || 0, 0, 1))}
            className={s.confidenceInput}
          />
        </div>
        <div className={s.bulkGroup}>
          <Button size="sm" variant="danger" onClick={requestRejectSelection} disabled={selected.size === 0}>
            Rejeitar seleção ({selected.size})
          </Button>
        </div>
      </div>

      {pendingBulk && (
        <div className={s.confirmBar} role="alertdialog" aria-live="assertive">
          <AlertTriangle size={14} />
          <span className={s.confirmText}>{pendingBulk.label}</span>
          <div style={{ flex: 1 }} />
          <Button size="sm" variant="danger" onClick={() => void confirmBulk()} disabled={bulkBusy}>
            {bulkBusy ? 'Aguarde...' : 'Confirmar'}
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setPendingBulk(null)} disabled={bulkBusy}>
            Cancelar
          </Button>
        </div>
      )}

      {loading && proposals.length === 0 ? (
        <div className={s.grid}>
          {Array.from({ length: 12 }).map((_, i) => (
            <Skeleton key={i} variant="rect" width="100%" height={140} />
          ))}
        </div>
      ) : proposals.length === 0 ? (
        <p className={s.emptyState}>
          Fila de triagem vazia — nenhuma proposta pendente com esses filtros.
        </p>
      ) : (
        <div className={s.grid}>
          {proposals.map((proposal, index) => {
            const aspectRatio =
              proposal.frame.width && proposal.frame.height
                ? `${proposal.frame.width} / ${proposal.frame.height}`
                : '4 / 3'
            const isFocused = index === focusedIndex
            return (
              <ProposalTile
                key={proposal.id}
                proposal={proposal}
                bbox={currentBboxFor(proposal)}
                aspectRatio={aspectRatio}
                broken={brokenImages.has(proposal.id)}
                focused={isFocused}
                correctMode={correctMode && isFocused}
                selected={selected.has(proposal.id)}
                corrected={proposal.id in correctedBboxes}
                onClick={event => onTileClick(event, index)}
                onToggleSelect={() => toggleSelect(proposal.id, index)}
                onImgError={() => setBrokenImages(prev => new Set(prev).add(proposal.id))}
                onImgRef={isFocused ? (el => { activeImgRef.current = el }) : undefined}
                onBoxMouseDown={event => handleBoxMouseDown(event, proposal)}
                onHandleMouseDown={(event, handle) => handleHandleMouseDown(event, proposal, handle)}
              />
            )
          })}
        </div>
      )}

      {totalPages > 1 && (
        <div className={s.pagination}>
          <Button size="sm" variant="secondary" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1}>
            ← Anterior
          </Button>
          <span className={s.resultLine}>
            Página {page} de {totalPages}
          </span>
          <Button
            size="sm"
            variant="secondary"
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
          >
            Próxima →
          </Button>
        </div>
      )}
    </div>
  )
}

// ─── tile ────────────────────────────────────────────────────────────────────

interface ProposalTileProps {
  proposal: Proposal
  bbox: ProposalBbox
  aspectRatio: string
  broken: boolean
  focused: boolean
  correctMode: boolean
  selected: boolean
  corrected: boolean
  onClick: (event: React.MouseEvent) => void
  onToggleSelect: () => void
  onImgError: () => void
  onImgRef?: (el: HTMLImageElement | null) => void
  onBoxMouseDown: (event: React.MouseEvent) => void
  onHandleMouseDown: (event: React.MouseEvent, handle: HandleId) => void
}

function ProposalTile({
  proposal,
  bbox,
  aspectRatio,
  broken,
  focused,
  correctMode,
  selected,
  corrected,
  onClick,
  onToggleSelect,
  onImgError,
  onImgRef,
  onBoxMouseDown,
  onHandleMouseDown,
}: ProposalTileProps) {
  const hasImage = Boolean(proposal.frame.url) && !broken
  const confidenceLabel = proposal.confidence != null ? proposal.confidence.toFixed(2) : '—'
  const tileClass = [
    s.tile,
    selected ? s.tileSelected : '',
    correctMode ? s.tileCorrectMode : focused ? s.tileFocused : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div className={tileClass} onClick={onClick} title={`${proposal.class_name} · ${confidenceLabel}`}>
      <input
        type="checkbox"
        className={`${s.checkbox}${selected ? ` ${s.checkboxVisible}` : ''}`}
        checked={selected}
        onChange={onToggleSelect}
        onClick={event => event.stopPropagation()}
      />
      {corrected && <span className={s.correctedBadge}>corrigido</span>}
      <div className={s.tileImageWrap} style={{ aspectRatio }}>
        {hasImage && proposal.frame.url ? (
          <>
            <img
              ref={onImgRef}
              src={proposal.frame.url}
              alt={proposal.class_name}
              loading="lazy"
              className={s.tileImage}
              draggable={false}
              onError={onImgError}
            />
            <div className={s.boxLayer}>
              <div
                className={[s.box, corrected ? s.boxCorrected : '', correctMode ? s.boxEditable : '']
                  .filter(Boolean)
                  .join(' ')}
                style={{
                  left: `${(bbox[0] - bbox[2] / 2) * 100}%`,
                  top: `${(bbox[1] - bbox[3] / 2) * 100}%`,
                  width: `${bbox[2] * 100}%`,
                  height: `${bbox[3] * 100}%`,
                }}
                onMouseDown={correctMode ? onBoxMouseDown : undefined}
              >
                {correctMode &&
                  HANDLES.map(handle => (
                    <div
                      key={handle}
                      className={s.handle}
                      style={HANDLE_POSITIONS[handle]}
                      onMouseDown={event => onHandleMouseDown(event, handle)}
                    />
                  ))}
              </div>
            </div>
          </>
        ) : (
          <div className={s.tileImagePlaceholder}>
            <ImageOff size={16} />
            <span>sem imagem</span>
          </div>
        )}
      </div>
      <div className={s.caption}>
        <span className={s.captionClass}>{proposal.class_name}</span>
        <span className={s.captionConfidence}>{confidenceLabel}</span>
      </div>
    </div>
  )
}
