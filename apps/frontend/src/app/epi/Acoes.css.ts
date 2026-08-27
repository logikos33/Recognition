/**
 * Estilos da tela AGIR (`EPI Ações.dc.html`). Medidas e pesos são os do
 * desenho; cor, fonte e espaço vêm SÓ de `lk.css.ts` — zero hex solto.
 *
 * As duas colunas do kanban e as linhas da lista compartilham o mesmo cartão
 * de propósito: no desenho a coluna É o estado, e o cartão não muda de forma
 * entre "aberta" e "concluída" — só de opacidade.
 */
import { style, styleVariants } from '@vanilla-extract/css'

import { lk, OVERLINE_TRACKING } from '../tokens/lk.css'

export const pagina = style({
  maxWidth: lk.medida.conteudoMax,
  margin: '0 auto',
  padding: lk.medida.padding,
  boxSizing: 'border-box',
  display: 'flex',
  flexDirection: 'column',
  gap: lk.espaco.x2,
})

export const cabecalho = style({
  display: 'flex',
  alignItems: 'center',
  gap: '14px',
  flexWrap: 'wrap',
})

export const titulo = style({
  margin: 0,
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '26px',
  color: lk.cor.brancoSinal,
})

export const empurra = style({ flex: 1 })

/** Segmentado do desenho: trilho grafite, pastilha ativa no fundo preto. */
export const segmentado = style({
  display: 'flex',
  background: lk.cor.grafite,
  borderRadius: lk.raio.s,
  padding: '3px',
  gap: '2px',
})

const segmentoBase = style({
  height: '32px',
  padding: '0 14px',
  border: 'none',
  borderRadius: '6px',
  fontFamily: lk.fonte.ui,
  fontSize: '13px',
  fontWeight: 600,
  cursor: 'pointer',
})

export const segmento = styleVariants({
  ativo: [segmentoBase, { background: lk.cor.preto, color: lk.cor.cianoVisao }],
  inativo: [segmentoBase, { background: 'transparent', color: lk.cor.cinzaNevoa }],
})

// ── Faixa de taxa ───────────────────────────────────────────────────────────

export const faixaTaxa = style({
  display: 'flex',
  alignItems: 'center',
  gap: lk.espaco.x3,
  padding: `${lk.espaco.x2} 20px`,
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.g,
  flexWrap: 'wrap',
})

export const taxaNumero = style({
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '38px',
  lineHeight: 1,
  color: lk.cor.brancoSinal,
})

export const taxaRotulo = style({ fontSize: '12.5px', color: lk.cor.cinzaNevoa })

export const taxaTrilho = style({
  flex: 1,
  minWidth: '120px',
  height: '10px',
  background: lk.cor.preto,
  borderRadius: '5px',
  overflow: 'hidden',
})

export const taxaBarra = style({ height: '100%', background: lk.estado.ok })

export const taxaContagem = style({
  fontFamily: lk.fonte.mono,
  fontSize: '12px',
  color: lk.cor.cinzaNevoa,
})

// ── Kanban ──────────────────────────────────────────────────────────────────

export const kanban = style({
  display: 'grid',
  gridTemplateColumns: '1fr 1fr',
  gap: '12px',
  alignItems: 'start',
  '@media': { 'screen and (max-width: 900px)': { gridTemplateColumns: '1fr' } },
})

export const coluna = style({ display: 'flex', flexDirection: 'column', gap: lk.espaco.x1 })

export const colunaTopo = style({
  display: 'flex',
  alignItems: 'center',
  gap: lk.espaco.x1,
  padding: '0 4px',
})

export const overline = style({
  fontFamily: lk.fonte.mono,
  fontSize: '10.5px',
  letterSpacing: OVERLINE_TRACKING,
  textTransform: 'uppercase',
  color: lk.cor.cinzaNevoa,
})

export const contador = style({
  fontFamily: lk.fonte.mono,
  fontSize: '11px',
  color: lk.cor.brancoSinal,
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: '10px',
  padding: '1px 8px',
})

const cartaoBase = style({
  display: 'flex',
  flexDirection: 'column',
  gap: lk.espaco.x1,
  padding: `14px ${lk.espaco.x2}`,
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.m,
})

export const cartao = styleVariants({
  aberta: [cartaoBase],
  concluida: [cartaoBase, { opacity: 0.65 }],
})

export const cartaoTitulo = style({
  fontFamily: lk.fonte.ui,
  fontSize: '13.5px',
  fontWeight: 600,
  color: lk.cor.brancoSinal,
})

/** Origem: mono e ciano — é a única coisa clicável do cartão no desenho. */
export const origem = style({
  fontFamily: lk.fonte.mono,
  fontSize: '11px',
  color: lk.cor.cianoVisao,
})

export const cartaoRodape = style({ display: 'flex', alignItems: 'center', gap: lk.espaco.x1 })

export const quando = style({
  marginLeft: 'auto',
  display: 'flex',
  alignItems: 'center',
  gap: '5px',
  fontFamily: lk.fonte.mono,
  fontSize: '10.5px',
  fontWeight: 700,
  color: lk.cor.cinzaNevoa,
})

/** Estado = cor + ícone + palavra. Nunca só cor. */
const estadoBase = style({
  display: 'flex',
  alignItems: 'center',
  gap: '5px',
  fontFamily: lk.fonte.ui,
  fontSize: '12px',
  fontWeight: 600,
})

export const estado = styleVariants({
  aguardando: [estadoBase, { color: lk.estado.atencao }],
  reconhecida: [estadoBase, { color: lk.estado.ok }],
})

export const botaoCartao = style({
  height: '34px',
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: '7px',
  background: 'transparent',
  color: lk.cor.brancoSinal,
  fontFamily: lk.fonte.ui,
  fontSize: '12.5px',
  fontWeight: 600,
  cursor: 'pointer',
  selectors: {
    '&:hover:not(:disabled)': { borderColor: lk.estado.ok, color: lk.estado.ok },
    '&:disabled': { cursor: 'not-allowed', opacity: 0.5 },
  },
})

// ── Lista ───────────────────────────────────────────────────────────────────

export const tabela = style({
  display: 'grid',
  gridTemplateColumns: '1.4fr 1fr 160px 130px',
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.m,
  overflowX: 'auto',
})

export const th = style({
  padding: `10px ${lk.espaco.x2}`,
  fontFamily: lk.fonte.mono,
  fontSize: '10px',
  letterSpacing: '0.14em',
  color: lk.cor.cinzaNevoa,
  borderBottom: `1px solid ${lk.cor.borda}`,
})

export const td = style({
  padding: `12px ${lk.espaco.x2}`,
  fontFamily: lk.fonte.ui,
  fontSize: '13px',
  color: lk.cor.brancoSinal,
  borderBottom: `1px solid ${lk.cor.borda}`,
})

export const tdMono = style([td, { fontFamily: lk.fonte.mono, fontSize: '12px' }])

// ── Estados da rota ─────────────────────────────────────────────────────────

export const centro = style({
  minHeight: '60vh',
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '14px',
  textAlign: 'center',
  padding: lk.medida.padding,
  boxSizing: 'border-box',
})

export const centroTitulo = style({
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '19px',
  color: lk.cor.brancoSinal,
})

export const centroTexto = style({
  fontFamily: lk.fonte.ui,
  fontSize: '13.5px',
  color: lk.cor.cinzaNevoa,
  maxWidth: '400px',
  lineHeight: 1.55,
})

export const centroMono = style({
  fontFamily: lk.fonte.mono,
  fontSize: '12px',
  color: lk.cor.cinzaNevoa,
})

export const botaoPrimario = style({
  display: 'flex',
  alignItems: 'center',
  height: '40px',
  padding: '0 18px',
  border: 'none',
  borderRadius: lk.raio.s,
  background: lk.cor.cianoVisao,
  color: lk.cor.preto,
  fontFamily: lk.fonte.ui,
  fontSize: '13.5px',
  fontWeight: 700,
  textDecoration: 'none',
  cursor: 'pointer',
  ':hover': { background: lk.cor.cianoProfundo },
})

/**
 * Nota de honestidade. Não é enfeite: esta tela mostra o ledger que existe
 * (reconhecimento de evento), e o desenho pede campos que o backend ainda não
 * tem. Sem esta linha a tela pareceria completa e mentiria.
 */
export const nota = style({
  fontFamily: lk.fonte.ui,
  fontSize: '12px',
  lineHeight: 1.5,
  color: lk.cor.cinzaNevoa,
  padding: `10px ${lk.espaco.x2}`,
  border: `1px dashed ${lk.cor.borda}`,
  borderRadius: lk.raio.s,
})
