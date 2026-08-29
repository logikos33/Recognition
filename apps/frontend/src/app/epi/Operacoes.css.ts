import { style } from '@vanilla-extract/css'

import { lk } from '../tokens/lk.css'

export const raiz = style({ display: 'flex', flexDirection: 'column', gap: lk.espaco.x2 })

export const cabecalho = style({ display: 'flex', alignItems: 'center', gap: '12px' })

export const voltar = style({
  fontSize: '13px',
  fontWeight: 600,
  color: lk.cor.cianoVisao,
  textDecoration: 'none',
})

export const titulo = style({
  margin: 0,
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '24px',
})

export const selo = style({
  display: 'flex',
  alignItems: 'center',
  gap: '6px',
  fontFamily: lk.fonte.mono,
  fontSize: '10.5px',
})

export const espacador = style({ flex: 1 })

export const botaoSecundario = style({
  height: '38px',
  display: 'flex',
  alignItems: 'center',
  gap: lk.espaco.x1,
  padding: `0 ${lk.espaco.x2}`,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.s,
  background: 'transparent',
  color: lk.cor.brancoSinal,
  fontSize: '13px',
  fontWeight: 600,
  textDecoration: 'none',
  cursor: 'pointer',
  ':hover': { borderColor: lk.cor.cianoVisao, color: lk.cor.cianoVisao },
})

export const botaoPrimario = style({
  height: '38px',
  padding: `0 ${lk.espaco.x2}`,
  border: 'none',
  borderRadius: lk.raio.s,
  background: lk.cor.cianoVisao,
  color: lk.cor.preto,
  fontSize: '13px',
  fontWeight: 700,
  cursor: 'pointer',
  ':disabled': { opacity: 0.45, cursor: 'not-allowed' },
})

export const explicacao = style({
  fontSize: '12.5px',
  color: lk.cor.cinzaNevoa,
  marginTop: '-6px',
})

export const cartao = style({
  display: 'flex',
  flexDirection: 'column',
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.g,
  overflow: 'hidden',
})

export const cartaoComErro = style({ borderColor: 'rgba(229,72,77,.4)' })

export const linha = style({
  display: 'flex',
  alignItems: 'center',
  gap: '14px',
  padding: '16px 18px',
})

export const estado = style({
  display: 'flex',
  alignItems: 'center',
  gap: '7px',
  fontSize: '12px',
  fontWeight: 700,
  flex: 'none',
})

export const bolinha = style({ width: '9px', height: '9px', borderRadius: '50%', flex: 'none' })

export const identificacao = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '1px',
  minWidth: 0,
})

export const nome = style({ fontSize: '14.5px', fontWeight: 600 })

export const meta = style({
  fontFamily: lk.fonte.mono,
  fontSize: '10.5px',
  color: lk.cor.cinzaNevoa,
})

export const ultima = style({
  fontFamily: lk.fonte.mono,
  fontSize: '11px',
  color: lk.cor.cinzaNevoa,
  textAlign: 'right',
  flex: 'none',
})

export const acao = style({
  height: '34px',
  padding: `0 14px`,
  background: 'transparent',
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: '7px',
  color: lk.cor.brancoSinal,
  fontSize: '12.5px',
  fontWeight: 600,
  cursor: 'pointer',
  flex: 'none',
  ':disabled': { opacity: 0.4, cursor: 'not-allowed' },
})

export const faixaFalta = style({
  display: 'flex',
  alignItems: 'center',
  gap: '10px',
  padding: '11px 18px',
  borderTop: `1px solid ${lk.cor.borda}`,
  fontSize: '12.5px',
  color: lk.cor.cinzaNevoa,
  lineHeight: 1.5,
})

export const rodape = style({
  display: 'flex',
  gap: '14px',
  padding: '14px 16px',
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.m,
  fontSize: '12.5px',
  color: lk.cor.cinzaNevoa,
  lineHeight: 1.6,
})

export const centro = style({
  minHeight: '60vh',
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
  fontSize: '19px',
})

export const centroTexto = style({
  fontSize: '13.5px',
  color: lk.cor.cinzaNevoa,
  maxWidth: '400px',
  lineHeight: 1.55,
})

export const centroTecnico = style({
  fontFamily: lk.fonte.mono,
  fontSize: '12px',
  color: lk.cor.cinzaNevoa,
})
