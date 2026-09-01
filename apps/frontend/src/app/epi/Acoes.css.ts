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
  // `overflowWrap: anywhere`: no runner do CI a JetBrains Mono não existe e o
  // fallback (Courier) é mais largo — token comprido que aqui coube passa a
  // vazar lá. Quebrar em qualquer ponto é honesto; esconder overflow não é.
  '@media': {
    [TELA_ESTREITA]: { padding: lk.espaco.x2, overflowWrap: 'anywhere' },
  },
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

export const coluna = style({
  display: 'flex',
  flexDirection: 'column',
  gap: lk.espaco.x1,
  // F5-LEVE (tema não pode estourar): cada coluna do kanban cresce com o
  // nº de ações (aberta/reconhecida, sem paginação) e empurra a página
  // inteira — rola por si só. O cálculo não desconta `nota` + `faixaTaxa`
  // (acima do kanban, altura variável) — a folga que sobra é constante,
  // não proporcional ao nº de cartões, que era o bug de verdade.
  maxHeight: `calc(100vh - ${lk.medida.topbar} - ${lk.medida.padding} * 2 - var(--global-banner-offset, 0px))`,
  overflowY: 'auto',
})

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
  // O cartão inteiro abre o evento — só os botões (stopPropagation) escapam.
  cursor: 'pointer',
  ':focus-visible': { outline: `2px solid ${lk.cor.cianoVisao}`, outlineOffset: '2px' },
})

export const cartao = styleVariants({
  aberta: [cartaoBase],
  concluida: [cartaoBase, { opacity: 0.65 }],
})

// ── Miniatura da evidência ──────────────────────────────────────────────────

export const miniatura = style({
  aspectRatio: '16 / 9',
  width: '100%',
  boxSizing: 'border-box',
  borderRadius: lk.raio.s,
  overflow: 'hidden',
  background: lk.cor.preto,
  border: `1px solid ${lk.cor.borda}`,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
})

export const miniaturaImagem = style({
  width: '100%',
  height: '100%',
  objectFit: 'cover',
  display: 'block',
})

export const miniaturaVazia = style({
  display: 'flex',
  alignItems: 'center',
  gap: '5px',
  fontFamily: lk.fonte.mono,
  fontSize: '10px',
  color: lk.cor.cinzaNevoa,
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

/**
 * Veredito é um TERCEIRO eixo — nem reconhecimento (verde/âmbar acima), nem
 * polaridade (verde/vermelho, nem mostrada aqui: a tela já filtra
 * `kind=violation`). `lk.css.ts` reserva ciano para SÓ interativo — então
 * veredito, que aqui é leitura, fica em cinza. `vereditoHumano()` (mesma
 * função pura de `VereditoHumano.tsx`/`EventoDetalhe.tsx`) decide o texto;
 * a cor não muda entre procedente/falso-positivo — ícone e palavra distinguem.
 */
export const veredito = style([estadoBase, { color: lk.cor.cinzaNevoa }])

export const acoesCartao = style({
  display: 'flex',
  alignItems: 'center',
  flexWrap: 'wrap',
  gap: '6px',
})

const botaoVereditoBase = style({
  display: 'inline-flex',
  alignItems: 'center',
  gap: '5px',
  height: '34px',
  padding: '0 12px',
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: '7px',
  background: 'transparent',
  color: lk.cor.brancoSinal,
  fontFamily: lk.fonte.ui,
  fontSize: '12.5px',
  fontWeight: 600,
  cursor: 'pointer',
  selectors: {
    // Ciano no hover, não no repouso — é a regra do token (`lk.css.ts`):
    // "CIANO É SÓ INTERATIVO... NUNCA como fundo".
    '&:hover:not(:disabled)': { borderColor: lk.cor.cianoVisao, color: lk.cor.cianoVisao },
    '&:disabled': { cursor: 'not-allowed', opacity: 0.5 },
  },
  '@media': { [TELA_ESTREITA]: { height: '44px' } },
})

/** Confirmar/Descartar têm a MESMA cor — ícone (Check/X) e palavra
 *  distinguem, nunca só a cor (mesma regra de `estado` acima). */
export const botaoVeredito = styleVariants({
  confirmar: [botaoVereditoBase],
  descartar: [botaoVereditoBase],
})

/** Tratativa (título/responsável/prazo do desenho): controle DESENHADO e
 *  desabilitado — mesma forma de `botaoDependente` em `Cenario.css.ts`. */
export const botaoTratativa = style({
  display: 'inline-flex',
  alignItems: 'center',
  gap: '5px',
  height: '34px',
  padding: '0 12px',
  border: `1px dashed ${lk.cor.bordaForte}`,
  borderRadius: '7px',
  background: 'transparent',
  color: lk.cor.cinzaNevoa,
  fontFamily: lk.fonte.ui,
  fontSize: '12.5px',
  fontWeight: 600,
  cursor: 'not-allowed',
  '@media': { [TELA_ESTREITA]: { height: '44px' } },
})

/** Mesmo `seloAguarda` de `Cenario.css.ts` — não é enfeite, é a honestidade
 *  do "controle desenhado + selo, sem ação falsa". */
export const seloAguarda = style({
  fontFamily: lk.fonte.mono,
  fontSize: '9px',
  letterSpacing: '.08em',
  color: lk.estado.atencao,
  border: `1px solid rgba(232,161,60,.4)`,
  borderRadius: '4px',
  padding: '2px 7px',
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

/**
 * Rajada (ux2/dedup) — "cartões repetem a mesma cena" era o achado: 33+33
 * detecções da MESMA câmera em 2min viravam 66 cartões idênticos. O cartão
 * mostra só o representante + este alternador; nunca esconde — expandir
 * revela as N repetições, cada uma com a própria ação.
 */
export const rajadaToggle = style({
  display: 'inline-flex',
  alignItems: 'center',
  gap: '4px',
  alignSelf: 'flex-start',
  border: 'none',
  background: 'transparent',
  padding: 0,
  fontFamily: lk.fonte.mono,
  fontSize: '10.5px',
  color: lk.cor.cianoVisao,
  cursor: 'pointer',
})

export const rajadaLista = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '5px',
  marginTop: '2px',
  paddingLeft: lk.espaco.x1,
  borderLeft: `2px solid ${lk.cor.borda}`,
})

export const rajadaItem = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: lk.espaco.x1,
  fontFamily: lk.fonte.mono,
  fontSize: '11px',
  color: lk.cor.cinzaNevoa,
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

/** Linha de repetição revelada ao expandir (ux2/dedup) — mesma estrutura,
 *  tom apagado (não é uma situação nova, é o mesmo fato redetectado). */
export const tdRepeticao = style([td, { opacity: 0.7 }])

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
