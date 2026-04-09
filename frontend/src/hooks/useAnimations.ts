/**
 * Returns Framer Motion variants and transition conditioned on the active theme.
 * In professional mode all variants are empty so components render instantly.
 */
import type { Variants, Transition } from 'framer-motion'
import { useThemeStore } from '../stores/themeStore'

export interface AnimationSet {
  isEnabled: boolean
  fadeIn: Variants
  scaleIn: Variants
  slideIn: Variants
  transition: Transition
  transitionSlow: Transition
}

export function useAnimations(): AnimationSet {
  const isEnabled = useThemeStore((s) => s.isAnimationsEnabled())

  const transition: Transition = isEnabled
    ? { duration: 0.25, ease: [0.4, 0, 0.2, 1] }
    : { duration: 0 }

  const transitionSlow: Transition = isEnabled
    ? { duration: 0.5, ease: [0.4, 0, 0.2, 1] }
    : { duration: 0 }

  const fadeIn: Variants = isEnabled
    ? {
        initial: { opacity: 0, y: 12 },
        animate: { opacity: 1, y: 0 },
        exit: { opacity: 0, y: -8 },
      }
    : { initial: {}, animate: {}, exit: {} }

  const scaleIn: Variants = isEnabled
    ? {
        initial: { opacity: 0, scale: 0.96 },
        animate: { opacity: 1, scale: 1 },
        exit: { opacity: 0, scale: 0.96 },
      }
    : { initial: {}, animate: {}, exit: {} }

  const slideIn: Variants = isEnabled
    ? {
        initial: { opacity: 0, x: -16 },
        animate: { opacity: 1, x: 0 },
        exit: { opacity: 0, x: -16 },
      }
    : { initial: {}, animate: {}, exit: {} }

  return { isEnabled, fadeIn, scaleIn, slideIn, transition, transitionSlow }
}
