import { style } from '@vanilla-extract/css'

import { lk, OVERLINE_TRACKING } from '../tokens/lk.css'

/** Zero hex solto: `tokens/semHexSolto.test.ts` varre `src/app/**` inteiro.
 * Tinta translúcida sobre token de superfície usa `color-mix`, não `rgba()`
 * — `rgba()` não aceita variável e devolveria o hex fixo do desenho,
 * quebrando o white-label (convenção de `epi/Eventos.css.ts`). */
const TINTA_ATENCAO = `color-mix(in srgb, ${lk.estado.atencao} 10%, transparent)`
const BORDA_ATENCAO = `color-mix(in srgb, ${lk.estado.atencao} 45%, transparent)`
const DIVISOR = `color-mix(in srgb, ${lk.cor.cinzaNevoa} 12%, transparent)`

export const raiz = style({
  display: 'flex',
  flexDirection: 'column',
  gap: lk.espaco.x2,
  maxWidth: lk.medida.conteudoMax,
  width: '100%',
})

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
  fontSize: '22px',
})

export const subtitulo = style({
  fontSize: '12.5px',
  color: lk.cor.cinzaNevoa,
})

export const espacador = style({ flex: 1 })

// ── aviso de desbalanceamento ────────────────────────────────────────────────

export const aviso = style({
  display: 'flex',
  gap: '10px',
  alignItems: 'flex-start',
  padding: '14px 16px',
  background: TINTA_ATENCAO,
  border: `1px solid ${BORDA_ATENCAO}`,
  borderRadius: lk.raio.m,
})

export const avisoIcone = style({ flexShrink: 0, marginTop: '1px' })

export const avisoCorpo = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '4px',
  fontSize: '13px',
  lineHeight: 1.5,
})

export const avisoTitulo = style({ fontWeight: 700, color: lk.estado.atencao })

// ── lista de classes do tenant ───────────────────────────────────────────────

export const secaoTitulo = style({
  margin: 0,
  fontFamily: lk.fonte.mono,
  fontSize: '11px',
  letterSpacing: OVERLINE_TRACKING,
  textTransform: 'uppercase',
  color: lk.cor.cinzaNevoa,
  fontWeight: 600,
})

export const secaoLegenda = style({
  fontSize: '12px',
  color: lk.cor.cinzaNevoa,
  margin: '2px 0 8px',
})

export const lista = style({
  display: 'flex',
  flexDirection: 'column',
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.m,
  overflow: 'hidden',
})

export const linha = style({
  display: 'flex',
  alignItems: 'center',
  gap: '12px',
  padding: '10px 14px',
  borderBottom: `1px solid ${DIVISOR}`,
  selectors: { '&:last-child': { borderBottom: 'none' } },
})

export const linhaArquivada = style({ opacity: 0.65 })

export const arrasto = style({
  display: 'flex',
  color: lk.cor.cinzaNevoa,
  cursor: 'grab',
  flexShrink: 0,
})

export const tecla = style({
  minWidth: '24px',
  height: '24px',
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  fontFamily: lk.fonte.mono,
  fontSize: '11px',
  fontWeight: 700,
  color: lk.cor.cinzaNevoa,
  background: lk.cor.preto,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: '6px',
  flexShrink: 0,
})

export const corInput = style({
  width: '24px',
  height: '22px',
  padding: 0,
  border: 'none',
  background: 'none',
  cursor: 'pointer',
  flexShrink: 0,
})

export const corSwatch = style({
  width: '14px',
  height: '14px',
  borderRadius: '4px',
  flexShrink: 0,
})

export const nomeBotao = style({
  flex: 1,
  minWidth: 0,
  display: 'flex',
  alignItems: 'center',
  gap: '6px',
  background: 'none',
  border: 'none',
  cursor: 'text',
  textAlign: 'left',
  fontFamily: lk.fonte.ui,
  fontSize: '14px',
  fontWeight: 600,
  color: lk.cor.brancoSinal,
  padding: 0,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
})

export const nomeTexto = style({
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
})

export const nomeIcone = style({ opacity: 0.4, flexShrink: 0 })

export const nomeInput = style({
  flex: 1,
  minWidth: 0,
  height: '30px',
  padding: '0 8px',
  fontSize: '13px',
  color: lk.cor.brancoSinal,
  background: lk.cor.preto,
  border: `1px solid ${lk.cor.cianoVisao}`,
  borderRadius: '6px',
  outline: 'none',
})

export const nomeCatalogo = style({
  flex: 1,
  minWidth: 0,
  fontSize: '14px',
  color: lk.cor.brancoSinal,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
})

export const inativaTag = style({
  marginLeft: '8px',
  fontSize: '11px',
  color: lk.cor.cinzaNevoa,
})

export const barraWrap = style({
  flex: 1,
  minWidth: '60px',
  height: '10px',
  background: lk.cor.preto,
  borderRadius: '4px',
  overflow: 'hidden',
  flexShrink: 1,
})

export const barraPreenchida = style({ height: '100%' })

export const contagem = style({
  fontFamily: lk.fonte.mono,
  fontSize: '12px',
  width: '76px',
  textAlign: 'right',
  color: lk.cor.cinzaNevoa,
  flexShrink: 0,
})

export const contagemBaixa = style({ color: lk.estado.atencao })

export const acoes = style({ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 })

const botaoBase = style({
  display: 'inline-flex',
  alignItems: 'center',
  gap: '4px',
  height: '28px',
  padding: '0 9px',
  fontFamily: lk.fonte.ui,
  fontSize: '12px',
  fontWeight: 600,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: '6px',
  background: 'transparent',
  color: lk.cor.cinzaNevoa,
  cursor: 'pointer',
  selectors: { '&:hover': { color: lk.cor.brancoSinal, borderColor: lk.cor.bordaForte } },
})

export const botaoIcone = style([botaoBase, { padding: 0, width: '28px', justifyContent: 'center' }])

export const botaoArquivar = botaoBase

export const botaoRestaurar = style([botaoBase, { color: lk.estado.ok }])

export const botaoExcluir = style([botaoBase, { color: lk.estado.nc }])

// ── criar classe ─────────────────────────────────────────────────────────────

export const criarForm = style({
  display: 'flex',
  gap: '8px',
  alignItems: 'center',
  padding: '12px 14px',
})

export const criarInput = style({
  flex: 1,
  height: '36px',
  padding: '0 12px',
  fontSize: '13px',
  color: lk.cor.brancoSinal,
  background: lk.cor.preto,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.s,
  outline: 'none',
  selectors: { '&:focus': { borderColor: lk.cor.cianoVisao } },
})

export const criarCor = style({
  width: '32px',
  height: '32px',
  padding: 0,
  border: 'none',
  background: 'none',
  cursor: 'pointer',
  flexShrink: 0,
})

export const criarBotao = style({
  height: '36px',
  padding: '0 16px',
  border: 'none',
  borderRadius: lk.raio.s,
  background: lk.cor.cianoVisao,
  color: lk.cor.preto,
  fontFamily: lk.fonte.ui,
  fontSize: '13px',
  fontWeight: 700,
  cursor: 'pointer',
  flexShrink: 0,
  selectors: { '&:disabled': { opacity: 0.5, cursor: 'not-allowed' } },
})

// ── arquivadas / catálogo ────────────────────────────────────────────────────

export const toggleSecao = style({
  display: 'flex',
  alignItems: 'center',
  gap: '6px',
  fontFamily: lk.fonte.ui,
  fontSize: '13px',
  fontWeight: 700,
  color: lk.cor.cinzaNevoa,
  background: 'none',
  border: 'none',
  cursor: 'pointer',
  padding: 0,
})

export const rodape = style({
  fontSize: '12px',
  color: lk.cor.cinzaNevoa,
  lineHeight: 1.55,
})

// ── estados de rota ──────────────────────────────────────────────────────────

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

export const vazioAcao = style({
  display: 'flex',
  gap: '8px',
  alignItems: 'center',
  marginTop: '6px',
})
