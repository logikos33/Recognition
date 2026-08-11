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
import { AlertTriangle, ImageOff, Upload } from 'lucide-react'
import { api } from '../../services/api'
import { useToast } from '../ui/Toast/useToast'
import { LoadingSpinner } from '../shared/LoadingSpinner'
import { Skeleton } from '../ui/Skeleton/Skeleton'
import { Button } from '../ui/Button/Button'
import { vars } from '../../styles/theme.css'
import type { ApiResponse } from '../../types'
import type { StudioFrame } from '../annotation/studioTypes'
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
  source?: string
}

interface GalleryResponse {
  frames: GalleryFrame[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

interface Facets {
  cameras: Array<{ camera_id: string | null; camera_name: string | null; count: number }>
  status: { nao_anotado: number; anotado: number; duvida: number; excluida: number }
}

// 'proposta_pendente' (migration 111): não é curation_status — filtra por
// ?pending_review=true (provenance='proposta' AND review_status IS NULL,
// ver FrameRepository.list_images_filtered). Abre o estúdio com a MESMA
// sequência filtrada (onCardClick já é genérico a qualquer filtro ativo) —
// o contador "X de Y" do estúdio passa a ler como "quantas propostas
// restam" de graça, sem UI dedicada nova.
type StatusFilter =
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
}

export function TrainingGallery({ onOpenStudio, onTotalChange, reloadKey = 0 }: TrainingGalleryProps) {
  const toast = useToast()
  const apiBase = import.meta.env.VITE_API_URL || ''

  // ── filtros / paginação ───────────────────────────────────────────────────
  const [images, setImages] = useState<GalleryFrame[]>([])
  const [facets, setFacets] = useState<Facets | null>(null)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('todos')
  const [cameraId, setCameraId] = useState<string | null>(null)
  const [source, setSource] = useState<SourceFilter>('all')
  const [loading, setLoading] = useState(false)

  // ── seleção múltipla ──────────────────────────────────────────────────────
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const lastClickIndexRef = useRef<number | null>(null)

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
      if (cameraId) params.set('camera_id', cameraId)
      if (source !== 'all') params.set('source', source)
      return params
    },
    [statusFilter, cameraId, source],
  )

  const loadImages = useCallback(
    async (targetPage: number) => {
      setLoading(true)
      try {
        const res = await api.get<ApiResponse<GalleryResponse>>(
          `/training/images?${buildQuery(targetPage)}`,
        )
        const d = res?.data
        if (d) {
          setImages(d.frames || [])
          setTotal(d.total)
          setPage(d.page)
          setTotalPages(d.total_pages)
          onTotalChange?.(d.total)
        }
      } catch {
        /* erro global já notificado pelo api.ts */
      } finally {
        setLoading(false)
      }
    },
    [buildQuery, onTotalChange],
  )

  const loadFacets = useCallback(async () => {
    try {
      const params = new URLSearchParams()
      const curation = curationParamFor(statusFilter)
      if (curation) params.set('curation_status', curation)
      if (cameraId) params.set('camera_id', cameraId)
      if (source !== 'all') params.set('source', source)
      const qs = params.toString()
      const res = await api.get<ApiResponse<Facets>>(
        `/training/images/facets${qs ? `?${qs}` : ''}`,
      )
      if (res?.data?.cameras && res.data.status) setFacets(res.data)
    } catch {
      /* facetas são progressivas — a galeria funciona sem elas */
    }
  }, [statusFilter, cameraId, source])

  useEffect(() => {
    void loadImages(page)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, statusFilter, cameraId, source, reloadKey])

  useEffect(() => {
    void loadFacets()
  }, [loadFacets, reloadKey])

  const resetPageAnd = useCallback((fn: () => void) => {
    fn()
    setPage(1)
    setSelected(new Set())
    lastClickIndexRef.current = null
  }, [])

  // ── nomes de câmera (facetas são a fonte dos nomes) ───────────────────────
  const cameraNames = useMemo(() => {
    const map = new Map<string, string>()
    facets?.cameras.forEach(c => {
      if (c.camera_id) map.set(c.camera_id, c.camera_name || 'Câmera sem nome')
    })
    return map
  }, [facets])

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

  const resultLabel = [
    `${total} image${total === 1 ? 'm' : 'ns'}`,
    cameraId ? cameraLabel(cameraId) : null,
    statusFilter !== 'todos' ? STATUS_LABELS[statusFilter].toLowerCase() : null,
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
          <button
            className={`${s.chip}${cameraId === null ? ` ${s.chipActive}` : ''}`}
            onClick={() => resetPageAnd(() => setCameraId(null))}
          >
            Todas
          </button>
          {facets?.cameras
            .filter(c => c.camera_id)
            .map(c => (
              <button
                key={c.camera_id}
                className={`${s.chip}${cameraId === c.camera_id ? ` ${s.chipActive}` : ''}`}
                onClick={() =>
                  resetPageAnd(() =>
                    setCameraId(prev => (prev === c.camera_id ? null : c.camera_id)),
                  )
                }
              >
                {c.camera_name || 'Câmera sem nome'}
                <span className={s.chipCount}>{c.count}</span>
              </button>
            ))}
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
    </div>
  )
}
