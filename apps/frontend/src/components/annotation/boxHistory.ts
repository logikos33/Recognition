/**
 * Estado de caixas por frame com desfazer/refazer — lógica pura, testável.
 *
 * Cada frame do estúdio tem sua própria pilha (Ctrl+Z / Ctrl+Shift+Z são
 * por frame). `commit` é a única porta de edição: recebe o array final de
 * caixas após uma operação discreta (desenhar, mover [mouseup], redimensionar
 * [mouseup], apagar, trocar classe, copiar do frame anterior).
 */
import type { Box, StudioClass } from './studioTypes'
import { nextBoxId } from './studioTypes'

export const MAX_HISTORY = 50

export interface FrameBoxState {
  boxes: Box[]
  undoStack: Box[][]
  redoStack: Box[][]
  /** Anotações do servidor já carregadas para este frame. */
  loaded: boolean
  /** Há mudança ainda não persistida (salvamento automático pendente). */
  dirty: boolean
}

export function emptyFrameState(): FrameBoxState {
  return { boxes: [], undoStack: [], redoStack: [], loaded: false, dirty: false }
}

export type BoxHistoryAction =
  | { type: 'load'; boxes: Box[] }
  | { type: 'commit'; boxes: Box[] }
  | { type: 'undo' }
  | { type: 'redo' }
  | { type: 'markSaved' }

export function boxHistoryReducer(
  state: FrameBoxState,
  action: BoxHistoryAction,
): FrameBoxState {
  switch (action.type) {
    case 'load':
      // Carga inicial do servidor — não entra na pilha de undo e não suja.
      return {
        boxes: action.boxes,
        undoStack: [],
        redoStack: [],
        loaded: true,
        dirty: false,
      }
    case 'commit':
      return {
        boxes: action.boxes,
        undoStack: [...state.undoStack, state.boxes].slice(-MAX_HISTORY),
        redoStack: [],
        loaded: state.loaded,
        dirty: true,
      }
    case 'undo': {
      if (state.undoStack.length === 0) return state
      const previous = state.undoStack[state.undoStack.length - 1]
      return {
        boxes: previous,
        undoStack: state.undoStack.slice(0, -1),
        redoStack: [...state.redoStack, state.boxes].slice(-MAX_HISTORY),
        loaded: state.loaded,
        dirty: true,
      }
    }
    case 'redo': {
      if (state.redoStack.length === 0) return state
      const next = state.redoStack[state.redoStack.length - 1]
      return {
        boxes: next,
        undoStack: [...state.undoStack, state.boxes].slice(-MAX_HISTORY),
        redoStack: state.redoStack.slice(0, -1),
        loaded: state.loaded,
        dirty: true,
      }
    }
    case 'markSaved':
      return state.dirty ? { ...state, dirty: false } : state
    default:
      return state
  }
}

/**
 * Tecla numérica (1–9) → classe da paleta, na ordem devolvida pelo backend
 * (tenant por display_order primeiro, catálogo depois). Mesma ordem exibida
 * na tela de classes — reordenar lá muda a tecla aqui.
 */
export function digitToClass(
  classes: StudioClass[],
  digit: number,
): StudioClass | null {
  if (digit < 1 || digit > 9) return null
  return classes[digit - 1] ?? null
}

/**
 * Copiar TODAS as caixas do frame anterior (tecla C) — frames sequenciais da
 * mesma câmera são quase idênticos; copiar e ajustar é ~5× mais rápido que
 * redesenhar. Gera ids locais novos para as cópias.
 */
export function cloneBoxes(source: Box[], makeId: () => string = nextBoxId): Box[] {
  return source.map(box => ({ ...box, id: makeId() }))
}
