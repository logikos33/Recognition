import type { CSSProperties } from 'react'
import { skeleton, skeletonGroup } from './Skeleton.css'

interface SkeletonProps {
  variant?: 'text' | 'title' | 'circle' | 'rect'
  width?: number | string
  height?: number | string
  className?: string
  style?: CSSProperties
}

export function Skeleton({ variant = 'text', width, height, className, style }: SkeletonProps) {
  return (
    <div
      className={`${skeleton({ variant })}${className ? ` ${className}` : ''}`}
      style={{ width, height, ...style }}
      aria-hidden="true"
    />
  )
}

export function SkeletonGroup({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`${skeletonGroup}${className ? ` ${className}` : ''}`}>
      {children}
    </div>
  )
}
