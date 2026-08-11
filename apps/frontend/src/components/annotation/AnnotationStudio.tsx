/**
 * AnnotationStudio — estúdio de anotação keyboard-first (tela cheia).
 *
 * Regra de ouro: 500 imagens, <10s por imagem, teclado antes de mouse,
 * zero diálogo de confirmação em ação reversível.
 *
 * - A sequência de frames chega CONGELADA por props e nunca é reconsultada
 *   durante a sessão (a coleta está ativa; a lista não pode escorregar).
 * - Salvamento automático (debounce ~800ms) + flush ao trocar de frame,
 *   sair e beforeunload. Erro de save = banner impossível de ignorar.
 *   ⛔ Nunca botão "Salvar" manual; ⛔ nunca perder anotação em silêncio.
 * - Atalhos: D/→ · A/← · 1–9 · C · F · V · X · H · B · +/− · Esc ·
 *   Ctrl+Z/Ctrl+Shift+Z · ? · G (mapa completo no overlay de ajuda).
 * - Fila de aprovação de propostas (migration 111): caixa com borda
 *   tracejada = proposta de IA ainda não revisada (isProposal, studioTypes.
 *   ts). V aprova (edita antes se quiser — flush→review, nunca corrida com
 *   o autosave) · X rejeita (nunca salva caixa). Ambas avançam sozinhas,
 *   mesmo padrão do F.
 */
import {
  useCallback,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
  type CSSProperties,
} from 'react'
import {
  AlertTriangle,
  ArrowLeft,
  Check,
  Eye,
  EyeOff,
  HelpCircle,
  ImageOff,
  Loader2,
  Plus,
  SlidersHorizontal,
  BookOpen,
} from 'lucide-react'
import { api } from '../../services/api'
import { useToast } from '../ui/Toast/useToast'
import { vars } from '../../styles/theme.css'
import type { ApiResponse } from '../../types'
import type { Box, RawAnnotation, StudioClass, StudioFrame } from './studioTypes'
import { boxToPayload, nextBoxId, rawToBox } from './studioTypes'
import {
  boxHistoryReducer,
  cloneBoxes,
  digitToClass,
  emptyFrameState,
  type FrameBoxState,
} from './boxHistory'
import {
  boxFromDrag,
  clamp,
  HANDLES,
  moveBox,
  resizeBox,
  type HandleId,
} from './boxGeometry'
import { useStudioKeyboard } from './useStudioKeyboard'
import {
  GUIDELINES,
  GUIDELINES_DATE,
  GUIDELINES_VERSION,
} from './guidelinesContent'
import * as s from './AnnotationStudio.css'

// ─── constantes ──────────────────────────────────────────────────────────────

const AUTOSAVE_DEBOUNCE_MS = 800
const MIN_ZOOM = 1
const MAX_ZOOM = 8

/** Cores fallback p/ classe sem cor no banco — cores de CLASSE são um
 * sistema à parte da marca (precisam ser distinguíveis entre si sobre
 * imagem de CFTV escura), não estilo de UI. */
const FALLBACK_CLASS_COLORS = [
  '#22c55e', '#3b82f6', '#f59e0b', '#ef4444', '#a855f7', '#14b8a6', // allow: cor de classe (conteúdo), não estilo de UI
  '#eab308', '#ec4899', '#84cc16', '#06b6d4', '#f97316', '#8b5cf6', // allow: cor de classe (conteúdo), não estilo de UI
]

const SHORTCUTS: Array<[string, string]> = [
  ['D  ou  →', 'Próxima imagem'],
  ['A  ou  ←', 'Imagem anterior'],
  ['1–9', 'Classe (na caixa selecionada, ou classe ativa p/ próximo desenho)'],
  ['C', 'Copiar todas as caixas do frame anterior da sequência'],
  ['F', 'Marcar "em dúvida" e avançar'],
  ['V', 'Aprovar proposta pendente (edita antes se quiser) e avançar'],
  ['X', 'Rejeitar proposta pendente (não salva caixa) e avançar'],
  ['Del / Backspace', 'Apagar caixa selecionada'],
  ['Ctrl+Z / Ctrl+Shift+Z', 'Desfazer / refazer (por frame)'],
  ['H', 'Esconder / mostrar caixas'],
  ['B', 'Painel de brilho e contraste (só na exibição)'],
  ['+ / − / roda do mouse', 'Zoom (Espaço+arrastar move a imagem ampliada)'],
  ['Esc', 'Cancelar desenho / desselecionar / fechar painel'],
  ['G', 'Diretrizes de anotação'],
  ['?', 'Este mapa de atalhos'],
]

// ─── estado de caixas por frame ──────────────────────────────────────────────

type StudioBoxesState = Record<string, FrameBoxState>

type StudioBoxesAction =
  | { type: 'load'; frameId: string; boxes: Box[] }
  | { type: 'commit'; frameId: string; boxes: Box[] }
  | { type: 'undo'; frameId: string }
  | { type: 'redo'; frameId: string }
  | { type: 'markSaved'; frameId: string }

function studioBoxesReducer(
  state: StudioBoxesState,
  action: StudioBoxesAction,
): StudioBoxesState {
  const current = state[action.frameId] ?? emptyFrameState()
  const next = boxHistoryReducer(current, action)
  if (next === current) return state
  return { ...state, [action.frameId]: next }
}

// ─── interações de mouse ─────────────────────────────────────────────────────

type Interaction =
  | { mode: 'draw'; startX: number; startY: number; classId: number }
  | { mode: 'move'; boxId: string; offsetX: number; offsetY: number }
  | { mode: 'resize'; boxId: string; handle: HandleId; start: Box }
  | { mode: 'pan'; startClientX: number; startClientY: number; panStartX: number; panStartY: number }

type Overlay = 'help' | 'guidelines' | 'newClass' | null

interface ClassResponseItem {
  id: number | string
  class_id: number
  class_name: string
  display_name?: string | null
  color?: string | null
  is_active?: boolean
  archived_at?: string | null
  usage_count?: number
  source?: string
}

export interface AnnotationStudioProps {
  frames: StudioFrame[]
  initialIndex: number
  moduleCode?: string
  onExit: () => void
}

const HANDLE_POSITIONS: Record<HandleId, CSSProperties> = {
  nw: { left: -5, top: -5, cursor: 'nwse-resize' },
  n: { left: '50%', top: -5, transform: 'translateX(-50%)', cursor: 'ns-resize' },
  ne: { right: -5, top: -5, cursor: 'nesw-resize' },
  e: { right: -5, top: '50%', transform: 'translateY(-50%)', cursor: 'ew-resize' },
  se: { right: -5, bottom: -5, cursor: 'nwse-resize' },
  s: { left: '50%', bottom: -5, transform: 'translateX(-50%)', cursor: 'ns-resize' },
  sw: { left: -5, bottom: -5, cursor: 'nesw-resize' },
  w: { left: -5, top: '50%', transform: 'translateY(-50%)', cursor: 'ew-resize' },
}

export function AnnotationStudio({
  frames,
  initialIndex,
  moduleCode = 'epi',
  onExit,
}: AnnotationStudioProps) {
  const toast = useToast()
  const apiBase = import.meta.env.VITE_API_URL || ''

  const [index, setIndex] = useState(() =>
    clamp(initialIndex, 0, Math.max(0, frames.length - 1)),
  )
  const currentFrame = frames[index]

  // ── caixas por frame (undo/redo por frame) ────────────────────────────────
  const [frameStates, dispatchBoxes] = useReducer(studioBoxesReducer, {})
  const statesRef = useRef<StudioBoxesState>(frameStates)
  statesRef.current = frameStates

  const currentState = frameStates[currentFrame?.id ?? ''] ?? null
  const currentBoxes = currentState?.boxes ?? []

  // ── classes ───────────────────────────────────────────────────────────────
  const [classes, setClasses] = useState<StudioClass[]>([])
  const [classesLoading, setClassesLoading] = useState(true)
  const [activeClassId, setActiveClassId] = useState<number | null>(null)
  const classesRef = useRef(classes)
  classesRef.current = classes
  const activeClassRef = useRef(activeClassId)
  activeClassRef.current = activeClassId

  const loadClasses = useCallback(async () => {
    setClassesLoading(true)
    try {
      const res = await api.get<ApiResponse<{ classes: ClassResponseItem[] }>>(
        `/modules/${moduleCode}/classes`,
      )
      const raw = res?.data?.classes ?? []
      const mapped: StudioClass[] = raw
        .filter(c => c.is_active !== false && !c.archived_at)
        .map((c, i) => ({
          classId: Number(c.class_id),
          name: c.display_name || c.class_name,
          color: c.color || FALLBACK_CLASS_COLORS[i % FALLBACK_CLASS_COLORS.length],
          usageCount: c.usage_count,
        }))
      setClasses(mapped)
      setActiveClassId(prev =>
        prev != null && mapped.some(c => c.classId === prev)
          ? prev
          : mapped[0]?.classId ?? null,
      )
      return mapped
    } catch {
      toast.error('Erro ao carregar classes')
      return []
    } finally {
      setClassesLoading(false)
    }
  }, [moduleCode, toast])

  useEffect(() => {
    void loadClasses()
  }, [loadClasses])

  const classById = useMemo(() => {
    const map = new Map<number, StudioClass>()
    classes.forEach(c => map.set(c.classId, c))
    return map
  }, [classes])

  // ── carga (lazy) das anotações do frame corrente ──────────────────────────
  const [loadingFrame, setLoadingFrame] = useState(false)
  const [loadFailed, setLoadFailed] = useState(false)

  const loadAnnotations = useCallback(async (frameId: string) => {
    if (statesRef.current[frameId]?.loaded) return
    setLoadingFrame(true)
    setLoadFailed(false)
    try {
      const res = await api.get<{ success: boolean; annotations: RawAnnotation[] }>(
        `/training/frames/${frameId}/annotations`,
      )
      dispatchBoxes({
        type: 'load',
        frameId,
        boxes: (res?.annotations ?? []).map(rawToBox),
      })
    } catch {
      setLoadFailed(true)
    } finally {
      setLoadingFrame(false)
    }
  }, [])

  useEffect(() => {
    if (currentFrame) void loadAnnotations(currentFrame.id)
  }, [currentFrame, loadAnnotations])

  // ── salvamento automático ─────────────────────────────────────────────────
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const savingRef = useRef<Set<string>>(new Set())

  const saveFrame = useCallback(
    async (frameId: string) => {
      const st = statesRef.current[frameId]
      if (!st?.dirty || savingRef.current.has(frameId)) return
      const boxesAtSave = st.boxes
      savingRef.current.add(frameId)
      setSaveStatus('saving')
      try {
        await api.post<{ success: boolean; saved: number }>(
          `/training/frames/${frameId}/annotations`,
          {
            annotations: boxesAtSave.map(b =>
              boxToPayload(b, classesRef.current.find(c => c.classId === b.classId)?.name, moduleCode),
            ),
          },
        )
        if (statesRef.current[frameId]?.boxes === boxesAtSave) {
          dispatchBoxes({ type: 'markSaved', frameId })
        }
        setSaveStatus('saved')
      } catch {
        setSaveStatus('error')
      } finally {
        savingRef.current.delete(frameId)
      }
    },
    [moduleCode],
  )
  const saveFrameRef = useRef(saveFrame)
  saveFrameRef.current = saveFrame

  // Debounce: qualquer commit re-arma o timer do frame corrente.
  useEffect(() => {
    if (!currentState?.dirty || !currentFrame) return
    const timer = setTimeout(() => {
      void saveFrameRef.current(currentFrame.id)
    }, AUTOSAVE_DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [currentState, currentFrame])

  const retryAllSaves = useCallback(() => {
    Object.entries(statesRef.current).forEach(([frameId, st]) => {
      if (st.dirty) void saveFrameRef.current(frameId)
    })
  }, [])

  // Flush com keepalive no beforeunload — nunca perder anotação em silêncio.
  useEffect(() => {
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      const dirtyEntries = Object.entries(statesRef.current).filter(([, st]) => st.dirty)
      if (dirtyEntries.length === 0) return
      const token = localStorage.getItem('token')
      dirtyEntries.forEach(([frameId, st]) => {
        void fetch(`${apiBase}/api/training/frames/${frameId}/annotations`, {
          method: 'POST',
          keepalive: true,
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            annotations: st.boxes.map(b =>
              boxToPayload(b, classesRef.current.find(c => c.classId === b.classId)?.name, moduleCode),
            ),
          }),
        })
      })
      event.preventDefault()
    }
    window.addEventListener('beforeunload', onBeforeUnload)
    return () => window.removeEventListener('beforeunload', onBeforeUnload)
  }, [apiBase, moduleCode])

  // ── seleção / desenho / zoom / exibição ───────────────────────────────────
  const [selectedBoxId, setSelectedBoxId] = useState<string | null>(null)
  const [draftBox, setDraftBox] = useState<Box | null>(null)
  const [transientBoxes, setTransientBoxes] = useState<Box[] | null>(null)
  const [boxesHidden, setBoxesHidden] = useState(false)
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [brightness, setBrightness] = useState(100)
  const [contrast, setContrast] = useState(100)
  const [showFilters, setShowFilters] = useState(false)
  const [overlay, setOverlay] = useState<Overlay>(null)
  const [spaceHeld, setSpaceHeld] = useState(false)
  const [imgFallback, setImgFallback] = useState<Record<string, 'fallback' | 'broken'>>({})

  const zoomRef = useRef(zoom)
  zoomRef.current = zoom
  const panRef = useRef(pan)
  panRef.current = pan
  const spaceHeldRef = useRef(spaceHeld)
  spaceHeldRef.current = spaceHeld
  const currentBoxesRef = useRef<Box[]>(currentBoxes)
  currentBoxesRef.current = currentBoxes
  const indexRef = useRef(index)
  indexRef.current = index

  const stageRef = useRef<HTMLDivElement>(null)
  const imgRef = useRef<HTMLImageElement>(null)
  const interactionRef = useRef<Interaction | null>(null)

  const visibleBoxes = transientBoxes ?? currentBoxes

  const commitBoxes = useCallback(
    (boxes: Box[]) => {
      if (!currentFrame) return
      dispatchBoxes({ type: 'commit', frameId: currentFrame.id, boxes })
    },
    [currentFrame],
  )
  const commitBoxesRef = useRef(commitBoxes)
  commitBoxesRef.current = commitBoxes

  // ── navegação ─────────────────────────────────────────────────────────────
  const goTo = useCallback(
    (nextIndex: number) => {
      const bounded = clamp(nextIndex, 0, frames.length - 1)
      const leavingId = frames[indexRef.current]?.id
      if (leavingId) void saveFrameRef.current(leavingId)
      setSelectedBoxId(null)
      setDraftBox(null)
      setTransientBoxes(null)
      interactionRef.current = null
      setIndex(bounded)
    },
    [frames],
  )
  const goToRef = useRef(goTo)
  goToRef.current = goTo

  const handleExit = useCallback(() => {
    Object.entries(statesRef.current).forEach(([frameId, st]) => {
      if (st.dirty) void saveFrameRef.current(frameId)
    })
    onExit()
  }, [onExit])

  // ── copiar caixas do frame anterior (C) ───────────────────────────────────
  const copyFromPrevious = useCallback(async () => {
    const i = indexRef.current
    if (i === 0) {
      toast.info('Primeiro frame da sequência — nada para copiar')
      return
    }
    const prevId = frames[i - 1].id
    let prevState = statesRef.current[prevId]
    if (!prevState?.loaded) {
      try {
        const res = await api.get<{ success: boolean; annotations: RawAnnotation[] }>(
          `/training/frames/${prevId}/annotations`,
        )
        dispatchBoxes({ type: 'load', frameId: prevId, boxes: (res?.annotations ?? []).map(rawToBox) })
        prevState = statesRef.current[prevId]
      } catch {
        toast.error('Erro ao buscar caixas do frame anterior')
        return
      }
    }
    const source = statesRef.current[prevId]?.boxes ?? []
    if (source.length === 0) {
      toast.info('O frame anterior não tem caixas')
      return
    }
    commitBoxesRef.current([...currentBoxesRef.current, ...cloneBoxes(source)])
  }, [frames, toast])

  // ── marcar em dúvida e avançar (F) ────────────────────────────────────────
  const markDuvida = useCallback(() => {
    const frame = frames[indexRef.current]
    if (!frame) return
    goToRef.current(indexRef.current + 1)
    void api
      .post<ApiResponse<{ updated: number }>>('/training/frames/curation', {
        frame_ids: [frame.id],
        status: 'duvida',
      })
      .catch(() => toast.error('Erro ao marcar em dúvida'))
  }, [frames, toast])

  // ── fila de aprovação de propostas: aprovar (V) / rejeitar (X) ────────────
  // migration 111. Só agem quando o frame corrente tem alguma caixa de
  // proposta (isProposal) carregada — F/D/A continuam livres em qualquer
  // frame, mas V/X sem proposta pendente é um no-op silencioso.
  const hasPendingProposal = useCallback(
    (frameId: string) => (statesRef.current[frameId]?.boxes ?? []).some(b => b.isProposal),
    [],
  )

  const approvePendingReview = useCallback(() => {
    const frame = frames[indexRef.current]
    if (!frame || !hasPendingProposal(frame.id)) return
    const isDirty = !!statesRef.current[frame.id]?.dirty
    if (isDirty) {
      // ⛔ Corrida autosave × accept: o usuário editou a proposta (moveu,
      // redimensionou, trocou classe) — as caixas ainda não estão no
      // servidor (autosave é debounced 800ms). Sequência OBRIGATÓRIA:
      // 1) flush do save (as caixas viram anotação humana normal via
      //    POST /annotations, replace-all) — 2) SÓ DEPOIS o endpoint de
      //    review estampa 'accepted' em training_frames. Nunca as duas em
      //    paralelo: se o review rodasse antes/junto do save, um GET
      //    concorrente veria o frame "revisado" com as caixas antigas (ou
      //    nenhuma) ainda no ar. goTo() (chamado abaixo) também dispara
      //    seu próprio flush do frame que está saindo — inofensivo aqui:
      //    o guard `savingRef` de saveFrame já reserva a chamada síncrona
      //    abaixo, então a chamada duplicada de goTo vira no-op.
      void saveFrameRef.current(frame.id).then(() =>
        api
          .post<ApiResponse<{ frame_id: string; status: string }>>(
            `/training/frames/${frame.id}/pre-annotation-review`,
            { status: 'accepted' },
          )
          .catch(() => toast.error('Erro ao aprovar proposta')),
      )
    } else {
      // Não editou nada — aceitar tal como veio. accept-suggestions já
      // estampa 'accepted' na MESMA transação do INSERT (annotation_
      // repository.accept_pre_annotations, migration 111) — sem 2º request.
      void api
        .post<ApiResponse<{ frame_id: string; accepted: number }>>(
          `/training/frames/${frame.id}/accept-suggestions`,
        )
        .catch(() => toast.error('Erro ao aprovar proposta'))
    }
    goToRef.current(indexRef.current + 1)
  }, [frames, hasPendingProposal, toast])

  const rejectPendingProposal = useCallback(() => {
    const frame = frames[indexRef.current]
    if (!frame || !hasPendingProposal(frame.id)) return
    // Rejeitar NUNCA salva caixa (mesmo se o usuário mexeu nelas antes de
    // decidir rejeitar) — ao contrário de goTo/markDuvida, que sempre
    // fazem flush do frame que está saindo. `markSaved` descarta o dirty
    // local SEM chamar /annotations: a edição fica só no estado do
    // navegador e nunca é persistida, evitando a mesma corrida do
    // approve (mas na direção oposta: aqui queremos GARANTIR que nada é
    // salvo, não sequenciar um save).
    dispatchBoxes({ type: 'markSaved', frameId: frame.id })
    setSelectedBoxId(null)
    setDraftBox(null)
    setTransientBoxes(null)
    interactionRef.current = null
    setIndex(clamp(indexRef.current + 1, 0, frames.length - 1))
    void api
      .post<ApiResponse<{ frame_id: string; status: string }>>(
        `/training/frames/${frame.id}/pre-annotation-review`,
        { status: 'rejected' },
      )
      .catch(() => toast.error('Erro ao rejeitar proposta'))
  }, [frames, hasPendingProposal])

  // ── zoom ──────────────────────────────────────────────────────────────────
  const applyZoom = useCallback((factor: number, originX?: number, originY?: number) => {
    const oldZoom = zoomRef.current
    const newZoom = clamp(oldZoom * factor, MIN_ZOOM, MAX_ZOOM)
    if (newZoom === oldZoom) return
    if (newZoom === MIN_ZOOM) {
      setZoom(MIN_ZOOM)
      setPan({ x: 0, y: 0 })
      return
    }
    const stage = stageRef.current
    if (stage && originX != null && originY != null) {
      const rect = stage.getBoundingClientRect()
      const sx = originX - (rect.left + rect.width / 2)
      const sy = originY - (rect.top + rect.height / 2)
      const ratio = newZoom / oldZoom
      setPan(prev => ({ x: sx - ratio * (sx - prev.x), y: sy - ratio * (sy - prev.y) }))
    }
    setZoom(newZoom)
  }, [])

  useEffect(() => {
    const stage = stageRef.current
    if (!stage) return
    const onWheel = (event: WheelEvent) => {
      event.preventDefault()
      applyZoom(event.deltaY < 0 ? 1.15 : 1 / 1.15, event.clientX, event.clientY)
    }
    stage.addEventListener('wheel', onWheel, { passive: false })
    return () => stage.removeEventListener('wheel', onWheel)
  }, [applyZoom])

  // ── mouse: desenhar / mover / redimensionar / pan ─────────────────────────
  const normFromEvent = useCallback((event: MouseEvent | React.MouseEvent) => {
    const img = imgRef.current
    if (!img) return null
    const rect = img.getBoundingClientRect()
    if (rect.width === 0 || rect.height === 0) return null
    return {
      x: clamp((event.clientX - rect.left) / rect.width, 0, 1),
      y: clamp((event.clientY - rect.top) / rect.height, 0, 1),
    }
  }, [])

  const onWindowMouseMove = useCallback(
    (event: MouseEvent) => {
      const interaction = interactionRef.current
      if (!interaction) return
      if (interaction.mode === 'pan') {
        setPan({
          x: interaction.panStartX + (event.clientX - interaction.startClientX),
          y: interaction.panStartY + (event.clientY - interaction.startClientY),
        })
        return
      }
      const pos = normFromEvent(event)
      if (!pos) return
      if (interaction.mode === 'draw') {
        setDraftBox(
          boxFromDrag(interaction.startX, interaction.startY, pos.x, pos.y, interaction.classId, 'draft'),
        )
      } else if (interaction.mode === 'move') {
        setTransientBoxes(
          currentBoxesRef.current.map(b =>
            b.id === interaction.boxId
              ? moveBox(b, pos.x - interaction.offsetX, pos.y - interaction.offsetY)
              : b,
          ),
        )
      } else if (interaction.mode === 'resize') {
        setTransientBoxes(
          currentBoxesRef.current.map(b =>
            b.id === interaction.boxId
              ? resizeBox(interaction.start, interaction.handle, pos.x, pos.y)
              : b,
          ),
        )
      }
    },
    [normFromEvent],
  )

  const onWindowMouseUp = useCallback(
    (event: MouseEvent) => {
      const interaction = interactionRef.current
      interactionRef.current = null
      window.removeEventListener('mousemove', onWindowMouseMove)
      window.removeEventListener('mouseup', onWindowMouseUp)
      if (!interaction || interaction.mode === 'pan') return
      if (interaction.mode === 'draw') {
        const pos = normFromEvent(event)
        setDraftBox(null)
        if (!pos) return
        const box = boxFromDrag(
          interaction.startX,
          interaction.startY,
          pos.x,
          pos.y,
          interaction.classId,
          nextBoxId(),
        )
        if (box) {
          commitBoxesRef.current([...currentBoxesRef.current, box])
          setSelectedBoxId(box.id)
        }
        return
      }
      // move / resize: commit do estado transiente (se houve mudança real)
      setTransientBoxes(prev => {
        if (prev) commitBoxesRef.current(prev)
        return null
      })
    },
    [normFromEvent, onWindowMouseMove],
  )

  const beginInteraction = useCallback(
    (interaction: Interaction) => {
      interactionRef.current = interaction
      window.addEventListener('mousemove', onWindowMouseMove)
      window.addEventListener('mouseup', onWindowMouseUp)
    },
    [onWindowMouseMove, onWindowMouseUp],
  )

  const onStageMouseDown = useCallback(
    (event: React.MouseEvent) => {
      if (event.button === 1 || (event.button === 0 && spaceHeldRef.current)) {
        event.preventDefault()
        beginInteraction({
          mode: 'pan',
          startClientX: event.clientX,
          startClientY: event.clientY,
          panStartX: panRef.current.x,
          panStartY: panRef.current.y,
        })
        return
      }
      if (event.button !== 0) return
      const pos = normFromEvent(event)
      if (!pos) return
      setSelectedBoxId(null)
      const classId = activeClassRef.current
      if (classId == null) return
      beginInteraction({ mode: 'draw', startX: pos.x, startY: pos.y, classId })
    },
    [beginInteraction, normFromEvent],
  )

  const onBoxMouseDown = useCallback(
    (event: React.MouseEvent, box: Box) => {
      if (event.button !== 0 || spaceHeldRef.current) return
      event.stopPropagation()
      const pos = normFromEvent(event)
      if (!pos) return
      setSelectedBoxId(box.id)
      beginInteraction({
        mode: 'move',
        boxId: box.id,
        offsetX: pos.x - box.xCenter,
        offsetY: pos.y - box.yCenter,
      })
    },
    [beginInteraction, normFromEvent],
  )

  const onHandleMouseDown = useCallback(
    (event: React.MouseEvent, box: Box, handle: HandleId) => {
      if (event.button !== 0) return
      event.stopPropagation()
      setSelectedBoxId(box.id)
      beginInteraction({ mode: 'resize', boxId: box.id, handle, start: box })
    },
    [beginInteraction],
  )

  // ── teclado ───────────────────────────────────────────────────────────────
  useStudioKeyboard(
    useCallback(
      (event: KeyboardEvent) => {
        const key = event.key
        if (key === ' ') {
          event.preventDefault()
          setSpaceHeld(true)
          return
        }
        if ((event.ctrlKey || event.metaKey) && key.toLowerCase() === 'z') {
          event.preventDefault()
          const frameId = frames[indexRef.current]?.id
          if (frameId) dispatchBoxes({ type: event.shiftKey ? 'redo' : 'undo', frameId })
          return
        }
        if (event.ctrlKey || event.metaKey || event.altKey) return

        if (key >= '1' && key <= '9') {
          const cls = digitToClass(classesRef.current, Number(key))
          if (!cls) return
          const selected = selectedBoxId
          if (selected) {
            commitBoxesRef.current(
              currentBoxesRef.current.map(b =>
                b.id === selected ? { ...b, classId: cls.classId } : b,
              ),
            )
          }
          setActiveClassId(cls.classId)
          return
        }

        switch (key) {
          case 'd':
          case 'D':
          case 'ArrowRight':
            event.preventDefault()
            goToRef.current(indexRef.current + 1)
            break
          case 'a':
          case 'A':
          case 'ArrowLeft':
            event.preventDefault()
            goToRef.current(indexRef.current - 1)
            break
          case 'c':
          case 'C':
            void copyFromPrevious()
            break
          case 'f':
          case 'F':
            markDuvida()
            break
          case 'v':
          case 'V':
            approvePendingReview()
            break
          case 'x':
          case 'X':
            rejectPendingProposal()
            break
          case 'h':
          case 'H':
            setBoxesHidden(prev => !prev)
            break
          case 'b':
          case 'B':
            setShowFilters(prev => !prev)
            break
          case 'g':
          case 'G':
            setOverlay(prev => (prev === 'guidelines' ? null : 'guidelines'))
            break
          case '?':
            setOverlay(prev => (prev === 'help' ? null : 'help'))
            break
          case '+':
          case '=':
            applyZoom(1.25)
            break
          case '-':
          case '_':
            applyZoom(1 / 1.25)
            break
          case 'Delete':
          case 'Backspace':
            if (selectedBoxId) {
              commitBoxesRef.current(
                currentBoxesRef.current.filter(b => b.id !== selectedBoxId),
              )
              setSelectedBoxId(null)
            }
            break
          case 'Escape':
            if (overlay) {
              setOverlay(null)
            } else if (interactionRef.current?.mode === 'draw') {
              interactionRef.current = null
              setDraftBox(null)
            } else if (showFilters) {
              setShowFilters(false)
            } else {
              setSelectedBoxId(null)
            }
            break
          default:
            break
        }
      },
      [
        applyZoom,
        approvePendingReview,
        copyFromPrevious,
        frames,
        markDuvida,
        overlay,
        rejectPendingProposal,
        selectedBoxId,
        showFilters,
      ],
    ),
  )

  // Soltar Espaço encerra o modo pan (keyup não passa pelo hook de atalhos).
  useEffect(() => {
    const onKeyUp = (event: KeyboardEvent) => {
      if (event.key === ' ') setSpaceHeld(false)
    }
    window.addEventListener('keyup', onKeyUp)
    return () => window.removeEventListener('keyup', onKeyUp)
  }, [])

  // ── criar classe sem perder contexto ──────────────────────────────────────
  const [newClassName, setNewClassName] = useState('')
  const [newClassColor, setNewClassColor] = useState('#22c55e')
  const [creatingClass, setCreatingClass] = useState(false)

  const createClass = useCallback(async () => {
    const name = newClassName.trim()
    if (!name) return
    setCreatingClass(true)
    try {
      const res = await api.post<ApiResponse<{ class_id: number }>>('/classes', {
        name,
        color: newClassColor,
        module: moduleCode,
      })
      const createdId = res?.data?.class_id
      const mapped = await loadClasses()
      if (createdId != null && mapped.some(c => c.classId === createdId)) {
        setActiveClassId(createdId)
      }
      setNewClassName('')
      setOverlay(null)
      toast.success(`Classe "${name}" criada`)
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Erro ao criar classe')
    } finally {
      setCreatingClass(false)
    }
  }, [loadClasses, moduleCode, newClassColor, newClassName, toast])

  // ── scroll automático da fila ─────────────────────────────────────────────
  const currentQueueItemRef = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    currentQueueItemRef.current?.scrollIntoView({ block: 'nearest' })
  }, [index])

  if (!currentFrame) {
    return null
  }

  const frameSrc = (frame: StudioFrame): string =>
    imgFallback[frame.id] === 'fallback' || !frame.url
      ? `${apiBase}/api/training/frames/${frame.id}/image`
      : frame.url

  const hasDirty = Object.values(frameStates).some(st => st.dirty)
  const activeClass = activeClassId != null ? classById.get(activeClassId) ?? null : null
  const frameBroken = imgFallback[currentFrame.id] === 'broken'

  return (
    <div className={s.root}>
      {/* barra superior */}
      <div className={s.topBar}>
        <button className={s.iconButton} onClick={handleExit} title="Voltar à galeria">
          <ArrowLeft size={14} /> Sair
        </button>
        <span className={s.progressText}>
          {index + 1} de {frames.length}
        </span>
        <span className={s.topBarTitle}>
          {currentFrame.cameraName || currentFrame.filename}
        </span>
        {currentFrame.capturedAt && (
          <span className={s.topBarMeta}>
            {new Date(currentFrame.capturedAt).toLocaleString('pt-BR', {
              dateStyle: 'short',
              timeStyle: 'short',
            })}
          </span>
        )}
        <div style={{ flex: 1 }} />
        {saveStatus === 'saving' || hasDirty ? (
          <span className={`${s.saveBadge} ${s.saveBadgeSaving}`}>
            <Loader2 size={12} className={s.spinIcon} /> Salvando…
          </span>
        ) : saveStatus === 'saved' ? (
          <span className={`${s.saveBadge} ${s.saveBadgeSaved}`}>
            <Check size={12} /> Salvo
          </span>
        ) : null}
        <button
          className={`${s.iconButton}${boxesHidden ? ` ${s.iconButtonActive}` : ''}`}
          onClick={() => setBoxesHidden(prev => !prev)}
          title="Esconder/mostrar caixas (H)"
        >
          {boxesHidden ? <EyeOff size={14} /> : <Eye size={14} />}
        </button>
        <button
          className={`${s.iconButton}${showFilters ? ` ${s.iconButtonActive}` : ''}`}
          onClick={() => setShowFilters(prev => !prev)}
          title="Brilho e contraste (B)"
        >
          <SlidersHorizontal size={14} />
        </button>
        <button
          className={`${s.iconButton}${overlay === 'guidelines' ? ` ${s.iconButtonActive}` : ''}`}
          onClick={() => setOverlay(prev => (prev === 'guidelines' ? null : 'guidelines'))}
          title="Diretrizes de anotação (G)"
        >
          <BookOpen size={14} />
        </button>
        <button
          className={`${s.iconButton}${overlay === 'help' ? ` ${s.iconButtonActive}` : ''}`}
          onClick={() => setOverlay(prev => (prev === 'help' ? null : 'help'))}
          title="Atalhos (?)"
        >
          <HelpCircle size={14} />
        </button>
      </div>

      {/* erro de salvamento — impossível de ignorar */}
      {saveStatus === 'error' && (
        <div className={s.errorBanner} role="alert">
          <AlertTriangle size={18} />
          Erro ao salvar as anotações — nada foi perdido, mas ainda não está no servidor.
          <button className={s.errorBannerButton} onClick={retryAllSaves}>
            Tentar de novo
          </button>
        </div>
      )}

      <div className={s.main}>
        {/* palco da imagem */}
        <div
          ref={stageRef}
          className={s.stage}
          style={{ cursor: spaceHeld ? 'grab' : activeClass ? 'crosshair' : 'default' }}
        >
          {frameBroken ? (
            <div className={s.imageBroken}>
              <ImageOff size={40} />
              <span>Esta imagem não carregou. Avance para a próxima (D).</span>
            </div>
          ) : (
            <div
              className={s.imageWrap}
              style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }}
              onMouseDown={onStageMouseDown}
            >
              <img
                ref={imgRef}
                key={currentFrame.id}
                src={frameSrc(currentFrame)}
                alt={currentFrame.filename}
                className={s.stageImage}
                style={{ filter: `brightness(${brightness}%) contrast(${contrast}%)` }}
                draggable={false}
                onError={() =>
                  setImgFallback(prev => ({
                    ...prev,
                    [currentFrame.id]:
                      prev[currentFrame.id] === 'fallback' || !currentFrame.url
                        ? 'broken'
                        : 'fallback',
                  }))
                }
              />
              {!boxesHidden && (
                <div className={s.boxLayer}>
                  {visibleBoxes.map(box => {
                    const cls = classById.get(box.classId)
                    const color = cls?.color ?? FALLBACK_CLASS_COLORS[0]
                    const isSelected = box.id === selectedBoxId
                    // Fila de aprovação de propostas (migration 111): caixa
                    // ainda não revisada (pre_annotations, source='ai') tem
                    // borda tracejada na cor de "atenção" do tema — mesma
                    // semântica do selo "⚠ Proposta" da galeria
                    // (TrainingGallery sealProposta), nunca hex hardcoded.
                    const isProposalBox = box.isProposal === true
                    return (
                      <div
                        key={box.id}
                        className={s.box}
                        style={{
                          left: `${(box.xCenter - box.width / 2) * 100}%`,
                          top: `${(box.yCenter - box.height / 2) * 100}%`,
                          width: `${box.width * 100}%`,
                          height: `${box.height * 100}%`,
                          borderColor: isProposalBox ? vars.color.warning : color,
                          borderStyle: isProposalBox ? 'dashed' : 'solid',
                          background: isSelected ? `${color}33` : 'transparent',
                          zIndex: isSelected ? 2 : 1,
                        }}
                        onMouseDown={e => onBoxMouseDown(e, box)}
                      >
                        <span
                          className={s.boxLabel}
                          style={{ background: isProposalBox ? vars.color.warning : color }}
                        >
                          {cls?.name ?? `classe ${box.classId}`}
                          {isProposalBox ? ' · proposta IA' : ''}
                        </span>
                        {isSelected &&
                          HANDLES.map(handle => (
                            <div
                              key={handle}
                              className={s.handle}
                              style={HANDLE_POSITIONS[handle]}
                              onMouseDown={e => onHandleMouseDown(e, box, handle)}
                            />
                          ))}
                      </div>
                    )
                  })}
                  {draftBox && (
                    <div
                      className={s.box}
                      style={{
                        left: `${(draftBox.xCenter - draftBox.width / 2) * 100}%`,
                        top: `${(draftBox.yCenter - draftBox.height / 2) * 100}%`,
                        width: `${draftBox.width * 100}%`,
                        height: `${draftBox.height * 100}%`,
                        borderColor: classById.get(draftBox.classId)?.color ?? FALLBACK_CLASS_COLORS[0],
                        borderStyle: 'dashed',
                        pointerEvents: 'none',
                      }}
                    />
                  )}
                </div>
              )}
            </div>
          )}

          {loadingFrame && (
            <div style={{ position: 'absolute', top: 12, right: 12, color: vars.color.textMuted, fontSize: 12 }}>
              <Loader2 size={14} className={s.spinIcon} />
            </div>
          )}
          {loadFailed && (
            <div className={s.floatPanel} role="alert" style={{ borderColor: vars.color.danger }}>
              <span style={{ color: vars.color.danger, fontWeight: 700 }}>
                Erro ao carregar as caixas deste frame.
              </span>
              <button className={s.iconButton} onClick={() => void loadAnnotations(currentFrame.id)}>
                Tentar de novo
              </button>
            </div>
          )}

          {/* painel de brilho/contraste — só na exibição, nunca no arquivo */}
          {showFilters && (
            <div className={s.floatPanel}>
              <strong style={{ color: vars.color.textPrimary, fontSize: 12 }}>
                Brilho e contraste (só na exibição)
              </strong>
              <label className={s.sliderRow}>
                <span style={{ width: 60 }}>Brilho</span>
                <input
                  type="range"
                  min={40}
                  max={220}
                  value={brightness}
                  onChange={e => setBrightness(Number(e.target.value))}
                  style={{ flex: 1 }}
                />
              </label>
              <label className={s.sliderRow}>
                <span style={{ width: 60 }}>Contraste</span>
                <input
                  type="range"
                  min={40}
                  max={220}
                  value={contrast}
                  onChange={e => setContrast(Number(e.target.value))}
                  style={{ flex: 1 }}
                />
              </label>
              <button
                className={s.iconButton}
                onClick={() => {
                  setBrightness(100)
                  setContrast(100)
                }}
              >
                Restaurar padrão
              </button>
            </div>
          )}
        </div>

        {/* sidebar */}
        <div className={s.sidebar}>
          <div className={s.sidebarSection}>
            <h4 className={s.sidebarTitle}>Classes</h4>
            {classesLoading ? (
              <span style={{ fontSize: 12, color: vars.color.textMuted }}>Carregando…</span>
            ) : classes.length === 0 ? (
              <button className={s.paletteRow} onClick={() => void loadClasses()}>
                <span className={s.paletteName} style={{ color: vars.color.textMuted }}>
                  Erro ao carregar classes — tentar de novo
                </span>
              </button>
            ) : (
              <>
                {classes.map((cls, i) => (
                  <button
                    key={cls.classId}
                    className={`${s.paletteRow}${cls.classId === activeClassId ? ` ${s.paletteRowActive}` : ''}`}
                    onClick={() => {
                      if (selectedBoxId) {
                        commitBoxes(
                          currentBoxes.map(b =>
                            b.id === selectedBoxId ? { ...b, classId: cls.classId } : b,
                          ),
                        )
                      }
                      setActiveClassId(cls.classId)
                    }}
                  >
                    <span className={s.keyBadge}>{i < 9 ? i + 1 : '·'}</span>
                    <span className={s.colorSwatch} style={{ background: cls.color }} />
                    <span className={s.paletteName}>{cls.name}</span>
                    {cls.usageCount != null && (
                      <span className={s.paletteCount}>{cls.usageCount}</span>
                    )}
                  </button>
                ))}
                <button className={s.paletteRow} onClick={() => setOverlay('newClass')}>
                  <span className={s.keyBadge}>
                    <Plus size={10} />
                  </span>
                  <span className={s.paletteName} style={{ color: vars.color.textMuted }}>
                    Nova classe
                  </span>
                </button>
              </>
            )}
          </div>

          <div className={s.queue}>
            {frames.map((frame, i) => {
              const st = frameStates[frame.id]
              const done = st ? st.boxes.length > 0 && !st.dirty : frame.annotated
              return (
                <button
                  key={frame.id}
                  ref={i === index ? currentQueueItemRef : undefined}
                  className={`${s.queueItem}${i === index ? ` ${s.queueItemCurrent}` : ''}`}
                  onClick={() => goTo(i)}
                >
                  <img
                    src={frameSrc(frame)}
                    alt=""
                    className={s.queueThumb}
                    loading="lazy"
                    onError={e => {
                      ;(e.target as HTMLImageElement).style.visibility = 'hidden'
                    }}
                  />
                  <span className={s.queueMeta}>
                    <span>#{i + 1}</span>
                    {done && (
                      <span className={s.queueDone}>
                        <Check size={10} /> anotado
                      </span>
                    )}
                  </span>
                </button>
              )
            })}
          </div>

          <div className={s.legend}>
            <span className={s.kbd}>D</span> próxima · <span className={s.kbd}>A</span> anterior ·{' '}
            <span className={s.kbd}>1–9</span> classe · <span className={s.kbd}>C</span> copiar ·{' '}
            <span className={s.kbd}>F</span> dúvida · <span className={s.kbd}>V</span> aprovar ·{' '}
            <span className={s.kbd}>X</span> rejeitar · <span className={s.kbd}>?</span> todos
          </div>
        </div>
      </div>

      {/* overlays */}
      {overlay === 'help' && (
        <div className={s.overlayBackdrop} onClick={() => setOverlay(null)}>
          <div className={s.overlayPanel} onClick={e => e.stopPropagation()}>
            <h3 className={s.overlayTitle}>Atalhos do estúdio</h3>
            <table className={s.shortcutTable}>
              <tbody>
                {SHORTCUTS.map(([keys, label]) => (
                  <tr key={keys}>
                    <td className={s.shortcutCell} style={{ whiteSpace: 'nowrap' }}>
                      <span className={s.kbd}>{keys}</span>
                    </td>
                    <td className={s.shortcutCell}>{label}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {overlay === 'guidelines' && (
        <div className={s.overlayBackdrop} onClick={() => setOverlay(null)}>
          <div className={s.overlayPanel} onClick={e => e.stopPropagation()}>
            <h3 className={s.overlayTitle}>Diretrizes de anotação</h3>
            {GUIDELINES.map(section => (
              <div key={section.title} className={s.guidelineSection}>
                <h4 className={s.guidelineTitle}>{section.title}</h4>
                <ul className={s.guidelineList}>
                  {section.items.map(item => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            ))}
            <div className={s.overlayFooter}>
              {GUIDELINES_VERSION} · {GUIDELINES_DATE}
            </div>
          </div>
        </div>
      )}

      {overlay === 'newClass' && (
        <div className={s.overlayBackdrop} onClick={() => setOverlay(null)}>
          <div className={s.overlayPanel} style={{ width: 320 }} onClick={e => e.stopPropagation()}>
            <h3 className={s.overlayTitle}>Nova classe</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <input
                className={s.textInput}
                placeholder="Nome da classe"
                value={newClassName}
                autoFocus
                onChange={e => setNewClassName(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter') void createClass()
                  if (e.key === 'Escape') setOverlay(null)
                }}
              />
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: vars.color.textSecondary }}>
                Cor
                <input
                  type="color"
                  value={newClassColor}
                  onChange={e => setNewClassColor(e.target.value)}
                />
              </label>
              <button
                className={s.iconButton}
                style={{ justifyContent: 'center' }}
                disabled={creatingClass || !newClassName.trim()}
                onClick={() => void createClass()}
              >
                {creatingClass ? 'Criando…' : 'Criar classe'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
