/**
 * Revisão Qualidade — medidas do desenho (`Revisão Qualidade.dc.html`, R1+R2).
 *
 * Transparência sai de `color-mix` sobre o token, nunca de `rgba()` escrito à
 * mão: um `rgba(255,92,71,.12)` é o vermelho do desenho copiado de novo, livre
 * para divergir do tema no primeiro white-label (mesma decisão de
 * `Verificacao.css.ts` e `AoVivo.css.ts`).
 *
 * A medida que manda aqui: **veredito 56px**. O desenho pinta os dois botões de
 * decisão com 56px de altura, e é o mesmo piso que a Verificação usa — a pessoa
 * decide dezenas de vezes seguidas e alvo pequeno em decisão repetida vira
 * clique errado carimbado em dado de treino.
 */
import { style } from '@vanilla-extract/css'

import { lk, OVERLINE_TRACKING } from '../tokens/lk.css'

const veu = (cor: string, pct: number) => `color-mix(in srgb, ${cor} ${pct}%, transparent)`

export const raiz = style({
  display: 'flex',
  flexDirection: 'column',
  gap: lk.espaco.x2,
  fontFamily: lk.fonte.ui,
  color: lk.cor.brancoSinal,
})

/** R1 abre em 1080px; R2 em 1240px (o desenho alarga para caber os 3 painéis). */
export const larguraFila = style({ maxWidth: '1080px', width: '100%', margin: '0 auto' })
export const larguraDetalhe = style({ maxWidth: '1240px', width: '100%', margin: '0 auto' })

export const cabecalho = style({
  display: 'flex',
  alignItems: 'baseline',
  gap: lk.espaco.x2,
  flexWrap: 'wrap',
})

export const titulo = style({
  margin: 0,
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '26px',
})

export const contagem = style({
  fontFamily: lk.fonte.mono,
  fontSize: '15px',
  color: lk.cor.cinzaNevoa,
})

export const espacador = style({ flex: 1 })

const pilula = style({
  display: 'inline-flex',
  alignItems: 'center',
  gap: '6px',
  fontSize: '13px',
  fontWeight: 600,
  padding: '3px 10px',
  borderRadius: '99px',
})

export const pilulaNc = style([pilula, { color: lk.estado.nc, background: veu(lk.estado.nc, 12) }])
export const pilulaOk = style([pilula, { color: lk.estado.ok, background: veu(lk.estado.ok, 12) }])

export const nota = style({
  fontSize: '12px',
  color: lk.cor.cinzaNevoa,
  lineHeight: 1.5,
})

export const notaMono = style([nota, { fontFamily: lk.fonte.mono }])

export const filtros = style({ display: 'flex', gap: '10px', flexWrap: 'wrap' })

export const seletor = style({
  height: '36px',
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: '6px',
  color: lk.cor.brancoSinal,
  fontFamily: lk.fonte.ui,
  fontSize: '13px',
  padding: `0 ${lk.espaco.x1}`,
  ':disabled': { opacity: 0.45, cursor: 'not-allowed' },
})

export const lista = style({ display: 'flex', flexDirection: 'column', gap: lk.espaco.x1 })

export const item = style({
  display: 'flex',
  alignItems: 'center',
  gap: lk.espaco.x2,
  padding: `12px ${lk.espaco.x2}`,
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.m,
  cursor: 'pointer',
  textAlign: 'left',
  width: '100%',
  color: 'inherit',
  fontFamily: 'inherit',
  ':hover': { borderColor: lk.cor.cianoVisao },
  ':focus-visible': { outline: `2px solid ${lk.cor.cianoVisao}`, outlineOffset: '2px' },
})

/** O quadro da miniatura fica — vazio e explicado. Ver o cabeçalho do .tsx:
 *  uma URL assinada por linha queima o teto de 60/h em poucos refreshes. */
export const miniatura = style({
  width: '96px',
  height: '64px',
  flex: 'none',
  background: lk.cor.preto,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: '6px',
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '4px',
  fontFamily: lk.fonte.mono,
  fontSize: '9px',
  color: lk.cor.cinzaNevoa,
})

export const corpoItem = style({
  flex: 1,
  minWidth: 0,
  display: 'flex',
  flexDirection: 'column',
  gap: '4px',
})

export const linhaTopo = style({ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' })

const chip = style({
  display: 'inline-flex',
  alignItems: 'center',
  gap: '5px',
  fontSize: '12px',
  fontWeight: 700,
  letterSpacing: '.05em',
  padding: '2px 9px',
  borderRadius: '4px',
  whiteSpace: 'nowrap',
})

export const chipNc = style([chip, { color: lk.estado.nc, background: veu(lk.estado.nc, 12) }])
export const chipOk = style([chip, { color: lk.estado.ok, background: veu(lk.estado.ok, 12) }])

export const classe = style({ fontSize: '15px', fontWeight: 600 })

export const meta = style({ fontSize: '13px', color: lk.cor.cinzaNevoa })

export const dado = style({ fontFamily: lk.fonte.mono })

export const idade = style({
  fontFamily: lk.fonte.mono,
  fontSize: '14px',
  color: lk.cor.cinzaNevoa,
  flex: 'none',
})

export const idadeVelha = style([idade, { color: lk.estado.atencao }])

export const seta = style({ color: lk.cor.cinzaNevoa, flex: 'none' })

// ── R2 · detalhe ────────────────────────────────────────────────────────────

export const cabecalhoDetalhe = style({
  display: 'flex',
  alignItems: 'center',
  gap: '14px',
  flexWrap: 'wrap',
})

export const voltar = style({
  height: '36px',
  padding: `0 14px`,
  background: 'transparent',
  border: `1px solid ${lk.cor.bordaForte}`,
  borderRadius: '6px',
  color: lk.cor.cinzaNevoa,
  fontFamily: lk.fonte.ui,
  fontSize: '13px',
  cursor: 'pointer',
  ':hover': { color: lk.cor.cianoVisao, borderColor: lk.cor.cianoVisao },
})

export const tituloDetalhe = style({
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '20px',
})

export const painesDetalhe = style({
  display: 'flex',
  gap: lk.espaco.x2,
  alignItems: 'stretch',
  flexWrap: 'wrap',
})

export const coluna = style({
  flex: '1.15 1 320px',
  minWidth: 0,
  display: 'flex',
  flexDirection: 'column',
  gap: '6px',
})

export const colunaLateral = style({
  width: '280px',
  flex: 'none',
  display: 'flex',
  flexDirection: 'column',
  gap: '6px',
  '@media': { 'screen and (max-width: 900px)': { width: '100%' } },
})

export const overline = style({
  fontFamily: lk.fonte.mono,
  fontSize: '12px',
  letterSpacing: OVERLINE_TRACKING,
  color: lk.cor.cinzaNevoa,
  textTransform: 'uppercase',
})

export const overlineNc = style([overline, { color: lk.estado.nc }])

export const palco = style({
  position: 'relative',
  height: '340px',
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.m,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  overflow: 'hidden',
})

/** Moldura vermelha do desenho: só quando a IA apontou NOK. */
export const palcoNc = style({ borderWidth: '2px', borderColor: lk.estado.nc })

export const imagem = style({ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' })

export const semImagem = style({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  gap: lk.espaco.x1,
  padding: lk.espaco.x3,
  textAlign: 'center',
  fontSize: '13px',
  color: lk.cor.cinzaNevoa,
  lineHeight: 1.5,
})

export const legendaPalco = style({
  position: 'absolute',
  right: '10px',
  bottom: '8px',
  fontFamily: lk.fonte.mono,
  fontSize: '11px',
  color: lk.cor.cinzaNevoa,
  background: `color-mix(in srgb, ${lk.cor.preto} 75%, transparent)`,
  padding: '2px 8px',
  borderRadius: '4px',
})

export const cartaoLateral = style({
  flex: 1,
  background: lk.cor.grafite,
  borderRadius: lk.raio.m,
  padding: '14px',
  display: 'flex',
  flexDirection: 'column',
  gap: '10px',
  minHeight: '160px',
})

export const rodapeLateral = style({
  marginTop: 'auto',
  paddingTop: '10px',
  borderTop: `1px solid ${lk.cor.borda}`,
  fontSize: '12px',
  color: lk.cor.cinzaNevoa,
  lineHeight: 1.5,
})

/** Faixa de classes do desenho — presente e desabilitada. Ver o .tsx. */
export const faixaClasses = style({
  display: 'flex',
  alignItems: 'center',
  gap: lk.espaco.x1,
  padding: `12px ${lk.espaco.x2}`,
  background: lk.cor.grafite,
  border: `1px solid ${veu(lk.estado.nc, 40)}`,
  borderRadius: lk.raio.m,
  flexWrap: 'wrap',
})

export const chipClasse = style({
  height: '38px',
  padding: `0 14px`,
  background: 'transparent',
  border: `1px solid ${veu(lk.estado.nc, 50)}`,
  borderRadius: '99px',
  color: lk.cor.brancoSinal,
  fontFamily: lk.fonte.ui,
  fontSize: '14px',
  ':disabled': { opacity: 0.45, cursor: 'not-allowed' },
})

export const barraDecisao = style({
  display: 'flex',
  alignItems: 'center',
  gap: '12px',
  padding: `14px 0 4px`,
  borderTop: `1px solid ${lk.cor.borda}`,
  flexWrap: 'wrap',
})

const veredito = style({
  height: lk.medida.vereditoVerificacao,
  border: 'none',
  borderRadius: lk.raio.s,
  color: lk.cor.preto,
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '17px',
  letterSpacing: '.03em',
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: lk.espaco.x1,
  flex: '1 1 220px',
  ':disabled': { opacity: 0.45, cursor: 'not-allowed' },
})

export const conforme = style([veredito, { background: lk.estado.ok }])
export const naoConforme = style([veredito, { background: lk.estado.nc }])

export const acaoNeutra = style({
  height: lk.medida.vereditoVerificacao,
  flex: 'none',
  padding: `0 26px`,
  background: 'transparent',
  border: `1px solid ${lk.cor.bordaForte}`,
  borderRadius: lk.raio.s,
  color: lk.cor.brancoSinal,
  fontFamily: lk.fonte.ui,
  fontSize: '15px',
  fontWeight: 600,
  cursor: 'pointer',
  ':disabled': { opacity: 0.45, cursor: 'not-allowed' },
})

export const tecla = style({
  fontFamily: lk.fonte.mono,
  fontSize: '12px',
  opacity: 0.6,
})

// ── estados de tela ─────────────────────────────────────────────────────────

export const centro = style({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '12px',
  padding: '56px',
  textAlign: 'center',
  background: lk.cor.grafite,
  borderRadius: lk.raio.m,
  color: lk.cor.cinzaNevoa,
})

export const centroTitulo = style({
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '18px',
  color: lk.cor.brancoSinal,
})

export const centroTexto = style({ fontSize: '14px', maxWidth: '48ch', lineHeight: 1.6 })

export const centroTecnico = style({
  fontFamily: lk.fonte.mono,
  fontSize: '12px',
  color: lk.cor.cinzaNevoa,
  wordBreak: 'break-word',
})

export const botaoPrimario = style({
  height: '38px',
  padding: `0 ${lk.espaco.x2}`,
  border: 'none',
  borderRadius: lk.raio.s,
  background: lk.cor.cianoVisao,
  color: lk.cor.preto,
  fontFamily: lk.fonte.ui,
  fontSize: '13px',
  fontWeight: 700,
  cursor: 'pointer',
})
