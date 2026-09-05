import { style } from '@vanilla-extract/css'

import { lk } from '../tokens/lk.css'

/** Zero hex solto (`tokens/semHexSolto.test.ts` varre `src/app/**`). Tinta
 * translúcida sobre token usa `color-mix`, nunca `rgba()` — `rgba()` não
 * aceita variável e devolveria o hex fixo, quebrando o white-label. */
const TINTA_MARCA = `color-mix(in srgb, ${lk.cor.cianoVisao} 12%, transparent)`
const TINTA_ATENCAO = `color-mix(in srgb, ${lk.estado.atencao} 10%, transparent)`
const BORDA_ATENCAO = `color-mix(in srgb, ${lk.estado.atencao} 45%, transparent)`

export const raiz = style({
  display: 'flex',
  flexDirection: 'column',
  gap: lk.espaco.x2,
  maxWidth: lk.medida.conteudoMax,
  width: '100%',
})

export const cabecalho = style({ display: 'flex', flexDirection: 'column', gap: '4px' })

export const titulo = style({
  margin: 0,
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '20px',
})

export const subtitulo = style({ margin: 0, fontSize: '12.5px', color: lk.cor.cinzaNevoa })

// ── avisos ───────────────────────────────────────────────────────────────────

/** O que a tela ainda NÃO faz. Discreto de propósito: é ressalva, não alarme —
 * pintar de âmbar faria parecer que algo quebrou. */
export const avisoEfeito = style({
  margin: 0,
  padding: '10px 12px',
  fontSize: '12.5px',
  lineHeight: 1.5,
  color: lk.cor.cinzaNevoa,
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.m,
})

/** Aqui sim: a pessoa não consegue fazer o que veio fazer. */
export const avisoBloqueio = style({
  margin: 0,
  padding: '10px 12px',
  fontSize: '12.5px',
  lineHeight: 1.5,
  color: lk.estado.atencao,
  background: TINTA_ATENCAO,
  border: `1px solid ${BORDA_ATENCAO}`,
  borderRadius: lk.raio.m,
})

// ── pendência: as câmeras sem uso definido ───────────────────────────────────

export const pendencia = style({
  display: 'flex',
  alignItems: 'center',
  gap: '10px',
  flexWrap: 'wrap',
  padding: '12px 14px',
  background: TINTA_MARCA,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.m,
})

export const pendenciaTexto = style({ flex: 1, fontSize: '13px' })

export const filtros = style({ display: 'flex', gap: lk.espaco.x1, flexWrap: 'wrap' })

// ── ação em massa ────────────────────────────────────────────────────────────

export const massa = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '10px',
  padding: '14px 16px',
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.bordaForte}`,
  borderRadius: lk.raio.m,
})

export const massaTitulo = style({ fontSize: '13px' })
export const massaChips = style({ display: 'flex', gap: '6px', flexWrap: 'wrap' })
export const massaAcoes = style({ display: 'flex', gap: lk.espaco.x1, flexWrap: 'wrap' })

// ── botões ───────────────────────────────────────────────────────────────────

const botaoBase = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: '6px',
  height: '32px',
  padding: '0 14px',
  borderRadius: lk.raio.s,
  fontSize: '12.5px',
  fontWeight: 600,
  cursor: 'pointer',
  selectors: { '&:disabled': { opacity: 0.5, cursor: 'default' } },
} as const

export const botaoPrimario = style({
  ...botaoBase,
  border: `1px solid ${lk.cor.cianoVisao}`,
  background: TINTA_MARCA,
  color: lk.cor.cianoVisao,
})

export const botaoSecundario = style({
  ...botaoBase,
  border: `1px solid ${lk.cor.bordaForte}`,
  background: 'transparent',
  color: lk.cor.brancoSinal,
})

/** "Ver todas" dentro de uma frase — botão de verdade (é ação), com cara de
 * link para não competir com os botões da barra de massa. */
export const linkInline = style({
  border: 'none',
  background: 'none',
  padding: 0,
  font: 'inherit',
  color: lk.cor.cianoVisao,
  cursor: 'pointer',
  textDecoration: 'underline',
})

// ── chips de módulo ──────────────────────────────────────────────────────────

export const chip = style({
  display: 'inline-flex',
  alignItems: 'center',
  height: '26px',
  padding: '0 11px',
  borderRadius: '999px',
  border: `1px solid ${lk.cor.bordaForte}`,
  background: 'transparent',
  color: lk.cor.cinzaNevoa,
  fontSize: '12px',
  whiteSpace: 'nowrap',
  cursor: 'pointer',
  selectors: {
    '&:disabled': { opacity: 0.6, cursor: 'default' },
  },
})

export const chipMarcado = style({
  border: `1px solid ${lk.cor.cianoVisao}`,
  background: TINTA_MARCA,
  color: lk.cor.cianoVisao,
  fontWeight: 600,
})

export const chips = style({ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center' })

// ── tabela ───────────────────────────────────────────────────────────────────

export const tabelaWrap = style({
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.m,
  overflowX: 'auto',
})

export const tabela = style({ width: '100%', borderCollapse: 'collapse' })

export const th = style({
  padding: '10px 12px',
  borderBottom: `1px solid ${lk.cor.borda}`,
  textAlign: 'left',
  fontFamily: lk.fonte.mono,
  fontSize: '10.5px',
  letterSpacing: '.14em',
  textTransform: 'uppercase',
  color: lk.cor.cinzaNevoa,
  fontWeight: 600,
})

export const td = style({
  padding: '10px 12px',
  borderBottom: `1px solid ${lk.cor.borda}`,
  verticalAlign: 'top',
  fontSize: '13px',
})

/** A câmera não declarada fica marcada na lista inteira, não só no contador —
 * quem rolar a tabela tem de conseguir achá-la sem voltar ao topo. */
export const linhaPendente = style({
  background: TINTA_ATENCAO,
})

export const nome = style({ display: 'block', color: lk.cor.brancoSinal })

export const local = style({ display: 'block', fontSize: '11.5px', color: lk.cor.cinzaNevoa })

export const arquivada = style({
  display: 'inline-block',
  marginTop: '3px',
  padding: '1px 6px',
  borderRadius: '999px',
  border: `1px solid ${lk.cor.bordaForte}`,
  fontSize: '10.5px',
  color: lk.cor.cinzaNevoa,
})

export const semUso = style({ fontSize: '12px', color: lk.estado.atencao })

// ── estados de carga ─────────────────────────────────────────────────────────

export const centro = style({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  gap: '10px',
  padding: lk.espaco.x5,
  color: lk.cor.cinzaNevoa,
  textAlign: 'center',
})

export const centroTitulo = style({ margin: 0, fontSize: '15px', color: lk.cor.brancoSinal })

export const centroTecnico = style({
  margin: 0,
  fontFamily: lk.fonte.mono,
  fontSize: '11.5px',
})
