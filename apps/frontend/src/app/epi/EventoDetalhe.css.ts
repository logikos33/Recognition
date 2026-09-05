/**
 * Estilos do EPI Evento Detalhe (`EPI Evento Detalhe.dc.html`).
 *
 * Toda cor e toda fonte saem de `lk.css.ts` — o teste `semHexSolto` reprova
 * qualquer hex escrito aqui, e é isso que faz o white-label do tenant alcançar
 * esta tela sem um segundo provider.
 *
 * Onde o CIANO aparece, e só onde: o link "Eventos" do cabeçalho, o CTA do
 * estado vazio e o foco do campo de motivo. Ele não pinta veredito, não pinta
 * caixa e não é fundo de nada — é o que separa "onde eu clico" do que eu leio.
 *
 * ESTADO = cor + ícone + palavra: os três chips de veredito têm os três, e as
 * classes abaixo só carregam a cor. O ícone e a palavra moram no componente,
 * juntos, para não existir a tentação de mandar só a cor.
 */
import { style, styleVariants } from '@vanilla-extract/css'

import { OVERLINE_TRACKING, TELA_ESTREITA, lk } from '../tokens/lk.css'

export const pagina = style({
  // O desenho desta tela pede 1360; o shell fixa 1280 no token. Fica o token —
  // medida solta no componente é a medida que some do contrato. Ver "PARA O
  // DESIGN" no .tsx.
  maxWidth: lk.medida.conteudoMax,
  margin: '0 auto',
  padding: `20px ${lk.medida.padding}`,
  boxSizing: 'border-box',
  display: 'flex',
  flexDirection: 'column',
  gap: '14px',
  fontFamily: lk.fonte.ui,
  color: lk.cor.brancoSinal,
})

// ── cabeçalho ───────────────────────────────────────────────────────────────

export const cabecalho = style({
  display: 'flex',
  alignItems: 'center',
  gap: '12px',
  flexWrap: 'wrap',
})

export const voltar = style({
  display: 'inline-flex',
  alignItems: 'center',
  gap: '5px',
  fontSize: '13px',
  fontWeight: 600,
  color: lk.cor.cianoVisao,
  textDecoration: 'none',
  ':hover': { color: lk.cor.cianoProfundo },
})

export const titulo = style({
  margin: 0,
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '22px',
})

/** O id do evento é dado, não texto: mono, sempre. */
export const tituloId = style({
  fontFamily: lk.fonte.mono,
  fontSize: '18px',
  color: lk.cor.cinzaNevoa,
})

const chipBase = style({
  display: 'inline-flex',
  alignItems: 'center',
  gap: '6px',
  fontFamily: lk.fonte.mono,
  fontSize: '10px',
  letterSpacing: '0.08em',
  borderRadius: '5px',
  padding: '4px 9px',
  border: '1px solid',
})

/** Só a COR muda aqui. Ícone e palavra vêm do componente, sempre os dois. */
export const chip = styleVariants({
  aguarda: [chipBase, {
    color: lk.estado.atencao,
    borderColor: `color-mix(in srgb, ${lk.estado.atencao} 40%, transparent)`,
  }],
  confirmado: [chipBase, {
    color: lk.estado.nc,
    borderColor: `color-mix(in srgb, ${lk.estado.nc} 40%, transparent)`,
  }],
  descartado: [chipBase, {
    color: lk.cor.cinzaNevoa,
    borderColor: lk.cor.borda,
  }],
})

export const chipIcone = style({ width: '12px', height: '12px', flex: 'none' })

// ── corpo: evidência + painel ───────────────────────────────────────────────

export const corpo = style({
  display: 'flex',
  gap: '14px',
  alignItems: 'flex-start',
  flexWrap: 'wrap',
  // SR3: coluna única — frame primeiro, painel de veredito embaixo.
  '@media': { [TELA_ESTREITA]: { flexDirection: 'column' } },
})

export const colunaEvidencia = style({
  flex: 1,
  minWidth: '320px',
  display: 'flex',
  flexDirection: 'column',
  gap: '10px',
  // `minWidth: 320px` some em telas mais estreitas que isso (regra do
  // handoff: "nada quebra até 320px") — senão vira o próprio causador de
  // scroll horizontal.
  '@media': { [TELA_ESTREITA]: { minWidth: '0' } },
})

/**
 * Palco da lupa. `touchAction: none` não é enfeite: sem ele o navegador rouba
 * a pinça e o zoom fica preso ao mouse.
 */
export const palco = style({
  position: 'relative',
  aspectRatio: '16 / 9',
  borderRadius: lk.raio.g,
  overflow: 'hidden',
  border: `1px solid ${lk.cor.borda}`,
  background: lk.cor.grafite,
  touchAction: 'none',
  userSelect: 'none',
  ':focus-visible': { outline: `2px solid ${lk.cor.cianoVisao}`, outlineOffset: '2px' },
})

/** Camada transformada: <img> E caixas juntas — é o que mantém a marcação
 *  colada nos mesmos pixels em qualquer zoom. Separar dessincroniza em silêncio. */
export const camada = style({
  position: 'absolute',
  inset: 0,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  transformOrigin: 'center',
  willChange: 'transform',
})

/**
 * Encolhe até o TAMANHO RENDERIZADO da imagem, e é por isso que ele existe:
 * a caixa é posicionada em % do frame. Se o % fosse do palco 16/9 e o frame
 * fosse 4:3, a barra preta lateral entraria na conta e a caixa sairia
 * deslocada — erro SILENCIOSO, bonito na tela em que foi desenhado.
 */
export const quadro = style({
  position: 'relative',
  display: 'inline-block',
  lineHeight: 0,
  maxWidth: '100%',
  maxHeight: '100%',
})

export const imagem = style({ maxWidth: '100%', maxHeight: '100%', display: 'block' })

export const semImagem = style({
  position: 'absolute',
  inset: 0,
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '10px',
  color: lk.cor.cinzaNevoa,
  fontSize: '13px',
})

/** `pointerEvents: none` é regra da casa: caixa não é alvo de clique. */
export const caixa = style({
  position: 'absolute',
  pointerEvents: 'none',
  borderStyle: 'solid',
  borderColor: lk.estado.nc,
})

export const caixaRotulo = style({
  position: 'absolute',
  bottom: '100%',
  left: 0,
  transformOrigin: '0 100%',
  background: lk.estado.nc,
  color: lk.cor.preto,
  fontFamily: lk.fonte.mono,
  fontSize: '10.5px',
  fontWeight: 700,
  padding: '3px 8px',
  borderRadius: '3px',
  whiteSpace: 'nowrap',
})

// ── correção de caixa (CorrigirCaixa.dc.html) ──────────────────────────────

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

/**
 * "SUA CORREÇÃO" — sólida, ciano. Única caixa desta tela que É alvo de
 * clique: é o próprio editor (arrastar move, alças redimensionam). A
 * vinheta escurece tudo FORA dela — mesmo truque do handoff
 * (`box-shadow: 0 0 0 9999px`), recortado pelo `overflow:hidden` do palco.
 */
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
  display: 'flex',
  alignItems: 'center',
  gap: '10px',
  fontFamily: lk.fonte.mono,
  fontSize: '10.5px',
  letterSpacing: '0.14em',
  color: lk.cor.cinzaNevoa,
})

const seloBase = style({
  position: 'absolute',
  top: '10px',
  zIndex: 3,
  background: `color-mix(in srgb, ${lk.cor.preto} 75%, transparent)`,
  borderRadius: '5px',
  padding: '4px 9px',
  fontFamily: lk.fonte.mono,
  fontSize: '11px',
  letterSpacing: '0.1em',
  pointerEvents: 'none',
  /**
   * Os dois selos são absolutos — um ancorado à esquerda, outro à direita — e
   * em tela larga nunca se encontram. Em 375px eles se ATRAVESSAM: medido na
   * captura desta rodada, o nome da câmera saía "CAM-01 · EXP" com a data
   * impressa por cima. Teto de metade da caixa + reticências separa os dois
   * sem esconder nenhum dos dados.
   */
  '@media': {
    [TELA_ESTREITA]: {
      maxWidth: 'calc(50% - 14px)',
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap',
    },
  },
})

export const selo = styleVariants({
  esquerda: [seloBase, { left: '10px', color: lk.cor.brancoSinal }],
  direita: [seloBase, { right: '10px', color: lk.cor.cinzaNevoa }],
})

export const barraLupa = style({
  display: 'flex',
  alignItems: 'center',
  gap: lk.espaco.x1,
  flexWrap: 'wrap',
})

export const botaoLupa = style({
  height: '38px',
  minWidth: '38px',
  padding: `0 12px`,
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '6px',
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.s,
  color: lk.cor.brancoSinal,
  fontFamily: lk.fonte.ui,
  fontSize: '12.5px',
  fontWeight: 600,
  cursor: 'pointer',
  ':disabled': { color: lk.cor.cinzaNevoa, cursor: 'default' },
  ':hover': { borderColor: lk.cor.cianoVisao },
  '@media': { [TELA_ESTREITA]: { height: '44px' } },
})

export const dicaLupa = style({
  fontFamily: lk.fonte.mono,
  fontSize: '10px',
  letterSpacing: OVERLINE_TRACKING,
  textTransform: 'uppercase',
  color: lk.cor.cinzaNevoa,
})

// ── painel lateral ──────────────────────────────────────────────────────────

export const painel = style({
  width: '380px',
  flex: 'none',
  display: 'flex',
  flexDirection: 'column',
  gap: '14px',
  background: lk.cor.grafite,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.g,
  padding: '18px',
  boxSizing: 'border-box',
  '@media': {
    'screen and (max-width: 900px)': { width: '100%' },
    [TELA_ESTREITA]: { padding: '14px' },
  },
})

/** Classe detectada: cor + ícone + palavra, os três. */
export const classeChip = style({
  display: 'inline-flex',
  alignItems: 'center',
  gap: '7px',
  background: `color-mix(in srgb, ${lk.estado.nc} 10%, transparent)`,
  border: `1px solid color-mix(in srgb, ${lk.estado.nc} 40%, transparent)`,
  borderRadius: '6px',
  padding: '6px 11px',
  color: lk.estado.nc,
  fontSize: '13px',
  fontWeight: 700,
})

export const classeIcone = style({ width: '14px', height: '14px', flex: 'none' })

export const grade = style({
  display: 'grid',
  gridTemplateColumns: 'auto 1fr',
  gap: `6px 14px`,
  fontSize: '12.5px',
  alignItems: 'baseline',
  // SR3: "meta empilha" — rótulo em cima, valor embaixo, em vez de espremer
  // as duas colunas na largura do celular.
  '@media': { [TELA_ESTREITA]: { gridTemplateColumns: '1fr', gap: '2px' } },
})

export const rotulo = style({ color: lk.cor.cinzaNevoa })

export const valorMono = style({ fontFamily: lk.fonte.mono })

export const overline = style({
  fontFamily: lk.fonte.mono,
  fontSize: '10px',
  letterSpacing: OVERLINE_TRACKING,
  textTransform: 'uppercase',
  color: lk.cor.cinzaNevoa,
})

export const bloco = style({ display: 'flex', flexDirection: 'column', gap: lk.espaco.x1 })

export const listaDeteccoes = style({
  margin: 0,
  padding: 0,
  listStyle: 'none',
  display: 'flex',
  flexDirection: 'column',
  gap: '5px',
  fontSize: '12.5px',
})

export const deteccao = style({ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: lk.espaco.x1 })

/** Marca a violação em edição — mesmo acento de borda-esquerda do nav ativo. */
export const deteccaoSelecionada = style({
  borderLeft: `2px solid ${lk.cor.cianoVisao}`,
  paddingLeft: '8px',
})

/** Agrupa classe + confiança num único item flex, para o botão "Corrigir
 *  caixa" ser o segundo (e só o segundo) filho de `deteccao`. */
export const deteccaoInfo = style({ display: 'flex', alignItems: 'center', gap: lk.espaco.x1 })

export const confianca = style({ fontFamily: lk.fonte.mono, color: lk.cor.cinzaNevoa })

export const botaoCorrigir = style({
  height: '26px',
  padding: '0 10px',
  flex: 'none',
  display: 'inline-flex',
  alignItems: 'center',
  background: 'transparent',
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.s,
  color: lk.cor.cinzaNevoa,
  fontFamily: lk.fonte.mono,
  fontSize: '10.5px',
  letterSpacing: '0.06em',
  textTransform: 'uppercase',
  cursor: 'pointer',
  ':hover': { borderColor: lk.cor.cianoVisao, color: lk.cor.cianoVisao },
})

/**
 * Badge de procedência — QUEM desenhou a caixa deste evento.
 *
 * Três leituras, três cores, e a cor nunca vai sozinha (a palavra está no
 * componente): `humana` e `retroativa` são ressalva sobre a cena, e por isso
 * usam ATENÇÃO; `modelo` é o caso esperado e fica em cinza, porque pintar de
 * âmbar a operação normal treina o olho a ignorar o âmbar.
 */
const procedenciaBase = style({
  display: 'inline-flex',
  alignItems: 'center',
  gap: '5px',
  fontFamily: lk.fonte.mono,
  fontSize: '10px',
  letterSpacing: '0.08em',
  textTransform: 'uppercase',
  borderRadius: '5px',
  padding: '2px 7px',
  whiteSpace: 'nowrap',
})

const tomProcedencia = (cor: string) => ({
  color: cor,
  border: `1px solid color-mix(in srgb, ${cor} 40%, transparent)`,
})

export const procedencia = styleVariants({
  humana: [procedenciaBase, tomProcedencia(lk.estado.atencao)],
  modelo: [procedenciaBase, tomProcedencia(lk.cor.cinzaNevoa)],
  retroativa: [procedenciaBase, tomProcedencia(lk.estado.atencao)],
})

export const procedenciaIcone = style({ width: '11px', height: '11px', flex: 'none' })

// ── veredito ────────────────────────────────────────────────────────────────

export const vereditoBloco = style({
  display: 'flex',
  flexDirection: 'column',
  gap: lk.espaco.x1,
  marginTop: 'auto',
})

export const campoMotivo = style({
  height: '38px',
  background: lk.cor.preto,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: '7px',
  color: lk.cor.brancoSinal,
  fontFamily: lk.fonte.ui,
  fontSize: '13px',
  padding: `0 11px`,
  outline: 'none',
  ':focus': { borderColor: lk.cor.cianoVisao },
  '::placeholder': { color: lk.cor.cinzaNevoa },
})

export const ajuda = style({ margin: 0, fontSize: '11.5px', lineHeight: 1.5, color: lk.cor.cinzaNevoa })

export const botoesVeredito = style({ display: 'flex', gap: lk.espaco.x1 })

const vereditoBase = style({
  flex: 1,
  // ≥48px é regra do handoff: quem opera de luva não acerta alvo pequeno.
  height: lk.medida.veredito,
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: lk.espaco.x1,
  borderRadius: '9px',
  fontFamily: lk.fonte.ui,
  fontSize: '14px',
  cursor: 'pointer',
  ':disabled': { opacity: 0.5, cursor: 'default' },
})

export const botaoVeredito = styleVariants({
  confirmar: [vereditoBase, {
    border: 'none',
    background: lk.estado.ok,
    color: lk.cor.preto,
    fontWeight: 700,
  }],
  descartar: [vereditoBase, {
    background: 'transparent',
    border: `1px solid ${lk.cor.borda}`,
    color: lk.cor.brancoSinal,
    fontWeight: 600,
    ':hover': { borderColor: lk.estado.nc, color: lk.estado.nc },
  }],
})

export const iconeVeredito = style({ width: '16px', height: '16px', flex: 'none' })

export const aviso = style({ margin: 0, fontSize: '12px', lineHeight: 1.5, color: lk.estado.atencao })

export const erro = style({ margin: 0, fontSize: '12.5px', color: lk.estado.nc })

export const linkTentarNovamente = style({
  marginLeft: '6px',
  padding: 0,
  background: 'none',
  border: 'none',
  color: lk.cor.cianoVisao,
  fontFamily: lk.fonte.ui,
  fontSize: '12.5px',
  fontWeight: 600,
  textDecoration: 'underline',
  cursor: 'pointer',
})

// ── correção de caixa: coordenadas + ações ─────────────────────────────────

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
  height: '44px',
  width: '100%',
  boxSizing: 'border-box',
  padding: '0 12px',
  borderRadius: lk.raio.s,
  border: `1px solid ${lk.cor.borda}`,
  background: lk.cor.preto,
  color: lk.cor.brancoSinal,
  fontFamily: lk.fonte.mono,
  fontSize: '15px',
  outline: 'none',
  ':focus': { borderColor: lk.cor.cianoVisao },
  ':disabled': { color: lk.cor.cinzaNevoa },
})

/** Mesma forma de `botaoVeredito` (48px, regra do handoff p/ quem opera de
 *  luva) — cor muda: "Salvar caixa" é ação, não confirmação/descarte. */
export const botaoCorrecao = styleVariants({
  salvar: [vereditoBase, {
    border: 'none',
    background: lk.cor.cianoVisao,
    color: lk.cor.preto,
    fontWeight: 700,
  }],
  cancelar: [vereditoBase, {
    background: 'transparent',
    border: `1px solid ${lk.cor.borda}`,
    color: lk.cor.brancoSinal,
    fontWeight: 600,
  }],
})

export const badgeAutoria = style({
  display: 'flex',
  gap: lk.espaco.x1,
  padding: '12px',
  borderRadius: lk.raio.s,
  background: lk.cor.preto,
  border: `1px solid ${lk.cor.borda}`,
})

export const badgeAutoriaTexto = style({
  margin: 0,
  fontSize: '12.5px',
  lineHeight: 1.5,
  color: lk.cor.cinzaNevoa,
})

// ── estados de tela inteira (vazio / erro) ──────────────────────────────────

export const estadoCentral = style({
  minHeight: '60vh',
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '14px',
  textAlign: 'center',
  padding: lk.medida.padding,
  boxSizing: 'border-box',
  fontFamily: lk.fonte.ui,
})

export const estadoIcone = styleVariants({
  neutro: { width: '36px', height: '36px', color: lk.cor.cinzaNevoa },
  falha: { width: '36px', height: '36px', color: lk.estado.nc },
})

export const estadoTitulo = style({
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  fontSize: '19px',
  color: lk.cor.brancoSinal,
})

export const estadoTexto = style({
  margin: 0,
  fontSize: '13.5px',
  color: lk.cor.cinzaNevoa,
  maxWidth: '380px',
  lineHeight: 1.55,
})

export const estadoMono = style({
  fontFamily: lk.fonte.mono,
  fontSize: '12px',
  color: lk.cor.cinzaNevoa,
})

export const botaoPrimario = style({
  display: 'inline-flex',
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
  '@media': { [TELA_ESTREITA]: { height: '44px' } },
})
