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
    status: {
      active: {
        background: vars.color.successMuted,
        color: vars.color.success,
      },
      inactive: {
        background: vars.color.bgElevated,
        color: vars.color.textMuted,
      },
      error: {
        background: vars.color.dangerMuted,
        color: vars.color.danger,
      },
      warning: {
        background: 'rgba(245, 158, 11, 0.15)',
        color: vars.color.warning,
      },
      running: {
        background: 'rgba(139, 92, 246, 0.15)',
        color: vars.color.purple400,
      },
      starting: {
        background: 'rgba(245, 158, 11, 0.15)',
        color: vars.color.warning,
      },
      pending: {
        background: vars.color.bgElevated,
        color: vars.color.textMuted,
      },
      completed: {
        background: vars.color.successMuted,
        color: vars.color.success,
      },
      failed: {
        background: vars.color.dangerMuted,
        color: vars.color.danger,
      },
      stopped: {
        background: vars.color.bgElevated,
        color: vars.color.textMuted,
      },
      online: {
        background: vars.color.successMuted,
        color: vars.color.success,
      },
      offline: {
        background: vars.color.bgElevated,
        color: vars.color.textMuted,
      },
    },
  },

  defaultVariants: {
    status: 'inactive',
  },
})
