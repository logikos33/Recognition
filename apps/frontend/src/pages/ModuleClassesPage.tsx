/**
 * ModuleClassesPage — o lugar ÚNICO para editar classes (estúdio de anotação).
 *
 * - Classes do tenant ativas, ordenadas por display_order, com: badge da
 *   tecla (1–9, a mesma do estúdio), cor fixa, rename inline, usage_count ao
 *   vivo, arquivar (sem diálogo — toast com Desfazer).
 * - Reordenar por drag (@dnd-kit) → PATCH display_order. Reordenar MUDA a
 *   tecla — o aviso está na tela.
 * - Arquivadas com restaurar (arquivar nunca apaga: caixas continuam).
 * - Catálogo global read-only depois das do tenant.
 * - 🔴 Alerta de desbalanceamento nomeando as classes raras.
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import hotToast, { Toaster } from 'react-hot-toast'
import {
  DndContext,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core'
import {
  SortableContext,
  arrayMove,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { AlertTriangle, Archive, ArchiveRestore, GripVertical, Pencil } from 'lucide-react'
import { api } from '../services/api'
import { useToast } from '../components/ui/Toast/useToast'
import { Skeleton } from '../components/ui/Skeleton/Skeleton'
import { Button } from '../components/ui/Button/Button'
import { vars } from '../styles/theme.css'
import type { ApiResponse } from '../types'
import { computeImbalance, imbalanceMessages } from '../utils/classImbalance'
import { SeletorPolaridade, type Polaridade } from '../components/shared/PolaridadeClasse'

// ─── tipos ───────────────────────────────────────────────────────────────────

interface ModuleClassItem {
  /** tenant: id inteiro de yolo_classes (usado no PATCH /classes/<id>). */
  id: number | string
  /** id p/ anotação — tenant vem namespaced (100000+id); usar como veio. */
  class_id: number
  class_name: string
  display_name: string
  color: string | null
  is_active?: boolean
  source: 'tenant' | 'module'
  archived_at?: string | null
  display_order?: number | null
  usage_count?: number
  /** ADR-0065: o que um evento desta classe É. Três estados — NULL no banco
   *  significa "ninguém decidiu", e isso NÃO é conformidade. */
  polaridade?: Polaridade
}

const MODULE_CODE = 'epi'

/** Cor de CLASSE é conteúdo (default do POST /classes no backend), não estilo de UI. */
const DEFAULT_CLASS_COLOR = '#3b82f6' // allow: cor de classe (conteúdo), não estilo de UI

// ─── linha arrastável (classe do tenant ativa) ───────────────────────────────

interface SortableRowProps {
  cls: ModuleClassItem
  keyNumber: number | null
  onRename: (cls: ModuleClassItem, name: string) => void
  onColor: (cls: ModuleClassItem, color: string) => void
  onArchive: (cls: ModuleClassItem) => void
  onPolaridade: (cls: ModuleClassItem, violacao: boolean) => void
}

function SortableClassRow({
  cls, keyNumber, onRename, onColor, onArchive, onPolaridade,
}: SortableRowProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: String(cls.id),
  })
  const [editing, setEditing] = useState(false)
  const [draftName, setDraftName] = useState(cls.display_name)

  const commitRename = () => {
    setEditing(false)
    const name = draftName.trim()
    if (name && name !== cls.display_name) onRename(cls, name)
    else setDraftName(cls.display_name)
  }

  return (
    <div
      ref={setNodeRef}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.6 : 1,
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '8px 10px',
        borderRadius: 8,
        border: `1px solid ${vars.color.borderDefault}`,
        background: vars.color.bgCard,
      }}
    >
      <span
        {...attributes}
        {...listeners}
        style={{ cursor: 'grab', color: vars.color.textDim, display: 'flex' }}
        title="Arrastar para reordenar (muda a tecla no estúdio)"
      >
        <GripVertical size={15} />
      </span>
      <span
        style={{
          minWidth: 20,
          height: 20,
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 11,
          fontWeight: 700,
          fontFamily: vars.font.mono,
          color: vars.color.textSecondary,
          background: vars.color.bgBase,
          border: `1px solid ${vars.color.borderDefault}`,
          borderRadius: 4,
        }}
        title="Tecla no estúdio de anotação"
      >
        {keyNumber ?? '·'}
      </span>
      <input
        type="color"
        value={cls.color || DEFAULT_CLASS_COLOR}
        onChange={e => onColor(cls, e.target.value)}
        style={{ width: 26, height: 22, padding: 0, border: 'none', background: 'none', cursor: 'pointer' }}
        title="Cor da classe (usada em toda a interface)"
      />
      {editing ? (
        <input
          value={draftName}
          autoFocus
          onChange={e => setDraftName(e.target.value)}
          onBlur={commitRename}
          onKeyDown={e => {
            if (e.key === 'Enter') commitRename()
            if (e.key === 'Escape') {
              setDraftName(cls.display_name)
              setEditing(false)
            }
          }}
          style={{
            flex: 1,
            padding: '4px 8px',
            fontSize: 14,
            color: vars.color.textPrimary,
            background: vars.color.bgBase,
            border: `1px solid ${vars.color.primary}`,
            borderRadius: 6,
          }}
        />
      ) : (
        <button
          onClick={() => setEditing(true)}
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            background: 'none',
            border: 'none',
            cursor: 'text',
            textAlign: 'left',
            fontSize: 14,
            fontWeight: 600,
            color: vars.color.textPrimary,
            padding: 0,
          }}
          title="Clique para renomear (renomear é seguro; as caixas continuam)"
        >
          {cls.display_name}
          <Pencil size={11} style={{ opacity: 0.35 }} />
        </button>
      )}
      <SeletorPolaridade
        polaridade={cls.polaridade ?? 'indefinida'}
        editavel={cls.source === 'tenant'}
        onChange={p => onPolaridade(cls, p === 'violacao')}
      />
      <span
        style={{ fontSize: 12, fontFamily: vars.font.mono, color: vars.color.textMuted }}
        title="Caixas anotadas com esta classe"
      >
        {cls.usage_count ?? 0} caixa{(cls.usage_count ?? 0) !== 1 ? 's' : ''}
      </span>
      <button
        onClick={() => onArchive(cls)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 4,
          padding: '4px 8px',
          fontSize: 12,
          color: vars.color.textMuted,
          background: 'none',
          border: `1px solid ${vars.color.borderDefault}`,
          borderRadius: 6,
          cursor: 'pointer',
        }}
        title="Arquivar (as caixas continuam; dá para restaurar)"
      >
        <Archive size={12} /> Arquivar
      </button>
    </div>
  )
}

// ─── página ──────────────────────────────────────────────────────────────────

export default function ModuleClassesPage() {
  const toast = useToast()
  const [items, setItems] = useState<ModuleClassItem[]>([])
  const [loading, setLoading] = useState(true)
  const [showArchived, setShowArchived] = useState(false)
  const [newName, setNewName] = useState('')
  const [newColor, setNewColor] = useState('#22c55e')
  const [creating, setCreating] = useState(false)

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }))

  const loadClasses = useCallback(async () => {
    try {
      const res = await api.get<ApiResponse<{ classes: ModuleClassItem[] }>>(
        `/modules/${MODULE_CODE}/classes?include_archived=1`,
      )
      setItems(res?.data?.classes ?? [])
    } catch {
      toast.error('Erro ao carregar classes')
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    void loadClasses()
  }, [loadClasses])

  // Partições preservando a ordem do backend (tenant por display_order, depois catálogo)
  const tenantActive = useMemo(
    () => items.filter(c => c.source === 'tenant' && !c.archived_at),
    [items],
  )
  const tenantArchived = useMemo(
    () => items.filter(c => c.source === 'tenant' && c.archived_at),
    [items],
  )
  const catalog = useMemo(() => items.filter(c => c.source === 'module'), [items])

  /** Ordem da paleta do estúdio = tenant ativas + catálogo ativas → teclas 1–9. */
  const keyOrder = useMemo(
    () => [...tenantActive, ...catalog.filter(c => c.is_active !== false)],
    [tenantActive, catalog],
  )
  const keyNumberFor = useCallback(
    (cls: ModuleClassItem): number | null => {
      const idx = keyOrder.findIndex(c => c.class_id === cls.class_id)
      return idx >= 0 && idx < 9 ? idx + 1 : null
    },
    [keyOrder],
  )

  // Desbalanceamento: entre classes ATIVAS (tenant + catálogo ativas)
  const imbalance = useMemo(
    () =>
      computeImbalance(
        keyOrder.map(c => ({ name: c.display_name, usage: c.usage_count ?? 0 })),
      ),
    [keyOrder],
  )

  // ── mutações ──────────────────────────────────────────────────────────────
  const patchClass = useCallback(
    async (cls: ModuleClassItem, fields: Record<string, unknown>, errorMsg: string) => {
      try {
        await api.patch<ApiResponse<unknown>>(`/classes/${cls.id}`, fields)
        void loadClasses()
        return true
      } catch (err: unknown) {
        toast.error(err instanceof Error ? err.message : errorMsg)
        void loadClasses()
        return false
      }
    },
    [loadClasses, toast],
  )

  const handleRename = useCallback(
    (cls: ModuleClassItem, name: string) => {
      setItems(prev =>
        prev.map(c =>
          c.source === 'tenant' && c.id === cls.id
            ? { ...c, display_name: name, class_name: name }
            : c,
        ),
      )
      void patchClass(cls, { name }, 'Erro ao renomear classe')
    },
    [patchClass],
  )

  const handleColor = useCallback(
    (cls: ModuleClassItem, color: string) => {
      setItems(prev =>
        prev.map(c => (c.source === 'tenant' && c.id === cls.id ? { ...c, color } : c)),
      )
      void patchClass(cls, { color }, 'Erro ao mudar a cor')
    },
    [patchClass],
  )

  /** ADR-0065 — polaridade é CADASTRO, não engenharia. Antes de existir esta
   *  rota, marcar uma classe como violação exigia SQL manual no banco, o que
   *  travava o onboarding de cliente novo. Só classe do TENANT: a polaridade
   *  do catálogo global vale para todos e o backend devolve 404 se tentar. */
  const handlePolaridade = useCallback(
    (cls: ModuleClassItem, violacao: boolean) => {
      setItems(prev =>
        prev.map(c =>
          c.source === 'tenant' && c.id === cls.id
            ? { ...c, polaridade: violacao ? 'violacao' : 'conformidade', is_violation: violacao }
            : c,
        ),
      )
      void patchClass(cls, { is_violation: violacao }, 'Erro ao mudar a polaridade')
    },
    [patchClass],
  )

  const handleArchive = useCallback(
    (cls: ModuleClassItem) => {
      const usage = cls.usage_count ?? 0
      // Sem diálogo: executa e oferece Desfazer no toast (~8s)
      setItems(prev =>
        prev.map(c =>
          c.source === 'tenant' && c.id === cls.id
            ? { ...c, archived_at: new Date().toISOString() }
            : c,
        ),
      )
      void patchClass(cls, { archived: true }, 'Erro ao arquivar')
      hotToast(
        t => (
          <span style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 13 }}>
            <span>
              <strong>{cls.display_name}</strong> arquivada
              {usage > 0 ? ` — ${usage} caixa${usage !== 1 ? 's' : ''} continua${usage !== 1 ? 'm' : ''} associada${usage !== 1 ? 's' : ''}` : ''}
              .
            </span>
            <button
              onClick={() => {
                hotToast.dismiss(t.id)
                void patchClass(cls, { archived: false }, 'Erro ao restaurar')
              }}
              style={{
                padding: '3px 10px',
                fontSize: 12,
                fontWeight: 700,
                color: vars.color.textOnPrimary,
                background: vars.color.primary,
                border: 'none',
                borderRadius: 6,
                cursor: 'pointer',
              }}
            >
              Desfazer
            </button>
          </span>
        ),
        { duration: 8000 },
      )
    },
    [patchClass],
  )

  const handleRestore = useCallback(
    (cls: ModuleClassItem) => {
      setItems(prev =>
        prev.map(c =>
          c.source === 'tenant' && c.id === cls.id ? { ...c, archived_at: null } : c,
        ),
      )
      void patchClass(cls, { archived: false }, 'Erro ao restaurar')
    },
    [patchClass],
  )

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event
      if (!over || active.id === over.id) return
      const oldIndex = tenantActive.findIndex(c => String(c.id) === String(active.id))
      const newIndex = tenantActive.findIndex(c => String(c.id) === String(over.id))
      if (oldIndex < 0 || newIndex < 0) return
      const reordered = arrayMove(tenantActive, oldIndex, newIndex)
      // Otimista: recompõe a lista com a nova ordem do tenant
      setItems(prev => [...reordered, ...prev.filter(c => !(c.source === 'tenant' && !c.archived_at))])
      // Persiste display_order = índice novo para as que mudaram
      void (async () => {
        try {
          await Promise.all(
            reordered.map((cls, idx) =>
              cls.display_order === idx
                ? Promise.resolve()
                : api.patch<ApiResponse<unknown>>(`/classes/${cls.id}`, { display_order: idx }),
            ),
          )
        } catch {
          toast.error('Erro ao salvar a ordem')
        } finally {
          void loadClasses()
        }
      })()
    },
    [tenantActive, loadClasses, toast],
  )

  const handleCreate = useCallback(async () => {
    const name = newName.trim()
    if (!name) return
    setCreating(true)
    try {
      await api.post<ApiResponse<{ class_id: number }>>('/classes', {
        name,
        color: newColor,
        module: MODULE_CODE,
      })
      setNewName('')
      toast.success(`Classe "${name}" criada`)
      void loadClasses()
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Erro ao criar classe')
    } finally {
      setCreating(false)
    }
  }, [newName, newColor, loadClasses, toast])

  // ── render ────────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div style={{ padding: 32, display: 'flex', flexDirection: 'column', gap: 10 }}>
        <Skeleton variant="title" width={180} />
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} variant="rect" width="100%" height={40} />
        ))}
      </div>
    )
  }

  const alertMessages = imbalanceMessages(imbalance)

  return (
    <div style={{ padding: '24px 32px', maxWidth: 760 }}>
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

      <h2 style={{ marginBottom: 4, color: vars.color.textPrimary }}>Classes</h2>
      <p style={{ color: vars.color.textSecondary, marginBottom: 20, fontSize: 14 }}>
        O lugar único das classes: a ordem define a tecla (1–9) no estúdio de anotação.
        Renomear é seguro; apagar não existe — arquive.
      </p>

      {/* 🔴 Alerta de desbalanceamento */}
      {alertMessages.length > 0 && (
        <div
          role="alert"
          style={{
            display: 'flex',
            gap: 10,
            alignItems: 'flex-start',
            padding: '12px 16px',
            marginBottom: 20,
            borderRadius: 10,
            background: vars.color.dangerMuted,
            border: `1px solid ${vars.color.danger}`,
            color: vars.color.danger,
            fontSize: 13,
            fontWeight: 600,
          }}
        >
          <AlertTriangle size={18} style={{ flexShrink: 0, marginTop: 1 }} />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <strong>Dataset desbalanceado</strong>
            {alertMessages.map(msg => (
              <span key={msg} style={{ fontWeight: 500 }}>
                {msg}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Classes do tenant (arrastáveis) */}
      <section style={{ marginBottom: 28 }}>
        <h3 style={{ fontSize: 13, fontWeight: 700, color: vars.color.textSecondary, marginBottom: 4 }}>
          Suas classes ({tenantActive.length})
        </h3>
        <p style={{ fontSize: 12, color: vars.color.textMuted, marginBottom: 10 }}>
          Arraste para reordenar — reordenar muda a tecla de atalho no estúdio.
        </p>
        {tenantActive.length === 0 ? (
          <p style={{ color: vars.color.textMuted, fontSize: 13 }}>
            Nenhuma classe própria ainda — crie abaixo ou use as do catálogo.
          </p>
        ) : (
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
            <SortableContext
              items={tenantActive.map(c => String(c.id))}
              strategy={verticalListSortingStrategy}
            >
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {tenantActive.map(cls => (
                  <SortableClassRow
                    key={String(cls.id)}
                    cls={cls}
                    keyNumber={keyNumberFor(cls)}
                    onRename={handleRename}
                    onColor={handleColor}
                    onArchive={handleArchive}
                    onPolaridade={handlePolaridade}
                  />
                ))}
              </div>
            </SortableContext>
          </DndContext>
        )}

        {/* Criar classe */}
        <div style={{ display: 'flex', gap: 8, marginTop: 12, alignItems: 'center' }}>
          <input
            value={newName}
            placeholder="Nova classe (ex.: protetor auricular)"
            onChange={e => setNewName(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter') void handleCreate()
            }}
            style={{
              flex: 1,
              padding: '8px 12px',
              fontSize: 13,
              color: vars.color.textPrimary,
              background: vars.color.bgCard,
              border: `1px solid ${vars.color.borderDefault}`,
              borderRadius: 8,
            }}
          />
          <input
            type="color"
            value={newColor}
            onChange={e => setNewColor(e.target.value)}
            style={{ width: 34, height: 34, padding: 0, border: 'none', background: 'none', cursor: 'pointer' }}
            title="Cor da nova classe"
          />
          <Button
            size="sm"
            variant="primary"
            loading={creating}
            disabled={!newName.trim()}
            onClick={() => void handleCreate()}
          >
            Criar classe
          </Button>
        </div>
      </section>

      {/* Arquivadas */}
      {tenantArchived.length > 0 && (
        <section style={{ marginBottom: 28 }}>
          <button
            onClick={() => setShowArchived(prev => !prev)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              fontSize: 13,
              fontWeight: 700,
              color: vars.color.textMuted,
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: 0,
              marginBottom: 10,
            }}
          >
            <Archive size={13} />
            Arquivadas ({tenantArchived.length}) {showArchived ? '▾' : '▸'}
          </button>
          {showArchived && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {tenantArchived.map(cls => (
                <div
                  key={String(cls.id)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    padding: '8px 10px',
                    borderRadius: 8,
                    border: `1px dashed ${vars.color.borderDefault}`,
                    background: vars.color.bgSurface,
                    opacity: 0.8,
                  }}
                >
                  <span
                    style={{
                      width: 12,
                      height: 12,
                      borderRadius: 3,
                      background: cls.color || vars.color.textDim,
                      flexShrink: 0,
                    }}
                  />
                  <span style={{ flex: 1, fontSize: 14, color: vars.color.textSecondary }}>
                    {cls.display_name}
                  </span>
                  <span style={{ fontSize: 12, fontFamily: vars.font.mono, color: vars.color.textMuted }}>
                    {cls.usage_count ?? 0} caixa{(cls.usage_count ?? 0) !== 1 ? 's' : ''}
                  </span>
                  <button
                    onClick={() => handleRestore(cls)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 4,
                      padding: '4px 8px',
                      fontSize: 12,
                      color: vars.color.textSecondary,
                      background: 'none',
                      border: `1px solid ${vars.color.borderDefault}`,
                      borderRadius: 6,
                      cursor: 'pointer',
                    }}
                  >
                    <ArchiveRestore size={12} /> Restaurar
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {/* Catálogo global (read-only) */}
      {catalog.length > 0 && (
        <section>
          <h3 style={{ fontSize: 13, fontWeight: 700, color: vars.color.textSecondary, marginBottom: 4 }}>
            Catálogo do módulo ({catalog.length})
          </h3>
          <p style={{ fontSize: 12, color: vars.color.textMuted, marginBottom: 10 }}>
            Classes padrão do módulo — somente leitura.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {catalog.map(cls => (
              <div
                key={`cat-${cls.class_id}`}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '8px 10px',
                  borderRadius: 8,
                  border: `1px solid ${vars.color.borderSubtle}`,
                  background: vars.color.bgSurface,
                  opacity: cls.is_active === false ? 0.5 : 1,
                }}
              >
                <span
                  style={{
                    minWidth: 20,
                    height: 20,
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 11,
                    fontWeight: 700,
                    fontFamily: vars.font.mono,
                    color: vars.color.textMuted,
                    background: vars.color.bgBase,
                    border: `1px solid ${vars.color.borderSubtle}`,
                    borderRadius: 4,
                  }}
                >
                  {cls.is_active === false ? '·' : keyNumberFor(cls) ?? '·'}
                </span>
                <span
                  style={{
                    width: 12,
                    height: 12,
                    borderRadius: 3,
                    background: cls.color || vars.color.textDim,
                    flexShrink: 0,
                  }}
                />
                <span style={{ flex: 1, fontSize: 14, color: vars.color.textSecondary }}>
                  {cls.display_name}
                  {cls.is_active === false && (
                    <span style={{ fontSize: 11, color: vars.color.textDim, marginLeft: 8 }}>
                      inativa
                    </span>
                  )}
                </span>
                <span style={{ fontSize: 12, fontFamily: vars.font.mono, color: vars.color.textMuted }}>
                  {cls.usage_count ?? 0} caixa{(cls.usage_count ?? 0) !== 1 ? 's' : ''}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
