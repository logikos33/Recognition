/** Status badge component. */

const COLORS: Record<string, { bg: string; text: string }> = {
  active:    { bg: '#dcfce7', text: '#16a34a' },
  running:   { bg: '#dbeafe', text: '#2563eb' },
  completed: { bg: '#dcfce7', text: '#16a34a' },
  pending:   { bg: '#fef3c7', text: '#d97706' },
  error:     { bg: '#fef2f2', text: '#dc2626' },
  failed:    { bg: '#fef2f2', text: '#dc2626' },
  stopped:   { bg: '#f1f5f9', text: '#64748b' },
  inactive:  { bg: '#f1f5f9', text: '#64748b' },
  uploaded:  { bg: '#dbeafe', text: '#2563eb' },
  extracting:{ bg: '#fef3c7', text: '#d97706' },
  extracted: { bg: '#dcfce7', text: '#16a34a' },
  starting:  { bg: '#fef3c7', text: '#d97706' },
}

export function StatusBadge({ status }: { status: string }) {
  const colors = COLORS[status] || COLORS.inactive
  return (
    <span style={{
      padding: '2px 10px', borderRadius: 6, fontSize: 11, fontWeight: 700,
      background: colors.bg, color: colors.text, textTransform: 'uppercase',
    }}>
      {status}
    </span>
  )
}
