/**
 * Theme contract — defines all design tokens used across both themes.
 * Never use hardcoded color values in component files; always reference vars.
 */
import { createThemeContract } from '@vanilla-extract/css'

export const vars = createThemeContract({
  color: {
    // Backgrounds
    bgPrimary: null,
    bgSurface: null,
    bgElevated: null,
    bgCard: null,
    bgHover: null,

    // Text
    textPrimary: null,
    textSecondary: null,
    textMuted: null,
    textDim: null,

    // Brand accents
    purple400: null,
    purple500: null,
    purple600: null,
    cyan400: null,
    cyan500: null,

    // Semantic
    success: null,
    successMuted: null,
    warning: null,
    danger: null,
    dangerMuted: null,

    // Borders
    borderSubtle: null,
    borderDefault: null,
    borderStrong: null,
    borderGlow: null,
  },

  space: {
    xs: null,
    sm: null,
    md: null,
    lg: null,
    xl: null,
    xxl: null,
  },

  radius: {
    sm: null,
    md: null,
    lg: null,
    xl: null,
    full: null,
  },

  font: {
    sans: null,
    mono: null,
  },

  shadow: {
    sm: null,
    md: null,
    lg: null,
    glow: null,
    glowCyan: null,
    glowDanger: null,
  },

  // Animation control — '1'/'0' to gate CSS animations, duration '0.3s'/'0s'
  animation: {
    enabled: null,
    duration: null,
    durationSlow: null,
    easing: null,
  },
})
