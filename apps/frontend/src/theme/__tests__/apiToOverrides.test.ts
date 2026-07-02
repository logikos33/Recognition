/**
 * Testes do mapeamento API (flat snake_case) → TenantThemeOverrides (WS1).
 */
import { describe, it, expect } from 'vitest'
import { apiToOverrides } from '../ThemeProvider'

describe('apiToOverrides', () => {
  it('mapeia campos de marca e cores', () => {
    const o = apiToOverrides({
      product_name: 'AcmeCo',
      logo_url: 'http://cdn/logo.png',
      favicon_url: 'http://cdn/fav.png',
      color_primary: '#16a34a',
      color_secondary: '#f59e0b',
    })
    expect(o.brand.productName).toBe('AcmeCo')
    expect(o.brand.logoUrl).toBe('http://cdn/logo.png')
    expect(o.brand.faviconUrl).toBe('http://cdn/fav.png')
    expect(o.colors?.primary).toBe('#16a34a')
    expect(o.colors?.accent).toBe('#f59e0b')
  })

  it('mapeia os 7 campos de surfaces (snake_case → camelCase)', () => {
    const o = apiToOverrides({
      color_bg_base: '#101014',
      color_bg_surface: '#16161c',
      color_bg_elevated: '#20202a',
      color_bg_card: '#18181f',
      color_text_primary: '#ffffff',
      color_text_secondary: '#aabbcc',
      color_border: '#2a2a35',
    })
    expect(o.surfaces).toEqual({
      bgBase: '#101014',
      bgSurface: '#16161c',
      bgElevated: '#20202a',
      bgCard: '#18181f',
      textPrimary: '#ffffff',
      textSecondary: '#aabbcc',
      border: '#2a2a35',
    })
  })

  it('campos ausentes/null → undefined (não sobrescreve o tema base)', () => {
    const o = apiToOverrides({ product_name: null, color_primary: null })
    expect(o.brand.productName).toBe('Recognition')
    expect(o.colors?.primary).toBeUndefined()
    expect(o.surfaces?.bgBase).toBeUndefined()
  })
})
