/**
 * Theme contract — defines all design tokens used across all themes.
 * Never use hardcoded color values in component files; always reference vars.
 *
 * Sprint 1 (Recognition rebrand): tokens migrated from brand-specific
 * (purple500/cyan400) to semantic (primary/accent) to support white-label.
 */
import { createThemeContract } from '@vanilla-extract/css'

export const vars = createThemeContract({
  color: {
    // Backgrounds
    bgBase: null,      // app background (was bgPrimary)
    bgSurface: null,   // sidebar, topbar, panels
    bgElevated: null,  // modals, dropdowns
    bgCard: null,      // cards, table cells
    bgHover: null,     // hover state for rows/items

    // Text
    textPrimary: null,
    textSecondary: null,
    textMuted: null,
    textDim: null,

    // Primary brand color (tenant-overridable)
    primary: null,       // main action color (was purple500)
    primaryLight: null,  // hover (was purple400)
    primaryDark: null,   // active/pressed (was purple600)
    primaryAlpha: null,  // rgba bg for active states, focus rings

    // Accent — used exclusively for high-severity alerts / safety signals
    accent: null,        // safety orange / alert accent (was cyan400)
    accentLight: null,   // hover on accent
    accentDark: null,    // active on accent
    accentAlpha: null,   // rgba bg for alert states

    // Semantic status
    success: null,
    successMuted: null,
    warning: null,
    warningMuted: null,
    danger: null,
    dangerMuted: null,

    // Borders
    borderSubtle: null,
    borderDefault: null,
    borderStrong: null,
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
    glow: null,       // focus ring / primary glow
    glowCyan: null,   // accent highlight (kept for compat)
    glowDanger: null,
  },

  // Animation control — '1'/'0' to gate CSS animations
  animation: {
    enabled: null,
    duration: null,
    durationSlow: null,
    easing: null,
  },
})
