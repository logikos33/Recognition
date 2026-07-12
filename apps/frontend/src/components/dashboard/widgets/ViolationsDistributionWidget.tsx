/**
 * ViolationsDistributionWidget — donut de violações por classe no período.
 * Fonte: GET /api/v1/events/summary (server-side — substitui a amostra
 * enviesada de 50 alerts da página 1; fecha BUG-7).
 */
import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip as RechartsTooltip } from 'recharts'
import { eventsService } from '../../../services/eventsService'
import { chartSeries } from '../../../theme/chartColors'
import { vars } from '../../../styles/theme.css'
import { rangeForPeriod } from '../../../utils/timeBuckets'
import type { DashboardPeriod } from '../../../stores/dashboardStore'
import { violationLabel } from './violationLabels'
import { WidgetContent } from './WidgetShell'
import { chartWrap, legendDot, legendList, legendName, legendRow, legendValue } from './widgets.css'

export function useEventsSummary(period: DashboardPeriod) {
  const range = useMemo(() => rangeForPeriod(period), [period])
  return useQuery({
    queryKey: ['events-summary', 'epi', period, range.from],
    queryFn: () =>
      eventsService.getSummary({ from: range.from, to: range.to, moduleCode: 'epi' }),
    staleTime: 30000,
    refetchInterval: 60000,
  })
}

export function ViolationsDistributionWidget({ period }: { period: DashboardPeriod }) {
  const query = useEventsSummary(period)

  const pieData = useMemo(
    () =>
      (query.data?.by_class ?? []).map((row) => ({
        name: violationLabel(row.class),
        value: row.count,
      })),
    [query.data]
  )

  return (
    <WidgetContent
      loading={query.isLoading}
      error={query.isError}
      empty={!query.isLoading && pieData.length === 0}
      onRetry={() => query.refetch()}
    >
      <div className={chartWrap}>
        <ResponsiveContainer width="100%" height={180}>
          <PieChart>
            <Pie
              data={pieData}
              cx="50%"
              cy="50%"
              innerRadius={50}
              outerRadius={80}
              dataKey="value"
              paddingAngle={2}
            >
              {pieData.map((entry, index) => (
                <Cell key={entry.name} fill={chartSeries[index % chartSeries.length]} />
              ))}
            </Pie>
            <RechartsTooltip
              contentStyle={{
                background: vars.color.bgCard,
                border: `1px solid ${vars.color.borderDefault}`,
                borderRadius: 8,
                fontSize: 12,
                color: vars.color.textPrimary,
              }}
              formatter={(value) => [value ?? 0, 'ocorrências']}
            />
          </PieChart>
        </ResponsiveContainer>

        <div className={legendList}>
          {pieData.map((entry, index) => (
            <div key={entry.name} className={legendRow}>
              <span
                className={legendDot}
                style={{ background: chartSeries[index % chartSeries.length] }}
              />
              <span className={legendName}>{entry.name}</span>
              <span className={legendValue}>{entry.value}</span>
            </div>
          ))}
        </div>
      </div>
    </WidgetContent>
  )
}
