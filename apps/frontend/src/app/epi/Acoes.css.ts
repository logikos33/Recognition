/**
 * Estilos da tela AGIR (`EPI Ações.dc.html`). Medidas e pesos são os do
 * desenho; cor, fonte e espaço vêm SÓ de `lk.css.ts` — zero hex solto.
 *
 * As duas colunas do kanban e as linhas da lista compartilham o mesmo cartão
 * de propósito: no desenho a coluna É o estado, e o cartão não muda de forma
 * entre "aberta" e "concluída" — só de opacidade.
 */
import { globalStyle, style, styleVariants } from '@vanilla-extract/css'

import { OVERLINE_TRACKING, TELA_ESTREITA, lk } from '../tokens/lk.css'

export const pagina = style({
  maxWidth: lk.medida.conteudoMax,
  margin: '0 auto',
  padding: lk.medida.padding,
  boxSizing: 'border-box',
  display: 'flex',
  flexDirection: 'column',
  gap: lk.espaco.x2,
  // 24px de cada lado é o dobro do que sobra pra ler numa coluna de telefone.
  '@media': { [TELA_ESTREITA]: { padding: lk.espaco.x2 } },
})

export const cabecalho = style({
  display: 'flex',
  alignItems: 'center',
  gap: '14px',
  flexWrap: 'wrap',
  // `minWidth: 0`: sem isto, o par "Kanban"/"Lista" vira o "automatic minimum
  // size" do cabeçalho inteiro e arrasta a página pra fora do viewport.
  '@media': { [TELA_ESTREITA]: { flexDirection: 'column', alignItems: 'stretch', minWidth: '0' } },
})

export const titulo = style({
  margin: 0,
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '26px',
  color: lk.cor.brancoSinal,
  // "corretivas" sozinha (a maior palavra do título, sem hífen) é mais larga
  // que a coluna inteira do telefone a 26px — min-content de texto é o
  // tamanho da MAIOR PALAVRA, então só a fonte menor resolve, não wrap.
  '@media': { [TELA_ESTREITA]: { fontSize: '21px' } },
})

export const empurra = style({ flex: 1 })

/** Segmentado do desenho: trilho grafite, pastilha ativa no fundo preto. */
export const segmentado = style({
  display: 'flex',
  background: lk.cor.grafite,
  borderRadius: lk.raio.s,
  padding: '3px',
  gap: '2px',
  '@media': { [TELA_ESTREITA]: { flexWrap: 'wrap', minWidth: '0' } },
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
  '@media': { [TELA_ESTREITA]: { height: '44px' } },
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
  // Leitura empilhada: número, rótulo, trilho cheio e contagem, cada um na
  // sua linha. Padding de 20px de cada lado é generoso demais numa coluna de
  // telefone já espremida pela sidebar fixa do shell — reduz pra sobrar
  // largura de verdade pro conteúdo.
  '@media': {
    [TELA_ESTREITA]: {
      flexDirection: 'column',
      alignItems: 'stretch',
      gap: lk.espaco.x1,
      padding: `${lk.espaco.x1} 12px`,
    },
  },
})

export const taxaNumero = style({
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '38px',
  lineHeight: 1,
  color: lk.cor.brancoSinal,
  // "100%" é um único token sem quebra — a 38px ele sozinho é o piso de
  // largura da faixa inteira numa coluna de telefone.
  '@media': { [TELA_ESTREITA]: { fontSize: '26px' } },
})

export const taxaRotulo = style({
  fontSize: '12.5px',
  color: lk.cor.cinzaNevoa,
  // "reconhecimento" sozinho já é mais largo que a coluna de um telefone —
  // sem isto a palavra vira o piso de largura da faixa inteira.
  '@media': { [TELA_ESTREITA]: { overflowWrap: 'break-word' } },
})

export const taxaTrilho = style({
  flex: 1,
  minWidth: '120px',
  height: '10px',
  background: lk.cor.preto,
  borderRadius: '5px',
  overflow: 'hidden',
  // O piso de 120px é bom de mira num trilho ao lado de texto (desktop); numa
  // coluna de ~100px de telefone ele é quem estoura a página — o número já
  // ao lado carrega o dado, o trilho pode encolher.
  '@media': { [TELA_ESTREITA]: { minWidth: '0' } },
})

export const taxaBarra = style({ height: '100%', background: lk.estado.ok })

export const taxaContagem = style({
  fontFamily: lk.fonte.mono,
  fontSize: '12px',
  color: lk.cor.cinzaNevoa,
  // "RECONHECIDAS" sozinha em mono é mais larga que a coluna do telefone.
  '@media': { [TELA_ESTREITA]: { overflowWrap: 'break-word' } },
})

// ── Kanban ──────────────────────────────────────────────────────────────────

export const kanban = style({
  display: 'grid',
  gridTemplateColumns: '1fr 1fr',
  gap: '12px',
  alignItems: 'start',
  // `minmax(0, 1fr)`, não `1fr` sozinho: uma track `1fr` pura ainda respeita o
  // min-content dos filhos (a "automatic minimum size" do CSS Grid) — com um
  // cartão cujo rodapé (estado + hora) não quebra linha, isso empurra a única
  // coluna pra fora da tela. `minmax(0, …)` é o que deixa a coluna encolher.
  '@media': { 'screen and (max-width: 900px)': { gridTemplateColumns: 'minmax(0, 1fr)' } },
})

export const coluna = style({ display: 'flex', flexDirection: 'column', gap: lk.espaco.x1 })

export const colunaTopo = style({
  display: 'flex',
  alignItems: 'center',
  gap: lk.espaco.x1,
  padding: '0 4px',
  '@media': { [TELA_ESTREITA]: { flexWrap: 'wrap' } },
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

export const cartaoRodape = style({
  display: 'flex',
  alignItems: 'center',
  gap: lk.espaco.x1,
  '@media': { [TELA_ESTREITA]: { flexWrap: 'wrap' } },
})

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
  '@media': { [TELA_ESTREITA]: { height: '44px' } },
})

// ── Lista ───────────────────────────────────────────────────────────────────

export const tabela = style({
  display: 'grid',
  gridTemplateColumns: '1.4fr 1fr 160px 130px',
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.m,
  overflowX: 'auto',
  // SR3: "lista vira cards" — uma coluna só, cada registro empilhado.
  '@media': { [TELA_ESTREITA]: { display: 'block' } },
})

export const th = style({
  padding: `10px ${lk.espaco.x2}`,
  fontFamily: lk.fonte.mono,
  fontSize: '10px',
  letterSpacing: '0.14em',
  color: lk.cor.cinzaNevoa,
  borderBottom: `1px solid ${lk.cor.borda}`,
  // Sem grid não há coluna pra rotular — o cartão lê pelo próprio texto.
  '@media': { [TELA_ESTREITA]: { display: 'none' } },
})

/**
 * Cada registro do `.tsx` é um `<div style={{ display: 'contents' }}>` — os 4
 * campos (EVENTO/ORIGEM/QUANDO/ESTADO) viram itens diretos do grid. Vira
 * card: os 4 `th` são sempre os 4 primeiros filhos de `tabela`, então
 * `nth-child(n+5)` pega só os wrappers de registro, nunca o cabeçalho.
 */
globalStyle(`${tabela} > div:nth-child(n+5)`, {
  '@media': {
    [TELA_ESTREITA]: {
      display: 'flex',
      flexDirection: 'column',
      gap: '4px',
      padding: '10px 0',
      borderBottom: `1px solid ${lk.cor.borda}`,
    },
  },
})

globalStyle(`${tabela} > div:last-child`, {
  '@media': { [TELA_ESTREITA]: { borderBottom: 'none' } },
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
  '@media': { [TELA_ESTREITA]: { height: '44px' } },
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
