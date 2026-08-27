/**
 * Estilos da PaletaComandos. Medidas e cores saem do handoff (Shell Logikos
 * Vision) — o painel é `lk.medida.paletaCmdK`, não um 600 solto no CSS: se o
 * design mudar a medida, muda no token e a paleta acompanha.
 *
 * CIANO aparece em dois lugares, e só dois: a lupa do campo e a marca de 2px
 * do item destacado. O fundo do destaque é PRETO — ciano nunca é fundo, senão
 * estoura o ≤10% e deixa de significar "onde eu clico".
 *
 * As transparências (véu e sombra) saem do próprio token via `color-mix`:
 * `rgba(10,10,15,.72)` seria o hex do preto escrito de novo, à mão, livre para
 * divergir do token no dia em que o preto mudar.
 */
import { style } from '@vanilla-extract/css'

import { OVERLINE_TRACKING, lk } from '../tokens/lk.css'

/** Véu sobre a aplicação. Painel encostado no topo (14vh), não centralizado:
 *  quem digita olha para cima, e a lista cresce para baixo sem pular. */
export const veu = style({
  position: 'fixed',
  inset: 0,
  zIndex: 90,
  display: 'flex',
  justifyContent: 'center',
  alignItems: 'flex-start',
  paddingTop: '14vh',
  background: `color-mix(in srgb, ${lk.cor.preto} 72%, transparent)`,
})

export const painel = style({
  width: lk.medida.paletaCmdK,
  maxWidth: '92vw',
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.g,
  boxShadow: `0 24px 80px color-mix(in srgb, ${lk.cor.preto} 80%, transparent)`,
  overflow: 'hidden',
})

export const cabecalho = style({
  display: 'flex',
  alignItems: 'center',
  gap: '11px',
  padding: `14px ${lk.espaco.x2}`,
  borderBottom: `1px solid ${lk.cor.borda}`,
})

/** Único ciano do cabeçalho. Marca o campo como o ponto de ação da tela. */
export const lupa = style({
  width: '17px',
  height: '17px',
  flex: 'none',
  fill: 'none',
  stroke: lk.cor.cianoVisao,
  strokeWidth: 1.8,
  strokeLinecap: 'square',
})

export const campo = style({
  flex: 1,
  minWidth: 0,
  background: 'transparent',
  border: 'none',
  outline: 'none',
  color: lk.cor.brancoSinal,
  fontFamily: lk.fonte.ui,
  fontSize: '15px',
  '::placeholder': { color: lk.cor.cinzaNevoa },
})

/** Chip de tecla — ESC no cabeçalho, atalho no item. Mono, sempre. */
export const tecla = style({
  flex: 'none',
  fontFamily: lk.fonte.mono,
  fontSize: '11px',
  color: lk.cor.cinzaNevoa,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.s,
  padding: '2px 6px',
  whiteSpace: 'nowrap',
})

export const lista = style({
  display: 'flex',
  flexDirection: 'column',
  padding: lk.espaco.x1,
  maxHeight: '52vh',
  overflowY: 'auto',
})

export const titulo = style({
  display: 'block',
  fontFamily: lk.fonte.mono,
  fontSize: '10px',
  textTransform: 'uppercase',
  letterSpacing: OVERLINE_TRACKING,
  color: lk.cor.cinzaNevoa,
  padding: '10px 10px 5px',
})

export const item = style({
  display: 'flex',
  alignItems: 'center',
  gap: '10px',
  padding: '9px 10px',
  borderRadius: lk.raio.s,
  cursor: 'pointer',
  color: lk.cor.brancoSinal,
  fontFamily: lk.fonte.ui,
  fontSize: '13.5px',
  ':hover': { background: lk.cor.preto },
})

/** Destaque = fundo preto + marca ciano de 2px à esquerda. A marca é o que
 *  sobrevive a monitor ruim e a quem não distingue cor: tem posição, não só
 *  matiz. Fundo ciano seria proibido. */
export const destacado = style({
  background: lk.cor.preto,
  boxShadow: `inset 2px 0 0 ${lk.cor.cianoVisao}`,
})

export const icone = style({
  display: 'flex',
  flex: 'none',
  width: '16px',
  height: '16px',
  color: lk.cor.cinzaNevoa,
})

export const rotulo = style({
  flex: 1,
  minWidth: 0,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
})

/** Acessório à direita do rótulo: hora do evento, estado da câmera. Mono
 *  porque é dado, não prosa. */
export const detalhe = style({
  flex: 'none',
  fontFamily: lk.fonte.mono,
  fontSize: '11px',
  color: lk.cor.cinzaNevoa,
})

export const vazio = style({
  padding: `${lk.espaco.x3} ${lk.espaco.x2}`,
  textAlign: 'center',
  fontFamily: lk.fonte.ui,
  fontSize: '13.5px',
  color: lk.cor.cinzaNevoa,
})
