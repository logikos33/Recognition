import { style } from '@vanilla-extract/css'

import { lk } from '../tokens/lk.css'

export const raiz = style({ position: 'relative' })

export const gatilho = style({
  display: 'inline-flex',
  alignItems: 'center',
  gap: lk.espaco.x1,
  height: '34px',
  padding: `0 ${lk.espaco.x2}`,
  borderRadius: lk.raio.s,
  // Âmbar, não ciano: é um AVISO de que falta escolher, não uma ação comum.
  border: `1px solid ${lk.estado.atencao}`,
  background: 'transparent',
  color: lk.estado.atencao,
  fontFamily: lk.fonte.ui,
  fontSize: '13px',
  fontWeight: 600,
  cursor: 'pointer',
})

export const menu = style({
  position: 'absolute',
  top: 'calc(100% + 8px)',
  right: 0,
  zIndex: 40,
  width: '320px',
  padding: lk.espaco.x2,
  borderRadius: lk.raio.m,
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  display: 'flex',
  flexDirection: 'column',
  gap: lk.espaco.x1,
})

export const titulo = style({
  margin: 0,
  fontFamily: lk.fonte.mono,
  fontSize: '11px',
  letterSpacing: '0.16em',
  textTransform: 'uppercase',
  color: lk.estado.atencao,
})

export const explicacao = style({
  margin: 0,
  fontSize: '12.5px',
  lineHeight: 1.5,
  color: lk.cor.cinzaNevoa,
})

export const item = style({
  display: 'flex',
  alignItems: 'center',
  gap: lk.espaco.x1,
  // 44px: é um controle de operação, e o chão de fábrica usa dedo.
  minHeight: '44px',
  padding: `0 ${lk.espaco.x2}`,
  borderRadius: lk.raio.s,
  border: `1px solid ${lk.cor.borda}`,
  background: lk.cor.preto,
  color: lk.cor.brancoSinal,
  cursor: 'pointer',
  textAlign: 'left',
  ':hover': { borderColor: lk.cor.cianoVisao },
  ':disabled': { opacity: 0.5, cursor: 'progress' },
})

export const nome = style({ flex: 1, fontSize: '14px' })

export const slug = style({
  fontFamily: lk.fonte.mono,
  fontSize: '11px',
  color: lk.cor.cinzaNevoa,
})

export const erro = style({ margin: 0, fontSize: '12.5px', color: lk.estado.nc })
