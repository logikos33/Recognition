/**
 * Geometria de caixas em coordenadas normalizadas (0–1) — lógica pura.
 *
 * Convenção YOLO: centro (xCenter, yCenter) + dimensões (width, height),
 * tudo relativo ao tamanho da imagem exibida.
 */
import type { Box } from './studioTypes'

export type HandleId = 'nw' | 'n' | 'ne' | 'e' | 'se' | 's' | 'sw' | 'w'

export const HANDLES: HandleId[] = ['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w']

/** Menor dimensão aceita p/ caixa (normalizada) — capacete a 20 px existe. */
export const MIN_BOX_SIZE = 0.01

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

/** Move a caixa para um novo centro, mantendo-a inteira dentro da imagem. */
export function moveBox(box: Box, xCenter: number, yCenter: number): Box {
  return {
    ...box,
    xCenter: clamp(xCenter, box.width / 2, 1 - box.width / 2),
    yCenter: clamp(yCenter, box.height / 2, 1 - box.height / 2),
  }
}

/**
 * Redimensiona pela alça `handle` levando a borda correspondente até (x, y).
 * A borda oposta fica fixa; a borda movida respeita MIN_BOX_SIZE e [0,1].
 */
export function resizeBox(start: Box, handle: HandleId, x: number, y: number): Box {
  let left = start.xCenter - start.width / 2
  let right = start.xCenter + start.width / 2
  let top = start.yCenter - start.height / 2
  let bottom = start.yCenter + start.height / 2

  if (handle.includes('w')) left = clamp(x, 0, right - MIN_BOX_SIZE)
  if (handle.includes('e')) right = clamp(x, left + MIN_BOX_SIZE, 1)
  if (handle.includes('n')) top = clamp(y, 0, bottom - MIN_BOX_SIZE)
  if (handle.includes('s')) bottom = clamp(y, top + MIN_BOX_SIZE, 1)

  return {
    ...start,
    xCenter: (left + right) / 2,
    yCenter: (top + bottom) / 2,
    width: right - left,
    height: bottom - top,
  }
}

/**
 * Caixa a partir de um arrasto de desenho — null se pequena demais
 * (clique acidental não vira caixa).
 */
export function boxFromDrag(
  x0: number,
  y0: number,
  x1: number,
  y1: number,
  classId: number,
  id: string,
): Box | null {
  const left = clamp(Math.min(x0, x1), 0, 1)
  const right = clamp(Math.max(x0, x1), 0, 1)
  const top = clamp(Math.min(y0, y1), 0, 1)
  const bottom = clamp(Math.max(y0, y1), 0, 1)
  const width = right - left
  const height = bottom - top
  if (width < MIN_BOX_SIZE || height < MIN_BOX_SIZE) return null
  return {
    id,
    classId,
    xCenter: (left + right) / 2,
    yCenter: (top + bottom) / 2,
    width,
    height,
  }
}
