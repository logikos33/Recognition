/**
 * Shell Logikos Vision — TopBar 56 · sidebar 236/64 · banner admin 42+2.
 * Medidas do README do handoff, via token. Zero hex solto.
 */
import { assignVars, globalStyle, style } from '@vanilla-extract/css'

import { vars } from '../../styles/theme.css'
import { lk } from '../tokens/lk.css'

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
})

export const sidebar = style({
  width: lk.medida.sidebar,
  flexShrink: 0,
  background: lk.cor.grafite,
  borderRight: `1px solid ${lk.cor.borda}`,
  padding: `${lk.espaco.x2} 0`,
  transition: 'width .15s steps(3, end)',
})

export const sidebarColapsada = style({ width: lk.medida.sidebarColapsada })

export const grupoTitulo = style({
  padding: `${lk.espaco.x1} ${lk.espaco.x3}`,
  fontFamily: lk.fonte.mono,
  fontSize: '11px',
  textTransform: 'uppercase',
  letterSpacing: '0.18em',
  color: lk.cor.cinzaNevoa,
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
})

/** Ativo: borda esquerda 2px ciano — o ciano marca ONDE ESTOU. */
export const itemAtivo = style({
  color: lk.cor.brancoSinal,
  borderLeftColor: lk.cor.cianoVisao,
  background: lk.cor.preto,
})

export const conteudo = style({
  flex: 1,
  minWidth: 0,
  padding: lk.medida.padding,
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
})

export const dicaAtalho = style({
  fontFamily: lk.fonte.mono,
  fontSize: '11px',
  color: lk.cor.cinzaNevoa,
  border: `1px solid ${lk.cor.borda}`,
  borderRadius: lk.raio.s,
  padding: '3px 8px',
})

export const rotuloColapsado = style({
  position: 'absolute',
  width: 1,
  height: 1,
  overflow: 'hidden',
  clipPath: 'inset(50%)',
})
