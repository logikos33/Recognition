import { recipe } from '@vanilla-extract/recipes'
import { style } from '@vanilla-extract/css'
import { vars } from '../../../styles/theme.css'

export const banner = recipe({
  base: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: vars.space.sm,
    padding: `${vars.space.sm} ${vars.space.md}`,
    borderRadius: vars.radius.md,
    border: '1px solid',
    fontFamily: vars.font.sans,
    fontSize: '13px',
  },
  variants: {
    variant: {
      info: {
        background: vars.color.primaryAlpha,
        borderColor: vars.color.primary,
        color: vars.color.primary,
      },
      success: {
        background: vars.color.successMuted,
        borderColor: vars.color.success,
        color: vars.color.success,
      },
      warning: {
        background: vars.color.warningMuted,
        borderColor: vars.color.warning,
        color: vars.color.warning,
      },
      danger: {
        background: vars.color.dangerMuted,
        borderColor: vars.color.danger,
        color: vars.color.danger,
      },
    },
  },
  defaultVariants: { variant: 'info' },
})

export const bannerMessage = style({
  flex: 1,
  color: vars.color.textSecondary,
  lineHeight: 1.5,
})

export const bannerClose = style({
  background: 'none',
  border: 'none',
  cursor: 'pointer',
  padding: 0,
  color: 'inherit',
  opacity: 0.6,
  ':hover': { opacity: 1 },
  flexShrink: 0,
})
