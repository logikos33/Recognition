/**
 * Ícones SVG proprietários para os 4 tipos canônicos de operação.
 * Retornam JSX inline para uso em cards do catálogo.
 */

interface IconProps {
  size?: number
  color?: string
}

export function PositionIcon({ size = 24, color = 'currentColor' }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="3" fill={color} />
      <path
        d="M12 2v4M12 18v4M2 12h4M18 12h4"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
      />
      <rect x="5" y="5" width="14" height="14" rx="2" stroke={color} strokeWidth="1.5" strokeDasharray="3 2" />
    </svg>
  )
}

export function OverlapFixedIcon({ size = 24, color = 'currentColor' }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="3" y="6" width="14" height="14" rx="2" stroke={color} strokeWidth="1.5" />
      <rect x="9" y="4" width="12" height="10" rx="2" fill={color} fillOpacity="0.15" stroke={color} strokeWidth="1.5" />
      <path d="M9 10h5v4H9z" fill={color} fillOpacity="0.4" />
    </svg>
  )
}

export function OverlapDynamicIcon({ size = 24, color = 'currentColor' }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="9" cy="12" r="5" stroke={color} strokeWidth="1.5" fill={color} fillOpacity="0.1" />
      <circle cx="15" cy="12" r="5" stroke={color} strokeWidth="1.5" fill={color} fillOpacity="0.1" />
      <path d="M12 8.5c1.2 1 2 2.1 2 3.5s-.8 2.5-2 3.5" stroke={color} strokeWidth="1" strokeDasharray="2 1" />
      <path d="M12 8.5c-1.2 1-2 2.1-2 3.5s.8 2.5 2 3.5" stroke={color} strokeWidth="1" strokeDasharray="2 1" />
      <path d="M5 12h2M17 12h2" stroke={color} strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}

export function CountStaticIcon({ size = 24, color = 'currentColor' }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="3" y="3" width="18" height="18" rx="2" stroke={color} strokeWidth="1.5" strokeDasharray="3 2" />
      <circle cx="8" cy="9" r="1.5" fill={color} />
      <circle cx="12" cy="9" r="1.5" fill={color} />
      <circle cx="16" cy="9" r="1.5" fill={color} />
      <circle cx="8" cy="15" r="1.5" fill={color} />
      <circle cx="12" cy="15" r="1.5" fill={color} />
      <text x="14.5" y="17" fontSize="7" fill={color} fontWeight="bold">+</text>
    </svg>
  )
}

export function getOperationIcon(typeId: string, props?: IconProps) {
  switch (typeId) {
    case 'position': return <PositionIcon {...props} />
    case 'overlap_fixed': return <OverlapFixedIcon {...props} />
    case 'overlap_dynamic': return <OverlapDynamicIcon {...props} />
    case 'count_static': return <CountStaticIcon {...props} />
    default: return <PositionIcon {...props} />
  }
}
