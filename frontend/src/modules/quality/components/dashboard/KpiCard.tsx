interface KpiCardProps {
  label: string
  value: string | number
  color?: string
  loading?: boolean
}

export function KpiCard({ label, value, color = '#111827', loading = false }: KpiCardProps) {
  return (
    <div style={{
      background: '#F9FAFB',
      border: '1px solid #E5E7EB',
      borderRadius: 12,
      padding: '18px 20px',
      flex: 1,
      minWidth: 0,
    }}>
      <div style={{ fontSize: 12, color: '#6B7280', marginBottom: 6, fontWeight: 500 }}>{label}</div>
      {loading ? (
        <div style={{
          height: 36, borderRadius: 6,
          background: 'linear-gradient(90deg,#E5E7EB 25%,#F3F4F6 50%,#E5E7EB 75%)',
          backgroundSize: '200% 100%',
          animation: 'shimmer 1.4s infinite',
        }} />
      ) : (
        <div style={{ fontSize: 32, fontWeight: 700, color, lineHeight: 1 }}>{value}</div>
      )}
    </div>
  )
}
