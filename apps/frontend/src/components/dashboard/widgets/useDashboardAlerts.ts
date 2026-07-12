/**
 * useDashboardAlerts — query compartilhada dos widgets de lista
 * (Últimos Alertas / Registro de Eventos). Mesma queryKey ⇒ react-query
 * deduplica: uma única request alimenta os dois widgets.
 */
import { useQuery } from '@tanstack/react-query'
import { api } from '../../../services/api'

export interface AlertViolation {
  class: string
  confidence: number
}

export interface DashboardAlert {
  id: string
  camera_id: string
  camera_name?: string
  violations: AlertViolation[]
  acknowledged: boolean
  created_at: string
}

interface AlertsApiResponse {
  alerts: DashboardAlert[]
  total: number
  page: number
  pages: number
}

interface Envelope {
  success?: boolean
  data?: AlertsApiResponse
}

export function useDashboardAlerts() {
  const query = useQuery({
    queryKey: ['dashboard-alerts'],
    queryFn: () => api.get<Envelope>('/alerts?per_page=50&page=1'),
    staleTime: 30000,
    refetchInterval: 60000,
  })

  const raw = query.data?.data ?? (query.data as unknown as AlertsApiResponse | undefined)
  const alerts: DashboardAlert[] = raw?.alerts ?? []

  return { ...query, alerts }
}

/** "há 5min" / "há 2h" / "há 3d" — tempo relativo pt-BR. */
export function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'agora'
  if (mins < 60) return `há ${mins}min`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `há ${hrs}h`
  return `há ${Math.floor(hrs / 24)}d`
}
