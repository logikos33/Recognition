/**
 * Tests: lógica pura do estúdio de anotação — pilha de undo/redo por frame,
 * mapeamento tecla→classe e cópia de caixas do frame anterior.
 */
import { describe, expect, it } from 'vitest'
import {
  boxHistoryReducer,
  cloneBoxes,
  digitToClass,
  emptyFrameState,
  MAX_HISTORY,
  type FrameBoxState,
} from '../../../components/annotation/boxHistory'
import type { Box, StudioClass } from '../../../components/annotation/studioTypes'

function box(id: string, classId = 1): Box {
  return { id, classId, xCenter: 0.5, yCenter: 0.5, width: 0.2, height: 0.2 }
}

describe('boxHistoryReducer', () => {
  it('load define as caixas sem sujar nem criar histórico', () => {
    const state = boxHistoryReducer(emptyFrameState(), {
      type: 'load',
      boxes: [box('a')],
    })
    expect(state.boxes).toHaveLength(1)
    expect(state.loaded).toBe(true)
    expect(state.dirty).toBe(false)
    expect(state.undoStack).toHaveLength(0)
  })

  it('commit empilha o estado anterior, limpa redo e marca dirty', () => {
    let state = boxHistoryReducer(emptyFrameState(), { type: 'load', boxes: [box('a')] })
    state = boxHistoryReducer(state, { type: 'commit', boxes: [box('a'), box('b')] })
    expect(state.boxes).toHaveLength(2)
    expect(state.dirty).toBe(true)
    expect(state.undoStack).toEqual([[expect.objectContaining({ id: 'a' })]])
    expect(state.redoStack).toHaveLength(0)
  })

  it('undo/redo restauram estados e mantêm dirty (o save é do estado atual)', () => {
    let state = boxHistoryReducer(emptyFrameState(), { type: 'load', boxes: [] })
    state = boxHistoryReducer(state, { type: 'commit', boxes: [box('a')] })
    state = boxHistoryReducer(state, { type: 'commit', boxes: [box('a'), box('b')] })

    state = boxHistoryReducer(state, { type: 'undo' })
    expect(state.boxes.map(b => b.id)).toEqual(['a'])

    state = boxHistoryReducer(state, { type: 'undo' })
    expect(state.boxes).toHaveLength(0)

    state = boxHistoryReducer(state, { type: 'redo' })
    expect(state.boxes.map(b => b.id)).toEqual(['a'])

    state = boxHistoryReducer(state, { type: 'redo' })
    expect(state.boxes.map(b => b.id)).toEqual(['a', 'b'])
    expect(state.dirty).toBe(true)
  })

  it('undo sem histórico e redo sem futuro são no-ops', () => {
    const loaded = boxHistoryReducer(emptyFrameState(), { type: 'load', boxes: [box('a')] })
    expect(boxHistoryReducer(loaded, { type: 'undo' })).toBe(loaded)
    expect(boxHistoryReducer(loaded, { type: 'redo' })).toBe(loaded)
  })

  it('commit depois de undo descarta o futuro (redo limpo)', () => {
    let state = boxHistoryReducer(emptyFrameState(), { type: 'load', boxes: [] })
    state = boxHistoryReducer(state, { type: 'commit', boxes: [box('a')] })
    state = boxHistoryReducer(state, { type: 'undo' })
    state = boxHistoryReducer(state, { type: 'commit', boxes: [box('c')] })
    expect(state.redoStack).toHaveLength(0)
    expect(state.boxes.map(b => b.id)).toEqual(['c'])
  })

  it('markSaved limpa dirty sem tocar nas caixas', () => {
    let state = boxHistoryReducer(emptyFrameState(), { type: 'load', boxes: [] })
    state = boxHistoryReducer(state, { type: 'commit', boxes: [box('a')] })
    state = boxHistoryReducer(state, { type: 'markSaved' })
    expect(state.dirty).toBe(false)
    expect(state.boxes).toHaveLength(1)
  })

  it('pilha de undo é limitada a MAX_HISTORY', () => {
    let state: FrameBoxState = boxHistoryReducer(emptyFrameState(), { type: 'load', boxes: [] })
    for (let i = 0; i < MAX_HISTORY + 10; i++) {
      state = boxHistoryReducer(state, { type: 'commit', boxes: [box(`b${i}`)] })
    }
    expect(state.undoStack).toHaveLength(MAX_HISTORY)
  })
})

describe('digitToClass', () => {
  const classes: StudioClass[] = [
    { classId: 100001, name: 'capacete', color: '#f00' },
    { classId: 100002, name: 'luva', color: '#0f0' },
  ]

  it('mapeia 1–9 pela ordem da paleta (ordem do backend)', () => {
    expect(digitToClass(classes, 1)?.name).toBe('capacete')
    expect(digitToClass(classes, 2)?.name).toBe('luva')
  })

  it('dígito além da paleta ou fora de 1–9 → null', () => {
    expect(digitToClass(classes, 3)).toBeNull()
    expect(digitToClass(classes, 0)).toBeNull()
    expect(digitToClass(classes, 10)).toBeNull()
  })
})

describe('cloneBoxes (tecla C — copiar do frame anterior)', () => {
  it('copia geometria e classe com ids locais novos', () => {
    let n = 0
    const source = [box('orig-1', 100001), box('orig-2', 100002)]
    const copies = cloneBoxes(source, () => `novo-${++n}`)
    expect(copies).toHaveLength(2)
    expect(copies.map(b => b.id)).toEqual(['novo-1', 'novo-2'])
    expect(copies[0]).toMatchObject({ classId: 100001, xCenter: 0.5, width: 0.2 })
    // não muta a origem
    expect(source[0].id).toBe('orig-1')
  })
})
