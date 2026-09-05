/**
 * EventLogWidget — tabela dos últimos eventos (extração 1:1 do Q3 do EpiDashboard).
 */
import { NavLink } from 'react-router-dom'
import { timeAgo, useDashboardAlerts } from './useDashboardAlerts'
import { violationLabel } from './violationLabels'
import { ProcedenciaEvento } from '../../shared/ProcedenciaEvento'
import { WidgetContent } from './WidgetShell'
import {
  eventRowAcknowledged,
  eventTable,
  eventTableWrap,
  eventTd,
  eventTh,
  viewAllLink,
} from './widgets.css'

export function EventLogWidget() {
  const query = useDashboardAlerts()
  const eventAlerts = query.alerts.slice(0, 8)

  return (
    <WidgetContent
      loading={query.isLoading}
      error={query.isError}
      empty={!query.isLoading && eventAlerts.length === 0}
      onRetry={() => query.refetch()}
    >
      <div className={eventTableWrap}>
        <table className={eventTable}>
          <thead>
            <tr>
              <th className={eventTh}>Câmera</th>
              <th className={eventTh}>Violação</th>
              <th className={eventTh}>Confiança</th>
              <th className={eventTh}>Horário</th>
            </tr>
          </thead>
          <tbody>
            {eventAlerts.map((alert) => {
              const firstViolation = alert.violations[0]
              return (
                <tr
                  key={alert.id}
                  className={alert.acknowledged ? eventRowAcknowledged : undefined}
                >
                  <td className={eventTd}>
                    <NavLink to={`/epi/alerts/${alert.id}`} style={{ color: 'inherit' }}>
                      {alert.camera_name ?? alert.camera_id}
                    </NavLink>
                  </td>
                  <td className={eventTd}>
                    {firstViolation ? violationLabel(firstViolation.class) : '—'}
                  </td>
                  <td className={eventTd}>
                    {firstViolation
                      ? `${Math.round(firstViolation.confidence * 100)}%`
                      : '—'}
                  </td>
                  <td className={eventTd}>
                    {timeAgo(alert.timestamp ?? alert.created_at)}{' '}
                    {/* Origem DECLARADA primeiro, atraso captura→gravação só como
                        fallback (issue #670): 4.609 dos 5.174 eventos do DEV têm
                        caixa desenhada por PESSOA e o critério temporal não acende
                        neles — o widget apresentava anotação humana como detecção. */}
                    <ProcedenciaEvento
                      violations={alert.violations}
                      capturadoEm={alert.timestamp}
                      gravadoEm={alert.created_at}
                    />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <NavLink to="/epi/alerts" className={viewAllLink}>
        Ver histórico completo →
      </NavLink>
    </WidgetContent>
  )
}
