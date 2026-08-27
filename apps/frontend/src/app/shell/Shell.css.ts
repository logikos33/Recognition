/**
 * Shell Logikos Vision — TopBar 56 · sidebar 236/64 · banner admin 42+2.
 * Medidas do README do handoff, via token. Zero hex solto.
 */
import { style } from '@vanilla-extract/css'

import { lk } from '../tokens/lk.css'

export const raiz = style({
  minHeight: '100vh',
  background: lk.cor.preto,
  color: lk.cor.brancoSinal,
  fontFamily: lk.fonte.ui,
})

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

export const corpo = style({ display: 'flex', alignItems: 'stretch' })

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
