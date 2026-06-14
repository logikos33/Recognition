import { forwardRef, type InputHTMLAttributes, type ReactNode } from 'react'
import {
  input, inputError, inputWithLeading, inputWithTrailing, inputWithBoth,
  label, errorText, fieldWrapper, inputWrapper, iconLeading, iconTrailing,
} from './Input.css'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  error?: string
  leadingIcon?: ReactNode
  trailingIcon?: ReactNode
}

interface FieldProps {
  label?: string
  error?: string
  children: ReactNode
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ error, leadingIcon, trailingIcon, className, ...props }, ref) => {
    const hasLeading = Boolean(leadingIcon)
    const hasTrailing = Boolean(trailingIcon)

    let inputClass = error ? inputError : input
    if (hasLeading && hasTrailing) inputClass = inputWithBoth
    else if (hasLeading) inputClass = inputWithLeading
    else if (hasTrailing) inputClass = inputWithTrailing

    if (!hasLeading && !hasTrailing) {
      return (
        <input
          ref={ref}
          className={`${inputClass}${className ? ` ${className}` : ''}`}
          {...props}
        />
      )
    }

    return (
      <div className={inputWrapper}>
        {hasLeading && <span className={iconLeading}>{leadingIcon}</span>}
        <input
          ref={ref}
          className={`${inputClass}${className ? ` ${className}` : ''}`}
          {...props}
        />
        {hasTrailing && <span className={iconTrailing}>{trailingIcon}</span>}
      </div>
    )
  }
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
