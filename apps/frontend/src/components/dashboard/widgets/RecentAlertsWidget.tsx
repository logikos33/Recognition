/**
 * RecentAlertsWidget — últimos 5 alertas (extração 1:1 do Q2 do EpiDashboard).
 */
import { NavLink } from 'react-router-dom'
import { timeAgo, useDashboardAlerts } from './useDashboardAlerts'
import { violationLabel } from './violationLabels'
import { ProcedenciaBadge } from '../../shared/ProcedenciaBadge'
import { WidgetContent } from './WidgetShell'
import {
  alertList,
  alertRow,
  alertRowBody,
  alertRowCamera,
  alertRowTime,
  alertRowViolation,
  viewAllLink,
} from './widgets.css'

export function RecentAlertsWidget() {
  const query = useDashboardAlerts()
  const recentAlerts = query.alerts.slice(0, 5)

  return (
    <WidgetContent
      loading={query.isLoading}
      error={query.isError}
      empty={!query.isLoading && recentAlerts.length === 0}
      onRetry={() => query.refetch()}
    >
      <div className={alertList}>
        {recentAlerts.map((alert) => (
          <div key={alert.id} className={alertRow}>
            <div className={alertRowBody}>
              <div className={alertRowCamera}>{alert.camera_name ?? alert.camera_id}</div>
              <div className={alertRowViolation}>
                {alert.violations.map((v) => violationLabel(v.class)).join(', ') || '—'}
              </div>
            </div>
            {/* Badge em linha própria: alertRowTime é flexShrink:0 e o Badge é
                nowrap (~130px) — inline empurraria o corpo do card. */}
            <div className={alertRowTime}>
              <div>{timeAgo(alert.timestamp ?? alert.created_at)}</div>
              <ProcedenciaBadge capturadoEm={alert.timestamp} gravadoEm={alert.created_at} />
            </div>
          </div>
        ))}
      </div>

      <NavLink to="/epi/alerts" className={viewAllLink}>
        Ver todos →
      </NavLink>
    </WidgetContent>
  )
}
