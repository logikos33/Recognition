import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { button } from './Button.css'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost' | 'success'
  size?: 'sm' | 'md' | 'lg'
  children: ReactNode
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'secondary', size = 'md', className, children, ...props }, ref) => (
    <button
      ref={ref}
      className={`${button({ variant, size })}${className ? ` ${className}` : ''}`}
      {...props}
    >
      {children}
    </button>
  )
)

Button.displayName = 'Button'
