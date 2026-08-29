/**
 * Medidas de `design/Carga.dc.html`. Cor e tipografia SÓ por token — a tela é
 * escura por identidade, mas a cor de acento é a do tenant.
 */
import { style, styleVariants } from '@vanilla-extract/css'

import { lk } from '../tokens/lk.css'

export const raiz = style({
  maxWidth: lk.medida.conteudoMax,
  margin: '0 auto',
  display: 'flex',
  flexDirection: 'column',
  gap: lk.espaco.x2,
})

export const cabecalho = style({
  display: 'flex',
  alignItems: 'center',
  gap: '12px',
  flexWrap: 'wrap',
})

export const titulo = style({
  margin: 0,
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '26px',
})

export const espacador = style({ flex: 1 })

export const seletor = style({
  height: '36px',
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: '6px',
  color: lk.cor.brancoSinal,
  fontFamily: lk.fonte.ui,
  fontSize: '13px',
  padding: `0 ${lk.espaco.x1}`,
  ':disabled': { opacity: 0.4, cursor: 'not-allowed' },
})

/**
 * As quatro abas do desenho moram na sidebar do módulo Carga; o Shell serve
 * a nav do EPI, então elas viram abas da própria tela — mesma navegação,
 * sem tocar no roteador.
 */
/** O painel da aba — separado do `raiz` porque `role="tabpanel"` precisa de
 *  um contêiner próprio para o leitor de tela saber onde a aba termina. */
export const painelAba = style({
  display: 'flex',
  flexDirection: 'column',
  gap: lk.espaco.x2,
})

export const abas = style({
  display: 'flex',
  gap: '2px',
  borderBottom: `1px solid ${lk.cor.borda}`,
})

const abaBase = style({
  display: 'flex',
  alignItems: 'center',
  gap: '9px',
  height: lk.medida.itemNav,
  padding: `0 ${lk.espaco.x2}`,
  background: 'transparent',
  border: 'none',
  borderBottom: '2px solid transparent',
  color: lk.cor.cinzaNevoa,
  fontFamily: lk.fonte.ui,
  fontSize: '13.5px',
  fontWeight: 500,
  cursor: 'pointer',
  ':hover': { color: lk.cor.brancoSinal },
})

export const aba = styleVariants({
  inativa: [abaBase],
  ativa: [
    abaBase,
    { color: lk.cor.cianoVisao, borderBottomColor: lk.cor.cianoVisao, fontWeight: 600 },
  ],
})

// ── KPIs ────────────────────────────────────────────────────────────────────

export const kpis = style({
  display: 'grid',
  gridTemplateColumns: 'repeat(4, 1fr)',
  gap: '12px',
  '@media': {
    '(max-width: 1100px)': { gridTemplateColumns: 'repeat(2, 1fr)' },
    '(max-width: 640px)': { gridTemplateColumns: '1fr' },
  },
})

export const kpi = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '6px',
  padding: '16px 18px',
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderTop: `2px solid ${lk.cor.bordaForte}`,
  borderRadius: lk.raio.g,
})

export const overline = style({
  fontFamily: lk.fonte.mono,
  fontSize: '10px',
  letterSpacing: '0.16em',
  color: lk.cor.cinzaNevoa,
})

export const kpiValor = style({
  fontFamily: lk.fonte.mono,
  fontWeight: 700,
  fontSize: '34px',
  lineHeight: 1,
})

export const kpiSub = style({ fontSize: '12px', color: lk.cor.cinzaNevoa })

// ── Painéis ─────────────────────────────────────────────────────────────────

export const doisPaineis = style({
  display: 'grid',
  gridTemplateColumns: '1.4fr 1fr',
  gap: '12px',
  '@media': { '(max-width: 1100px)': { gridTemplateColumns: '1fr' } },
})

export const painel = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '12px',
  padding: '18px',
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.g,
})

export const painelTitulo = style({ fontSize: '14px', fontWeight: 600 })

export const nota = style({ fontSize: '12px', color: lk.cor.cinzaNevoa, lineHeight: 1.55 })

// ── Barras (agregado diário do relatório) ───────────────────────────────────

export const barras = style({
  display: 'flex',
  alignItems: 'flex-end',
  gap: '5px',
  height: '110px',
})

export const colunaBarra = style({
  flex: 1,
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  gap: '5px',
  height: '100%',
  justifyContent: 'flex-end',
})

export const barra = style({
  width: '100%',
  background: lk.cor.cianoProfundo,
  borderRadius: '3px 3px 0 0',
  minHeight: '2px',
})

export const barraRotulo = style({
  fontFamily: lk.fonte.mono,
  fontSize: '9.5px',
  color: lk.cor.cinzaNevoa,
})

export const linhaDia = style({ display: 'flex', alignItems: 'center', gap: '10px' })

export const linhaDiaRotulo = style({
  fontFamily: lk.fonte.mono,
  fontSize: '13px',
  width: '76px',
  flex: 'none',
})

export const trilho = style({
  flex: 1,
  height: '14px',
  background: lk.cor.preto,
  borderRadius: '4px',
  overflow: 'hidden',
})

export const trilhoCheio = style({ height: '100%' })

export const linhaDiaValor = style({
  fontFamily: lk.fonte.mono,
  fontSize: '13px',
  minWidth: '54px',
  textAlign: 'right',
  flex: 'none',
})

// ── Tabela ──────────────────────────────────────────────────────────────────

export const tabela = style({
  width: '100%',
  borderCollapse: 'collapse',
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.m,
  overflow: 'hidden',
})

export const th = style({
  textAlign: 'left',
  padding: '10px 14px',
  fontFamily: lk.fonte.mono,
  fontWeight: 400,
  fontSize: '10px',
  letterSpacing: '0.14em',
  color: lk.cor.cinzaNevoa,
  borderBottom: `1px solid ${lk.cor.borda}`,
  whiteSpace: 'nowrap',
})

export const td = style({
  padding: '12px 14px',
  fontSize: '13px',
  borderBottom: `1px solid ${lk.cor.borda}`,
})

export const tdMono = style([td, { fontFamily: lk.fonte.mono, fontSize: '12.5px' }])

export const selo = style({
  display: 'inline-flex',
  alignItems: 'center',
  gap: '6px',
  fontFamily: lk.fonte.mono,
  fontSize: '10px',
  letterSpacing: '0.08em',
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: '5px',
  padding: '3px 8px',
  whiteSpace: 'nowrap',
})

// ── Cartões de sessão (aba Baias) ───────────────────────────────────────────

export const cartoes = style({
  display: 'grid',
  gridTemplateColumns: 'repeat(2, 1fr)',
  gap: '12px',
  '@media': { '(max-width: 900px)': { gridTemplateColumns: '1fr' } },
})

export const cartao = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '12px',
  padding: '16px 18px',
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.g,
})

export const cartaoTopo = style({ display: 'flex', alignItems: 'center', gap: '10px' })

export const cartaoNome = style({
  fontFamily: lk.fonte.mono,
  fontSize: '12px',
  letterSpacing: '0.1em',
})

export const contagem = style({ display: 'flex', alignItems: 'baseline', gap: lk.espaco.x1 })

export const contagemValor = style({
  fontFamily: lk.fonte.mono,
  fontWeight: 700,
  fontSize: '30px',
  lineHeight: 1,
})

export const cartaoRodape = style({
  display: 'flex',
  alignItems: 'center',
  gap: '12px',
  flexWrap: 'wrap',
})

// ── Validação ───────────────────────────────────────────────────────────────

export const fichaValidacao = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '14px',
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: '14px',
  padding: '22px',
})

export const tresCaixas = style({
  display: 'grid',
  gridTemplateColumns: 'repeat(3, 1fr)',
  gap: '12px',
  '@media': { '(max-width: 900px)': { gridTemplateColumns: '1fr' } },
})

export const caixa = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '6px',
  padding: '18px',
  background: lk.cor.preto,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.m,
})

export const numeroGrande = style({
  fontFamily: lk.fonte.mono,
  fontWeight: 700,
  fontSize: '52px',
  lineHeight: 1,
})

export const parDeBotoes = style({
  display: 'flex',
  gap: lk.espaco.x1,
  '@media': { '(max-width: 700px)': { flexDirection: 'column' } },
})

export const botaoVeredito = style({
  flex: 1,
  height: lk.medida.veredito,
  background: 'transparent',
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: '9px',
  color: lk.cor.brancoSinal,
  fontFamily: lk.fonte.ui,
  fontSize: '14px',
  fontWeight: 600,
  cursor: 'pointer',
  ':disabled': { opacity: 0.45, cursor: 'not-allowed' },
})

// ── Botões e faixas ─────────────────────────────────────────────────────────

export const botaoPrimario = style({
  height: '40px',
  padding: `0 18px`,
  border: 'none',
  borderRadius: lk.raio.s,
  background: lk.cor.cianoVisao,
  color: lk.cor.preto,
  fontFamily: lk.fonte.ui,
  fontSize: '13.5px',
  fontWeight: 700,
  cursor: 'pointer',
  ':disabled': { opacity: 0.45, cursor: 'not-allowed' },
})

export const botaoSecundario = style({
  height: '32px',
  padding: '0 13px',
  background: 'transparent',
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: '7px',
  color: lk.cor.brancoSinal,
  fontFamily: lk.fonte.ui,
  fontSize: '12.5px',
  fontWeight: 600,
  cursor: 'pointer',
  ':hover': { borderColor: lk.cor.cianoVisao, color: lk.cor.cianoVisao },
  ':disabled': { opacity: 0.4, cursor: 'not-allowed' },
})

export const faixaFalta = style({
  display: 'flex',
  alignItems: 'flex-start',
  gap: '10px',
  padding: '12px 14px',
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.m,
  fontSize: '12.5px',
  color: lk.cor.cinzaNevoa,
  lineHeight: 1.55,
})

// ── Estados de tela ─────────────────────────────────────────────────────────

export const centro = style({
  minHeight: '52vh',
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
  maxWidth: '420px',
  lineHeight: 1.55,
})

export const centroTecnico = style({
  fontFamily: lk.fonte.mono,
  fontSize: '12px',
  color: lk.cor.cinzaNevoa,
})
