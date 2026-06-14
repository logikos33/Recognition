import { recipe } from '@vanilla-extract/recipes'
import { vars } from '../../../styles/theme.css'

export const badge = recipe({
  base: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '5px',
    fontFamily: vars.font.sans,
    fontWeight: 700,
    fontSize: '11px',
    letterSpacing: '0.04em',
    textTransform: 'uppercase',
    borderRadius: vars.radius.full,
    padding: `3px 10px`,
    whiteSpace: 'nowrap',
  },

  variants: {
    variant: {
      success: {
        background: vars.color.successMuted,
        color: vars.color.success,
      },
      warning: {
        background: vars.color.warningMuted,
        color: vars.color.warning,
      },
      danger: {
        background: vars.color.dangerMuted,
        color: vars.color.danger,
      },
      primary: {
        background: vars.color.primaryAlpha,
        color: vars.color.primaryLight,
      },
      neutral: {
        background: vars.color.bgElevated,
        color: vars.color.textMuted,
      },
      accent: {
        background: vars.color.accentAlpha,
        color: vars.color.accentLight,
      },
    },
  },

  defaultVariants: { variant: 'neutral' },
})
