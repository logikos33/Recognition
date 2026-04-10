import { style } from '@vanilla-extract/css'
import { vars } from '../styles/theme.css'

export const page = style({ padding: vars.space.lg, maxWidth: '1200px', margin: '0 auto' })

export const pageHeader = style({ marginBottom: vars.space.lg })

export const pageTitle = style({
  fontSize: '22px', fontWeight: 700, color: vars.color.textPrimary, margin: 0,
})

export const pageSubtitle = style({
  fontSize: '13px', color: vars.color.textMuted, margin: '4px 0 0',
})

export const cardsGrid = style({
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
  gap: '12px',
  marginBottom: vars.space.lg,
})

export const reportCard = style({
  background: vars.color.bgCard, borderRadius: vars.radius.lg,
  padding: '20px 24px', display: 'flex', alignItems: 'center', gap: vars.space.md,
  border: `1px solid ${vars.color.borderDefault}`,
})

export const reportIconBox = style({
  width: '44px', height: '44px', borderRadius: vars.radius.md,
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  fontSize: '22px', flexShrink: 0,
})

export const reportLabel = style({
  fontSize: '12px', color: vars.color.textSecondary, marginBottom: '2px',
})

export const reportValue = style({
  fontSize: '24px', fontWeight: 700, color: vars.color.textPrimary,
})

export const reportSub = style({ fontSize: '11px', color: vars.color.textMuted })

export const chartCard = style({
  background: vars.color.bgCard, borderRadius: vars.radius.lg,
  padding: vars.space.lg, marginBottom: vars.space.lg,
  border: `1px solid ${vars.color.borderDefault}`,
})

export const chartTitle = style({
  fontSize: '14px', fontWeight: 600, color: vars.color.textPrimary, marginBottom: vars.space.md,
})

export const chartEmpty = style({
  color: vars.color.textDim, fontSize: '13px', textAlign: 'center', padding: '24px 0',
})

export const chartBars = style({ display: 'flex', alignItems: 'flex-end', gap: '3px', height: '80px' })

export const chartBar = style({
  flex: 1, minWidth: '4px', borderRadius: '2px 2px 0 0',
  background: vars.color.purple500, cursor: 'default',
})

export const modulesSection = style({ marginBottom: vars.space.md })

export const modulesSectionTitle = style({
  fontSize: '16px', fontWeight: 600, color: vars.color.textPrimary, margin: `0 0 ${vars.space.md}`,
})

export const modulesGrid = style({
  display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: vars.space.md,
})

export const moduleCard = style({
  background: vars.color.bgCard, borderRadius: vars.radius.lg, padding: vars.space.lg,
  border: `1px solid ${vars.color.borderDefault}`,
  transition: `border-color ${vars.animation.duration}`,
  ':hover': { borderColor: vars.color.borderStrong },
})

export const moduleCardClickable = style([moduleCard, { cursor: 'pointer' }])

export const moduleCardDisabled = style([moduleCard, { opacity: 0.7, cursor: 'default' }])

export const moduleCardInner = style({ display: 'flex', alignItems: 'flex-start', gap: vars.space.md })

export const moduleCardTitle = style({ fontWeight: 700, fontSize: '16px', color: vars.color.textPrimary })

export const moduleCardDesc = style({ fontSize: '13px', color: vars.color.textMuted, margin: 0, lineHeight: 1.5, marginTop: '6px' })

export const moduleCardStats = style({
  display: 'flex', gap: vars.space.lg, marginTop: vars.space.md, fontSize: '12px', color: vars.color.textSecondary,
})

export const moduleCardCta = style({ marginTop: vars.space.md, fontSize: '12px', color: vars.color.purple400 })

export const comingSoonBadge = style({
  fontSize: '10px', background: vars.color.bgElevated, color: vars.color.textMuted,
  padding: '2px 6px', borderRadius: vars.radius.sm, marginLeft: '8px',
})

export const loadingBox = style({
  display: 'flex', justifyContent: 'center', alignItems: 'center', height: '300px',
  color: vars.color.textMuted,
})
