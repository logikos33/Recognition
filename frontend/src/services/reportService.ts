import { api } from './api'

export interface HomeReports {
  cards: {
    alerts_today: number
    alerts_week: number
    cameras_active: number
    cameras_total: number
    processings_today: number
    objects_identified: number
  }
  chart: {
    alerts_by_hour: Array<{ hour: string; count: number }>
  }
}

type R<T> = { status: string; data: T }

const EMPTY_REPORTS: HomeReports = {
  cards: {
    alerts_today: 0, alerts_week: 0,
    cameras_active: 0, cameras_total: 0,
    processings_today: 0, objects_identified: 0,
  },
  chart: { alerts_by_hour: [] },
}

export const reportService = {
  getHomeReports: async (): Promise<HomeReports> => {
    const res = await api.get<R<HomeReports>>('/api/reports/home')
    return res.data ?? EMPTY_REPORTS
  },
}
