import { style } from '@vanilla-extract/css'

import { lk } from '../tokens/lk.css'

export const centro = style({
  minHeight: '52vh',
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '14px',
  textAlign: 'center',
  padding: lk.medida.padding,
})

export const titulo = style({
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '19px',
})

export const texto = style({
  fontSize: '13.5px',
  color: lk.cor.cinzaNevoa,
  maxWidth: '420px',
  lineHeight: 1.55,
})

export const voltar = style({
  fontSize: '13px',
  color: lk.cor.cianoVisao,
  textDecoration: 'none',
  ':hover': { textDecoration: 'underline' },
})
