/**
 * Estilos do SessaoExpirando. Zero hex solto: só tokens.
 *
 * A cor do cartão é ÂMBAR (`lk.estado.atencao`), não vermelha: ainda dá para
 * renovar. Vermelho (`lk.estado.nc`) é falha consumada — usá-lo aqui ensinaria
 * o operador a ignorar o vermelho de verdade.
 *
 * O ciano aparece só no botão primário. Isso NÃO contraria "ciano nunca como
 * fundo": a regra é sobre superfície (topbar, card, painel). Botão primário é
 * justamente o "onde eu clico" que o ciano existe para marcar.
 */
import { style } from '@vanilla-extract/css'

import { lk } from '../tokens/lk.css'

/** Canto inferior direito, acima da barra de status — igual ao protótipo. */
export const cartao = style({
  position: 'fixed',
  right: '20px',
  bottom: '64px',
  width: '330px',
  maxWidth: 'calc(100vw - 32px)',
  zIndex: 110,
  display: 'flex',
  flexDirection: 'column',
  gap: '10px',
  padding: lk.espaco.x2,
  background: lk.cor.grafite,
  // Borda âmbar a 50% — presente sem gritar. `color-mix` evita o rgba() com
  // hex solto que o protótipo usava.
  border: `1px solid color-mix(in srgb, ${lk.estado.atencao} 50%, transparent)`,
  borderRadius: lk.raio.g,
  boxShadow: '0 12px 48px rgba(0, 0, 0, 0.7)',
  fontFamily: lk.fonte.ui,
  color: lk.cor.brancoSinal,
})

export const cabecalho = style({
  display: 'flex',
  alignItems: 'center',
  gap: '10px',
})

/** Ícone de relógio: traço reto, cantos retos — o estilo de ícone da marca. */
export const icone = style({
  flexShrink: 0,
  strokeLinecap: 'square',
  color: lk.estado.atencao,
})

export const titulo = style({
  margin: 0,
  fontSize: '13.5px',
  fontWeight: 600,
  color: lk.cor.brancoSinal,
})

/**
 * Contador em MONO — número que muda a cada segundo precisa de largura fixa
 * por dígito, senão o cartão "respira" e o olho persegue o texto.
 */
export const contador = style({
  marginLeft: 'auto',
  fontFamily: lk.fonte.mono,
  fontWeight: 700,
  fontSize: '15px',
  fontVariantNumeric: 'tabular-nums',
  color: lk.estado.atencao,
})

export const descricao = style({
  margin: 0,
  fontSize: '12.5px',
  lineHeight: 1.5,
  color: lk.cor.cinzaNevoa,
})

export const acoes = style({
  display: 'flex',
  gap: lk.espaco.x1,
})

const botao = style({
  height: '38px',
  borderRadius: lk.raio.s,
  fontFamily: lk.fonte.ui,
  fontSize: '13px',
  cursor: 'pointer',
  ':focus-visible': {
    // Foco é ciano em todo o sistema — inclusive dentro de um cartão âmbar.
    outline: `2px solid ${lk.cor.cianoVisao}`,
    outlineOffset: '2px',
  },
})

export const botaoRenovar = style([
  botao,
  {
    flex: 1,
    border: 'none',
    background: lk.cor.cianoVisao,
    color: lk.cor.preto,
    fontWeight: 700,
    ':hover': { background: lk.cor.cianoProfundo },
  },
])

export const botaoSair = style([
  botao,
  {
    padding: `0 ${lk.espaco.x2}`,
    background: 'transparent',
    border: `1px solid ${lk.cor.borda}`,
    color: lk.cor.brancoSinal,
    fontWeight: 600,
    ':hover': { borderColor: lk.cor.cinzaNevoa },
  },
])
