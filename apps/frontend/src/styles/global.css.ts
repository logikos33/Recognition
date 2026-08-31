/**
 * Global styles — CSS reset and base typography.
 * Import this once in main.tsx.
 *
 * Sprint 1: purple rgba substituído por valores do tema recognition-dark
 * (primary: #06b6d4). O CONTRATO ANTIGO (`vars.color.*`, `styles/theme.css.ts`)
 * não está disponível aqui — só é preenchido em runtime pela classe de tema
 * (`professionalTheme`/`cyberpunkTheme`/...) aplicada em `document.documentElement`,
 * e este arquivo roda antes disso. Os tokens `lk.*` são diferentes: nascem
 * direto no `:root` (`createGlobalTheme`, `app/tokens/lk.css.ts`) sem depender
 * de classe nenhuma — por isso `lk.cor.preto` é seguro de usar aqui embaixo.
 *
 * F5-LEVE (tema não pode estourar): `html`/`body` SEM fundo é o que deixa o
 * branco padrão do navegador aparecer — no overscroll (rubber-band do macOS)
 * e em qualquer área fora do que os componentes de topo pintam. Todo layout
 * de topo (Shell novo, AppShell/AppLayout/QualityLayout/AdminLayout/Login do
 * front antigo) já pinta `minHeight:100vh` + o próprio fundo por cima disto
 * — então isto aqui é só a rede de segurança, nunca o que o usuário vê no
 * caminho normal.
 */
import { globalStyle } from '@vanilla-extract/css'

import { lk } from '../app/tokens/lk.css'

globalStyle('*, *::before, *::after', {
  boxSizing: 'border-box',
  margin: 0,
  padding: 0,
})

globalStyle('html, body', {
  height: '100%',
  background: lk.cor.preto,
  colorScheme: 'dark',
  fontFamily: "'Inter Variable', Inter, system-ui, sans-serif",
  WebkitFontSmoothing: 'antialiased',
  MozOsxFontSmoothing: 'grayscale',
})

globalStyle('#root', {
  height: '100%',
  background: 'inherit',
  display: 'flex',
  flexDirection: 'column',
})

globalStyle('button', {
  cursor: 'pointer',
  border: 'none',
  background: 'none',
  font: 'inherit',
})

globalStyle('input, select, textarea', {
  font: 'inherit',
  outline: 'none',
})

globalStyle('a', {
  color: 'inherit',
  textDecoration: 'none',
})

// Recognition rebrand: foco usa ciano primário (era rgba purple)
globalStyle(':focus-visible', {
  outline: '2px solid rgba(6, 182, 212, 0.6)', // allow: primary focus ring
  outlineOffset: '2px',
})

globalStyle('::-webkit-scrollbar', {
  width: '6px',
  height: '6px',
})

globalStyle('::-webkit-scrollbar-track', {
  background: 'transparent',
})

// Recognition rebrand: scrollbar usa ciano primário (era rgba purple)
globalStyle('::-webkit-scrollbar-thumb', {
  background: 'rgba(6, 182, 212, 0.25)', // allow: scrollbar primary
  borderRadius: '3px',
})

globalStyle('::-webkit-scrollbar-thumb:hover', {
  background: 'rgba(6, 182, 212, 0.45)', // allow: scrollbar primary hover
})
