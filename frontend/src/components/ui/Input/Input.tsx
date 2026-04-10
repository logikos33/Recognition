import { forwardRef, type InputHTMLAttributes, type ReactNode } from 'react'
import { input, inputError, label, errorText, fieldWrapper } from './Input.css'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  error?: string
}

interface FieldProps {
  label?: string
  error?: string
  children: ReactNode
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ error, className, ...props }, ref) => (
    <input
      ref={ref}
      className={`${error ? inputError : input}${className ? ` ${className}` : ''}`}
      {...props}
    />
  )
)
Input.displayName = 'Input'

export function Field({ label: labelText, error, children }: FieldProps) {
  return (
    <div className={fieldWrapper}>
      {labelText && <label className={label}>{labelText}</label>}
      {children}
      {error && <span className={errorText}>{error}</span>}
    </div>
  )
}
