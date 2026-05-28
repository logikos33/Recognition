import { style } from '@vanilla-extract/css'
import { vars } from '../../../styles/theme.css'

export const card = style({
  background: vars.color.bgCard,
  borderRadius: vars.radius.lg,
  border: `1px solid ${vars.color.borderDefault}`,
  overflow: 'hidden',
  transition: `border-color ${vars.animation.duration} ${vars.animation.easing}`,
})

export const cardHoverable = style([card, {
  ':hover': {
    borderColor: vars.color.borderStrong,
  },
}])

export const cardHeader = style({
  padding: `${vars.space.md} ${vars.space.lg}`,
  borderBottom: `1px solid ${vars.color.borderSubtle}`,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: vars.space.md,
})

export const cardBody = style({
  padding: vars.space.lg,
})

export const cardFooter = style({
  padding: `${vars.space.md} ${vars.space.lg}`,
  borderTop: `1px solid ${vars.color.borderSubtle}`,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'flex-end',
  gap: vars.space.sm,
})

export const cardTitle = style({
  fontFamily: vars.font.sans,
  fontWeight: 600,
  fontSize: '15px',
  color: vars.color.textPrimary,
  margin: 0,
})

export const cardDescription = style({
  fontFamily: vars.font.sans,
  fontSize: '13px',
  color: vars.color.textMuted,
  marginTop: vars.space.xs,
})
