/**
 * Classes — o lugar único das classes do Estúdio (`Estúdio.dc.html`, seção
 * "Classes"). A ORQUESTRAÇÃO é a de `pages/ModuleClassesPage.tsx` (fonte da
 * paridade, lida função a função) — porte de COMPORTAMENTO, não de markup:
 *
 *   - GET /modules/{module}/classes?include_archived=1 é o MESMO endpoint que
 *     o antigo usa (`ModuleService.get_classes`, não a rota crua
 *     `/api/classes`): já devolve tenant ∪ catálogo com `polaridade` de três
 *     estados computada no servidor (ADR-0065), `usage_count` e
 *     `display_order` — uma chamada só, sem remontar isso no cliente.
 *   - Mutações vão pela rota crua `/api/classes` (POST cria, PATCH renomeia/
 *     recolore/reordena/arquiva/decide polaridade, DELETE remove) — mesmos
 *     verbos do antigo. DELETE devolve 409 com mensagem legível quando há
 *     anotações vinculadas (`TenantClassService.delete_class`); o antigo
 *     nunca expôs essa ação na UI — aqui ela mora só nas Arquivadas, com
 *     confirmação nativa, porque apagar é o único passo sem volta desta tela.
 *   - Reordenar é DRAG (@dnd-kit), como o antigo — a ordem final é a tecla
 *     1–9 do estúdio.
 *   - `useToast` (novo front) não hospeda botão dentro do toast: o "Desfazer"
 *     do antigo (react-hot-toast com ação embutida) não tem como se portar
 *     literalmente. Arquivar mostra um toast informativo; o desfazer vive na
 *     seção Arquivadas, sempre visível, um clique em "Restaurar" — mesma
 *     reversibilidade, sem o componente que a hospedava.
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  DndContext,
  PointerSensor,
  closestCenter,
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
import {
  AlertTriangle,
  Archive,
  ArchiveRestore,
  GripVertical,
  Pencil,
  Trash2,
} from 'lucide-react'

import { EmptyState } from '../../components/ui/EmptyState/EmptyState'
import { useToast } from '../../components/ui/Toast/useToast'
import { SeletorPolaridade, type Polaridade } from '../../components/shared/PolaridadeClasse'
import { api } from '../../services/api'
import type { ApiResponse } from '../../types'
import { computeImbalance, imbalanceMessages } from '../../utils/classImbalance'
import { LogikosLoader } from '../shell/LogikosLoader'
import { VALORES } from '../tokens/lk.css'
import * as s from './Classes.css'

const MODULE_CODE = 'epi'
const ROTA_LISTA = `/modules/${MODULE_CODE}/classes?include_archived=1`

interface ClasseItem {
  /** tenant: id de yolo_classes (é o que PATCH/DELETE /classes/<id> espera). */
  id: number | string
  /** id namespaced p/ anotação — tenant vem 100000+id; usar como veio. */
  class_id: number
  class_name: string
  display_name: string
  color: string | null
  is_active?: boolean
  source: 'tenant' | 'module'
  archived_at?: string | null
  display_order?: number | null
  usage_count?: number
  /** ADR-0065 — três estados; NULL no banco vira 'indefinida' (ninguém decidiu). */
  polaridade?: Polaridade
}

const caixas = (n: number) => `${n} caixa${n !== 1 ? 's' : ''}`

// ─── linha arrastável (classe do tenant ativa) ───────────────────────────────

interface LinhaProps {
  cls: ClasseItem
  tecla: number | null
  maxUso: number
  onRename: (cls: ClasseItem, name: string) => void
  onColor: (cls: ClasseItem, color: string) => void
  onArchive: (cls: ClasseItem) => void
  onPolaridade: (cls: ClasseItem, violacao: boolean) => void
}

function LinhaClasse({ cls, tecla, maxUso, onRename, onColor, onArchive, onPolaridade }: LinhaProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: String(cls.id),
  })
  const [editando, setEditando] = useState(false)
  const [rascunho, setRascunho] = useState(cls.display_name)
  const uso = cls.usage_count ?? 0
  const pct = maxUso > 0 ? Math.round((uso / maxUso) * 100) : 0

  const salvar = () => {
    setEditando(false)
    const nome = rascunho.trim()
    if (nome && nome !== cls.display_name) onRename(cls, nome)
    else setRascunho(cls.display_name)
  }

  return (
    <div
      ref={setNodeRef}
      className={s.linha}
      style={{ transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.6 : 1 }}
    >
      <span {...attributes} {...listeners} className={s.arrasto} title="Arrastar para reordenar (muda a tecla no estúdio)">
        <GripVertical size={15} />
      </span>
      <span className={s.tecla} title="Tecla no estúdio de anotação">{tecla ?? '·'}</span>
      <input
        type="color"
        className={s.corInput}
        value={cls.color || VALORES.cianoVisao}
        onChange={(e) => onColor(cls, e.target.value)}
        title="Cor da classe (usada em toda a interface)"
      />
      {editando ? (
        <input
          className={s.nomeInput}
          value={rascunho}
          autoFocus
          onChange={(e) => setRascunho(e.target.value)}
          onBlur={salvar}
          onKeyDown={(e) => {
            if (e.key === 'Enter') salvar()
            if (e.key === 'Escape') {
              setRascunho(cls.display_name)
              setEditando(false)
            }
          }}
        />
      ) : (
        <button className={s.nomeBotao} onClick={() => setEditando(true)} title="Clique para renomear — as caixas seguem a classe">
          <span className={s.nomeTexto}>{cls.display_name}</span>
          <Pencil size={11} className={s.nomeIcone} />
        </button>
      )}
      <SeletorPolaridade
        polaridade={cls.polaridade ?? 'indefinida'}
        editavel={cls.source === 'tenant'}
        onChange={(p) => onPolaridade(cls, p === 'violacao')}
      />
      <div className={s.barraWrap}>
        <div className={s.barraPreenchida} style={{ width: `${pct}%`, background: cls.color || VALORES.cianoVisao }} />
      </div>
      <span className={uso < 50 ? `${s.contagem} ${s.contagemBaixa}` : s.contagem}>{caixas(uso)}</span>
      <div className={s.acoes}>
        <button className={s.botaoArquivar} onClick={() => onArchive(cls)} title="Arquivar — as caixas continuam; dá para restaurar">
          <Archive size={12} /> Arquivar
        </button>
      </div>
    </div>
  )
}

// ─── página ──────────────────────────────────────────────────────────────────

export function Classes() {
  const toast = useToast()
  const [items, setItems] = useState<ClasseItem[] | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [showArchived, setShowArchived] = useState(false)
  const [newName, setNewName] = useState('')
  const [newColor, setNewColor] = useState<string>(VALORES.cianoVisao)
  const [creating, setCreating] = useState(false)

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }))

  const carregar = useCallback(() => {
    setErro(null)
    api
      .get<ApiResponse<{ classes: ClasseItem[] }>>(ROTA_LISTA)
      .then((res) => setItems(res?.data?.classes ?? []))
      .catch((e) => setErro(e instanceof Error ? e.message : 'Erro ao carregar classes'))
  }, [])

  useEffect(() => {
    carregar()
  }, [carregar])

  const tenantActive = useMemo(() => (items ?? []).filter((c) => c.source === 'tenant' && !c.archived_at), [items])
  const tenantArchived = useMemo(() => (items ?? []).filter((c) => c.source === 'tenant' && !!c.archived_at), [items])
  const catalog = useMemo(() => (items ?? []).filter((c) => c.source === 'module'), [items])

  /** Ordem da paleta do estúdio = tenant ativas + catálogo ativas → teclas 1–9. */
  const keyOrder = useMemo(
    () => [...tenantActive, ...catalog.filter((c) => c.is_active !== false)],
    [tenantActive, catalog],
  )
  const teclaDe = useCallback(
    (cls: ClasseItem): number | null => {
      const idx = keyOrder.findIndex((c) => c.class_id === cls.class_id)
      return idx >= 0 && idx < 9 ? idx + 1 : null
    },
    [keyOrder],
  )
  const maxUso = useMemo(() => Math.max(0, ...keyOrder.map((c) => c.usage_count ?? 0)), [keyOrder])

  const imbalance = useMemo(
    () => computeImbalance(keyOrder.map((c) => ({ name: c.display_name, usage: c.usage_count ?? 0 }))),
    [keyOrder],
  )
  const avisos = imbalanceMessages(imbalance)

  // ── mutações ────────────────────────────────────────────────────────────
  const patch = useCallback(
    (cls: ClasseItem, fields: Record<string, unknown>, msgErro: string) =>
      api
        .patch<ApiResponse<unknown>>(`/classes/${cls.id}`, fields)
        .then(() => true)
        .catch((e: unknown) => {
          toast.error(e instanceof Error ? e.message : msgErro)
          return false
        })
        .finally(carregar),
    [carregar, toast],
  )

  const handleRename = useCallback(
    (cls: ClasseItem, name: string) => {
      setItems((prev) => (prev ?? []).map((c) => (c.source === 'tenant' && c.id === cls.id ? { ...c, display_name: name, class_name: name } : c)))
      void patch(cls, { name }, 'Erro ao renomear classe')
    },
    [patch],
  )

  const handleColor = useCallback(
    (cls: ClasseItem, color: string) => {
      setItems((prev) => (prev ?? []).map((c) => (c.source === 'tenant' && c.id === cls.id ? { ...c, color } : c)))
      void patch(cls, { color }, 'Erro ao mudar a cor')
    },
    [patch],
  )

  const handlePolaridade = useCallback(
    (cls: ClasseItem, violacao: boolean) => {
      setItems((prev) =>
        (prev ?? []).map((c) =>
          c.source === 'tenant' && c.id === cls.id ? { ...c, polaridade: violacao ? 'violacao' : 'conformidade' } : c,
        ),
      )
      void patch(cls, { is_violation: violacao }, 'Erro ao mudar a polaridade')
    },
    [patch],
  )

  const handleArchive = useCallback(
    (cls: ClasseItem) => {
      const uso = cls.usage_count ?? 0
      setItems((prev) => (prev ?? []).map((c) => (c.source === 'tenant' && c.id === cls.id ? { ...c, archived_at: new Date().toISOString() } : c)))
      void patch(cls, { archived: true }, 'Erro ao arquivar')
      toast.success(
        `"${cls.display_name}" arquivada`,
        uso > 0 ? `${caixas(uso)} continuam associadas. Restaure em "Arquivadas" a qualquer momento.` : 'Restaure em "Arquivadas" a qualquer momento.',
      )
    },
    [patch, toast],
  )

  const handleRestore = useCallback(
    (cls: ClasseItem) => {
      setItems((prev) => (prev ?? []).map((c) => (c.source === 'tenant' && c.id === cls.id ? { ...c, archived_at: null } : c)))
      void patch(cls, { archived: false }, 'Erro ao restaurar')
    },
    [patch],
  )

  const handleDelete = useCallback(
    (cls: ClasseItem) => {
      if (!window.confirm(`Excluir "${cls.display_name}" definitivamente? Isso não pode ser desfeito.`)) return
      api
        .delete<ApiResponse<unknown>>(`/classes/${cls.id}`)
        .then(() => {
          toast.success(`"${cls.display_name}" excluída`)
          carregar()
        })
        .catch((e: unknown) => {
          // 409 chega legível do backend ("Classe possui N anotações vinculadas...").
          toast.error(e instanceof Error ? e.message : 'Erro ao excluir classe')
        })
    },
    [carregar, toast],
  )

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event
      if (!over || active.id === over.id) return
      const oldIndex = tenantActive.findIndex((c) => String(c.id) === String(active.id))
      const newIndex = tenantActive.findIndex((c) => String(c.id) === String(over.id))
      if (oldIndex < 0 || newIndex < 0) return
      const reordered = arrayMove(tenantActive, oldIndex, newIndex)
      setItems((prev) => [...reordered, ...(prev ?? []).filter((c) => !(c.source === 'tenant' && !c.archived_at))])
      Promise.all(
        reordered.map((cls, idx) =>
          cls.display_order === idx ? Promise.resolve() : api.patch<ApiResponse<unknown>>(`/classes/${cls.id}`, { display_order: idx }),
        ),
      )
        .catch(() => toast.error('Erro ao salvar a ordem'))
        .finally(carregar)
    },
    [tenantActive, carregar, toast],
  )

  const handleCreate = useCallback(() => {
    const name = newName.trim()
    if (!name) return
    setCreating(true)
    api
      .post<ApiResponse<{ class_id: number }>>('/classes', { name, color: newColor, module_code: MODULE_CODE })
      .then(() => {
        setNewName('')
        toast.success(`Classe "${name}" criada`)
        carregar()
      })
      .catch((e: unknown) => toast.error(e instanceof Error ? e.message : 'Erro ao criar classe'))
      .finally(() => setCreating(false))
  }, [newName, newColor, carregar, toast])

  // ── render ────────────────────────────────────────────────────────────────
  const criarForm = (
    <div className={s.criarForm}>
      <input
        className={s.criarInput}
        value={newName}
        placeholder="Nova classe (ex.: protetor auricular)"
        onChange={(e) => setNewName(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') handleCreate()
        }}
      />
      <input type="color" className={s.criarCor} value={newColor} onChange={(e) => setNewColor(e.target.value)} title="Cor da nova classe" />
      <button className={s.criarBotao} disabled={!newName.trim() || creating} onClick={handleCreate}>
        {creating ? 'Criando…' : 'Nova classe'}
      </button>
    </div>
  )

  if (erro) {
    return (
      <div className={s.centro}>
        <AlertTriangle size={36} strokeWidth={1.5} color={VALORES.cianoVisao} aria-hidden="true" />
        <span className={s.centroTitulo}>Não foi possível carregar as classes</span>
        <span className={s.centroTecnico}>GET /api{ROTA_LISTA} · {erro}</span>
        <button className={s.botaoRetry} onClick={carregar}>Tentar novamente</button>
      </div>
    )
  }

  if (items === null) {
    return <LogikosLoader estado="waiting" variante="tile" rotulo="CARREGANDO CLASSES" />
  }

  if (tenantActive.length === 0 && tenantArchived.length === 0 && catalog.length === 0) {
    return (
      <EmptyState
        title="Nenhuma classe cadastrada ainda"
        description="Crie a primeira classe para começar a anotar — a ordem em que elas aparecem aqui vira a tecla 1–9 no estúdio."
        action={<div className={s.vazioAcao}>{criarForm}</div>}
      />
    )
  }

  return (
    <div className={s.raiz}>
      <div className={s.cabecalho}>
        <h1 className={s.titulo}>Classes</h1>
        <span className={s.subtitulo}>a ordem define a tecla no anotador</span>
      </div>

      {avisos.length > 0 && (
        <div className={s.aviso} role="alert">
          <AlertTriangle size={18} className={s.avisoIcone} color={VALORES.cianoVisao} aria-hidden="true" />
          <div className={s.avisoCorpo}>
            <span className={s.avisoTitulo}>Desbalanceamento</span>
            {avisos.map((msg) => (
              <span key={msg}>{msg}</span>
            ))}
          </div>
        </div>
      )}

      <section>
        <h2 className={s.secaoTitulo}>Suas classes ({tenantActive.length})</h2>
        <p className={s.secaoLegenda}>Arraste para reordenar — reordenar muda a tecla de atalho no estúdio.</p>
        {tenantActive.length > 0 && (
          <div className={s.lista}>
            <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
              <SortableContext items={tenantActive.map((c) => String(c.id))} strategy={verticalListSortingStrategy}>
                {tenantActive.map((cls) => (
                  <LinhaClasse
                    key={String(cls.id)}
                    cls={cls}
                    tecla={teclaDe(cls)}
                    maxUso={maxUso}
                    onRename={handleRename}
                    onColor={handleColor}
                    onArchive={handleArchive}
                    onPolaridade={handlePolaridade}
                  />
                ))}
              </SortableContext>
            </DndContext>
            {criarForm}
          </div>
        )}
        {tenantActive.length === 0 && <div className={s.lista}>{criarForm}</div>}
      </section>

      {tenantArchived.length > 0 && (
        <section>
          <button className={s.toggleSecao} onClick={() => setShowArchived((v) => !v)}>
            <Archive size={13} />
            Arquivadas ({tenantArchived.length}) {showArchived ? '▾' : '▸'}
          </button>
          {showArchived && (
            <div className={s.lista} style={{ marginTop: '8px' }}>
              {tenantArchived.map((cls) => (
                <div key={String(cls.id)} className={`${s.linha} ${s.linhaArquivada}`}>
                  <span className={s.corSwatch} style={{ background: cls.color || VALORES.cianoVisao }} />
                  <span className={s.nomeCatalogo}>{cls.display_name}</span>
                  <span className={s.contagem}>{caixas(cls.usage_count ?? 0)}</span>
                  <div className={s.acoes}>
                    <button className={s.botaoRestaurar} onClick={() => handleRestore(cls)} title="As caixas continuam associadas">
                      <ArchiveRestore size={12} /> Restaurar
                    </button>
                    <button className={s.botaoExcluir} onClick={() => handleDelete(cls)} title="Exclui de vez — recusa se houver anotações vinculadas">
                      <Trash2 size={12} /> Excluir
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {catalog.length > 0 && (
        <section>
          <h2 className={s.secaoTitulo}>Catálogo do módulo ({catalog.length})</h2>
          <p className={s.secaoLegenda}>Classes padrão do módulo — somente leitura.</p>
          <div className={s.lista}>
            {catalog.map((cls) => (
              <div key={`cat-${cls.class_id}`} className={s.linha} style={{ opacity: cls.is_active === false ? 0.5 : 1 }}>
                <span className={s.tecla}>{cls.is_active === false ? '·' : teclaDe(cls) ?? '·'}</span>
                <span className={s.corSwatch} style={{ background: cls.color || VALORES.cianoVisao }} />
                <span className={s.nomeCatalogo}>
                  {cls.display_name}
                  {cls.is_active === false && <span className={s.inativaTag}>inativa</span>}
                </span>
                <SeletorPolaridade polaridade={cls.polaridade ?? 'indefinida'} editavel={false} onChange={() => {}} />
                <span className={s.contagem}>{caixas(cls.usage_count ?? 0)}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      <p className={s.rodape}>
        Renomear é seguro — as caixas seguem a classe. Apagar não existe na lista principal: classe com caixas é{' '}
        <strong>arquivada</strong> e some das teclas; excluir de vez só é possível em "Arquivadas", e a API recusa se
        houver anotações vinculadas.
      </p>
    </div>
  )
}
