/**
 * Estilos da tela Gestão Qualidade (D1 Dashboard / D2 Peças & OPs / D3 Relatórios).
 *
 * Zero hex solto: cor, fonte e medida de shell saem de `lk.css.ts`. As medidas
 * miúdas do desenho (gap 12/18, padding 16/18, 11px, 30px, painel de 430px)
 * ficam em px aqui porque são medidas DESTA tela, não do sistema — o token set
 * não as cobre e não deve cobrir.
 */
import { style, styleVariants } from '@vanilla-extract/css'

import { OVERLINE_TRACKING, lk } from '../tokens/lk.css'

export const raiz = style({
  maxWidth: lk.medida.conteudoMax,
  margin: '0 auto',
  width: '100%',
  display: 'flex',
  flexDirection: 'column',
  gap: '18px',
})

// ── Cabeçalho: título + abas + período ──────────────────────────────────────

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
  fontSize: '26px',
  color: lk.cor.brancoSinal,
})

export const abas = style({
  display: 'flex',
  background: lk.cor.grafite,
  borderRadius: lk.raio.s,
  padding: '3px',
  gap: '2px',
})

const abaBase = style({
  height: '36px',
  padding: '0 18px',
  border: 'none',
  borderRadius: '6px',
  fontFamily: lk.fonte.ui,
  fontSize: '14px',
  fontWeight: 600,
  cursor: 'pointer',
  selectors: {
    '&:focus-visible': { outline: `2px solid ${lk.cor.cianoVisao}`, outlineOffset: '2px' },
  },
})

export const aba = styleVariants({
  ativa: [abaBase, { background: lk.cor.preto, color: lk.cor.cianoVisao }],
  inativa: [abaBase, { background: 'transparent', color: lk.cor.cinzaNevoa }],
})

export const espacador = style({ flex: 1 })

/** Conteúdo da aba ativa — herda o ritmo de 18px do desenho. */
export const painelAba = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '18px',
})

export const seletor = style({
  height: '36px',
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: '6px',
  color: lk.cor.brancoSinal,
  fontFamily: lk.fonte.ui,
  fontSize: '13px',
  padding: '0 10px',
  selectors: {
    '&:focus-visible': { outline: `2px solid ${lk.cor.cianoVisao}`, outlineOffset: '1px' },
    '&:disabled': { color: lk.cor.cinzaNevoa, cursor: 'not-allowed' },
  },
})

export const entradaData = style([seletor, { fontFamily: lk.fonte.mono, colorScheme: 'dark' }])

export const entradaTexto = style([seletor, { minWidth: '160px' }])

// ── KPIs ────────────────────────────────────────────────────────────────────

export const gradeKpis = style({
  display: 'grid',
  gridTemplateColumns: 'repeat(6, 1fr)',
  gap: '12px',
  '@media': {
    '(max-width: 1100px)': { gridTemplateColumns: 'repeat(3, 1fr)' },
    '(max-width: 620px)': { gridTemplateColumns: 'repeat(2, 1fr)' },
  },
})

const kpiBase = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '6px',
  padding: '16px',
  background: lk.cor.grafite,
  borderRadius: lk.raio.m,
  borderTop: `2px solid ${lk.cor.bordaForte}`,
})

/** A borda superior do cartão repete a semântica do valor — nunca a substitui. */
export const kpi = styleVariants({
  neutro: [kpiBase],
  ok: [kpiBase, { borderTopColor: lk.estado.ok }],
  atencao: [kpiBase, { borderTopColor: lk.estado.atencao }],
  nc: [kpiBase, { borderTopColor: lk.estado.nc }],
})

export const kpiRotulo = style({
  fontFamily: lk.fonte.mono,
  fontSize: '10.5px',
  letterSpacing: OVERLINE_TRACKING,
  textTransform: 'uppercase',
  color: lk.cor.cinzaNevoa,
})

const kpiValorBase = style({
  fontFamily: lk.fonte.mono,
  fontWeight: 700,
  fontSize: '30px',
  lineHeight: 1,
  color: lk.cor.brancoSinal,
})

export const kpiValor = styleVariants({
  neutro: [kpiValorBase],
  ok: [kpiValorBase, { color: lk.estado.ok }],
  atencao: [kpiValorBase, { color: lk.estado.atencao }],
  nc: [kpiValorBase, { color: lk.estado.nc }],
})

export const kpiSub = style({
  fontSize: '12px',
  lineHeight: 1.4,
  color: lk.cor.cinzaNevoa,
})

// ── Cartões ─────────────────────────────────────────────────────────────────

export const grade3 = style({
  display: 'grid',
  gridTemplateColumns: '1fr 1fr 1fr',
  gap: '12px',
  alignItems: 'start',
  '@media': {
    '(max-width: 1000px)': { gridTemplateColumns: '1fr' },
  },
})

export const cartao = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '12px',
  padding: '18px',
  background: lk.cor.grafite,
  borderRadius: lk.raio.m,
})

export const cartaoTitulo = style({
  fontSize: '14px',
  fontWeight: 600,
  color: lk.cor.brancoSinal,
})

export const nota = style({
  margin: 0,
  fontSize: '12px',
  lineHeight: 1.5,
  color: lk.cor.cinzaNevoa,
})

export const dado = style({
  fontFamily: lk.fonte.mono,
  color: lk.cor.brancoSinal,
})

// ── Barras ──────────────────────────────────────────────────────────────────

export const linhaBarra = style({
  display: 'flex',
  alignItems: 'center',
  gap: '10px',
})

export const barraCodigo = style({
  fontFamily: lk.fonte.mono,
  fontSize: '13px',
  color: lk.cor.brancoSinal,
  minWidth: '30px',
})

export const barraNome = style({
  fontSize: '12.5px',
  color: lk.cor.brancoSinal,
  width: '150px',
  whiteSpace: 'nowrap',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
})

export const trilho = style({
  flex: 1,
  height: '16px',
  background: lk.cor.preto,
  borderRadius: '4px',
  overflow: 'hidden',
})

const preenchimentoBase = style({ height: '100%', background: lk.cor.cinzaNevoa })

export const preenchimento = styleVariants({
  neutro: [preenchimentoBase],
  atencao: [preenchimentoBase, { background: lk.estado.atencao }],
  nc: [preenchimentoBase, { background: lk.estado.nc }],
})

export const barraNumero = style({
  fontFamily: lk.fonte.mono,
  fontSize: '13px',
  color: lk.cor.brancoSinal,
  minWidth: '30px',
  textAlign: 'right',
})

// ── Fila de revisão ─────────────────────────────────────────────────────────

export const numeroGrande = style({
  fontFamily: lk.fonte.mono,
  fontWeight: 700,
  fontSize: '38px',
  lineHeight: 1,
  color: lk.cor.brancoSinal,
})

export const numeroLegenda = style({
  fontSize: '13px',
  color: lk.cor.cinzaNevoa,
})

export const linhaNumeros = style({
  display: 'flex',
  gap: lk.espaco.x3,
  alignItems: 'baseline',
  flexWrap: 'wrap',
})

// ── Estações ────────────────────────────────────────────────────────────────

export const gradeEstacoes = style({
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
  gap: '12px',
})

export const estacao = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '6px',
  padding: '14px',
  background: lk.cor.preto,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.s,
})

export const estacaoTopo = style({
  display: 'flex',
  alignItems: 'baseline',
  gap: lk.espaco.x1,
})

export const estacaoCodigo = style({
  fontFamily: lk.fonte.mono,
  fontSize: '13px',
  fontWeight: 700,
  color: lk.cor.brancoSinal,
})

export const estacaoNome = style({
  fontSize: '13px',
  color: lk.cor.cinzaNevoa,
})

// ── D2: lista de peças ──────────────────────────────────────────────────────

export const colunasD2 = style({
  display: 'flex',
  gap: lk.espaco.x2,
  alignItems: 'flex-start',
  '@media': {
    '(max-width: 1080px)': { flexDirection: 'column' },
  },
})

export const listaPecas = style({
  flex: 1,
  minWidth: 0,
  display: 'flex',
  flexDirection: 'column',
  gap: '6px',
  width: '100%',
})

export const filtros = style({
  display: 'flex',
  gap: '10px',
  alignItems: 'flex-end',
  flexWrap: 'wrap',
})

export const campo = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '5px',
})

export const rotulo = style({
  fontSize: '12px',
  color: lk.cor.cinzaNevoa,
})

const pecaBase = style({
  display: 'flex',
  alignItems: 'center',
  gap: lk.espaco.x2,
  padding: '12px 16px',
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.s,
  cursor: 'pointer',
  textAlign: 'left',
  width: '100%',
  selectors: {
    '&:focus-visible': { outline: `2px solid ${lk.cor.cianoVisao}`, outlineOffset: '2px' },
  },
})

export const peca = styleVariants({
  normal: [pecaBase],
  selecionada: [pecaBase, { borderColor: lk.cor.cianoVisao }],
})

export const pecaCodigo = style({
  fontFamily: lk.fonte.mono,
  fontWeight: 500,
  fontSize: '14px',
  color: lk.cor.brancoSinal,
  width: '120px',
  flex: 'none',
})

export const pecaOp = style({
  fontSize: '13px',
  color: lk.cor.cinzaNevoa,
  width: '120px',
  flex: 'none',
  whiteSpace: 'nowrap',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
})

export const pecaTipo = style({
  fontSize: '13px',
  color: lk.cor.brancoSinal,
  flex: 1,
  minWidth: 0,
  whiteSpace: 'nowrap',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
})

export const pecaRetrabalho = style({
  fontFamily: lk.fonte.mono,
  fontSize: '12px',
  color: lk.cor.cinzaNevoa,
  whiteSpace: 'nowrap',
})

export const pecaCiclo = style({
  fontFamily: lk.fonte.mono,
  fontSize: '12px',
  color: lk.cor.cinzaNevoa,
  width: '58px',
  flex: 'none',
  textAlign: 'right',
})

/** Estado = cor + ícone + PALAVRA. A cor nunca vai sozinha. */
const situacaoBase = style({
  display: 'flex',
  alignItems: 'center',
  gap: '6px',
  fontSize: '12px',
  fontWeight: 600,
  width: '150px',
  flex: 'none',
  justifyContent: 'flex-end',
  textAlign: 'right',
})

export const situacao = styleVariants({
  neutro: [situacaoBase, { color: lk.cor.cinzaNevoa }],
  ok: [situacaoBase, { color: lk.estado.ok }],
  atencao: [situacaoBase, { color: lk.estado.atencao }],
  nc: [situacaoBase, { color: lk.estado.nc }],
})

export const paginacao = style({
  display: 'flex',
  alignItems: 'center',
  gap: '10px',
  paddingTop: lk.espaco.x1,
})

export const botaoPagina = style({
  height: '32px',
  padding: '0 14px',
  background: 'transparent',
  border: `1px solid ${lk.cor.bordaForte}`,
  borderRadius: '6px',
  color: lk.cor.brancoSinal,
  fontFamily: lk.fonte.ui,
  fontSize: '13px',
  cursor: 'pointer',
  selectors: {
    '&:disabled': { color: lk.cor.cinzaNevoa, cursor: 'not-allowed' },
    '&:focus-visible': { outline: `2px solid ${lk.cor.cianoVisao}`, outlineOffset: '2px' },
  },
})

// ── D2: painel de detalhe ───────────────────────────────────────────────────

export const painel = style({
  width: '430px',
  flex: 'none',
  display: 'flex',
  flexDirection: 'column',
  gap: '12px',
  background: lk.cor.grafite,
  borderRadius: lk.raio.g,
  padding: '18px',
  '@media': {
    '(max-width: 1080px)': { width: '100%' },
  },
})

export const painelTopo = style({
  display: 'flex',
  alignItems: 'baseline',
  gap: '10px',
  flexWrap: 'wrap',
})

export const painelCodigo = style({
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '19px',
  color: lk.cor.brancoSinal,
})

export const painelMeta = style({
  fontSize: '13px',
  color: lk.cor.cinzaNevoa,
})

export const overline = style({
  fontFamily: lk.fonte.mono,
  fontSize: '10.5px',
  letterSpacing: OVERLINE_TRACKING,
  textTransform: 'uppercase',
  color: lk.cor.cinzaNevoa,
})

export const linhaTempo = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '10px',
})

export const evento = style({
  display: 'flex',
  gap: '12px',
})

/** Sem rota que assine a foto: a caixa fica, vazia e dizendo por quê. */
export const semFoto = style({
  width: '64px',
  height: '44px',
  flex: 'none',
  background: lk.cor.preto,
  border: `1px dashed ${lk.cor.bordaForte}`,
  borderRadius: '5px',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  fontFamily: lk.fonte.mono,
  fontSize: '9px',
  color: lk.cor.cinzaNevoa,
})

export const eventoCorpo = style({
  flex: 1,
  minWidth: 0,
  display: 'flex',
  flexDirection: 'column',
  gap: '2px',
})

export const eventoLinha = style({
  display: 'flex',
  alignItems: 'center',
  gap: lk.espaco.x1,
})

export const eventoCodigo = style({
  fontFamily: lk.fonte.mono,
  fontSize: '13px',
  fontWeight: 700,
  color: lk.cor.brancoSinal,
})

export const eventoHora = style({
  fontFamily: lk.fonte.mono,
  fontSize: '11px',
  color: lk.cor.cinzaNevoa,
  marginLeft: 'auto',
})

export const eventoDetalhe = style({
  fontSize: '12.5px',
  lineHeight: 1.45,
  color: lk.cor.cinzaNevoa,
})

export const rodapePainel = style({
  paddingTop: '10px',
  borderTop: `1px solid ${lk.cor.borda}`,
  fontSize: '12.5px',
  lineHeight: 1.5,
  color: lk.cor.cinzaNevoa,
})

// ── D3: tabela ──────────────────────────────────────────────────────────────

export const tabela = style({
  display: 'grid',
  gridTemplateColumns: '1fr 130px 130px',
  background: lk.cor.grafite,
  borderRadius: lk.raio.s,
  overflow: 'hidden',
})

const celulaBase = style({
  padding: '11px 14px',
  fontSize: '13px',
  borderBottom: `1px solid ${lk.cor.borda}`,
  color: lk.cor.brancoSinal,
})

export const cabecalhoCelula = style([
  celulaBase,
  {
    fontFamily: lk.fonte.mono,
    fontSize: '10.5px',
    letterSpacing: OVERLINE_TRACKING,
    textTransform: 'uppercase',
    color: lk.cor.cinzaNevoa,
  },
])

export const celula = styleVariants({
  texto: [celulaBase],
  numero: [celulaBase, { fontFamily: lk.fonte.mono, textAlign: 'right' }],
})

export const acoes = style({
  display: 'flex',
  gap: '10px',
  alignItems: 'center',
  flexWrap: 'wrap',
})

export const botaoPrimario = style({
  height: '44px',
  padding: '0 20px',
  border: 'none',
  borderRadius: lk.raio.s,
  background: lk.cor.cianoVisao,
  color: lk.cor.preto,
  fontFamily: lk.fonte.ui,
  fontSize: '14px',
  fontWeight: 700,
  cursor: 'pointer',
  selectors: {
    '&:disabled': { background: lk.cor.borda, color: lk.cor.cinzaNevoa, cursor: 'not-allowed' },
    '&:focus-visible': { outline: `2px solid ${lk.cor.cianoVisao}`, outlineOffset: '2px' },
  },
})

export const botaoSecundario = style({
  height: '44px',
  padding: '0 20px',
  background: 'transparent',
  border: `1px solid ${lk.cor.bordaForte}`,
  borderRadius: lk.raio.s,
  color: lk.cor.brancoSinal,
  fontFamily: lk.fonte.ui,
  fontSize: '14px',
  fontWeight: 600,
  cursor: 'pointer',
  selectors: {
    '&:disabled': { color: lk.cor.cinzaNevoa, cursor: 'not-allowed' },
    '&:focus-visible': { outline: `2px solid ${lk.cor.cianoVisao}`, outlineOffset: '2px' },
  },
})

// ── Estados de tela: carregando / vazio / erro ──────────────────────────────

export const centro = style({
  minHeight: '40vh',
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '12px',
  textAlign: 'center',
  padding: lk.medida.padding,
})

export const centroTitulo = style({
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '18px',
  color: lk.cor.brancoSinal,
})

export const centroTexto = style({
  fontSize: '13.5px',
  lineHeight: 1.55,
  color: lk.cor.cinzaNevoa,
  maxWidth: '420px',
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
    '&:focus-visible': { outline: `2px solid ${lk.cor.cianoVisao}`, outlineOffset: '2px' },
  },
})

const avisoBase = style({
  display: 'flex',
  alignItems: 'center',
  gap: lk.espaco.x1,
  fontSize: '12.5px',
  lineHeight: 1.45,
})

export const aviso = styleVariants({
  neutro: [avisoBase, { color: lk.cor.cinzaNevoa }],
  atencao: [avisoBase, { color: lk.estado.atencao }],
  nc: [avisoBase, { color: lk.estado.nc }],
})

export const ligacao = style({
  fontSize: '12px',
  marginLeft: 'auto',
  color: lk.cor.cianoVisao,
  textDecoration: 'none',
  selectors: {
    '&:hover': { color: lk.cor.cianoProfundo },
    '&:focus-visible': { outline: `2px solid ${lk.cor.cianoVisao}`, outlineOffset: '2px' },
  },
})
