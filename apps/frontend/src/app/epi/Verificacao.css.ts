/**
 * EPI Verificação — medidas do desenho (`EPI Verificação.dc.html`), via token.
 *
 * A medida que manda aqui: **veredito ≥56px**, não 48. É o único lugar do
 * produto onde o README sobe o piso do botão — a pessoa decide dezenas de vezes
 * seguidas, no teclado ou no mouse, e alvo pequeno em decisão repetida vira
 * erro de clique que carimba veredito errado em dado de treino.
 *
 * Transparência sai de `color-mix` sobre o token, nunca de `rgba()` escrito à
 * mão: um `rgba(10,10,15,.75)` é o preto do desenho copiado de novo, livre para
 * divergir do tema do tenant no primeiro white-label (mesma decisão de
 * `PaletaComandos.css.ts`).
 */
import { globalStyle, style } from '@vanilla-extract/css'

import { lk, OVERLINE_TRACKING } from '../tokens/lk.css'

/** O desenho abre para 1360px — mais largo que o 1280 padrão do shell: a
 *  evidência é o conteúdo, e apertá-la encolhe o que se está julgando. */
export const pagina = style({
  maxWidth: '1360px',
  margin: '0 auto',
  padding: `20px ${lk.espaco.x3}`,
  boxSizing: 'border-box',
  display: 'flex',
  flexDirection: 'column',
  gap: '14px',
  minHeight: '100%',
  fontFamily: lk.fonte.ui,
  color: lk.cor.brancoSinal,
})

export const cabecalho = style({
  display: 'flex',
  alignItems: 'center',
  gap: '14px',
  flexWrap: 'wrap',
})

export const titulo = style({
  margin: 0,
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '26px',
})

/** Âmbar: é o que ainda pesa na fila. Acompanhado da palavra RESTANTES —
 *  cor sozinha não é estado. */
export const restantes = style({
  fontFamily: lk.fonte.mono,
  fontSize: '13px',
  fontWeight: 700,
  color: lk.estado.atencao,
})

export const trilho = style({
  width: '180px',
  height: '8px',
  background: lk.cor.grafite,
  borderRadius: '4px',
  overflow: 'hidden',
})

/** Ciano no progresso: é o único não-interativo que o desenho pinta de ciano,
 *  e é a mesma família do playhead (posição no tempo). Cabe no ≤10%. */
export const trilhoCheio = style({
  height: '100%',
  background: lk.cor.cianoVisao,
  transition: 'width .2s steps(4, end)',
})

export const espacador = style({ flex: 1 })

export const atalhos = style({
  display: 'flex',
  gap: '14px',
  flexWrap: 'wrap',
  fontFamily: lk.fonte.mono,
  fontSize: '11px',
  color: lk.cor.cinzaNevoa,
})

export const tecla = style({
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: '4px',
  padding: '2px 6px',
})

export const palco = style({
  flex: 1,
  display: 'flex',
  gap: '14px',
  minHeight: '420px',
  alignItems: 'stretch',
})

/** Palco da lupa (pan+zoom, contrato B1). `touchAction: none` não é enfeite:
 *  sem ele o navegador rouba a pinça e o zoom fica preso ao mouse. */
export const evidencia = style({
  flex: 1,
  minWidth: 0,
  position: 'relative',
  borderRadius: lk.raio.g,
  overflow: 'hidden',
  border: `1px solid ${lk.cor.borda}`,
  background: lk.cor.grafite,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  touchAction: 'none',
  userSelect: 'none',
})

/** Camada que recebe o zoom: <img> e caixas JUNTAS, senão a marcação
 *  descola dos pixels que ela está marcando. */
export const camadaZoom = style({
  position: 'relative',
  width: '100%',
  height: '100%',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  transformOrigin: 'center',
  transition: 'transform .12s steps(3, end)',
})

export const quadro = style({
  position: 'relative',
  display: 'block',
  maxWidth: '100%',
  maxHeight: '100%',
})

export const imagem = style({
  display: 'block',
  maxWidth: '100%',
  maxHeight: '100%',
  objectFit: 'contain',
})

export const caixa = style({
  position: 'absolute',
  border: `2.5px solid ${lk.estado.nc}`,
  borderRadius: '4px',
  // A caixa é marcação, não alvo: clique nela é clique na evidência.
  pointerEvents: 'none',
})

export const caixaRotulo = style({
  position: 'absolute',
  top: '-24px',
  left: '-2px',
  background: lk.estado.nc,
  color: lk.cor.preto,
  fontFamily: lk.fonte.mono,
  fontSize: '10.5px',
  fontWeight: 700,
  padding: '3px 8px',
  borderRadius: '3px',
  whiteSpace: 'nowrap',
})

export const selo = style({
  position: 'absolute',
  top: '10px',
  left: '10px',
  background: `color-mix(in srgb, ${lk.cor.preto} 75%, transparent)`,
  borderRadius: '5px',
  padding: '4px 9px',
  fontFamily: lk.fonte.mono,
  fontSize: '11px',
  letterSpacing: '0.1em',
})

export const zoomBarra = style({
  position: 'absolute',
  bottom: '10px',
  right: '10px',
  display: 'flex',
  gap: '6px',
})

export const zoomBotao = style({
  width: '34px',
  height: '34px',
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: '7px',
  background: `color-mix(in srgb, ${lk.cor.preto} 80%, transparent)`,
  color: lk.cor.brancoSinal,
  fontSize: '15px',
  fontFamily: lk.fonte.ui,
  cursor: 'pointer',
  selectors: {
    '&:hover:not(:disabled)': { borderColor: lk.cor.cianoVisao, color: lk.cor.cianoVisao },
    '&:disabled': { opacity: 0.4, cursor: 'default' },
  },
})

export const zoomValor = style({
  height: '34px',
  display: 'flex',
  alignItems: 'center',
  padding: `0 ${lk.espaco.x1}`,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: '7px',
  background: `color-mix(in srgb, ${lk.cor.preto} 80%, transparent)`,
  fontFamily: lk.fonte.mono,
  fontSize: '11.5px',
})

export const painel = style({
  width: '340px',
  flex: 'none',
  display: 'flex',
  flexDirection: 'column',
  gap: '14px',
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.g,
  padding: '18px',
  boxSizing: 'border-box',
})

export const overline = style({
  fontFamily: lk.fonte.mono,
  fontSize: '10px',
  letterSpacing: OVERLINE_TRACKING,
  textTransform: 'uppercase',
  color: lk.cor.cinzaNevoa,
})

export const classeLinha = style({
  display: 'flex',
  alignItems: 'center',
  gap: lk.espaco.x1,
  color: lk.estado.nc,
})

export const classeNome = style({
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '19px',
  color: lk.cor.brancoSinal,
})

export const ficha = style({
  display: 'grid',
  gridTemplateColumns: 'auto 1fr',
  gap: `6px ${lk.espaco.x2}`,
  fontSize: '12.5px',
})

export const fichaRotulo = style({ color: lk.cor.cinzaNevoa })
export const fichaDado = style({ fontFamily: lk.fonte.mono, wordBreak: 'break-word' })

/**
 * Rajada (ux2/dedup) — este item é UM entre N detecções da mesma câmera+
 * classe em <60s (a mesma cena redetectada, não N situações). Informativo:
 * a fila NÃO filtra nem propaga veredito entre irmãos (decisão pendente,
 * ver docblock do módulo `verification_service.py`) — só avisa quem está
 * olhando, e deixa expandir pra ver os horários das outras detecções.
 */
export const rajadaAviso = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '4px',
  fontSize: '11.5px',
  color: lk.cor.cinzaNevoa,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.s,
  padding: `6px ${lk.espaco.x1}`,
})

globalStyle(`${rajadaAviso} summary`, {
  cursor: 'pointer',
  fontFamily: lk.fonte.mono,
  color: lk.cor.cianoVisao,
})

export const rajadaListaHorarios = style({
  margin: '4px 0 0',
  paddingLeft: lk.espaco.x2,
  fontFamily: lk.fonte.mono,
  fontSize: '11px',
})

export const recorte = style({
  position: 'relative',
  aspectRatio: '16 / 10',
  borderRadius: lk.raio.s,
  overflow: 'hidden',
  border: `1px solid ${lk.cor.borda}`,
  background: lk.cor.preto,
  backgroundRepeat: 'no-repeat',
})

export const recorteRotulo = style({
  position: 'absolute',
  bottom: '5px',
  left: '8px',
  fontFamily: lk.fonte.mono,
  fontSize: '9.5px',
  color: lk.cor.cinzaNevoa,
  textShadow: `0 1px 3px ${lk.cor.preto}`,
})

export const veredito = style({
  display: 'flex',
  flexDirection: 'column',
  gap: lk.espaco.x1,
  marginTop: 'auto',
})

/** Motivo estruturado do veredito (contrato B2) — select nativo, sem
 *  componente próprio: é escolha fechada de poucas opções, o caso exato que
 *  `<select>` resolve sem biblioteca. */
export const motivoLinha = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '4px',
})

export const motivoRotulo = style({
  fontSize: '11px',
  color: lk.cor.cinzaNevoa,
})

export const motivoSelect = style({
  height: '38px',
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.s,
  background: lk.cor.grafite,
  color: lk.cor.brancoSinal,
  fontFamily: lk.fonte.ui,
  fontSize: '12.5px',
  padding: `0 ${lk.espaco.x1}`,
  selectors: {
    '&:disabled': { opacity: 0.5, cursor: 'not-allowed' },
  },
})

export const motivoSelectErro = style({
  borderColor: lk.estado.nc,
})

export const motivoErro = style({
  fontSize: '11px',
  color: lk.estado.nc,
})

/** ≥56px — o piso que o README sobe SÓ nesta tela. */
const botaoVeredito = {
  height: lk.medida.vereditoVerificacao,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '9px',
  borderRadius: lk.raio.m,
  fontFamily: lk.fonte.ui,
  fontSize: '15px',
  fontWeight: 700,
  cursor: 'pointer',
} as const

export const confirmar = style({
  ...botaoVeredito,
  border: 'none',
  background: lk.estado.ok,
  color: lk.cor.preto,
  selectors: {
    '&:disabled': { opacity: 0.45, cursor: 'not-allowed' },
  },
})

export const rejeitar = style({
  ...botaoVeredito,
  background: 'transparent',
  border: `1.5px solid color-mix(in srgb, ${lk.estado.nc} 55%, transparent)`,
  color: lk.estado.nc,
  selectors: {
    '&:hover:not(:disabled)': {
      background: `color-mix(in srgb, ${lk.estado.nc} 8%, transparent)`,
    },
    '&:disabled': { opacity: 0.45, cursor: 'not-allowed' },
  },
})

export const anotar = style({
  height: '40px',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '9px',
  background: 'transparent',
  border: `1px dashed ${lk.cor.borda}`,
  borderRadius: '9px',
  color: lk.cor.cinzaNevoa,
  fontFamily: lk.fonte.ui,
  fontSize: '13px',
  fontWeight: 600,
  selectors: {
    '&:disabled': { cursor: 'not-allowed', opacity: 0.7 },
  },
})

export const teclaBotao = style({
  fontFamily: lk.fonte.mono,
  fontSize: '11px',
  opacity: 0.7,
})

export const nota = style({
  fontSize: '11.5px',
  color: lk.cor.cinzaNevoa,
  textAlign: 'center',
  lineHeight: 1.5,
})

// ── correção de caixa (contrato B1 — mesma matemática de EventoDetalhe.css.ts) ─

/** "ONDE A IA MARCOU" — tracejada, cinza. Só a leitura do que o modelo gravou. */
export const caixaIA = style({
  position: 'absolute',
  pointerEvents: 'none',
  borderStyle: 'dashed',
  borderColor: lk.cor.cinzaNevoa,
  borderRadius: '2px',
})

export const rotuloCaixaIA = style({
  position: 'absolute',
  bottom: '100%',
  left: 0,
  marginBottom: '4px',
  transformOrigin: '0 100%',
  fontFamily: lk.fonte.mono,
  fontSize: '10px',
  color: lk.cor.cinzaNevoa,
  whiteSpace: 'nowrap',
})

/** "SUA CORREÇÃO" — sólida, ciano. Única caixa desta tela que É alvo de
 *  clique: arrastar move, alças redimensionam. Vinheta escurece tudo FORA
 *  dela, recortada pelo `overflow:hidden` do palco. */
export const caixaCorrecao = style({
  position: 'absolute',
  cursor: 'move',
  borderStyle: 'solid',
  borderColor: lk.cor.cianoVisao,
  borderRadius: '2px',
  boxShadow: `0 0 0 9999px color-mix(in srgb, ${lk.cor.preto} 45%, transparent)`,
})

export const rotuloCaixaCorrecao = style({
  position: 'absolute',
  bottom: '100%',
  left: 0,
  marginBottom: '4px',
  pointerEvents: 'none',
  fontFamily: lk.fonte.mono,
  fontSize: '10px',
  fontWeight: 700,
  color: lk.cor.cianoVisao,
  whiteSpace: 'nowrap',
})

/** Alça de resize — tamanho e posição vêm inline (contra-escala do zoom + 8 cantos). */
export const alca = style({
  position: 'absolute',
  background: lk.cor.cianoVisao,
  borderRadius: '2px',
})

export const dicaCorrecao = style({
  margin: 0,
  position: 'absolute',
  bottom: '10px',
  left: '10px',
  display: 'flex',
  alignItems: 'center',
  gap: '10px',
  background: `color-mix(in srgb, ${lk.cor.preto} 75%, transparent)`,
  padding: '4px 9px',
  borderRadius: '5px',
  fontFamily: lk.fonte.mono,
  fontSize: '10px',
  letterSpacing: '0.1em',
  color: lk.cor.cinzaNevoa,
})

export const botaoCorrigir = style({
  height: '30px',
  padding: '0 11px',
  display: 'inline-flex',
  alignItems: 'center',
  gap: '6px',
  alignSelf: 'flex-start',
  background: 'transparent',
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.s,
  color: lk.cor.cinzaNevoa,
  fontFamily: lk.fonte.mono,
  fontSize: '10.5px',
  letterSpacing: '0.06em',
  textTransform: 'uppercase',
  cursor: 'pointer',
  selectors: {
    '&:hover:not(:disabled)': { borderColor: lk.cor.cianoVisao, color: lk.cor.cianoVisao },
  },
})

/** Autoria da correção (ADR-0066: "a caixa diz quem a desenhou") — NOME,
 *  nunca UUID cru. */
export const badgeAutoria = style({
  display: 'flex',
  gap: lk.espaco.x1,
  padding: '10px',
  borderRadius: lk.raio.s,
  background: lk.cor.preto,
  border: `1px solid ${lk.cor.borda}`,
})

export const badgeAutoriaTexto = style({
  margin: 0,
  fontSize: '11.5px',
  lineHeight: 1.5,
  color: lk.cor.cinzaNevoa,
})

export const gradeCoordenadas = style({
  display: 'grid',
  gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
  gap: lk.espaco.x1,
})

export const campoCoordenada = style({ display: 'flex', flexDirection: 'column', gap: '5px' })

export const rotuloCoordenada = style({
  fontFamily: lk.fonte.mono,
  fontSize: '10px',
  letterSpacing: OVERLINE_TRACKING,
  color: lk.cor.cinzaNevoa,
})

export const inputCoordenada = style({
  height: '40px',
  width: '100%',
  boxSizing: 'border-box',
  padding: '0 11px',
  borderRadius: lk.raio.s,
  border: `1px solid ${lk.cor.borda}`,
  background: lk.cor.preto,
  color: lk.cor.brancoSinal,
  fontFamily: lk.fonte.mono,
  fontSize: '14px',
  outline: 'none',
  selectors: {
    '&:focus': { borderColor: lk.cor.cianoVisao },
    '&:disabled': { color: lk.cor.cinzaNevoa },
  },
})

/** Mesma forma de `confirmar`/`rejeitar` (56px, piso desta tela) — cor muda:
 *  "Salvar caixa" é ação, não confirmação/descarte de veredito. */
export const botaoSalvarCaixa = style({
  ...botaoVeredito,
  border: 'none',
  background: lk.cor.cianoVisao,
  color: lk.cor.preto,
  selectors: { '&:disabled': { opacity: 0.5, cursor: 'not-allowed' } },
})

export const botaoCancelarCaixa = style({
  ...botaoVeredito,
  background: 'transparent',
  border: `1px solid ${lk.cor.borda}`,
  color: lk.cor.brancoSinal,
  selectors: { '&:disabled': { opacity: 0.5, cursor: 'not-allowed' } },
})

export const navegacao = style({
  display: 'flex',
  gap: lk.espaco.x1,
  alignItems: 'center',
})

export const navBotao = style({
  height: '32px',
  padding: `0 ${lk.espaco.x1}`,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.s,
  background: 'transparent',
  color: lk.cor.cinzaNevoa,
  fontFamily: lk.fonte.ui,
  fontSize: '12px',
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
  gap: '6px',
  selectors: {
    '&:hover:not(:disabled)': { borderColor: lk.cor.cianoVisao, color: lk.cor.cianoVisao },
    '&:disabled': { opacity: 0.4, cursor: 'default' },
  },
})

/** Carimbo do que JÁ foi decidido — o operador volta com ← e vê o que fez.
 *  Estado = cor + ícone + palavra: os três, sempre. */
export const decidido = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '6px',
  fontFamily: lk.fonte.mono,
  fontSize: '11px',
  letterSpacing: OVERLINE_TRACKING,
  textTransform: 'uppercase',
})

export const decididoOk = style({ color: lk.estado.ok })
export const decididoNc = style({ color: lk.estado.nc })

// ── Estados de rota: vazio · erro · sem permissão ───────────────────────────

export const centro = style({
  minHeight: '420px',
  height: '100%',
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '14px',
  textAlign: 'center',
  padding: lk.espaco.x3,
  boxSizing: 'border-box',
  fontFamily: lk.fonte.ui,
  color: lk.cor.brancoSinal,
})

export const centroTitulo = style({
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '19px',
})

export const centroTexto = style({
  fontSize: '13.5px',
  color: lk.cor.cinzaNevoa,
  maxWidth: '380px',
  lineHeight: 1.55,
})

export const centroTecnico = style({
  fontFamily: lk.fonte.mono,
  fontSize: '12px',
  color: lk.cor.cinzaNevoa,
})

export const acaoPrimaria = style({
  display: 'flex',
  alignItems: 'center',
  height: '40px',
  padding: `0 18px`,
  border: 'none',
  borderRadius: lk.raio.s,
  background: lk.cor.cianoVisao,
  color: lk.cor.preto,
  fontFamily: lk.fonte.ui,
  fontSize: '13.5px',
  fontWeight: 700,
  textDecoration: 'none',
  cursor: 'pointer',
  ':hover': { background: lk.cor.cianoProfundo },
})

/** Ícone de estado: cor + ícone + palavra — os três, sempre. */
export const iconeNc = style({ color: lk.estado.nc })
export const iconeOk = style({ color: lk.estado.ok })

export const semImagem = style({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  gap: lk.espaco.x1,
  fontSize: '13px',
  color: lk.cor.cinzaNevoa,
  fontFamily: lk.fonte.ui,
})
