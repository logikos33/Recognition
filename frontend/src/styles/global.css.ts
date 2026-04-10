/**
 * Global styles — CSS reset and base typography.
 * Import this once in main.tsx.
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

globalStyle(':focus-visible', {
  outline: '2px solid rgba(139, 92, 246, 0.6)',
  outlineOffset: '2px',
})

globalStyle('::-webkit-scrollbar', {
  width: '6px',
  height: '6px',
})

globalStyle('::-webkit-scrollbar-track', {
  background: 'transparent',
})

globalStyle('::-webkit-scrollbar-thumb', {
  background: 'rgba(139, 92, 246, 0.3)',
  borderRadius: '3px',
})

globalStyle('::-webkit-scrollbar-thumb:hover', {
  background: 'rgba(139, 92, 246, 0.5)',
})
