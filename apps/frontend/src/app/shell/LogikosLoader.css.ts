/**
 * Estilos do LogikosLoader. Todo motion em `steps()` — catraca, não deslize.
 * Zero hex solto: só tokens.
 */
import { keyframes, style, styleVariants } from '@vanilla-extract/css'

import { lk } from '../tokens/lk.css'

const tique = keyframes({
  from: { transform: 'rotate(0deg)' },
  to: { transform: 'rotate(360deg)' },
})

/** Franja: deslocamento seco de 2px em 3 saltos. Nunca suave. */
const glitchCiano = keyframes({
  '0%': { transform: 'translate(0,0)', opacity: 0 },
  '33%': { transform: 'translate(-2px,1px)', opacity: 0.9 },
  '66%': { transform: 'translate(2px,-1px)', opacity: 0.6 },
  '100%': { transform: 'translate(0,0)', opacity: 0 },
})
const glitchMagenta = keyframes({
  '0%': { transform: 'translate(0,0)', opacity: 0 },
  '33%': { transform: 'translate(2px,-1px)', opacity: 0.8 },
  '66%': { transform: 'translate(-2px,1px)', opacity: 0.5 },
  '100%': { transform: 'translate(0,0)', opacity: 0 },
})

/** Substituto acessível: pulso de opacidade, sem giro nem franja. */
const pulso = keyframes({
  '0%,100%': { opacity: 1 },
  '50%': { opacity: 0.45 },
})

const base = style({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  gap: lk.espaco.x2,
})

export const raiz = styleVariants({
  fullscreen: [base, { minHeight: '60vh', width: '100%' }],
  tile: [base, { minHeight: '180px', width: '100%' }],
  spinner: [base, { display: 'inline-flex', gap: 0 }],
})

export const wrap = style({
  position: 'relative',
  width: 'var(--lk-size, 112px)',
  height: 'var(--lk-size, 112px)',
})

export const girando = style({})

/** Aplicada por UM ciclo quando o estado pede glitch (entrada/retry/saída). */
export const rajada = style({})

export const simbolo = style({
  position: 'absolute',
  inset: 0,
  width: '100%',
  height: '100%',
})

export const corpo = style({ fill: lk.cor.brancoSinal })

const franja = style({
  opacity: 0,
  mixBlendMode: 'screen',
  '@media': {
    // Franja é enfeite de movimento: some por inteiro em reduced-motion.
    '(prefers-reduced-motion: reduce)': { display: 'none' },
  },
})

export const franjaCiano = style([
  franja,
  {
    fill: lk.cor.cianoVisao,
    selectors: {
      [`${rajada} &`]: {
        animation: `${glitchCiano} var(--lk-glitch-dur, 500ms) steps(1, end) 1`,
      },
    },
  },
])

export const franjaMagenta = style([
  franja,
  {
    // ⚠️ Único lugar do sistema onde o magenta aparece.
    fill: lk.cor.magentaGlitch,
    selectors: {
      [`${rajada} &`]: {
        animation: `${glitchMagenta} var(--lk-glitch-dur, 500ms) steps(1, end) 1`,
      },
    },
  },
])

export const resolvido = style({
  opacity: 0.35,
  transition: 'opacity .2s steps(2, end)',
})

export const anel = style({
  position: 'absolute',
  inset: 0,
  borderRadius: '50%',
  border: `2px solid ${lk.cor.borda}`,
  borderTopColor: lk.cor.cianoVisao,
  selectors: {
    [`${girando} &`]: {
      animation: `${tique} var(--lk-tick-dur, 1.2s) steps(var(--lk-steps, 8), end) infinite`,
    },
  },
  '@media': {
    '(prefers-reduced-motion: reduce)': {
      selectors: {
        [`${girando} &`]: {
          animation: `${pulso} 1.6s steps(2, end) infinite`,
        },
      },
    },
  },
})

export const rotulo = style({
  margin: 0,
  fontFamily: lk.fonte.mono,
  fontSize: '13px',
  textTransform: 'uppercase',
  letterSpacing: '0.18em',
  color: lk.cor.cinzaNevoa,
  whiteSpace: 'nowrap',
})

export const apenasLeitor = style({
  position: 'absolute',
  width: 1,
  height: 1,
  overflow: 'hidden',
  clipPath: 'inset(50%)',
  whiteSpace: 'nowrap',
})
