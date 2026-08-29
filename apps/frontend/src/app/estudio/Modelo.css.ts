import { style } from '@vanilla-extract/css'

import { lk, OVERLINE_TRACKING } from '../tokens/lk.css'

export const raiz = style({
  display: 'flex',
  flexDirection: 'column',
  gap: lk.espaco.x2,
})

export const cabecalho = style({
  display: 'flex',
  alignItems: 'center',
  gap: lk.espaco.x2,
  flexWrap: 'wrap',
})

export const titulo = style({
  margin: 0,
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '20px',
})

export const espacador = style({ flex: 1 })

export const linkContorno = style({
  height: '34px',
  padding: '0 14px',
  display: 'inline-flex',
  alignItems: 'center',
  gap: '6px',
  background: 'transparent',
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: '6px',
  color: lk.cor.brancoSinal,
  fontSize: '13px',
  fontWeight: 600,
  textDecoration: 'none',
  flex: 'none',
})

export const cartaoAtivo = style({
  padding: '16px 20px',
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.g,
})

export const cartaoAtivoComModelo = style({
  borderColor: lk.estado.ok,
})

export const secaoTitulo = style({
  margin: 0,
  fontFamily: lk.fonte.mono,
  fontSize: '11px',
  letterSpacing: OVERLINE_TRACKING,
  color: lk.cor.cinzaNevoa,
  fontWeight: 600,
  textTransform: 'uppercase',
})

export const nomeAtivo = style({
  fontSize: '15px',
  fontWeight: 700,
  color: lk.cor.cianoVisao,
})

export const semAtivo = style({
  fontSize: '13px',
  color: lk.cor.cinzaNevoa,
  margin: '6px 0 0',
})

export const metricas = style({
  display: 'flex',
  gap: '16px',
  marginTop: '8px',
  flexWrap: 'wrap',
})

export const metrica = style({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  gap: '1px',
})

export const metricaRotulo = style({
  fontFamily: lk.fonte.mono,
  fontSize: '9px',
  color: lk.cor.cinzaNevoa,
  textTransform: 'uppercase',
  letterSpacing: '.05em',
  fontWeight: 600,
})

export const metricaValor = style({
  fontFamily: lk.fonte.mono,
  fontSize: '14px',
  fontWeight: 700,
  color: lk.cor.brancoSinal,
})

export const rodapeAtivo = style({
  display: 'flex',
  gap: '12px',
  marginTop: '6px',
  flexWrap: 'wrap',
  alignItems: 'center',
  fontSize: '11px',
  color: lk.cor.cinzaNevoa,
})

export const classesGrid = style({
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fill, minmax(160px,1fr))',
  gap: '8px',
})

export const classeChip = style({
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
  padding: '10px 12px',
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.s,
  fontSize: '13px',
  fontWeight: 500,
})

export const classeCor = style({
  width: '10px',
  height: '10px',
  borderRadius: '50%',
  flexShrink: 0,
})

export const modelosGrid = style({
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fill, minmax(260px,1fr))',
  gap: '10px',
})

export const modeloCartao = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '8px',
  padding: '14px 16px',
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.s,
})

export const modeloCartaoAtivo = style({
  borderColor: lk.estado.ok,
})

export const modeloLinha = style({
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'flex-start',
  gap: '8px',
})

export const modeloNome = style({
  fontSize: '13.5px',
  fontWeight: 700,
})

export const badgeAtivo = style({
  display: 'inline-flex',
  alignItems: 'center',
  gap: '3px',
  marginLeft: '8px',
  padding: '2px 8px',
  borderRadius: '999px',
  background: 'rgba(62,207,142,.15)',
  color: lk.estado.ok,
  fontSize: '10.5px',
  fontWeight: 700,
})

export const acoes = style({
  display: 'flex',
  gap: '6px',
  flexWrap: 'wrap',
})

export const botaoAcao = style({
  height: '30px',
  padding: '0 12px',
  background: 'transparent',
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: '6px',
  color: lk.cor.brancoSinal,
  fontSize: '12px',
  fontWeight: 600,
  cursor: 'pointer',
  display: 'inline-flex',
  alignItems: 'center',
  gap: '5px',
  ':disabled': { opacity: 0.5, cursor: 'not-allowed' },
})

export const dataModelo = style({
  fontFamily: lk.fonte.mono,
  fontSize: '11px',
  color: lk.cor.cinzaNevoa,
})

export const aviso = style({
  display: 'flex',
  alignItems: 'flex-start',
  gap: '10px',
  padding: '12px 16px',
  background: 'rgba(232,161,60,.1)',
  border: `1px solid ${lk.estado.atencao}`,
  borderRadius: lk.raio.m,
  fontSize: '12.5px',
  color: lk.estado.atencao,
  lineHeight: 1.5,
})

export const centro = style({
  minHeight: '50vh',
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '14px',
  textAlign: 'center',
  padding: lk.medida.padding,
})

export const centroTitulo = style({
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '18px',
})

export const centroTecnico = style({
  fontFamily: lk.fonte.mono,
  fontSize: '12px',
  color: lk.cor.cinzaNevoa,
})

export const botaoRetry = style({
  height: '38px',
  padding: `0 ${lk.espaco.x2}`,
  border: 'none',
  borderRadius: lk.raio.s,
  background: lk.cor.cianoVisao,
  color: lk.cor.preto,
  fontSize: '13px',
  fontWeight: 700,
  cursor: 'pointer',
})
