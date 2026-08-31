/**
 * Medidas do `Qualidade.dc.html`. Cor, fonte e espaço só por token.
 *
 * Duas larguras saem do desenho de propósito, e é o conteúdo que manda:
 * a coluna "PONTO" (60px) virou "VALIDAÇÃO" — a palavra não cabe em 60px —
 * e a coluna de ação ficou mais larga porque o rótulo honesto do botão
 * ("Concluir retrabalho") é mais longo que o do desenho.
 */
import { style, styleVariants } from '@vanilla-extract/css'

import { lk } from '../tokens/lk.css'

export const raiz = style({ display: 'flex', flexDirection: 'column', gap: lk.espaco.x2 })

// ── Abas do módulo ──────────────────────────────────────────────────────────

export const abas = style({
  display: 'flex',
  alignItems: 'center',
  gap: '4px',
  flexWrap: 'wrap',
  paddingBottom: '2px',
  borderBottom: `1px solid ${lk.cor.borda}`,
})

/** "← Voltar", primeiro item da barra — sem lateral própria (SEM_BARRA_LATERAL),
 * é a única saída do módulo. Borda à direita porque a barra aqui é horizontal
 * (mesmo papel da borda inferior no `voltar` do Estúdio). */
export const voltar = style({
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
  height: lk.medida.itemNav,
  padding: '0 12px 0 0',
  marginRight: '8px',
  borderRight: `1px solid ${lk.cor.borda}`,
  fontSize: '13.5px',
  color: lk.cor.cinzaNevoa,
  textDecoration: 'none',
  selectors: {
    '&:hover': { color: lk.cor.brancoSinal },
  },
})

const abaBase = style({
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
  height: lk.medida.itemNav,
  padding: '0 12px',
  background: 'transparent',
  border: 'none',
  borderBottom: '2px solid transparent',
  fontFamily: lk.fonte.ui,
  fontSize: '13.5px',
  cursor: 'pointer',
  whiteSpace: 'nowrap',
  ':disabled': { opacity: 0.4, cursor: 'not-allowed' },
})

export const aba = styleVariants({
  ativa: [abaBase, { color: lk.cor.cianoVisao, fontWeight: 600, borderBottomColor: lk.cor.cianoVisao }],
  inativa: [abaBase, { color: lk.cor.cinzaNevoa, fontWeight: 500 }],
})

// ── Cabeçalho da aba ────────────────────────────────────────────────────────

export const cabecalho = style({ display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap' })

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
  ':disabled': { opacity: 0.5, cursor: 'not-allowed' },
})

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
  fontFamily: lk.fonte.ui,
  fontSize: '13px',
  fontWeight: 600,
  cursor: 'pointer',
  ':hover': { borderColor: lk.cor.cianoVisao, color: lk.cor.cianoVisao },
  ':disabled': { opacity: 0.45, cursor: 'not-allowed', borderColor: lk.cor.borda, color: lk.cor.brancoSinal },
})

export const botaoPrimario = style({
  height: '38px',
  display: 'flex',
  alignItems: 'center',
  gap: lk.espaco.x1,
  padding: `0 ${lk.espaco.x2}`,
  border: 'none',
  borderRadius: lk.raio.s,
  background: lk.cor.cianoVisao,
  color: lk.cor.preto,
  fontFamily: lk.fonte.ui,
  fontSize: '13px',
  fontWeight: 700,
  cursor: 'pointer',
  ':disabled': { opacity: 0.45, cursor: 'not-allowed' },
})

// ── KPIs ────────────────────────────────────────────────────────────────────

export const kpis = style({
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
  gap: '12px',
})

export const kpi = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '6px',
  padding: lk.espaco.x2,
  background: lk.cor.grafite,
  borderRadius: lk.raio.m,
  borderTop: `2px solid ${lk.cor.borda}`,
})

export const kpiDestaque = style({ borderTopColor: lk.estado.atencao })

export const kpiLabel = style({
  fontSize: '11px',
  color: lk.cor.cinzaNevoa,
  letterSpacing: '.07em',
})

export const kpiValor = style({
  fontFamily: lk.fonte.mono,
  fontWeight: 700,
  fontSize: '30px',
  lineHeight: 1,
})

export const kpiValorAtencao = style({ color: lk.estado.atencao })

export const kpiSub = style({ fontSize: '12px', color: lk.cor.cinzaNevoa, lineHeight: 1.45 })

// ── Tabela de retrabalho ────────────────────────────────────────────────────

export const rolagem = style({ overflowX: 'auto' })

export const tabela = style({
  display: 'grid',
  gridTemplateColumns: '110px 110px 96px minmax(220px, 1.2fr) 90px 104px 160px 190px',
  minWidth: '1080px',
  background: lk.cor.grafite,
  borderRadius: lk.raio.m,
  overflow: 'hidden',
})

export const cabecalhoCelula = style({
  padding: '10px 14px',
  fontFamily: lk.fonte.mono,
  fontSize: '11px',
  color: lk.cor.cinzaNevoa,
  letterSpacing: '.08em',
  borderBottom: `1px solid ${lk.cor.borda}`,
})

export const alinhaDireita = style({ textAlign: 'right' })

export const celula = style({
  padding: '12px 14px',
  fontSize: '13px',
  borderBottom: `1px solid ${lk.cor.borda}`,
  display: 'flex',
  alignItems: 'center',
})

export const celulaMono = style({ fontFamily: lk.fonte.mono, fontSize: '12.5px' })

export const celulaSecundaria = style({ color: lk.cor.cinzaNevoa })

export const celulaAcao = style({ justifyContent: 'flex-end' })

export const acao = style({
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

/** Estado = cor + ícone + palavra. A cor nunca vai sozinha. */
export const estado = style({
  display: 'flex',
  alignItems: 'center',
  gap: '6px',
  fontSize: '12px',
  fontWeight: 600,
  whiteSpace: 'nowrap',
})

export const tom = styleVariants({
  ok: { color: lk.estado.ok },
  atencao: { color: lk.estado.atencao },
  nc: { color: lk.estado.nc },
  neutro: { color: lk.cor.cinzaNevoa },
})

export const nota = style({
  fontSize: '12.5px',
  color: lk.cor.cinzaNevoa,
  lineHeight: 1.6,
})

// ── Câmeras das estações ────────────────────────────────────────────────────

export const split = style({
  display: 'flex',
  gap: '14px',
  alignItems: 'flex-start',
  flexWrap: 'wrap',
})

export const listaCameras = style({
  width: '330px',
  flex: 'none',
  display: 'flex',
  flexDirection: 'column',
  gap: '6px',
  '@media': { 'screen and (max-width: 900px)': { width: '100%' } },
})

export const cartaoCamera = style({
  display: 'flex',
  alignItems: 'center',
  gap: '12px',
  padding: '13px 14px',
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: '9px',
  cursor: 'pointer',
  textAlign: 'left',
  ':hover': { borderColor: lk.cor.bordaForte },
})

export const cartaoCameraAtivo = style({ borderColor: lk.cor.cianoVisao })

export const bolinha = style({ width: '9px', height: '9px', borderRadius: '50%', flex: 'none' })

export const cartaoTextos = style({ display: 'flex', flexDirection: 'column', gap: '1px', minWidth: 0 })

export const cartaoNome = style({
  fontFamily: lk.fonte.mono,
  fontSize: '13px',
  fontWeight: 700,
  color: lk.cor.brancoSinal,
})

export const cartaoSub = style({ fontSize: '12px', color: lk.cor.cinzaNevoa })

export const cartaoEstado = style({
  marginLeft: 'auto',
  fontFamily: lk.fonte.mono,
  fontSize: '10px',
  whiteSpace: 'nowrap',
})

export const detalhe = style({
  flex: 1,
  minWidth: '320px',
  display: 'flex',
  flexDirection: 'column',
  gap: '14px',
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.g,
  padding: '18px',
  boxSizing: 'border-box',
})

export const detalheTopo = style({ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' })

export const detalheNome = style({ fontFamily: lk.fonte.titulo, fontWeight: 700, fontSize: '19px' })

export const corpoDetalhe = style({ display: 'flex', gap: '14px', flexWrap: 'wrap' })

/**
 * A prévia do desenho traz um retângulo tracejado ("ZONA DE CAPTURA
 * DEMARCADA"). Não existe ROI/zona em `quality_camera_config`, e esta rota não
 * devolve snapshot — a moldura fica, o desenho da zona não, porque desenhá-la
 * num lugar arbitrário seria afirmar onde a câmera olha.
 */
export const previa = style({
  width: '300px',
  flex: 'none',
  aspectRatio: '16 / 9',
  borderRadius: lk.raio.s,
  border: `1px solid ${lk.cor.borda}`,
  background: lk.cor.preto,
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '6px',
  textAlign: 'center',
  padding: '10px',
  boxSizing: 'border-box',
})

export const previaTexto = style({
  fontFamily: lk.fonte.mono,
  fontSize: '9.5px',
  letterSpacing: '.14em',
  color: lk.cor.cinzaNevoa,
  lineHeight: 1.6,
})

export const campos = style({
  flex: 1,
  minWidth: '260px',
  display: 'grid',
  gridTemplateColumns: 'auto 1fr',
  gap: '7px 16px',
  fontSize: '12.5px',
  alignContent: 'start',
  margin: 0,
})

export const rotulo = style({ color: lk.cor.cinzaNevoa })

export const valor = style({ margin: 0 })

export const valorMono = style({ margin: 0, fontFamily: lk.fonte.mono, fontSize: '12px' })

export const painelTeste = style({
  display: 'flex',
  flexDirection: 'column',
  gap: lk.espaco.x1,
  padding: '14px',
  background: lk.cor.preto,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.m,
})

export const overline = style({
  fontFamily: lk.fonte.mono,
  fontSize: '10px',
  letterSpacing: '.18em',
  color: lk.cor.cinzaNevoa,
  textTransform: 'uppercase',
})

export const passo = style({ display: 'flex', alignItems: 'center', gap: '10px' })

export const passoMarca = style({
  width: '20px',
  height: '20px',
  flex: 'none',
  borderRadius: '50%',
  border: `1px solid ${lk.cor.bordaForte}`,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  fontSize: '11px',
  fontWeight: 700,
})

export const passoTexto = style({ fontSize: '13px' })

export const passoMensagem = style({
  marginLeft: 'auto',
  fontFamily: lk.fonte.mono,
  fontSize: '11px',
  textAlign: 'right',
})

// ── Estados da tela ─────────────────────────────────────────────────────────

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

export const centroTitulo = style({ fontFamily: lk.fonte.titulo, fontWeight: 700, fontSize: '19px' })

export const centroTexto = style({
  fontSize: '13.5px',
  color: lk.cor.cinzaNevoa,
  maxWidth: '440px',
  lineHeight: 1.55,
})

export const centroTecnico = style({
  fontFamily: lk.fonte.mono,
  fontSize: '12px',
  color: lk.cor.cinzaNevoa,
})
