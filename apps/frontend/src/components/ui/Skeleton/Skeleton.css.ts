import { style, keyframes } from '@vanilla-extract/css'
import { recipe } from '@vanilla-extract/recipes'
import { vars } from '../../../styles/theme.css'

const shimmer = keyframes({
  '0%': { backgroundPosition: '-200% 0' },
  '100%': { backgroundPosition: '200% 0' },
})

export const skeleton = recipe({
  base: {
    background: `linear-gradient(90deg, ${vars.color.bgElevated} 25%, ${vars.color.bgHover} 50%, ${vars.color.bgElevated} 75%)`,
    backgroundSize: '200% 100%',
    animation: `${shimmer} 1.5s ease-in-out infinite`,
    borderRadius: vars.radius.sm,
  },
  variants: {
    variant: {
      text: { height: '1em', width: '100%' },
      title: { height: '1.5em', width: '60%' },
      circle: { borderRadius: vars.radius.full, width: 40, height: 40 },
      rect: { width: '100%', height: 120 },
    },
  },
  defaultVariants: { variant: 'text' },
})

export const skeletonGroup = style({
  display: 'flex',
  flexDirection: 'column',
  gap: vars.space.sm,
})
