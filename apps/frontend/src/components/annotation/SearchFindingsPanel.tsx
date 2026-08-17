/**
 * SearchFindingsPanel — resultados da busca por conteúdo, agrupados por
 * termo. ACHADO ≠ PROPOSTA: nada aqui vira anotação sozinho — o usuário
 * promove manualmente, um a um ou em lote por termo, escolhendo (ou
 * criando) a classe de destino. Painel ANCORADO (drawer fixo — mesma regra
 * de SearchContentPanel), aberto pelo "Ver achados" de SearchStatusBar.
 *
 * Crop do achado: <div> com overflow hidden + <img> absoluta posicionada
 * por porcentagem do bbox normalizado (0–1) — funciona sem saber a
 * resolução real do frame, porque porcentagens de um filho absoluto são
 * relativas ao container, não ao tamanho intrínseco da imagem.
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { CheckCircle2, X } from 'lucide-react'
import { api } from '../../services/api'
import { searchService, type SearchFinding, type SearchJob } from '../../services/searchService'
import { useToast } from '../ui/Toast/useToast'
import { Skeleton } from '../ui/Skeleton/Skeleton'
import { Button } from '../ui/Button/Button'
import type { ApiResponse } from '../../types'
import { groupFindings } from './searchContentUi'
import * as s from './SearchFindingsPanel.css'

// Mesma convenção de ModuleClassesPage.tsx — módulo único hoje (EPI); os
// termos prontos desta feature também são todos de EPI.
const MODULE_CODE = 'epi'

interface PromotableClass {
  class_name: string
  display_name: string
  is_active?: boolean
  source?: 'tenant' | 'module'
}

export interface SearchFindingsPanelProps {
  jobId: string
  onClose: () => void
}

/** Estilo absoluto do crop: escala a imagem inteira pra que só a região do
 * bbox [x,y,w,h] (fração 0–1) preencha o tile — porcentagens de left/top/
 * width/height de um filho `position:absolute` são relativas ao container,
 * então isto funciona sem precisar da resolução real do frame. */
function cropStyle(bbox: SearchFinding['bbox']): React.CSSProperties {
  const [x, y, w, h] = bbox
  const safeW = Math.max(w, 0.02)
  const safeH = Math.max(h, 0.02)
  return {
    left: `${-(x / safeW) * 100}%`,
    top: `${-(y / safeH) * 100}%`,
    width: `${(1 / safeW) * 100}%`,
    height: `${(1 / safeH) * 100}%`,
  }
}

export function SearchFindingsPanel({ jobId, onClose }: SearchFindingsPanelProps) {
  const toast = useToast()
  const apiBase = import.meta.env.VITE_API_URL || ''

  const [job, setJob] = useState<SearchJob | null>(null)
  const [loading, setLoading] = useState(true)
  const [classes, setClasses] = useState<PromotableClass[]>([])
  const [groupClass, setGroupClass] = useState<Record<string, string>>({})
  const [promotedIndices, setPromotedIndices] = useState<Set<number>>(new Set())
  const [promotingTerm, setPromotingTerm] = useState<string | null>(null)
  const [creatingForTerm, setCreatingForTerm] = useState<string | null>(null)
  const [newClassName, setNewClassName] = useState('')
  const [newClassColor, setNewClassColor] = useState('#22c55e')
  const [creatingClass, setCreatingClass] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    void searchService
      .getJob(jobId)
      .then(data => {
        if (!cancelled) setJob(data)
      })
      .catch(() => {
        if (!cancelled) toast.error('Erro ao carregar os achados desta busca')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId])

  const loadClasses = useCallback(async () => {
    try {
      const res = await api.get<ApiResponse<{ classes: PromotableClass[] }>>(
        `/modules/${MODULE_CODE}/classes`,
      )
      setClasses((res?.data?.classes ?? []).filter(c => c.is_active !== false))
    } catch {
      /* select fica vazio — "criar classe…" continua funcionando isolado */
    }
  }, [])

  useEffect(() => {
    void loadClasses()
  }, [loadClasses])

  const groups = useMemo(() => groupFindings(job?.results ?? []), [job])

  // Pré-seleciona a classe do grupo quando já existe uma com o mesmo nome
  // do rótulo pt do termo (ex.: achou "capacete" e já existe a classe
  // "capacete") — o usuário pode trocar livremente antes de promover.
  useEffect(() => {
    if (classes.length === 0 || groups.length === 0) return
    setGroupClass(prev => {
      let changed = false
      const next = { ...prev }
      for (const g of groups) {
        if (next[g.term]) continue
        const match = classes.find(
          c =>
            c.display_name.toLowerCase() === g.label.toLowerCase() ||
            c.class_name.toLowerCase() === g.label.toLowerCase(),
        )
        if (match) {
          next[g.term] = match.class_name
          changed = true
        }
      }
      return changed ? next : prev
    })
  }, [classes, groups])

  const promote = useCallback(
    async (term: string, indices: number[]) => {
      const className = groupClass[term]
      if (!className || indices.length === 0) return
      setPromotingTerm(term)
      try {
        const promoted = await searchService.promoteFindings(
          jobId,
          indices.map(index => ({ index, class_name: className })),
        )
        setPromotedIndices(prev => {
          const next = new Set(prev)
          indices.forEach(i => next.add(i))
          return next
        })
        toast.success(`${promoted} achado${promoted === 1 ? '' : 's'} promovido${promoted === 1 ? '' : 's'} a proposta`)
      } catch (err: unknown) {
        toast.error(err instanceof Error ? err.message : 'Erro ao promover achado(s)')
      } finally {
        setPromotingTerm(null)
      }
    },
    [groupClass, jobId, toast],
  )

  const handleCreateClass = useCallback(
    async (term: string) => {
      const name = newClassName.trim()
      if (!name) return
      setCreatingClass(true)
      try {
        await api.post<ApiResponse<{ class_id: number }>>('/classes', {
          name,
          color: newClassColor,
          module: MODULE_CODE,
        })
        setClasses(prev => [...prev, { class_name: name, display_name: name, is_active: true, source: 'tenant' }])
        setGroupClass(prev => ({ ...prev, [term]: name }))
        setCreatingForTerm(null)
        setNewClassName('')
        toast.success(`Classe "${name}" criada`)
      } catch (err: unknown) {
        toast.error(err instanceof Error ? err.message : 'Erro ao criar classe')
      } finally {
        setCreatingClass(false)
      }
    },
    [newClassName, newClassColor, toast],
  )

  return (
    <div className={s.panel} role="dialog" aria-label="Achados da busca por conteúdo">
      <div className={s.header}>
        <span className={s.title}>Achados da busca</span>
        <button className={s.closeButton} onClick={onClose} title="Fechar">
          <X size={16} />
        </button>
      </div>

      <div className={s.body}>
        <p className={s.disclaimer} role="alert">
          <strong className={s.disclaimerStrong}>Isto é AMOSTRA, não contagem.</strong> Objeto pequeno em
          substream 704×480 pode não ser visto — "não apareceu" NÃO significa "não tem"; significa que a
          busca não viu.
        </p>

        {loading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <Skeleton variant="text" width="60%" />
            <Skeleton variant="rect" width="100%" height={120} />
          </div>
        ) : !job || job.status !== 'completed' ? (
          <p className={s.emptyText}>
            Esta busca ainda não terminou ou não foi encontrada — feche e acompanhe pela barra de status.
          </p>
        ) : groups.length === 0 ? (
          <p className={s.emptyText}>Nenhum achado nesta busca.</p>
        ) : (
          groups.map(group => {
            const remaining = group.indices.filter(i => !promotedIndices.has(i))
            const selectedClass = groupClass[group.term] ?? ''
            return (
              <div className={s.group} key={group.term}>
                <span className={s.groupTitle}>
                  {group.label} — apareceu em {group.frameCount} imagem{group.frameCount === 1 ? '' : 'ns'} ·
                  {' '}confiança média {Math.round(group.avgConfidence * 100)}%
                </span>

                <div className={s.classRow}>
                  <select
                    className={s.classSelect}
                    value={selectedClass}
                    onChange={e => {
                      if (e.target.value === '__create__') {
                        setCreatingForTerm(group.term)
                        setNewClassName(group.label)
                        return
                      }
                      setGroupClass(prev => ({ ...prev, [group.term]: e.target.value }))
                    }}
                  >
                    <option value="" disabled>
                      selecione a classe…
                    </option>
                    {classes.map(c => (
                      <option key={c.class_name} value={c.class_name}>
                        {c.display_name}
                        {c.source === 'module' ? ' (catálogo)' : ''}
                      </option>
                    ))}
                    <option value="__create__">+ Criar classe…</option>
                  </select>
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={!selectedClass || promotingTerm === group.term || remaining.length === 0}
                    onClick={() => void promote(group.term, remaining)}
                  >
                    {promotingTerm === group.term
                      ? 'Promovendo…'
                      : `Promover todos (${remaining.length})`}
                  </Button>
                </div>

                {creatingForTerm === group.term && (
                  <div className={s.createRow}>
                    <input
                      className={s.createInput}
                      value={newClassName}
                      onChange={e => setNewClassName(e.target.value)}
                      placeholder="Nome da classe"
                      autoFocus
                    />
                    <input
                      type="color"
                      value={newClassColor}
                      onChange={e => setNewClassColor(e.target.value)}
                      style={{ width: 28, height: 26, padding: 0, border: 'none', background: 'none', cursor: 'pointer' }}
                      title="Cor da classe"
                    />
                    <Button
                      size="sm"
                      variant="primary"
                      loading={creatingClass}
                      disabled={!newClassName.trim()}
                      onClick={() => void handleCreateClass(group.term)}
                    >
                      Criar
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setCreatingForTerm(null)}>
                      Cancelar
                    </Button>
                  </div>
                )}

                <div className={s.grid}>
                  {group.indices.map(index => {
                    const finding = job.results[index]
                    const isPromoted = promotedIndices.has(index)
                    return (
                      <div className={s.tile} key={index}>
                        <img
                          className={s.tileImg}
                          src={`${apiBase}/api/training/frames/${finding.frame_id}/image`}
                          style={cropStyle(finding.bbox)}
                          alt=""
                        />
                        <span className={s.confidenceBadge}>{Math.round(finding.confidence * 100)}%</span>
                        {isPromoted ? (
                          <span className={s.promotedBadge}>
                            <CheckCircle2 size={12} /> promovido
                          </span>
                        ) : (
                          <button
                            className={s.promoteButton}
                            disabled={!selectedClass || promotingTerm === group.term}
                            onClick={() => void promote(group.term, [index])}
                          >
                            Promover
                          </button>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
