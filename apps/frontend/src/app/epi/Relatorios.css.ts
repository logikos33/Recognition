/**
 * Estilos da tela EPI Relatórios. Zero hex solto: cor, fonte e medida de shell
 * saem de `lk.css.ts`. Medidas locais do desenho (gap 14, padding 20, 13px)
 * ficam em px porque o token set não cobre — e não deve cobrir: são medidas
 * DESTA tela, não do sistema.
 */
import { style, styleVariants } from '@vanilla-extract/css'

import { OVERLINE_TRACKING, lk } from '../tokens/lk.css'

/** O desenho fecha esta tela em 1080 — mais estreita que o shell (1280). */
const LARGURA = '1080px'

export const raiz = style({
  maxWidth: LARGURA,
  margin: '0 auto',
  display: 'flex',
  flexDirection: 'column',
  gap: lk.espaco.x2,
})

export const titulo = style({
  margin: 0,
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '26px',
  color: lk.cor.brancoSinal,
})

export const colunas = style({
  display: 'grid',
  gridTemplateColumns: '1fr 1.2fr',
  gap: '14px',
  alignItems: 'start',
  '@media': {
    '(max-width: 900px)': { gridTemplateColumns: '1fr' },
  },
})

export const cartao = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '14px',
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.g,
  padding: '20px',
})

/** Overline: mono, caixa alta, tracking do contrato. */
export const overline = style({
  fontFamily: lk.fonte.mono,
  fontSize: '10px',
  letterSpacing: OVERLINE_TRACKING,
  textTransform: 'uppercase',
  color: lk.cor.cinzaNevoa,
})

export const campo = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '6px',
})

export const rotulo = style({
  fontSize: '13px',
  color: lk.cor.cinzaNevoa,
})

const controle = {
  height: '40px',
  background: lk.cor.preto,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.s,
  color: lk.cor.brancoSinal,
  fontFamily: lk.fonte.ui,
  fontSize: '13px',
  padding: '0 11px',
} as const

export const seletor = style({
  ...controle,
  selectors: {
    '&:focus-visible': { outline: `2px solid ${lk.cor.cianoVisao}`, outlineOffset: '1px' },
  },
})

export const linhaDatas = style({
  display: 'flex',
  gap: '10px',
})

export const dataInput = style({
  ...controle,
  flex: 1,
  minWidth: 0,
  fontFamily: lk.fonte.mono,
  colorScheme: 'dark',
  selectors: {
    '&:focus-visible': { outline: `2px solid ${lk.cor.cianoVisao}`, outlineOffset: '1px' },
  },
})

export const segmentado = style({
  display: 'flex',
  background: lk.cor.preto,
  borderRadius: lk.raio.s,
  padding: '3px',
  gap: '2px',
})

const segmentoBase = style({
  flex: 1,
  height: '36px',
  border: 'none',
  borderRadius: '6px',
  fontFamily: lk.fonte.mono,
  fontSize: '12.5px',
  fontWeight: 600,
  cursor: 'pointer',
  selectors: {
    '&:focus-visible': { outline: `2px solid ${lk.cor.cianoVisao}`, outlineOffset: '1px' },
  },
})

export const segmento = styleVariants({
  ativo: [segmentoBase, { background: lk.cor.grafite, color: lk.cor.cianoVisao }],
  inativo: [segmentoBase, { background: 'transparent', color: lk.cor.cinzaNevoa }],
})

/** O que o formato escolhido realmente traz — não é promessa, é o que a API gera. */
export const legenda = style({
  margin: 0,
  fontSize: '12.5px',
  lineHeight: 1.55,
  color: lk.cor.cinzaNevoa,
})

export const botaoPrimario = style({
  height: '44px',
  border: 'none',
  borderRadius: '9px',
  background: lk.cor.cianoVisao,
  color: lk.cor.preto,
  fontFamily: lk.fonte.ui,
  fontSize: '14px',
  fontWeight: 700,
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '9px',
  selectors: {
    '&:hover:not(:disabled)': { background: lk.cor.cianoProfundo },
    '&:disabled': { background: lk.cor.borda, color: lk.cor.cinzaNevoa, cursor: 'not-allowed' },
    '&:focus-visible': { outline: `2px solid ${lk.cor.cianoVisao}`, outlineOffset: '2px' },
  },
})

/** Estado = cor + ícone + palavra. Nunca só a cor. */
const avisoBase = style({
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
  fontSize: '12.5px',
  lineHeight: 1.45,
})

export const aviso = styleVariants({
  neutro: [avisoBase, { color: lk.cor.cinzaNevoa }],
  ok: [avisoBase, { color: lk.estado.ok }],
  nc: [avisoBase, { color: lk.estado.nc }],
})

/** Painel do resumo — o "prova" da tela: só número que a API devolveu. */
export const painel = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '10px',
  padding: lk.espaco.x2,
  background: lk.cor.preto,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.m,
})

export const scoreLinha = style({
  display: 'flex',
  alignItems: 'baseline',
  gap: '10px',
  flexWrap: 'wrap',
})

export const score = style({
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '34px',
  color: lk.cor.brancoSinal,
})

export const scoreLegenda = style({
  fontSize: '12.5px',
  color: lk.cor.cinzaNevoa,
})

export const fatos = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '4px',
  fontSize: '12.5px',
  color: lk.cor.cinzaNevoa,
})

/** Dado é mono — id de câmera, contagem, hora. */
export const dado = style({
  fontFamily: lk.fonte.mono,
  color: lk.cor.brancoSinal,
})

/** Lacuna declarada na tela: o desenho pede, o backend não serve. */

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
  color: lk.cor.brancoSinal,
})

export const centroTexto = style({
  fontSize: '13.5px',
  color: lk.cor.cinzaNevoa,
  maxWidth: '380px',
  lineHeight: 1.55,
})

export const centroCodigo = style({
  fontFamily: lk.fonte.mono,
  fontSize: '12px',
  color: lk.cor.cinzaNevoa,
})

export const botaoCentro = style({
  height: '40px',
  padding: '0 18px',
  border: 'none',
  borderRadius: lk.raio.s,
  background: lk.cor.cianoVisao,
  color: lk.cor.preto,
  fontFamily: lk.fonte.ui,
  fontSize: '13.5px',
  fontWeight: 700,
  cursor: 'pointer',
  selectors: {
    '&:hover': { background: lk.cor.cianoProfundo },
    '&:focus-visible': { outline: `2px solid ${lk.cor.cianoVisao}`, outlineOffset: '2px' },
  },
})
