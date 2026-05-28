import { api } from '../../../services/api'
import type { DashboardSummaryResponse, DashboardStationsResponse } from '../types/qualityDashboard'

export const qualityDashboardService = {
  getSummary: () =>
    api.get<DashboardSummaryResponse>('/v1/quality/dashboard/summary'),

  getStations: () =>
    api.get<DashboardStationsResponse>('/v1/quality/dashboard/stations'),
}
