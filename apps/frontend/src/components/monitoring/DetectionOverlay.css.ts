import { style } from '@vanilla-extract/css'

/**
 * REGRA ABSOLUTA: pointerEvents deve ser 'none' SEMPRE.
 * Esta classe garante isso. Nunca remover esta propriedade.
 */
export const canvas = style({
  position: 'absolute',
  top: 0,
  left: 0,
  // CRÍTICO: nunca remover — bounding boxes não podem capturar eventos de mouse
  pointerEvents: 'none',
  zIndex: 10,
})
