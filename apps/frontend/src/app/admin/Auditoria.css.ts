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

export const seletorPeriodo = style({
  height: '36px',
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.s,
  color: lk.cor.brancoSinal,
  fontSize: '13px',
  padding: '0 10px',
})

export const botaoExportar = style({
  height: '36px',
  padding: '0 14px',
  background: 'transparent',
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.s,
  color: lk.cor.brancoSinal,
  fontFamily: lk.fonte.ui,
  fontSize: '13px',
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
  gap: '6px',
  selectors: {
    '&:disabled': { opacity: 0.6, cursor: 'default' },
  },
})

export const lista = style({
  display: 'flex',
  flexDirection: 'column',
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.g,
  overflow: 'hidden',
})

export const linha = style({
  display: 'flex',
  alignItems: 'center',
  gap: lk.espaco.x1,
  padding: '11px 16px',
  borderBottom: `1px solid ${lk.cor.borda}`,
  selectors: {
    '&:last-child': { borderBottom: 'none' },
  },
})

export const quando = style({
  fontFamily: lk.fonte.mono,
  fontSize: '11.5px',
  color: lk.cor.cinzaNevoa,
  width: '150px',
  flexShrink: 0,
})

export const quem = style({
  fontSize: '12.5px',
  fontWeight: 600,
  width: '180px',
  flexShrink: 0,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
})

/** Cor do pill de tipo vem de `--tipo-cor` (heurística por palavra-chave da
 * ação — ver `corTipo` no componente), não de um enum do backend. */
export const tipo = style({
  fontFamily: lk.fonte.mono,
  fontSize: '10px',
  letterSpacing: '.06em',
  textTransform: 'uppercase',
  color: 'var(--tipo-cor)',
  border: '1px solid var(--tipo-cor)',
  borderRadius: '5px',
  padding: '3px 8px',
  flexShrink: 0,
})

export const detalhe = style({
  fontSize: '12.5px',
  color: lk.cor.cinzaNevoa,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
})

export const paginacao = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: lk.espaco.x1,
})

export const botaoPaginacao = style({
  height: '32px',
  padding: '0 13px',
  background: 'transparent',
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: '7px',
  color: lk.cor.brancoSinal,
  fontSize: '12.5px',
  cursor: 'pointer',
  selectors: {
    '&:disabled': { opacity: 0.4, cursor: 'default' },
  },
})

export const paginaAtual = style({
  fontFamily: lk.fonte.mono,
  fontSize: '12px',
  color: lk.cor.cinzaNevoa,
})

// ── estados de tela ──────────────────────────────────────────────────────────
// Mesmo padrão de `VisaoGeral.css.ts` / `estudio/Classes.css.ts`.

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
  fontSize: '13.5px',
  fontWeight: 700,
  cursor: 'pointer',
})
