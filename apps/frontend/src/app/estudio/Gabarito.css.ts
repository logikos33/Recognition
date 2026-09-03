/**
 * Estilo da triagem do gabarito — MOBILE-FIRST de verdade, não "responsivo".
 *
 * O layout base É o do telefone em pé: coluna única, `100dvh` em três faixas
 * (topo fino / foto elástica / respostas), sem scroll de página. `dvh` e não
 * `vh` porque a barra de endereço do Chrome no Android come ~60px de `vh` — e
 * o que sumiria embaixo é justamente a fileira de botões.
 *
 * A largura só é usada para CRESCER (`@media (min-width: 720px)` limita a
 * coluna e para de esticar a foto). Nenhuma media query desliga funcionalidade.
 *
 * Alvo de toque: 48px nos vereditos (`lk.medida.veredito`, o token que já
 * existia para isto), 52px no atalho de um toque. O mínimo de acessibilidade é
 * 44; quem vai usar isto está de pé, andando, com uma mão só.
 *
 * ⛔ Zero hex solto — `npm run lint:hex` reprova. Cor só de `lk.*`.
 * Estado = cor + ícone + palavra (contrato dos tokens): os três botões
 * carregam ícone e rótulo, a cor é o terceiro sinal, nunca o único.
 */
import { style, styleVariants } from '@vanilla-extract/css'

import { lk } from '../tokens/lk.css'

export const raiz = style({
  display: 'flex',
  flexDirection: 'column',
  height: '100dvh',
  background: lk.cor.preto,
  color: lk.cor.brancoSinal,
  fontFamily: lk.fonte.ui,
  // A tela inteira é gesto e toque: seleção de texto por toque longo só
  // atrapalha quem está arrastando a foto.
  userSelect: 'none',
  overflow: 'hidden',
})

export const aviso = style({
  padding: lk.espaco.x3,
  color: lk.cor.cinzaNevoa,
  fontFamily: lk.fonte.ui,
  background: lk.cor.preto,
  minHeight: '100dvh',
})

export const topo = style({
  display: 'flex',
  alignItems: 'center',
  gap: lk.espaco.x1,
  padding: `${lk.espaco.x1} ${lk.espaco.x2}`,
  borderBottom: `1px solid ${lk.cor.borda}`,
  background: lk.cor.grafite,
  flexShrink: 0,
  fontSize: '12px',
})

/** Única saída da tela (não há Shell nem lateral). Alvo de toque ≥44px. */
export const voltar = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: '44px',
  minHeight: '44px',
  marginLeft: '-10px',
  color: lk.cor.cinzaNevoa,
  flexShrink: 0,
})

export const contador = style({
  fontFamily: lk.fonte.mono,
  fontWeight: 700,
  fontSize: '13px',
  color: lk.cor.brancoSinal,
  flexShrink: 0,
})

export const camera = style({
  color: lk.cor.cinzaNevoa,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
  flex: 1,
  minWidth: 0,
})

export const pendencia = style({
  fontFamily: lk.fonte.mono,
  color: lk.estado.atencao,
  flexShrink: 0,
})

export const progresso = style({
  fontFamily: lk.fonte.mono,
  color: lk.cor.cinzaNevoa,
  flexShrink: 0,
})

/**
 * A foto come todo o espaço que sobra (`flex: 1`) — é a informação da tela.
 *
 * `touchAction: 'none'` entrega os gestos ao componente: sem isso o navegador
 * intercepta o arrasto como scroll da página e o pan da imagem nunca acontece.
 * Só aqui — o resto da página continua com o comportamento nativo.
 */
export const painelFoto = style({
  position: 'relative',
  flex: 1,
  minHeight: 0,
  overflow: 'hidden',
  background: lk.cor.preto,
  touchAction: 'none',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
})

export const foto = style({
  maxWidth: '100%',
  maxHeight: '100%',
  objectFit: 'contain',
  transformOrigin: 'center center',
  // Sem transição: o pinch precisa acompanhar o dedo. Uma animação de 150ms
  // aqui faz a imagem "escorregar" atrás do gesto e o zoom parecer quebrado.
  willChange: 'transform',
})

export const zerarZoom = style({
  position: 'absolute',
  bottom: lk.espaco.x1,
  right: lk.espaco.x1,
  minHeight: '32px',
  padding: `0 ${lk.espaco.x1}`,
  borderRadius: lk.raio.s,
  border: `1px solid ${lk.cor.bordaForte}`,
  background: lk.cor.grafite,
  color: lk.cor.cinzaNevoa,
  fontFamily: lk.fonte.mono,
  fontSize: '11px',
  cursor: 'pointer',
})

export const painelRespostas = style({
  flexShrink: 0,
  padding: lk.espaco.x1,
  display: 'flex',
  flexDirection: 'column',
  gap: lk.espaco.x1,
  borderTop: `1px solid ${lk.cor.borda}`,
  background: lk.cor.grafite,
  // Teto: com as 5 classes abertas a lista rola DENTRO do painel em vez de
  // empurrar a foto para fora da tela.
  maxHeight: '54dvh',
  overflowY: 'auto',
})

export const semPessoa = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: lk.espaco.x1,
  width: '100%',
  minHeight: '52px',
  borderRadius: lk.raio.m,
  border: `1px solid ${lk.cor.bordaForte}`,
  background: lk.cor.preto,
  color: lk.cor.brancoSinal,
  fontFamily: lk.fonte.ui,
  fontSize: '15px',
  fontWeight: 600,
  cursor: 'pointer',
})

export const semPessoaAtivo = style({
  borderColor: lk.cor.cianoVisao,
  color: lk.cor.cianoVisao,
})

export const classe = style({
  display: 'flex',
  flexDirection: 'column',
  gap: '6px',
})

export const classeNome = style({
  display: 'flex',
  alignItems: 'center',
  gap: lk.espaco.x1,
  fontSize: '13px',
  color: lk.cor.cinzaNevoa,
  fontFamily: lk.fonte.ui,
})

/**
 * "foco" nas duas classes com gabarito ZERO. A hierarquia é conteúdo: são elas
 * que travam o A/B, e cinco perguntas de peso visual igual esconderiam isso.
 */
export const selo = style({
  fontFamily: lk.fonte.mono,
  fontSize: '10px',
  letterSpacing: '0.14em',
  textTransform: 'uppercase',
  color: lk.cor.cianoVisao,
  border: `1px solid ${lk.cor.cianoVisao}`,
  borderRadius: lk.raio.s,
  padding: '1px 6px',
})

export const botoes = style({
  display: 'grid',
  gridTemplateColumns: 'repeat(3, 1fr)',
  gap: '6px',
})

export const botao = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '6px',
  minHeight: lk.medida.veredito,
  borderRadius: lk.raio.m,
  border: `1px solid ${lk.cor.bordaForte}`,
  background: lk.cor.preto,
  color: lk.cor.brancoSinal,
  fontFamily: lk.fonte.ui,
  fontSize: '15px',
  fontWeight: 600,
  cursor: 'pointer',
})

/**
 * Escolhido = borda + texto na cor do estado, fundo escuro.
 *
 * Fundo CHAPADO na cor do estado seria mais óbvio e está errado por duas
 * razões da casa: o ciano nunca é fundo de superfície, e verde/vermelho
 * chapados num painel que o dono olha 138 vezes cansam a vista até ele parar
 * de distinguir. A palavra e o ícone já estavam lá antes da cor.
 */
// `styleVariants` (e não três `style` soltos) porque o componente indexa por
// veredito — `s.botaoAtivo[valor]`, com o `Veredito` do domínio como chave.
// Somar um estado ao tipo passa a dar erro de tipo aqui até ele ganhar cor.
export const botaoAtivo = styleVariants({
  sim: { borderColor: lk.estado.nc, color: lk.estado.nc },
  nao: { borderColor: lk.estado.ok, color: lk.estado.ok },
  nao_sei: { borderColor: lk.cor.cianoVisao, color: lk.cor.cianoVisao },
})

export const maisClasses = style({
  minHeight: '44px',
  borderRadius: lk.raio.s,
  border: `1px dashed ${lk.cor.bordaForte}`,
  background: 'transparent',
  color: lk.cor.cinzaNevoa,
  fontFamily: lk.fonte.ui,
  fontSize: '13px',
  cursor: 'pointer',
})

export const rodape = style({
  display: 'grid',
  gridTemplateColumns: '1fr 1fr',
  gap: lk.espaco.x1,
  padding: lk.espaco.x1,
  paddingBottom: `calc(${lk.espaco.x1} + env(safe-area-inset-bottom))`,
  borderTop: `1px solid ${lk.cor.borda}`,
  background: lk.cor.grafite,
  flexShrink: 0,
})

export const navegar = style({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '6px',
  minHeight: lk.medida.veredito,
  borderRadius: lk.raio.m,
  border: `1px solid ${lk.cor.bordaForte}`,
  background: lk.cor.preto,
  color: lk.cor.brancoSinal,
  fontFamily: lk.fonte.ui,
  fontSize: '15px',
  fontWeight: 600,
  cursor: 'pointer',
  selectors: {
    '&:disabled': { opacity: 0.35, cursor: 'default' },
  },
})
