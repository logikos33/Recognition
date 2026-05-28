/**
 * Hook de estado para o workspace de anotação de qualidade.
 *
 * REGRAS CRÍTICAS do canvas:
 * - bboxes renderizadas com pointerEvents: 'none' — NUNCA onClick nelas
 * - seleção feita via hit-test matemático em handleMouseDown
 * - coordenadas SEMPRE normalizadas [0,1] internamente
 * - auto-save ao trocar de frame
 * - teclado: A/← anterior, D/→ próximo, S pular, Del remover bbox selecionado
 */
import { useState, useCallback, useEffect, useRef } from 'react'
import { qualityService } from '../services/qualityService'
import type { BoundingBox, AnnotationFrame, FrameStatus } from '../types/quality'

interface DrawState {
  startX: number
  startY: number
  currentX: number
  currentY: number
}

interface AnnotationState {
  frames: AnnotationFrame[]
  currentIndex: number
  bboxes: BoundingBox[]
  selectedId: string | null
  isDrawing: boolean
  drawState: DrawState | null
  activeClassId: number
  loading: boolean
  saving: boolean
  error: string | null
}

const INITIAL_STATE: AnnotationState = {
  frames: [],
  currentIndex: 0,
  bboxes: [],
  selectedId: null,
  isDrawing: false,
  drawState: null,
  activeClassId: 1,  // produto_nok por padrão
  loading: true,
  saving: false,
  error: null,
}

export function useQualityAnnotation(inspectionId: string) {
  const [state, setState] = useState<AnnotationState>(INITIAL_STATE)
  const containerRef = useRef<HTMLDivElement | null>(null)
  const savedForFrame = useRef<Set<string>>(new Set())

  // Carregar frames da inspeção
  useEffect(() => {
    let mounted = true
    setState(INITIAL_STATE)
    savedForFrame.current.clear()

    async function load() {
      try {
        const res = await qualityService.getAnnotationFrames(inspectionId)
        if (!mounted) return
        const frames = res.data.frames
        setState(s => ({
          ...s,
          frames,
          bboxes: frames[0]?.annotations ?? [],
          loading: false,
        }))
      } catch {
        if (!mounted) return
        setState(s => ({ ...s, loading: false, error: 'Erro ao carregar frames' }))
      }
    }

    load()
    return () => { mounted = false }
  }, [inspectionId])

  // Auto-save ao sair de um frame
  const saveCurrentFrame = useCallback(async (frameId: string, bboxes: BoundingBox[]) => {
    if (savedForFrame.current.has(`${frameId}:${JSON.stringify(bboxes)}`)) return
    try {
      await qualityService.saveAnnotations(frameId, bboxes)
      savedForFrame.current.add(`${frameId}:${JSON.stringify(bboxes)}`)
    } catch {
      // silent — próxima tentativa será na navegação seguinte
    }
  }, [])

  const currentFrame = state.frames[state.currentIndex] as AnnotationFrame | undefined

  // Navegar para frame (com auto-save do atual)
  const goToFrame = useCallback(async (index: number) => {
    const from = state.frames[state.currentIndex]
    if (from) {
      setState(s => ({ ...s, saving: true }))
      await saveCurrentFrame(from.id, state.bboxes)
      setState(s => ({ ...s, saving: false }))
    }

    const target = state.frames[index]
    if (!target) return
    setState(s => ({
      ...s,
      currentIndex: index,
      bboxes: target.annotations ?? [],
      selectedId: null,
      isDrawing: false,
      drawState: null,
    }))
  }, [state.frames, state.currentIndex, state.bboxes, saveCurrentFrame])

  const goNext = useCallback(() => {
    if (state.currentIndex < state.frames.length - 1) goToFrame(state.currentIndex + 1)
  }, [state.currentIndex, state.frames.length, goToFrame])

  const goPrev = useCallback(() => {
    if (state.currentIndex > 0) goToFrame(state.currentIndex - 1)
  }, [state.currentIndex, goToFrame])

  const skipFrame = useCallback(async () => {
    const frame = currentFrame
    if (!frame) return
    try {
      // Salvar com status 'skipped' (array vazio sinaliza ao backend pular)
      await qualityService.saveAnnotations(frame.id, [])
      setState(s => ({
        ...s,
        frames: s.frames.map((f, i) =>
          i === s.currentIndex ? { ...f, status: 'skipped' as FrameStatus } : f
        ),
      }))
    } catch { /* silent */ }
    goNext()
  }, [currentFrame, goNext])

  // ── Lógica do canvas ──────────────────────────────────────────────────────

  /** Converte coordenadas do evento mouse para normalizadas [0,1] relativas ao container. */
  const toNorm = useCallback((e: React.MouseEvent<HTMLDivElement>): { x: number; y: number } => {
    const rect = e.currentTarget.getBoundingClientRect()
    return {
      x: Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width)),
      y: Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height)),
    }
  }, [])

  /** Hit-test matemático: verifica se ponto (nx, ny) está dentro de alguma bbox. */
  const hitTest = useCallback((nx: number, ny: number, bboxes: BoundingBox[]): string | null => {
    // Percorrer em ordem reversa (última desenhada = primeiro clicável)
    for (let i = bboxes.length - 1; i >= 0; i--) {
      const b = bboxes[i]
      const x1 = b.cx - b.w / 2
      const y1 = b.cy - b.h / 2
      const x2 = b.cx + b.w / 2
      const y2 = b.cy + b.h / 2
      if (nx >= x1 && nx <= x2 && ny >= y1 && ny <= y2) {
        return b.id
      }
    }
    return null
  }, [])

  const handleMouseDown = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (e.button !== 0) return
    const { x, y } = toNorm(e)

    // Hit-test: se clicou em bbox existente, selecionar
    const hit = hitTest(x, y, state.bboxes)
    if (hit) {
      setState(s => ({ ...s, selectedId: hit }))
      return
    }

    // Iniciar desenho de nova bbox
    setState(s => ({
      ...s,
      isDrawing: true,
      selectedId: null,
      drawState: { startX: x, startY: y, currentX: x, currentY: y },
    }))
  }, [toNorm, hitTest, state.bboxes])

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!state.isDrawing || !state.drawState) return
    const { x, y } = toNorm(e)
    setState(s => ({
      ...s,
      drawState: s.drawState ? { ...s.drawState, currentX: x, currentY: y } : null,
    }))
  }, [state.isDrawing, state.drawState, toNorm])

  const handleMouseUp = useCallback((_e: React.MouseEvent<HTMLDivElement>) => {
    if (!state.isDrawing || !state.drawState) return

    const { startX, startY, currentX, currentY } = state.drawState
    const w = Math.abs(currentX - startX)
    const h = Math.abs(currentY - startY)

    // Ignorar bbox muito pequena (< 1% de largura e altura)
    if (w < 0.01 || h < 0.01) {
      setState(s => ({ ...s, isDrawing: false, drawState: null }))
      return
    }

    const cx = Math.min(startX, currentX) + w / 2
    const cy = Math.min(startY, currentY) + h / 2

    const newBox: BoundingBox = {
      id: crypto.randomUUID(),
      class_id: state.activeClassId,
      cx, cy, w, h,
    }

    setState(s => ({
      ...s,
      bboxes: [...s.bboxes, newBox],
      selectedId: newBox.id,
      isDrawing: false,
      drawState: null,
    }))
  }, [state.isDrawing, state.drawState, state.activeClassId])

  const removeSelected = useCallback(() => {
    if (!state.selectedId) return
    setState(s => ({
      ...s,
      bboxes: s.bboxes.filter(b => b.id !== s.selectedId),
      selectedId: null,
    }))
  }, [state.selectedId])

  const setActiveClass = useCallback((classId: number) => {
    setState(s => ({ ...s, activeClassId: classId }))
  }, [])

  // Atalhos de teclado
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      // Não interferir com inputs de texto
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes((e.target as HTMLElement).tagName)) return

      if (e.key === 'ArrowRight' || e.key === 'd') goNext()
      else if (e.key === 'ArrowLeft' || e.key === 'a') goPrev()
      else if (e.key === 's') skipFrame()
      else if (e.key === 'Delete' || e.key === 'Backspace') removeSelected()
      else if (e.key === 'Escape') setState(s => ({ ...s, selectedId: null }))
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [goNext, goPrev, skipFrame, removeSelected])

  // Bbox sendo desenhada (para preview no canvas)
  const previewBox: BoundingBox | null = state.drawState
    ? (() => {
        const { startX, startY, currentX, currentY } = state.drawState
        const w = Math.abs(currentX - startX)
        const h = Math.abs(currentY - startY)
        return {
          id: '__preview__',
          class_id: state.activeClassId,
          cx: Math.min(startX, currentX) + w / 2,
          cy: Math.min(startY, currentY) + h / 2,
          w, h,
        }
      })()
    : null

  return {
    frames: state.frames,
    currentIndex: state.currentIndex,
    currentFrame,
    bboxes: state.bboxes,
    selectedId: state.selectedId,
    isDrawing: state.isDrawing,
    previewBox,
    activeClassId: state.activeClassId,
    loading: state.loading,
    saving: state.saving,
    error: state.error,
    containerRef,
    // handlers
    goToFrame,
    goNext,
    goPrev,
    skipFrame,
    removeSelected,
    setActiveClass,
    handleMouseDown,
    handleMouseMove,
    handleMouseUp,
  }
}
