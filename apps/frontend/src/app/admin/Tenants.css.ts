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
})

export const titulo = style({
  margin: 0,
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '26px',
})

export const subtitulo = style({
  fontSize: '12.5px',
  color: lk.cor.cinzaNevoa,
})

export const spacer = style({ flex: 1 })

export const busca = style({
  height: '36px',
  minWidth: '240px',
  padding: '0 12px',
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.s,
  color: lk.cor.brancoSinal,
  fontSize: '13px',
})

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
  height: '32px',
  padding: '0 13px',
  background: 'transparent',
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.s,
  color: lk.cor.brancoSinal,
  fontFamily: lk.fonte.ui,
  fontSize: '12.5px',
  fontWeight: 600,
  cursor: 'pointer',
  selectors: { '&:disabled': { opacity: 0.6, cursor: 'default' } },
})

export const tabelaWrap = style({
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.m,
  overflow: 'auto',
})

export const tabela = style({
  width: '100%',
  borderCollapse: 'collapse',
})

export const th = style({
  textAlign: 'left',
  padding: '10px 16px',
  fontFamily: lk.fonte.mono,
  fontSize: '10px',
  letterSpacing: '.14em',
  textTransform: 'uppercase',
  color: lk.cor.cinzaNevoa,
  borderBottom: `1px solid ${lk.cor.borda}`,
  whiteSpace: 'nowrap',
})

export const td = style({
  padding: '12px 16px',
  fontSize: '13.5px',
  color: lk.cor.brancoSinal,
  borderBottom: `1px solid ${lk.cor.borda}`,
  verticalAlign: 'middle',
})

export const linkNome = style({
  background: 'none',
  border: 'none',
  padding: 0,
  fontSize: '13.5px',
  fontWeight: 600,
  color: lk.cor.brancoSinal,
  cursor: 'pointer',
  textAlign: 'left',
  selectors: { '&:hover': { color: lk.cor.cianoVisao } },
})

export const badges = style({
  display: 'flex',
  flexWrap: 'wrap',
  gap: '5px',
})

export const badge = style({
  fontFamily: lk.fonte.mono,
  fontSize: '10px',
  color: lk.cor.cinzaNevoa,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: '5px',
  padding: '2px 7px',
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

export const rodape = style({
  fontSize: '12.5px',
  color: lk.cor.cinzaNevoa,
})

// ── modal Novo tenant ────────────────────────────────────────────────────

export const overlay = style({
  position: 'fixed',
  inset: 0,
  background: 'rgba(10,10,15,.7)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  zIndex: 1000,
})

export const modal = style({
  width: '480px',
  maxHeight: '90vh',
  overflowY: 'auto',
  display: 'flex',
  flexDirection: 'column',
  gap: lk.espaco.x1,
  padding: lk.espaco.x2,
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.g,
})

export const modalTitulo = style({
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '18px',
})

export const campoLabel = style({
  fontSize: '12.5px',
  color: lk.cor.cinzaNevoa,
})

export const campo = style({
  width: '100%',
  boxSizing: 'border-box',
  height: '36px',
  padding: '0 12px',
  background: lk.cor.preto,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.s,
  color: lk.cor.brancoSinal,
  fontSize: '13px',
})

export const modulosGrid = style({
  display: 'flex',
  flexWrap: 'wrap',
  gap: lk.espaco.x1,
})

export const moduloItem = style({
  display: 'flex',
  alignItems: 'center',
  gap: '6px',
  fontSize: '13px',
  color: lk.cor.brancoSinal,
  cursor: 'pointer',
})

export const erro = style({
  fontSize: '12.5px',
  color: lk.estado.nc,
  padding: '8px 10px',
  border: `1px solid ${lk.estado.nc}`,
  borderRadius: lk.raio.s,
})

export const acoesModal = style({
  display: 'flex',
  justifyContent: 'flex-end',
  gap: lk.espaco.x1,
  marginTop: lk.espaco.x1,
})

export const credenciais = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '8px',
  padding: lk.espaco.x1,
  background: lk.cor.preto,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.s,
})

export const credenciaisLinha = style({
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
})

export const credenciaisCodigo = style({
  flex: 1,
  fontFamily: lk.fonte.mono,
  fontSize: '13px',
  color: lk.cor.brancoSinal,
  wordBreak: 'break-all',
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
