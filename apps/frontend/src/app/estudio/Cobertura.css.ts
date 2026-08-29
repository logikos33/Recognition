import { style } from '@vanilla-extract/css'

import { lk } from '../tokens/lk.css'

// Mesmo padrão de Dados.css.ts — cabeçalho simples de seção do Estúdio.
export const cabecalho = style({
  display: 'flex',
  alignItems: 'baseline',
  justifyContent: 'space-between',
  marginBottom: '16px',
})

export const titulo = style({
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '20px',
  margin: 0,
})
