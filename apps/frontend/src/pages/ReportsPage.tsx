/**
 * ReportsPage — placeholder for reports module.
 */
import { FileBarChart } from 'lucide-react'
import { vars } from '../styles/theme.css'

export function ReportsPage() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', flex: 1, gap: 16, color: vars.color.textMuted }}>
      <FileBarChart size={48} />
      <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: vars.color.textSecondary }}>Relatorios</h2>
      <p style={{ margin: 0, fontSize: 14 }}>Em breve — export Excel, graficos de tendencia, compliance reports.</p>
    </div>
  )
}
