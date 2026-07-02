/**
 * AlertsTimelineWidget — série temporal de alertas (zero-filled).
 * Fonte: GET /api/v1/events/timeline (tenant-scoped, bucket hour/day).
 */
import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { eventsService } from '../../../services/eventsService'
import { chartColors } from '../../../theme/chartColors'
import { vars } from '../../../styles/theme.css'
import { fillBuckets, formatBucketLabel, rangeForPeriod } from '../../../utils/timeBuckets'
import type { DashboardPeriod } from '../../../stores/dashboardStore'
import { WidgetContent } from './WidgetShell'
import { chartWrap } from './widgets.css'

const tooltipStyle = {
  background: vars.color.bgCard,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: 8,
  fontSize: 12,
  color: vars.color.textPrimary,
}

export function AlertsTimelineWidget({ period }: { period: DashboardPeriod }) {
  const range = useMemo(() => rangeForPeriod(period), [period])

  const query = useQuery({
    queryKey: ['events-timeline', 'epi', period, range.from],
    queryFn: () =>
      eventsService.getTimeline({
        from: range.from,
        to: range.to,
        bucket: range.bucket,
        moduleCode: 'epi',
      }),
    staleTime: 30000,
    refetchInterval: 60000,
  })

  const rows = useMemo(() => query.data?.timeline ?? [], [query.data])
  const points = useMemo(
    () =>
      fillBuckets(range.from, range.to, range.bucket, rows).map((p) => ({
        ...p,
        label: formatBucketLabel(p.bucket, range.bucket),
      })),
    [rows, range]
  )

  return (
    <WidgetContent
      loading={query.isLoading}
      error={query.isError}
      empty={!query.isLoading && rows.length === 0}
      onRetry={() => query.refetch()}
    >
      <div className={chartWrap}>
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid stroke={chartColors.grid} strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fill: chartColors.axis, fontSize: 11 }}
              stroke={chartColors.grid}
              tickLine={false}
              interval="preserveStartEnd"
            />
            <YAxis
              allowDecimals={false}
              tick={{ fill: chartColors.axis, fontSize: 11 }}
              stroke={chartColors.grid}
              tickLine={false}
              width={34}
            />
            <RechartsTooltip
              contentStyle={tooltipStyle}
              labelStyle={{ color: vars.color.textSecondary }}
              formatter={(value) => [value ?? 0, 'alertas']}
            />
            <Area
              type="monotone"
              dataKey="count"
              name="Alertas"
              stroke={chartColors.primary}
              strokeWidth={2}
              fill={chartColors.primary}
              fillOpacity={0.15}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </WidgetContent>
  )
}
