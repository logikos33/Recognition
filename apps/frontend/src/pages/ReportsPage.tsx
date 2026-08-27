/**
 * ⚠️ SUPERADA — esta tela tem substituta no front novo.
 *
 * @migrado-para src/app/epi/Relatorios.tsx
 * rota nova: /novo/epi/relatorios
 *
 * Continua VIVA e servindo a rota antiga: os dois fronts convivem até a
 * migração terminar (decisão do Vitor, 27/08). Não apague nesta rodada.
 *
 * Na rodada de remoção, ANTES de apagar: a substituta foi provada renderizando
 * com dado real no DEV, mas paridade de FUNCIONALIDADE não foi conferida item a
 * item. Compare as duas telas primeiro — e confira quem mais importa deste
 * arquivo (componentes e estilos só dele saem junto; os compartilhados, não).
 * A lista está em docs/migration/MANIFESTO-FRONT-ANTIGO.md.
 */
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
