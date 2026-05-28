import { Check } from 'lucide-react'
import { stepper, stepItem, stepConnector, stepCircle, stepLabel } from './Stepper.css'

interface Step {
  label: string
}

interface StepperProps {
  steps: Step[]
  current: number
  orientation?: 'horizontal' | 'vertical'
}

export function Stepper({ steps, current, orientation = 'horizontal' }: StepperProps) {
  return (
    <div className={stepper({ orientation })} aria-label="Progresso">
      {steps.map((step, i) => {
        const state = i < current ? 'completed' : i === current ? 'active' : 'pending'
        return (
          <div key={i} className={stepItem} data-orientation={orientation}>
            <div className={stepCircle({ state })} aria-current={state === 'active' ? 'step' : undefined}>
              {state === 'completed' ? <Check size={12} /> : i + 1}
            </div>
            <span className={stepLabel}>{step.label}</span>
            {i < steps.length - 1 && <div className={stepConnector} />}
          </div>
        )
      })}
    </div>
  )
}
