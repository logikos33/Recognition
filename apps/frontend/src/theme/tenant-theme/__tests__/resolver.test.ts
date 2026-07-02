/**
 * Testes do resolver de tema por tenant (WS1).
 */
import { describe, it, expect } from 'vitest'
import { resolveTheme, darkenHex, lightenHex } from '../resolver'

describe('darkenHex / lightenHex', () => {
  it('escurece cada canal com clamp em 0', () => {
    expect(darkenHex('#06b6d4')).toBe('#0098b6')
    expect(darkenHex('#000000')).toBe('#000000')
  })

  it('clareia cada canal com clamp em 255', () => {
    expect(lightenHex('#06b6d4')).toBe('#24d4f2')
    expect(lightenHex('#ffffff')).toBe('#ffffff')
  })
})

describe('resolveTheme', () => {
  it('sem overrides → nenhuma CSS var (tema base intacto)', () => {
    const { cssVars } = resolveTheme({ brand: {} })
    expect(Object.keys(cssVars)).toEqual([])
  })

  it('primary gera light/dark/alpha/glow derivados', () => {
    const { cssVars } = resolveTheme({ brand: {}, colors: { primary: '#16a34a' } })
    expect(cssVars['--color-primary']).toBe('#16a34a')
    expect(cssVars['--color-primary-light']).toBe(lightenHex('#16a34a'))
    expect(cssVars['--color-primary-dark']).toBe(darkenHex('#16a34a'))
    expect(cssVars['--color-primary-alpha']).toBe('rgba(22, 163, 74, 0.1)')
    expect(cssVars['--shadow-glow']).toBe('0 0 0 3px rgba(22, 163, 74, 0.12)')
    // não vaza para surfaces
    expect(cssVars['--color-bg-surface']).toBeUndefined()
  })

  it('primaryHover explícito vence o derivado', () => {
    const { cssVars } = resolveTheme({
      brand: {},
      colors: { primary: '#16a34a', primaryHover: '#15803d' },
    })
    expect(cssVars['--color-primary-light']).toBe('#15803d')
  })

  it('accent gera light/dark/alpha derivados', () => {
    const { cssVars } = resolveTheme({ brand: {}, colors: { accent: '#f59e0b' } })
    expect(cssVars['--color-accent']).toBe('#f59e0b')
    expect(cssVars['--color-accent-light']).toBe(lightenHex('#f59e0b'))
    expect(cssVars['--color-accent-dark']).toBe(darkenHex('#f59e0b'))
    expect(cssVars['--color-accent-alpha']).toBe('rgba(245, 158, 11, 0.12)')
  })

  it('surfaces: só as chaves customizadas sobrescrevem', () => {
    const { cssVars } = resolveTheme({
      brand: {},
      surfaces: { bgElevated: '#20202a' },
    })
    expect(cssVars['--color-bg-elevated']).toBe('#20202a')
    expect(cssVars['--color-bg-base']).toBeUndefined()
    expect(cssVars['--color-bg-surface']).toBeUndefined()
    expect(cssVars['--color-text-primary']).toBeUndefined()
  })

  it('bgSurface deriva bgHover; textSecondary deriva textMuted; border deriva subtle/strong', () => {
    const { cssVars } = resolveTheme({
      brand: {},
      surfaces: {
        bgSurface: '#16161c',
        textSecondary: '#aabbcc',
        border: '#2a2a35',
      },
    })
    expect(cssVars['--color-bg-surface']).toBe('#16161c')
    expect(cssVars['--color-bg-hover']).toBe(lightenHex('#16161c', 10))
    expect(cssVars['--color-text-secondary']).toBe('#aabbcc')
    expect(cssVars['--color-text-muted']).toBe(darkenHex('#aabbcc', 24))
    expect(cssVars['--color-border']).toBe('#2a2a35')
    expect(cssVars['--color-border-subtle']).toBe(darkenHex('#2a2a35', 10))
    expect(cssVars['--color-border-strong']).toBe(lightenHex('#2a2a35', 18))
  })
})
