import { recipe } from '@vanilla-extract/recipes'
import { vars } from '../../../styles/theme.css'

export const button = recipe({
  base: {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: vars.space.sm,
    fontFamily: vars.font.sans,
    fontWeight: 600,
    borderRadius: vars.radius.md,
    border: 'none',
    cursor: 'pointer',
    transition: `background ${vars.animation.duration} ${vars.animation.easing}, box-shadow ${vars.animation.duration} ${vars.animation.easing}, opacity ${vars.animation.duration}`,
    ':disabled': {
      opacity: 0.45,
      cursor: 'not-allowed',
    },
  },

  variants: {
    variant: {
      primary: {
        background: vars.color.primary,
        color: '#fff',
        ':hover': {
          background: vars.color.primaryDark,
          boxShadow: vars.shadow.glow,
        },
      },
      secondary: {
        background: vars.color.bgElevated,
        color: vars.color.textSecondary,
        border: `1px solid ${vars.color.borderDefault}`,
        ':hover': {
          background: vars.color.bgHover,
          color: vars.color.textPrimary,
          borderColor: vars.color.borderStrong,
        },
      },
      danger: {
        background: vars.color.danger,
        color: '#fff',
        ':hover': {
          boxShadow: vars.shadow.glowDanger,
          filter: 'brightness(1.1)',
        },
      },
      ghost: {
        background: 'transparent',
        color: vars.color.textMuted,
        ':hover': {
          background: vars.color.bgHover,
          color: vars.color.textPrimary,
        },
      },
      success: {
        background: vars.color.success,
        color: '#fff',
        ':hover': {
          filter: 'brightness(1.1)',
        },
      },
    },

    size: {
      sm: {
        fontSize: '12px',
        padding: `${vars.space.xs} ${vars.space.sm}`,
        height: '28px',
      },
      md: {
        fontSize: '14px',
        padding: `${vars.space.sm} ${vars.space.md}`,
        height: '36px',
      },
      lg: {
        fontSize: '15px',
        padding: `${vars.space.sm} ${vars.space.lg}`,
        height: '42px',
      },
    },
  },

  defaultVariants: {
    variant: 'secondary',
    size: 'md',
  },
})
