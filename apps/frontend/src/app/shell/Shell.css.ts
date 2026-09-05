/**
 * Shell Logikos Vision — TopBar 56 · sidebar 236/64 · banner admin 42+2.
 * Medidas do README do handoff, via token. Zero hex solto.
 */
import { assignVars, globalStyle, style } from '@vanilla-extract/css'

import { vars } from '../../styles/theme.css'
import { TELA_ESTREITA, lk } from '../tokens/lk.css'

/**
 * F5-LEVE (identidade): componentes LEGADOS renderizados sob este shell
 * (`CameraPlayer` via AoVivo, `TrainingGallery`/`CropClassifier` via
 * Estúdio, ...) importam `vars.color.primary/primaryLight/primaryDark/
 * primaryAlpha` do contrato antigo (`styles/theme.css.ts`). Esse contrato é
 * aplicado em `document.documentElement` pelo `AppShell` (tema
 * recognition-dark/cyberpunk/professional) — uma custom property de
 * `<html>`, então ela cascateia para DENTRO do shell novo também, e o roxo
 * do tema legado (professional/cyberpunk: `#8b5cf6`) vaza pra cá.
 *
 * Sobrescrever as quatro vars aqui, na raiz do shell novo, corta a herança
 * pra este subtree inteiro — pinta com os tokens `lk` (ciano), sem tocar no
 * tema antigo nem nos componentes legados em si. Remoção quando o legado
 * morrer (`docs/migration/MANIFESTO-FRONT-ANTIGO.md`).
 */
export const paletaLkSobreTemaLegado = assignVars(
  {
    primary: vars.color.primary,
    primaryLight: vars.color.primaryLight,
    primaryDark: vars.color.primaryDark,
    primaryAlpha: vars.color.primaryAlpha,
  },
  {
    primary: lk.cor.cianoVisao,
    primaryLight: lk.cor.cianoVisao,
    primaryDark: lk.cor.cianoProfundo,
    primaryAlpha: `color-mix(in srgb, ${lk.cor.cianoVisao} 12%, transparent)`,
  },
)

export const raiz = style({
  vars: paletaLkSobreTemaLegado,
  minHeight: '100vh',
  background: lk.cor.preto,
  color: lk.cor.brancoSinal,
  fontFamily: lk.fonte.ui,
})

/**
 * F5-LEVE (identidade, rodada 2): o remap acima só alcança quem está DENTRO
 * da árvore DOM de `.raiz`. Radix (`Dialog.Portal` do Modal/ConfirmDialog,
 * `Popover.Portal` do CameraFilterSelector, `Tooltip.Portal`) anexa direto em
 * `document.body`, e o `ToastProvider` (main.tsx) monta como IRMÃO de
 * `<App/>` — os dois escapam da árvore de `.raiz` e herdam puro do tema
 * legado aplicado em `document.documentElement` (mesmo raciocínio do
 * comentário em `AppShell.tsx`: só o que está no documentElement alcança
 * portal). Resultado medido: botão "Arquivar" do ConfirmDialog e o
 * "Ver todos os alertas" do sino saíam roxo mesmo com o remap de `.raiz` no
 * lugar.
 *
 * `Shell.tsx` publica `data-lk-shell` em `document.documentElement` enquanto
 * o shell novo está montado (e remove ao desmontar — sem isto o front antigo
 * herdaria ciano depois de navegar de volta). Esta regra repete o MESMO
 * remap ali: `<html>` é ancestral de QUALQUER coisa anexada a `document.body`
 * (portal ou não) e do `#root` inteiro (ToastProvider incluso), então alcança
 * as duas fugas de uma vez, sem tocar nos componentes legados em si.
 */
globalStyle('html[data-lk-shell]', { vars: paletaLkSobreTemaLegado })

export const topbar = style({
  position: 'sticky',
  // Os banners globais (impersonation / contexto assumido) são sticky no topo e
  // publicam a própria altura em --global-banner-offset. A topbar desce o que
  // eles ocupam; sem isto ela nasce por baixo deles.
  top: 'var(--global-banner-offset, 0px)',
  zIndex: 30,
  height: lk.medida.topbar,
  display: 'flex',
  alignItems: 'center',
  gap: lk.espaco.x2,
  padding: `0 ${lk.espaco.x3}`,
  background: lk.cor.grafite,
  borderBottom: `1px solid ${lk.cor.borda}`,
  // Em 375px os oito controles da topbar não cabem com respiro de 24/16. O
  // aperto é de espaçamento, não de conteúdo: nada some daqui.
  '@media': { [TELA_ESTREITA]: { gap: lk.espaco.x1, padding: `0 ${lk.espaco.x1}` } },
})

export const marca = style({
  display: 'flex',
  alignItems: 'center',
  gap: lk.espaco.x1,
  fontFamily: lk.fonte.titulo,
  fontWeight: 700,
  letterSpacing: '0.04em',
  color: lk.cor.brancoSinal,
})

export const espacador = style({ flex: 1 })

export const corpo = style({
  display: 'flex',
  alignItems: 'stretch',
  // Sem altura mínima, a sidebar termina onde o conteúdo termina — numa tela
  // com pouco conteúdo (um vazio honesto, por exemplo) ela vira uma faixa
  // curta no meio da página, e o shell parece quebrado.
  minHeight: `calc(100vh - ${lk.medida.topbar})`,
  // Celular: a barra lateral vira uma FAIXA no topo do conteúdo (regras em
  // `sidebar`), então o corpo empilha em vez de dividir a largura.
  '@media': { [TELA_ESTREITA]: { flexDirection: 'column' } },
})

/**
 * Barra lateral — coluna de 236px no desktop, FAIXA horizontal no celular.
 *
 * Medido antes de mexer (`mobile-caminho.spec.ts`, viewport 375): com
 * `width: 236px; flex-shrink: 0` a barra comia 63% da tela e sobravam **91px**
 * de conteúdo. Nada estourava a viewport — o `<main>` é `flex: 1; min-width: 0`
 * e encolhia calado —, então o teste de "sem scroll horizontal" que já existia
 * (`front-novo-mobile.spec.ts`) passava com o Dashboard ilegível, uma palavra
 * por linha.
 *
 * Duas saídas foram descartadas:
 *
 * · **Esconder o menu** (`display: none`): a tela ganha largura e o operador
 *   perde a saída — abriu um evento no chão de fábrica e não volta pra lista.
 *   É o beco que `becoSemSaida.test.tsx` existe pra impedir.
 * · **Gaveta com overlay** (o padrão do desenho mobile): exige estado novo em
 *   `Shell.tsx` — botão que abre/fecha, foco preso, Esc. Fora do alcance de um
 *   conserto de CSS e fora do que esta rodada pode tocar (issue aberta).
 *
 * A faixa é a adaptação que cabe em CSS: os mesmos itens, na mesma ordem, em
 * uma tira rolável de 44px. O ciano continua marcando ONDE ESTOU — só muda de
 * borda esquerda para borda inferior, que é o que uma tira lê.
 */
export const sidebar = style({
  width: lk.medida.sidebar,
  flexShrink: 0,
  background: lk.cor.grafite,
  borderRight: `1px solid ${lk.cor.borda}`,
  padding: `${lk.espaco.x2} 0`,
  transition: 'width .15s steps(3, end)',
  '@media': {
    [TELA_ESTREITA]: {
      width: '100%',
      display: 'flex',
      alignItems: 'stretch',
      padding: 0,
      // A tira rola DENTRO de si: com 3 grupos de itens ela passa de 375px, e
      // é a tira que rola, nunca a página.
      overflowX: 'auto',
      borderRight: 'none',
      borderBottom: `1px solid ${lk.cor.borda}`,
      transition: 'none',
    },
  },
})

/**
 * Recolher é conceito de coluna. Na faixa a largura já é 100% e o botão de
 * menu só apaga os rótulos (`rotuloColapsado`) — 64px aqui deixaria a tira
 * espremida contra a borda esquerda, com a tela toda vazia ao lado.
 */
export const sidebarColapsada = style({
  width: lk.medida.sidebarColapsada,
  '@media': { [TELA_ESTREITA]: { width: '100%' } },
})

/**
 * Cada grupo da nav é um `<div>` (título + itens). Na faixa eles entram em
 * linha; é o único jeito de manter a ORDEM dos itens sem tocar no `Shell.tsx`.
 */
globalStyle(`${sidebar} > div`, {
  '@media': { [TELA_ESTREITA]: { display: 'flex', alignItems: 'stretch' } },
})

export const grupoTitulo = style({
  padding: `${lk.espaco.x1} ${lk.espaco.x3}`,
  fontFamily: lk.fonte.mono,
  fontSize: '11px',
  textTransform: 'uppercase',
  letterSpacing: '0.18em',
  color: lk.cor.cinzaNevoa,
  // "EPI" / "ESTÚDIO" / "ADMINISTRAÇÃO" numa tira de 44px viram três rótulos
  // atravessados no caminho dos itens. O agrupamento é do desktop.
  '@media': { [TELA_ESTREITA]: { display: 'none' } },
})

export const item = style({
  display: 'flex',
  alignItems: 'center',
  gap: lk.espaco.x2,
  height: lk.medida.itemNav,
  padding: `0 ${lk.espaco.x3}`,
  color: lk.cor.cinzaNevoa,
  textDecoration: 'none',
  fontSize: '14px',
  // 2px transparentes reservados: sem isto o texto pula 2px ao ativar.
  borderLeft: '2px solid transparent',
  ':hover': { color: lk.cor.brancoSinal, background: lk.cor.preto },
  '@media': {
    [TELA_ESTREITA]: {
      // 44px: chão de fábrica usa dedo (mesma régua do `SeletorTenant`).
      height: '44px',
      flex: 'none',
      whiteSpace: 'nowrap',
      padding: `0 ${lk.espaco.x2}`,
      borderLeft: 'none',
      borderBottom: '2px solid transparent',
    },
  },
})

/** Ativo: borda esquerda 2px ciano — o ciano marca ONDE ESTOU. */
export const itemAtivo = style({
  color: lk.cor.brancoSinal,
  borderLeftColor: lk.cor.cianoVisao,
  background: lk.cor.preto,
  // Na faixa a borda esquerda não existe mais — o "onde estou" desce pra base.
  '@media': { [TELA_ESTREITA]: { borderBottomColor: lk.cor.cianoVisao } },
})

export const conteudo = style({
  flex: 1,
  minWidth: 0,
  padding: lk.medida.padding,
  // 24px de cada lado custam 13% de uma tela de 375px. 16px devolve a largura
  // sem colar o texto na borda.
  '@media': { [TELA_ESTREITA]: { padding: lk.espaco.x2 } },
})

export const conteudoInterno = style({
  maxWidth: lk.medida.conteudoMax,
  margin: '0 auto',
})

export const botaoIcone = style({
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: '34px',
  height: '34px',
  borderRadius: lk.raio.s,
  border: `1px solid ${lk.cor.borda}`,
  background: 'transparent',
  color: lk.cor.cinzaNevoa,
  cursor: 'pointer',
  ':hover': { color: lk.cor.brancoSinal, borderColor: lk.cor.cianoVisao },
  // 34px é alvo de mouse. No celular estes três (menu, busca, sair) são os
  // únicos controles do shell, e 44px é o piso de alvo de dedo que o resto do
  // front novo já usa (`SeletorTenant`, botões de veredito).
  '@media': { [TELA_ESTREITA]: { width: '44px', height: '44px', flex: 'none' } },
})

export const dicaAtalho = style({
  fontFamily: lk.fonte.mono,
  fontSize: '11px',
  color: lk.cor.cinzaNevoa,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.s,
  padding: '3px 8px',
  // "⌘K" num aparelho sem teclado é enfeite ocupando espaço de controle. O
  // botão de busca ao lado continua lá, e ele é o caminho no celular.
  '@media': { [TELA_ESTREITA]: { display: 'none' } },
})

export const rotuloColapsado = style({
  position: 'absolute',
  width: 1,
  height: 1,
  overflow: 'hidden',
  clipPath: 'inset(50%)',
})
