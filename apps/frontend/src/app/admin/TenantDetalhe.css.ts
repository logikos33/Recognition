import { style } from '@vanilla-extract/css'

import { lk } from '../tokens/lk.css'

export const raiz = style({
  display: 'flex',
  flexDirection: 'column',
  gap: lk.espaco.x2,
  maxWidth: lk.medida.conteudoMax,
})

export const cabecalho = style({
  display: 'flex',
  alignItems: 'center',
  gap: lk.espaco.x1,
  flexWrap: 'wrap',
})

export const voltar = style({
  background: 'none',
  border: 'none',
  padding: 0,
  fontSize: '13px',
  fontWeight: 600,
  color: lk.cor.cinzaNevoa,
  cursor: 'pointer',
  selectors: { '&:hover': { color: lk.cor.brancoSinal } },
})

export const titulo = style({
  margin: 0,
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '26px',
})

export const spacer = style({ flex: 1 })

export const botaoPrimario = style({
  height: '38px',
  padding: `0 ${lk.espaco.x2}`,
  border: 'none',
  borderRadius: lk.raio.s,
  background: lk.cor.cianoVisao,
  color: lk.cor.preto,
  fontFamily: lk.fonte.ui,
  fontSize: '13.5px',
  fontWeight: 700,
  cursor: 'pointer',
  selectors: { '&:disabled': { opacity: 0.6, cursor: 'default' } },
})

export const botaoSecundario = style({
  height: '38px',
  padding: `0 ${lk.espaco.x2}`,
  background: 'transparent',
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.s,
  color: lk.cor.brancoSinal,
  fontFamily: lk.fonte.ui,
  fontSize: '13px',
  fontWeight: 600,
  cursor: 'pointer',
  selectors: { '&:disabled': { opacity: 0.6, cursor: 'default' } },
})

export const botaoPerigo = style({
  height: '38px',
  padding: `0 ${lk.espaco.x2}`,
  background: 'transparent',
  border: `1px solid ${lk.estado.nc}`,
  borderRadius: lk.raio.s,
  color: lk.estado.nc,
  fontFamily: lk.fonte.ui,
  fontSize: '13px',
  fontWeight: 600,
  cursor: 'pointer',
  selectors: { '&:disabled': { opacity: 0.6, cursor: 'default' } },
})

export const grid = style({
  display: 'grid',
  gridTemplateColumns: '1fr 1fr',
  gap: lk.espaco.x1,
  alignItems: 'start',
  '@media': { 'screen and (max-width: 900px)': { gridTemplateColumns: '1fr' } },
})

export const painel = style({
  display: 'flex',
  flexDirection: 'column',
  gap: lk.espaco.x1,
  padding: lk.espaco.x2,
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.g,
})

export const overline = style({
  fontFamily: lk.fonte.mono,
  fontSize: '10px',
  letterSpacing: '.18em',
  textTransform: 'uppercase',
  color: lk.cor.cinzaNevoa,
})

export const dadosGrid = style({
  display: 'grid',
  gridTemplateColumns: 'auto 1fr',
  gap: '8px 16px',
  fontSize: '13px',
})

export const dadosLabel = style({ color: lk.cor.cinzaNevoa })

export const mono = style({ fontFamily: lk.fonte.mono, fontSize: '12px' })

export const divisor = style({
  borderTop: `1px solid ${lk.cor.borda}`,
  paddingTop: lk.espaco.x1,
  display: 'flex',
  flexDirection: 'column',
  gap: '8px',
})

export const barraLinha = style({
  display: 'flex',
  alignItems: 'center',
  gap: '10px',
})

export const barraLabel = style({
  fontSize: '12.5px',
  width: '80px',
  flexShrink: 0,
  color: lk.cor.cinzaNevoa,
})

export const barraTrilho = style({
  flex: 1,
  height: '8px',
  background: lk.cor.preto,
  borderRadius: '4px',
  overflow: 'hidden',
})

export const barraPreenchida = style({
  height: '100%',
  background: lk.cor.cianoVisao,
})

export const barraValor = style({
  fontFamily: lk.fonte.mono,
  fontSize: '12px',
  flexShrink: 0,
})

export const moduloLinha = style({
  display: 'flex',
  alignItems: 'center',
  gap: '10px',
  background: 'none',
  border: 'none',
  padding: '3px 0',
  cursor: 'pointer',
  textAlign: 'left',
  width: '100%',
  selectors: { '&:disabled': { opacity: 0.6, cursor: 'default' } },
})

export const toggleTrilho = style({
  width: '30px',
  height: '16px',
  borderRadius: '8px',
  position: 'relative',
  flexShrink: 0,
  background: lk.cor.borda,
  transition: 'background .1s steps(2,end)',
})

export const toggleTrilhoLigado = style({
  background: lk.cor.cianoProfundo,
})

export const toggleBolinha = style({
  position: 'absolute',
  top: '2px',
  left: '2px',
  width: '12px',
  height: '12px',
  borderRadius: '50%',
  background: lk.cor.brancoSinal,
  transition: 'left .1s steps(2,end)',
})

export const toggleBolinhaLigado = style({ left: '16px' })

export const moduloNome = style({ fontSize: '13px', color: lk.cor.brancoSinal })

export const moduloNota = style({ fontSize: '11.5px', color: lk.cor.cinzaNevoa })

// ── White-label ──────────────────────────────────────────────────────────

export const explicacao = style({
  fontSize: '12.5px',
  color: lk.cor.cinzaNevoa,
  lineHeight: 1.5,
})

export const acentosLinha = style({
  display: 'flex',
  gap: '8px',
  alignItems: 'center',
  flexWrap: 'wrap',
})

export const swatch = style({
  width: '36px',
  height: '36px',
  borderRadius: lk.raio.s,
  border: `2px solid ${lk.cor.borda}`,
  cursor: 'pointer',
  padding: 0,
})

export const swatchSelecionado = style({
  borderColor: lk.cor.brancoSinal,
})

export const inputCustom = style({
  height: '36px',
  width: '110px',
  padding: '0 10px',
  background: lk.cor.preto,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.s,
  color: lk.cor.brancoSinal,
  fontFamily: lk.fonte.mono,
  fontSize: '13px',
})

export const uploadArea = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '10px',
  height: '64px',
  border: `1px dashed ${lk.cor.bordaForte}`,
  borderRadius: lk.raio.s,
  color: lk.cor.cinzaNevoa,
  fontSize: '12.5px',
  cursor: 'pointer',
})

export const logoPreview = style({
  height: '40px',
  maxWidth: '160px',
  objectFit: 'contain',
})

export const previaBox = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '8px',
  padding: lk.espaco.x1,
  background: lk.cor.preto,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.m,
})

export const previaLinha = style({
  display: 'flex',
  alignItems: 'center',
  gap: '10px',
})

export const previaBotao = style({
  height: '34px',
  display: 'flex',
  alignItems: 'center',
  padding: '0 14px',
  borderRadius: '7px',
  color: lk.cor.preto,
  fontSize: '13px',
  fontWeight: 700,
  border: 'none',
})

export const previaItem = style({
  height: '34px',
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
  padding: '0 12px',
  borderRadius: '7px',
  background: lk.cor.grafite,
  fontSize: '13px',
  fontWeight: 600,
})

export const previaLink = style({ fontSize: '13px', fontWeight: 600 })

export const avisoAjuste = style({
  fontSize: '11.5px',
  color: lk.estado.atencao,
})

export const contrasteTexto = style({
  fontFamily: lk.fonte.mono,
  fontSize: '11px',
  color: lk.cor.cinzaNevoa,
})

export const erro = style({
  fontSize: '12.5px',
  color: lk.estado.nc,
  padding: '8px 10px',
  border: `1px solid ${lk.estado.nc}`,
  borderRadius: lk.raio.s,
})

export const linkAntigo = style({
  fontSize: '12.5px',
  color: lk.cor.cianoVisao,
})

// ── estados de tela ──────────────────────────────────────────────────────

export const centro = style({
  minHeight: '50vh',
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
  fontSize: '18px',
})

export const centroTecnico = style({
  fontFamily: lk.fonte.mono,
  fontSize: '12px',
  color: lk.cor.cinzaNevoa,
})

export const botaoRetry = style({
  height: '38px',
  padding: `0 ${lk.espaco.x2}`,
  border: 'none',
  borderRadius: lk.raio.s,
  background: lk.cor.cianoVisao,
  color: lk.cor.preto,
  fontSize: '13px',
  fontWeight: 700,
  cursor: 'pointer',
})

export const statusOk = style({
  display: 'flex',
  alignItems: 'center',
  gap: '6px',
  fontSize: '12.5px',
  fontWeight: 600,
  color: lk.estado.ok,
})

export const statusNc = style({
  display: 'flex',
  alignItems: 'center',
  gap: '6px',
  fontSize: '12.5px',
  fontWeight: 600,
  color: lk.estado.nc,
})

export const dot = style({
  width: '8px',
  height: '8px',
  borderRadius: '50%',
  background: 'currentColor',
})
