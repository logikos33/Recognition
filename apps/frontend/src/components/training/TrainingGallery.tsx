/**
 * TrainingGallery — aba "Imagens" do treinamento: a porta de entrada da
 * anotação (a galeria NÃO é um navegador de arquivos).
 *
 * - Filtros facetados (câmera com contagem, status de curadoria, origem) com
 *   contagem visível do resultado.
 * - Paginação de servidor (page_size 60) — ⛔ nunca renderizar milhares de
 *   cards de uma vez.
 * - Seleção múltipla (clique/Shift/Ctrl) + barra de ação FIXA sobreposta.
 * - Excluir/dúvida SEM diálogo antes — toast com "Desfazer" (~8s) reverte
 *   via curadoria (excluir nunca apaga do banco).
 * - Clique simples fora do modo seleção abre o AnnotationStudio com a lista
 *   CONGELADA (página filtrada atual), começando naquele frame.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import hotToast, { Toaster } from 'react-hot-toast'
import { AlertTriangle, ImageOff, Search, Upload } from 'lucide-react'
import { api } from '../../services/api'
import { cameraService } from '../../services/cameraService'
import { useToast } from '../ui/Toast/useToast'
import { LoadingSpinner } from '../shared/LoadingSpinner'
import { Skeleton } from '../ui/Skeleton/Skeleton'
import { Button } from '../ui/Button/Button'
import { vars } from '../../styles/theme.css'
import type { ApiResponse, Camera } from '../../types'
import type { StudioFrame } from '../annotation/studioTypes'
import { searchService, type SearchJob } from '../../services/searchService'
import { dismissSearchJob, pickSearchJobToResurface } from '../annotation/searchContentUi'
import { SearchContentPanel } from '../annotation/SearchContentPanel'
import { SearchStatusBar } from '../annotation/SearchStatusBar'
import { SearchFindingsPanel } from '../annotation/SearchFindingsPanel'
import { CameraFilterSelector, type CameraFilterOption } from './CameraFilterSelector'
import * as s from './TrainingGallery.css'

// ─── tipos ───────────────────────────────────────────────────────────────────

export interface GalleryFrame {
  id: string
  video_id: string | null
  frame_number: number
  filename: string
  is_annotated: boolean
  created_at: string
  video_name?: string
  /** Presigned R2 (ttl 1h). */
  url?: string | null
  camera_id?: string | null
  curation_status?: 'active' | 'duvida' | 'excluida'
  provenance?: 'humana' | 'aprovada' | 'proposta' | null
  annotation_count?: number
  /** Propostas de IA ainda sem veredito neste frame (0 quando revisadas). */
  pending_proposals_count?: number
  source?: string
}

interface GalleryResponse {
  frames: GalleryFrame[]
  total: number
  /** Soma das propostas pendentes de TODOS os frames do filtro (não só a página). */
  total_pending_proposals?: number
  page: number
  page_size: number
  total_pages: number
}

interface Facets {
  cameras: Array<{ camera_id: string | null; camera_name: string | null; count: number }>
  status: { nao_anotado: number; anotado: number; duvida: number; excluida: number }
}

// 'proposta_pendente' (migration 111): não é curation_status — filtra por
// ?pending_review=true (proposta de IA sem veredito, INCLUSIVE em frame já
// anotado — ver FrameRepository._PENDING_PROPOSAL_CONDITION). Abre o
// estúdio com a MESMA sequência filtrada (onCardClick já é genérico a
// qualquer filtro ativo) — o contador "X de Y" do estúdio passa a ler como
// "quantas propostas restam" de graça, sem UI dedicada nova.
export type StatusFilter =
  | 'todos'
  | 'nao_anotado'
  | 'anotado'
  | 'duvida'
  | 'excluida'
  | 'proposta_pendente'
type SourceFilter = 'all' | 'nvr' | 'upload' | 'auto' | 'video'
type CurationStatus = 'active' | 'duvida' | 'excluida'

const PAGE_SIZE = 60

const STATUS_LABELS: Record<StatusFilter, string> = {
  todos: 'Todas',
  nao_anotado: 'Não anotadas',
  anotado: 'Anotadas',
  duvida: 'Em dúvida',
  excluida: 'Excluídas',
  proposta_pendente: 'Propostas pendentes',
}

const SOURCE_LABELS: Record<SourceFilter, string> = {
  all: 'Todas',
  nvr: 'Câmera/NVR',
  upload: 'Upload',
  auto: 'Detecção',
  video: 'Vídeo',
}

/** curation_status enviado à API para cada filtro de status da UI. */
function curationParamFor(filter: StatusFilter): CurationStatus | null {
  switch (filter) {
    case 'nao_anotado':
    case 'anotado':
      return 'active'
    case 'duvida':
      return 'duvida'
    case 'excluida':
      return 'excluida'
    default:
      return null
  }
}

export interface TrainingGalleryProps {
  onOpenStudio: (frames: StudioFrame[], initialIndex: number) => void
  onTotalChange?: (total: number) => void
  /** Incrementado pelo pai quando o estúdio fecha — recarrega a página atual. */
  reloadKey?: number
  /** Troca o filtro de status de fora (ex.: "Revisar" na barra de
   * propagação semeada) — `nonce` muda a cada pedido (mesmo filtro pode
   * ser solicitado de novo) pra disparar o efeito mesmo se `filter` não
   * mudar em relação ao valor atual. */
  statusFilterRequest?: { filter: StatusFilter; nonce: number } | null
  /** Foca a galeria numa câmera vindo da matriz de cobertura (aba Cobertura):
   * seleciona só aquela câmera e mostra as não anotadas — "ir anotar aqui".
   * `nonce` re-dispara mesmo pedindo a mesma câmera. */
  cameraFocusRequest?: { cameraId: string; nonce: number } | null
}

export function TrainingGallery({
  onOpenStudio,
  onTotalChange,
  reloadKey = 0,
  statusFilterRequest,
  cameraFocusRequest,
}: TrainingGalleryProps) {
  const toast = useToast()
  const apiBase = import.meta.env.VITE_API_URL || ''

  // ── filtros / paginação ───────────────────────────────────────────────────
  const [images, setImages] = useState<GalleryFrame[]>([])
  const [facets, setFacets] = useState<Facets | null>(null)
  const [total, setTotal] = useState(0)
  const [totalPendingProposals, setTotalPendingProposals] = useState(0)
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('todos')
  // Seleção vazia = "todas" (nenhum filtro de câmera) — mesma convenção do
  // resto da galeria. Substituiu o `cameraId` único (pílulas em linha, que
  // viraram parede ilegível com 29 câmeras — 8 ativas + 21 draft).
  const [cameraIds, setCameraIds] = useState<Set<string>>(new Set())
  const [source, setSource] = useState<SourceFilter>('all')
  const [loading, setLoading] = useState(false)

  // ── câmeras do tenant (lista completa — inclui draft e câmeras sem
  // nenhum frame coletado, requisito 3) ──────────────────────────────────
  const [allCameras, setAllCameras] = useState<Camera[]>([])

  useEffect(() => {
    let cancelled = false
    void cameraService
      .list()
      .then(list => {
        if (!cancelled) setAllCameras(list)
      })
      .catch(() => { /* seletor cai pra o que as facets já trazem */ })
    return () => {
      cancelled = true
    }
  }, [])

  // ── seleção múltipla ──────────────────────────────────────────────────────
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const lastClickIndexRef = useRef<number | null>(null)

  // ── busca por conteúdo (job de GPU sob demanda nas imagens selecionadas) ──
  // Painel de config (frameIds != null), status bar (sobrevive a reload —
  // ressurge no mount igual à barra de propagação semeada) e resultados
  // (searchResultsJobId, aberto pelo "Ver achados" da barra) vivem aqui,
  // self-contidos na galeria (mesmo componente onde o botão de entrada mora).
  const [searchPanelFrameIds, setSearchPanelFrameIds] = useState<string[] | null>(null)
  const [activeSearchJobId, setActiveSearchJobId] = useState<string | null>(null)
  const [searchResultsJobId, setSearchResultsJobId] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    void searchService
      .listJobs()
      .then(jobs => {
        if (cancelled) return
        const job = pickSearchJobToResurface(jobs)
        if (job) setActiveSearchJobId(job.id)
      })
      .catch(() => { /* silent — sem job ativo reconstruído, sem problema */ })
    return () => {
      cancelled = true
    }
  }, [])

  // ── upload ────────────────────────────────────────────────────────────────
  const [uploading, setUploading] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [brokenImages, setBrokenImages] = useState<Set<string>>(new Set())

  const buildQuery = useCallback(
    (targetPage: number) => {
      const params = new URLSearchParams({
        page: String(targetPage),
        page_size: String(PAGE_SIZE),
      })
      const curation = curationParamFor(statusFilter)
      if (curation) params.set('curation_status', curation)
      if (statusFilter === 'nao_anotado') params.set('is_annotated', 'false')
      if (statusFilter === 'anotado') params.set('is_annotated', 'true')
      if (statusFilter === 'proposta_pendente') params.set('pending_review', 'true')
      if (cameraIds.size > 0) params.set('camera_ids', Array.from(cameraIds).join(','))
      if (source !== 'all') params.set('source', source)
      return params
    },
    [statusFilter, cameraIds, source],
  )

  // Sequência da última carga pedida: resposta de um pedido SUPERADO é
  // descartada. Sem isso, trocar de filtro enquanto a carga anterior ainda
  // voa deixa a resposta LENTA (ex.: 'todos', 60 presigned URLs) aterrissar
  // depois da rápida (fila de propostas) e sobrescrever grid e contadores
  // com dados do filtro antigo — visto em navegador real: cabeçalho
  // "8449 imagens · 0 propostas pendentes" com o chip da fila ativo.
  const loadSeqRef = useRef(0)

  const loadImages = useCallback(
    async (targetPage: number) => {
      const seq = ++loadSeqRef.current
      setLoading(true)
      try {
        const res = await api.get<ApiResponse<GalleryResponse>>(
          `/training/images?${buildQuery(targetPage)}`,
        )
        if (seq !== loadSeqRef.current) return
        const d = res?.data
        if (d) {
          setImages(d.frames || [])
          setTotal(d.total)
          setTotalPendingProposals(d.total_pending_proposals ?? 0)
          setPage(d.page)
          setTotalPages(d.total_pages)
          onTotalChange?.(d.total)
        }
      } catch {
        /* erro global já notificado pelo api.ts */
      } finally {
        if (seq === loadSeqRef.current) setLoading(false)
      }
    },
    [buildQuery, onTotalChange],
  )

  const loadFacets = useCallback(async () => {
    try {
      const params = new URLSearchParams()
      const curation = curationParamFor(statusFilter)
      if (curation) params.set('curation_status', curation)
      if (cameraIds.size > 0) params.set('camera_ids', Array.from(cameraIds).join(','))
      if (source !== 'all') params.set('source', source)
      const qs = params.toString()
      const res = await api.get<ApiResponse<Facets>>(
        `/training/images/facets${qs ? `?${qs}` : ''}`,
      )
      if (res?.data?.cameras && res.data.status) setFacets(res.data)
    } catch {
      /* facetas são progressivas — a galeria funciona sem elas */
    }
  }, [statusFilter, cameraIds, source])

  useEffect(() => {
    void loadImages(page)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, statusFilter, cameraIds, source, reloadKey])

  useEffect(() => {
    void loadFacets()
  }, [loadFacets, reloadKey])

  const resetPageAnd = useCallback((fn: () => void) => {
    fn()
    setPage(1)
    setSelected(new Set())
    lastClickIndexRef.current = null
  }, [])

  // Pedido de troca de filtro vindo de fora (barra de propagação semeada,
  // botão "Revisar" — tanto de dentro do estúdio quanto da própria
  // TrainingPage). `nonce` garante que o efeito dispara mesmo pedindo o
  // MESMO filtro de novo (usuário revisita "Revisar" sem trocar de status
  // no meio do caminho).
  useEffect(() => {
    if (!statusFilterRequest) return
    resetPageAnd(() => setStatusFilter(statusFilterRequest.filter))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilterRequest?.nonce])

  // Foco de câmera vindo da matriz de cobertura: filtra só aquela câmera e já
  // mostra as NÃO anotadas — o caminho direto "achei a lacuna → vou anotar".
  useEffect(() => {
    if (!cameraFocusRequest) return
    resetPageAnd(() => {
      setCameraIds(new Set([cameraFocusRequest.cameraId]))
      setStatusFilter('nao_anotado')
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cameraFocusRequest?.nonce])

  // ── opções do seletor de câmera (requisito 3: merge lista completa do
  // tenant + contagens das facets — câmera com 0 frames aparece igual) ──────
  const cameraOptions = useMemo<CameraFilterOption[]>(() => {
    const byId = new Map<string, CameraFilterOption>()
    // Base: TODAS as câmeras do tenant (inclui draft — is_active=false —
    // e as que nunca coletaram frame nenhum; saber que uma câmera não
    // coletou nada é informação, não deve ficar invisível).
    allCameras.forEach(cam => {
      byId.set(cam.id, { cameraId: cam.id, channel: cam.channel, name: cam.name || null, count: 0 })
    })
    // Sobrepõe as contagens das facets — já respeitam o filtro de status/
    // origem ativo (faceta cruzada, requisito 6). Câmera ausente do merge
    // acima (ex.: falha ao carregar /cameras) ainda assim aparece, senão o
    // filtro "esconderia" imagens que existem de verdade.
    facets?.cameras.forEach(c => {
      if (!c.camera_id) return
      const existing = byId.get(c.camera_id)
      if (existing) existing.count = c.count
      else byId.set(c.camera_id, { cameraId: c.camera_id, channel: 0, name: c.camera_name, count: c.count })
    })
    return Array.from(byId.values())
  }, [allCameras, facets])

  const cameraNames = useMemo(() => {
    const map = new Map<string, string>()
    cameraOptions.forEach(c => {
      if (c.name) map.set(c.cameraId, c.name)
    })
    return map
  }, [cameraOptions])

  const cameraLabel = useCallback(
    (id: string | null | undefined): string | null =>
      id ? cameraNames.get(id) ?? 'Câmera' : null,
    [cameraNames],
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
          const img = images[i]
          if (img) next.add(img.id)
        }
        return next
      })
      lastClickIndexRef.current = to
    },
    [images],
  )

  const clearSelection = useCallback(() => {
    setSelected(new Set())
    lastClickIndexRef.current = null
  }, [])

  // ── abrir o estúdio (lista congelada) ─────────────────────────────────────
  const toStudioFrames = useCallback(
    (frames: GalleryFrame[]): StudioFrame[] =>
      frames.map(f => ({
        id: f.id,
        url: f.url ?? null,
        filename: f.filename,
        cameraName: cameraLabel(f.camera_id),
        capturedAt: f.created_at,
        annotated: f.is_annotated,
        cameraId: f.camera_id ?? null,
      })),
    [cameraLabel],
  )

  const openStudioAt = useCallback(
    (index: number) => {
      onOpenStudio(toStudioFrames(images), index)
    },
    [images, onOpenStudio, toStudioFrames],
  )

  const annotateSelection = useCallback(() => {
    const chosen = images.filter(img => selected.has(img.id))
    if (chosen.length === 0) return
    onOpenStudio(toStudioFrames(chosen), 0)
    clearSelection()
  }, [images, selected, onOpenStudio, toStudioFrames, clearSelection])

  const onCardClick = useCallback(
    (event: React.MouseEvent, index: number) => {
      const img = images[index]
      if (!img) return
      if (event.shiftKey && lastClickIndexRef.current != null) {
        event.preventDefault()
        selectRange(lastClickIndexRef.current, index)
        return
      }
      if (event.ctrlKey || event.metaKey) {
        toggleSelect(img.id, index)
        return
      }
      if (selected.size > 0) {
        toggleSelect(img.id, index)
        return
      }
      openStudioAt(index)
    },
    [images, selected, selectRange, toggleSelect, openStudioAt],
  )

  // ── curadoria em lote (sem diálogo; desfazer via toast) ───────────────────
  const curate = useCallback(
    async (
      ids: string[],
      status: CurationStatus,
      message: string,
      undoStatus: CurationStatus | null,
    ) => {
      if (ids.length === 0) return
      try {
        await api.post<ApiResponse<{ updated: number }>>('/training/frames/curation', {
          frame_ids: ids,
          status,
        })
        clearSelection()
        void loadImages(page)
        void loadFacets()
        if (undoStatus) {
          hotToast(
            t => (
              <span style={{ display: 'flex', alignItems: 'center', fontSize: 13 }}>
                {message}
                <button
                  className={s.undoButton}
                  onClick={() => {
                    hotToast.dismiss(t.id)
                    void curate(ids, undoStatus, 'Desfeito.', null)
                  }}
                >
                  Desfazer
                </button>
              </span>
            ),
            { duration: 8000 },
          )
        } else if (message) {
          hotToast.success(message, { duration: 2500 })
        }
      } catch {
        toast.error('Erro na curadoria — nada foi alterado')
      }
    },
    [clearSelection, loadImages, loadFacets, page, toast],
  )

  const selectedIds = useMemo(() => Array.from(selected), [selected])

  // ── upload (funcionalidade existente, preservada) ─────────────────────────
  const uploadImages = useCallback(
    async (files: File[]) => {
      const valid = files.filter(f => /\.(jpe?g|png|webp)$/i.test(f.name))
      if (!valid.length) {
        toast.error('Selecione imagens JPG, PNG ou WebP')
        return
      }
      if (valid.length > 50) {
        toast.error('Máximo de 50 imagens por upload')
        return
      }
      setUploading(true)
      try {
        const form = new FormData()
        valid.forEach(f => form.append('images', f))
        const res = await api.post<ApiResponse<{ uploaded?: number }>>(
          '/v1/videos/images/upload',
          form,
        )
        toast.success(`${res?.data?.uploaded ?? valid.length} imagens enviadas`)
        setPage(1)
        void loadImages(1)
        void loadFacets()
      } catch (err: unknown) {
        toast.error(err instanceof Error ? err.message : 'Erro ao enviar imagens')
      } finally {
        setUploading(false)
      }
    },
    [loadImages, loadFacets, toast],
  )

  // ── render ────────────────────────────────────────────────────────────────
  const statusCount = (f: StatusFilter): number | null => {
    if (!facets) return null
    if (f === 'todos') {
      const st = facets.status
      return st.nao_anotado + st.anotado + st.duvida
    }
    // 'proposta_pendente' (migration 111) não é uma faceta de curation_status
    // — get_facets não conta essa dimensão (MVP sem lote); o chip fica sem
    // número, mesmo padrão visual de qualquer filtro sem faceta carregada.
    if (f === 'proposta_pendente') return null
    return facets.status[f]
  }

  const cameraResultLabel =
    cameraIds.size === 0
      ? null
      : cameraIds.size === 1
        ? cameraLabel(Array.from(cameraIds)[0])
        : `${cameraIds.size} câmeras`

  // Na fila de aprovação o rótulo carrega TAMBÉM o total de propostas —
  // é o número que precisa bater com o toast da propagação e com a soma
  // dos contadores dos cards (invariante da fila; propostas por frame
  // variam, então "N imagens" sozinho não confere com "M propostas").
  const resultLabel = [
    `${total} image${total === 1 ? 'm' : 'ns'}`,
    cameraResultLabel,
    statusFilter === 'proposta_pendente'
      ? `${totalPendingProposals} proposta${totalPendingProposals === 1 ? '' : 's'} pendente${totalPendingProposals === 1 ? '' : 's'}`
      : statusFilter !== 'todos'
        ? STATUS_LABELS[statusFilter].toLowerCase()
        : null,
  ]
    .filter(Boolean)
    .join(' · ')

  return (
    <div>
      <Toaster
        position="bottom-center"
        toastOptions={{
          style: {
            background: vars.color.bgElevated,
            color: vars.color.textPrimary,
            border: `1px solid ${vars.color.borderStrong}`,
          },
        }}
      />

      {/* Progresso da busca por conteúdo — ocupa espaço no layout, sobrevive
          a reload/troca de aba (ressurge no mount via pickSearchJobToResurface). */}
      {activeSearchJobId && (
        <div style={{ marginBottom: 12 }}>
          <SearchStatusBar
            jobId={activeSearchJobId}
            onReview={() => setSearchResultsJobId(activeSearchJobId)}
            onClose={() => {
              dismissSearchJob(activeSearchJobId)
              setActiveSearchJobId(null)
            }}
          />
        </div>
      )}

      {/* Upload */}
      <div
        className={`${s.uploadZone}${dragOver ? ` ${s.uploadZoneActive}` : ''}`}
        onDragOver={e => {
          e.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={e => {
          e.preventDefault()
          setDragOver(false)
          void uploadImages(Array.from(e.dataTransfer.files))
        }}
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          multiple
          hidden
          onChange={e => {
            if (e.target.files) void uploadImages(Array.from(e.target.files))
            e.target.value = ''
          }}
        />
        {uploading ? (
          <>
            <LoadingSpinner />
            <span style={{ fontSize: 13, color: vars.color.textMuted }}>Enviando imagens...</span>
          </>
        ) : (
          <>
            <Upload size={18} style={{ opacity: 0.4, flexShrink: 0 }} />
            <span style={{ fontSize: 13, color: vars.color.textMuted }}>
              Arraste imagens (JPG/PNG/WebP) ou clique — até 50 por vez
            </span>
          </>
        )}
      </div>

      {/* Barra de filtros fixa */}
      <div className={s.filterBar}>
        <div className={s.filterRow}>
          <span className={s.filterLabel}>Câmera:</span>
          <CameraFilterSelector
            cameras={cameraOptions}
            selected={cameraIds}
            onChange={next => resetPageAnd(() => setCameraIds(next))}
          />
        </div>
        <div className={s.filterRow}>
          <span className={s.filterLabel}>Status:</span>
          {(Object.keys(STATUS_LABELS) as StatusFilter[]).map(f => {
            const count = statusCount(f)
            return (
              <button
                key={f}
                className={`${s.chip}${statusFilter === f ? ` ${s.chipActive}` : ''}`}
                onClick={() => resetPageAnd(() => setStatusFilter(f))}
              >
                {STATUS_LABELS[f]}
                {count != null && <span className={s.chipCount}>{count}</span>}
              </button>
            )
          })}
          <span className={s.filterLabel} style={{ marginLeft: 12 }}>
            Origem:
          </span>
          {(Object.keys(SOURCE_LABELS) as SourceFilter[]).map(sf => (
            <button
              key={sf}
              className={`${s.chip}${source === sf ? ` ${s.chipActive}` : ''}`}
              onClick={() => resetPageAnd(() => setSource(sf))}
            >
              {SOURCE_LABELS[sf]}
            </button>
          ))}
        </div>
        <div className={s.filterRow}>
          <span className={s.resultLine}>{resultLabel}</span>
          <div style={{ flex: 1 }} />
          <button
            className={s.selectionLink}
            onClick={() => {
              setSelected(new Set(images.map(i => i.id)))
              lastClickIndexRef.current = null
            }}
          >
            Selecionar todos os visíveis
          </button>
          {selected.size > 0 && (
            <button className={s.selectionLink} onClick={clearSelection}>
              Limpar seleção
            </button>
          )}
        </div>
      </div>

      {/* Grid */}
      {loading && images.length === 0 ? (
        <div className={s.grid}>
          {Array.from({ length: 12 }).map((_, i) => (
            <Skeleton key={i} variant="rect" width="100%" height={104} />
          ))}
        </div>
      ) : images.length === 0 ? (
        <p style={{ color: vars.color.textMuted }}>
          {statusFilter === 'excluida'
            ? 'Nenhuma imagem excluída da coleta.'
            : statusFilter === 'nao_anotado'
              ? 'Nada a anotar com esses filtros — troque a câmera ou o status.'
              : statusFilter === 'proposta_pendente'
                ? 'Fila de aprovação vazia — nenhuma proposta de IA pendente.'
                : 'Nenhuma imagem com esses filtros. Faça upload ou colete frames das câmeras.'}
        </p>
      ) : (
        <div className={s.grid}>
          {images.map((img, index) => {
            const isSelected = selected.has(img.id)
            const camera = cameraLabel(img.camera_id)
            const time = new Date(img.created_at).toLocaleString('pt-BR', {
              day: '2-digit',
              month: '2-digit',
              hour: '2-digit',
              minute: '2-digit',
            })
            const boxes = img.annotation_count ?? 0
            const proposals = img.pending_proposals_count ?? 0
            return (
              <div
                key={img.id}
                className={[
                  s.card,
                  isSelected ? s.cardSelected : '',
                  img.curation_status === 'excluida' ? s.cardExcluded : '',
                ]
                  .filter(Boolean)
                  .join(' ')}
                onClick={e => onCardClick(e, index)}
                title={camera ?? img.video_name ?? img.filename}
              >
                <input
                  type="checkbox"
                  className={`${s.checkbox}${selected.size > 0 ? ` ${s.checkboxVisible}` : ''}`}
                  checked={isSelected}
                  onChange={() => toggleSelect(img.id, index)}
                  onClick={e => e.stopPropagation()}
                />
                {img.provenance === 'humana' && (
                  <span className={`${s.seal} ${s.sealHumana}`}>✓ Humana</span>
                )}
                {img.provenance === 'aprovada' && (
                  <span className={`${s.seal} ${s.sealAprovada}`}>✓ Aprovada</span>
                )}
                {img.provenance === 'proposta' && (
                  <span className={`${s.seal} ${s.sealProposta}`}>⚠ Proposta</span>
                )}
                {brokenImages.has(img.id) ? (
                  <div className={s.cardImageBroken}>
                    <ImageOff size={18} />
                    <span>Imagem não carregou</span>
                  </div>
                ) : (
                  <img
                    src={img.url || `${apiBase}/api/training/frames/${img.id}/image`}
                    alt={img.filename}
                    loading="lazy"
                    className={s.cardImage}
                    onError={() => setBrokenImages(prev => new Set(prev).add(img.id))}
                  />
                )}
                <div className={s.cardMeta}>
                  <div className={s.cardMetaRow}>
                    <span className={s.cardCamera}>
                      {camera ?? img.video_name ?? `#${img.frame_number}`}
                    </span>
                    <span className={s.cardTime}>{time}</span>
                  </div>
                  <div className={s.cardMetaRow}>
                    <span>
                      {boxes} caixa{boxes !== 1 ? 's' : ''}
                      {proposals > 0 &&
                        ` · ${proposals} proposta${proposals !== 1 ? 's' : ''}`}
                    </span>
                    {img.curation_status === 'duvida' && (
                      <span className={`${s.statusChip} ${s.statusChipDuvida}`}>
                        <AlertTriangle size={9} /> Em dúvida
                      </span>
                    )}
                    {img.curation_status === 'excluida' && (
                      <span className={`${s.statusChip} ${s.statusChipExcluida}`}>Excluído</span>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Paginação de servidor */}
      {totalPages > 1 && (
        <div className={s.pagination}>
          <Button
            size="sm"
            variant="secondary"
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page <= 1}
          >
            ← Anterior
          </Button>
          <span style={{ fontSize: 12, color: vars.color.textMuted, fontFamily: vars.font.mono }}>
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

      {/* Barra de ação fixa — sobreposta, não empurra o conteúdo */}
      {selected.size > 0 && (
        <div className={s.actionBar}>
          <span className={s.actionBarCount}>{selected.size} selecionado{selected.size !== 1 ? 's' : ''}</span>
          <Button size="sm" variant="primary" onClick={annotateSelection}>
            Anotar em sequência ({selected.size})
          </Button>
          <Button
            size="sm"
            variant="secondary"
            onClick={() => setSearchPanelFrameIds(selectedIds)}
          >
            <Search size={13} /> Buscar nestas imagens
          </Button>
          <Button
            size="sm"
            variant="secondary"
            onClick={() =>
              void curate(
                selectedIds,
                'duvida',
                `${selectedIds.length} marcada${selectedIds.length !== 1 ? 's' : ''} em dúvida.`,
                'active',
              )
            }
          >
            Marcar em dúvida
          </Button>
          {statusFilter === 'excluida' ? (
            <Button
              size="sm"
              variant="success"
              onClick={() =>
                void curate(
                  selectedIds,
                  'active',
                  `${selectedIds.length} restaurada${selectedIds.length !== 1 ? 's' : ''} para a coleta.`,
                  'excluida',
                )
              }
            >
              Restaurar
            </Button>
          ) : (
            <Button
              size="sm"
              variant="danger"
              onClick={() =>
                void curate(
                  selectedIds,
                  'excluida',
                  `${selectedIds.length} excluída${selectedIds.length !== 1 ? 's' : ''} da coleta.`,
                  'active',
                )
              }
            >
              Excluir da coleta
            </Button>
          )}
          <button className={s.selectionLink} onClick={clearSelection}>
            Limpar
          </button>
        </div>
      )}

      {/* Busca por conteúdo — painel de config (dispara o job) e painel de
          resultados (achados promovíveis) são drawers ancorados fixos, não
          disputam layout com a barra de status acima. */}
      {searchPanelFrameIds && (
        <SearchContentPanel
          frameIds={searchPanelFrameIds}
          onClose={() => setSearchPanelFrameIds(null)}
          onStarted={(job: SearchJob) => {
            setActiveSearchJobId(job.id)
            setSearchPanelFrameIds(null)
            clearSelection()
          }}
        />
      )}
      {searchResultsJobId && (
        <SearchFindingsPanel jobId={searchResultsJobId} onClose={() => setSearchResultsJobId(null)} />
      )}
    </div>
  )
}
