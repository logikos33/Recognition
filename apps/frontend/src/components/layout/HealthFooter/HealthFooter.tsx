import { useQuery } from '@tanstack/react-query'
import { api } from '../../../services/api'
import { useAuth } from '../../../hooks/useAuth'
import { footer, item, dotOk, dotErr, dotNeutral, separator } from './HealthFooter.css'

interface HealthMetrics {
  database: boolean
  redis: boolean
  cameras_active: number
}

export function HealthFooter() {
  const { isAdmin, isSuperAdmin } = useAuth()

  const { data } = useQuery<HealthMetrics>({
    queryKey: ['health-metrics'],
    queryFn: async () => {
      const res = await api.get<{ data?: HealthMetrics }>('/v1/health/metrics')
      return (res as unknown as { data?: HealthMetrics }).data ?? (res as unknown as HealthMetrics)
    },
    refetchInterval: 60000,
    staleTime: 50000,
    enabled: isAdmin || isSuperAdmin,
    retry: false,
  })

  if (!isAdmin && !isSuperAdmin) return null
  if (!data) return null

  return (
    <div className={footer}>
      <div className={item}>
        <span className={data.database ? dotOk : dotErr} />
        Banco de dados
      </div>
      <div className={separator} />
      <div className={item}>
        <span className={data.redis ? dotOk : dotErr} />
        Redis
      </div>
      <div className={separator} />
      <div className={item}>
        <span className={data.cameras_active > 0 ? dotOk : dotNeutral} />
        {data.cameras_active} câmera{data.cameras_active !== 1 ? 's' : ''} ativa{data.cameras_active !== 1 ? 's' : ''}
      </div>
    </div>
  )
}
