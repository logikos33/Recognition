import type { ReactNode, HTMLAttributes } from 'react'
import { card, cardHoverable, cardHeader, cardBody, cardFooter, cardTitle, cardDescription } from './Card.css'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  hoverable?: boolean
  children: ReactNode
}

export function Card({ hoverable, className, children, ...props }: CardProps) {
  const base = hoverable ? cardHoverable : card
  return (
    <div className={`${base}${className ? ` ${className}` : ''}`} {...props}>
      {children}
    </div>
  )
}

export function CardHeader({ className, children, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={`${cardHeader}${className ? ` ${className}` : ''}`} {...props}>{children}</div>
}

export function CardBody({ className, children, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={`${cardBody}${className ? ` ${className}` : ''}`} {...props}>{children}</div>
}

export function CardFooter({ className, children, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={`${cardFooter}${className ? ` ${className}` : ''}`} {...props}>{children}</div>
}

export function CardTitle({ className, children, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={`${cardTitle}${className ? ` ${className}` : ''}`} {...props}>{children}</h3>
}

export function CardDescription({ className, children, ...props }: HTMLAttributes<HTMLParagraphElement>) {
  return <p className={`${cardDescription}${className ? ` ${className}` : ''}`} {...props}>{children}</p>
}
