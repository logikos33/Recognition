import { style } from '@vanilla-extract/css'

import { lk } from '../tokens/lk.css'

// Sem minHeight próprio: o `corpo` do Shell já garante 100vh-topbar, e somar
// os dois criava barra de rolagem permanente (achado do cético).
export const raiz = style({
  display: 'flex',
  alignItems: 'stretch',
})

/** Largura da lateral PRÓPRIA do Estúdio — medida do desenho (`Estúdio.dc.html`),
 * menor que a `lk.medida.sidebar` do Shell (que some nesta rota). */
export const lateral = style({
  width: '220px',
  flexShrink: 0,
  display: 'flex',
  flexDirection: 'column',
  gap: '2px',
  padding: '16px 8px',
  borderRight: `1px solid ${lk.cor.borda}`,
  background: lk.cor.grafite,
})

export const lateralTitulo = style({
  fontFamily: lk.fonte.mono,
  fontSize: '10.5px',
  letterSpacing: '.18em',
  textTransform: 'uppercase',
  color: lk.cor.cinzaNevoa,
  padding: '0 10px 8px',
})

export const item = style({
  display: 'flex',
  alignItems: 'center',
  gap: '10px',
  height: lk.medida.itemNav,
  padding: '0 10px',
  fontSize: '13.5px',
  color: lk.cor.cinzaNevoa,
  textDecoration: 'none',
  borderLeft: '2px solid transparent',
  selectors: {
    '&:hover': { color: lk.cor.brancoSinal },
  },
})

export const itemAtivo = style({
  color: lk.cor.brancoSinal,
  borderLeftColor: lk.cor.cianoVisao,
  background: lk.cor.preto,
})

// Só o respiro entre o trilho e o conteúdo — o `main` do Shell já dá 24px em
// volta de tudo; padding aqui dobrava para 48px (achado do cético).
export const conteudo = style({
  flex: 1,
  minWidth: 0,
  paddingLeft: lk.medida.padding,
})
