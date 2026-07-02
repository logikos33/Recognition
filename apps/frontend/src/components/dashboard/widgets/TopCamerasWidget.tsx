/**
 * TopCamerasWidget — câmeras com mais alertas no período (barras horizontais).
 * Fonte: GET /api/v1/events/summary (by_camera, top 10, tenant-scoped).
 */
import { useMemo } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { chartColors } from '../../../theme/chartColors'
import { vars } from '../../../styles/theme.css'
import type { DashboardPeriod } from '../../../stores/dashboardStore'
import { useEventsSummary } from './ViolationsDistributionWidget'
import { WidgetContent } from './WidgetShell'
import { chartWrap } from './widgets.css'

export function TopCamerasWidget({ period }: { period: DashboardPeriod }) {
  const query = useEventsSummary(period)

  const rows = useMemo(
    () =>
      (query.data?.by_camera ?? []).map((row) => ({
        name: row.camera_name ?? 'Câmera',
        count: row.count,
      })),
    [query.data]
  )

  return (
    <WidgetContent
      loading={query.isLoading}
      error={query.isError}
      empty={!query.isLoading && rows.length === 0}
      onRetry={() => query.refetch()}
    >
      <div className={chartWrap}>
        <ResponsiveContainer width="100%" height={Math.max(180, rows.length * 34)}>
          <BarChart
            data={rows}
            layout="vertical"
            margin={{ top: 4, right: 16, bottom: 0, left: 4 }}
          >
            <CartesianGrid stroke={chartColors.grid} strokeDasharray="3 3" horizontal={false} />
            <XAxis
              type="number"
              allowDecimals={false}
              tick={{ fill: chartColors.axis, fontSize: 11 }}
              stroke={chartColors.grid}
              tickLine={false}
            />
            <YAxis
              type="category"
              dataKey="name"
              width={120}
              tick={{ fill: chartColors.label, fontSize: 11 }}
              stroke={chartColors.grid}
              tickLine={false}
            />
            <RechartsTooltip
              cursor={{ fill: vars.color.bgSurface }}
              contentStyle={{
                background: vars.color.bgCard,
                border: `1px solid ${vars.color.borderDefault}`,
                borderRadius: 8,
                fontSize: 12,
                color: vars.color.textPrimary,
              }}
              formatter={(value) => [value ?? 0, 'alertas']}
            />
            <Bar
              dataKey="count"
              name="Alertas"
              fill={chartColors.accent}
              radius={[0, 4, 4, 0]}
              barSize={14}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </WidgetContent>
  )
}
