import { vars } from '../../../../styles/theme.css'

interface KpiCardProps {
  label: string
  value: string | number
  accentColor?: string
  loading?: boolean
}

export function KpiCard({ label, value, accentColor, loading = false }: KpiCardProps) {
  return (
    <div style={{
      background: vars.color.bgCard,
      border: `1px solid ${vars.color.borderSubtle}`,
      borderRadius: 12,
      padding: '18px 20px',
      flex: 1,
      minWidth: 0,
    }}>
      <div style={{ fontSize: 11, color: vars.color.textSecondary, marginBottom: 6, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</div>
      {loading ? (
        <div style={{
          height: 36, borderRadius: 6,
          background: vars.color.bgHover,
        }} />
      ) : (
        <div style={{ fontSize: 28, fontWeight: 700, color: accentColor ?? vars.color.textPrimary, lineHeight: 1 }}>{value}</div>
      )}
    </div>
  )
}
