import { style } from '@vanilla-extract/css'

import { lk } from '../tokens/lk.css'

export const raiz = style({
  display: 'flex',
  flexDirection: 'column',
  gap: lk.espaco.x2,
  maxWidth: lk.medida.conteudoMax,
})

export const titulo = style({
  margin: 0,
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '26px',
})

export const kpiGrid = style({
  display: 'grid',
  gridTemplateColumns: 'repeat(4, 1fr)',
  gap: lk.espaco.x1,
})

export const kpiCard = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '6px',
  padding: '16px 18px',
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.g,
  borderTop: '2px solid var(--kpi-cor, transparent)',
})

export const kpiLabel = style({
  fontFamily: lk.fonte.mono,
  fontSize: '10px',
  letterSpacing: '.16em',
  textTransform: 'uppercase',
  color: lk.cor.cinzaNevoa,
})

export const kpiValor = style({
  fontFamily: lk.fonte.mono,
  fontWeight: 700,
  fontSize: '34px',
  lineHeight: 1,
  color: lk.cor.brancoSinal,
})

export const kpiSub = style({
  fontSize: '12px',
  color: lk.cor.cinzaNevoa,
})

export const painelGrid = style({
  display: 'grid',
  gridTemplateColumns: '1.3fr 1fr',
  gap: lk.espaco.x1,
  alignItems: 'start',
})

export const painel = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '10px',
  padding: lk.espaco.x2,
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.g,
})

export const painelTitulo = style({
  fontSize: '14px',
  fontWeight: 600,
  color: lk.cor.brancoSinal,
})

export const linha = style({
  display: 'flex',
  alignItems: 'center',
  gap: '12px',
  padding: '10px 12px',
  background: lk.cor.preto,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.s,
})

export const linhaNome = style({
  fontSize: '13px',
  fontWeight: 600,
  color: lk.cor.brancoSinal,
  flex: 1,
  minWidth: 0,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
})

export const linhaValor = style({
  fontFamily: lk.fonte.mono,
  fontSize: '11.5px',
  color: lk.cor.cinzaNevoa,
  flexShrink: 0,
})

export const painelVazio = style({
  fontSize: '12.5px',
  color: lk.cor.cinzaNevoa,
  padding: '4px 2px',
})

// ── estados de tela ──────────────────────────────────────────────────────────
// Mesmo padrão de `app/estudio/Classes.css.ts`.

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
