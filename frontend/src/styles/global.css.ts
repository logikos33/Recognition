/**
 * Global styles — CSS reset and base typography.
 * Import this once in main.tsx.
 *
 * Sprint 1: purple rgba substituído por valores do tema recognition-dark
 * (primary: #06b6d4). CSS vars de tema não estão disponíveis aqui pois
 * este arquivo roda antes da classe de tema ser aplicada.
 */
import { globalStyle } from '@vanilla-extract/css'

globalStyle('*, *::before, *::after', {
  boxSizing: 'border-box',
  margin: 0,
  padding: 0,
})

globalStyle('html, body', {
  height: '100%',
  WebkitFontSmoothing: 'antialiased',
  MozOsxFontSmoothing: 'grayscale',
})

globalStyle('#root', {
  height: '100%',
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
