import { style } from '@vanilla-extract/css'

import { lk } from '../tokens/lk.css'

export const raiz = style({
  display: 'flex',
  flexDirection: 'column',
  gap: lk.espaco.x2,
  maxWidth: lk.medida.conteudoMax,
})

export const cabecalho = style({
  display: 'flex',
  alignItems: 'center',
  gap: lk.espaco.x1,
})

export const titulo = style({
  margin: 0,
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '26px',
})

export const subtitulo = style({
  fontSize: '12.5px',
  color: lk.cor.cinzaNevoa,
})

export const botaoPrimario = style({
  height: '38px',
  padding: `0 ${lk.espaco.x2}`,
  border: 'none',
  borderRadius: lk.raio.s,
  background: lk.cor.cianoVisao,
  color: lk.cor.preto,
  fontSize: '13.5px',
  fontWeight: 700,
  cursor: 'pointer',
  selectors: {
    '&:disabled': { opacity: 0.6, cursor: 'default' },
  },
})

/** Faixa de destaque com o código — mesma família visual do `cianoVisao`,
 * em tom translúcido (`rgba` com os canais do próprio token, não hex novo). */
export const bannerCodigo = style({
  display: 'flex',
  alignItems: 'center',
  gap: lk.espaco.x2,
  padding: `${lk.espaco.x1} ${lk.espaco.x2}`,
  background: 'rgba(0,229,255,.05)',
  border: '1px solid rgba(0,229,255,.35)',
  borderRadius: lk.raio.m,
  flexWrap: 'wrap',
})

export const codigo = style({
  fontFamily: lk.fonte.mono,
  fontWeight: 700,
  fontSize: '26px',
  letterSpacing: '.28em',
  color: lk.cor.brancoSinal,
})

export const expira = style({
  fontFamily: lk.fonte.mono,
  fontSize: '11px',
  color: lk.estado.atencao,
})

export const botaoCopiar = style({
  marginLeft: 'auto',
  display: 'flex',
  alignItems: 'center',
  gap: '6px',
  height: '32px',
  padding: '0 13px',
  background: 'transparent',
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: '7px',
  color: lk.cor.cinzaNevoa,
  fontSize: '12.5px',
  fontWeight: 600,
  cursor: 'pointer',
})

/** Nota honesta: seção do desenho sem rota real (listagem/revogação). */
export const notaOmissao = style({
  display: 'flex',
  alignItems: 'flex-start',
  gap: '10px',
  padding: lk.espaco.x2,
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.g,
  color: lk.cor.cinzaNevoa,
  fontSize: '12.5px',
  lineHeight: 1.55,
})
