import { useState, useEffect, useRef } from 'react'
import { vars } from '../../../../styles/theme.css'

interface StepTimerProps {
  startedAt: string | null
  warn?: boolean
}

function elapsed(startedAt: string): string {
  const diff = Math.max(0, Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000))
  const h = Math.floor(diff / 3600)
  const m = Math.floor((diff % 3600) / 60)
  const s = diff % 60
  if (h > 0) return `${h}h ${String(m).padStart(2, '0')}m`
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

export function StepTimer({ startedAt, warn = false }: StepTimerProps) {
  const [display, setDisplay] = useState(() => (startedAt ? elapsed(startedAt) : '—'))
  const timer = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (!startedAt) { setDisplay('—'); return }
    setDisplay(elapsed(startedAt))
    timer.current = setInterval(() => setDisplay(elapsed(startedAt)), 1000)
    return () => { if (timer.current) clearInterval(timer.current) }
  }, [startedAt])

  return (
    <span style={{ color: warn ? vars.color.warning : vars.color.textPrimary, fontVariantNumeric: 'tabular-nums' }}>
      {display}
    </span>
  )
}
