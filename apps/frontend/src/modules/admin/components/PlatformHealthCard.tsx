import * as s from './admin.css'
import type { PlatformHealth } from '../types/admin'

function statusToDot(status: string): 'healthy' | 'degraded' | 'critical' {
  if (status === 'ok' || status === 'healthy') return 'healthy'
  if (status === 'degraded') return 'degraded'
  return 'critical'
}

export function PlatformHealthCard({ health }: { health: PlatformHealth }) {
  return (
    <div className={s.card}>
      <div className={s.flex} style={{ marginBottom: 12 }}>
        <span className={s.cardTitle} style={{ marginBottom: 0 }}>Saúde da Plataforma</span>
        <span className={s.healthBadge[health.status]}>{health.status}</span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {Object.entries(health.services).map(([name, svc]) => {
          const dot = statusToDot(svc.status)
          return (
            <div key={name} className={s.flex}>
              <span className={s.dot[dot]} />
              <span style={{ flex: 1, fontSize: 13 }}>{name}</span>
              {svc.latency_ms !== undefined && (
                <span className={s.muted}>{svc.latency_ms.toFixed(0)} ms</span>
              )}
              {svc.details && <span className={s.muted}>{svc.details}</span>}
            </div>
          )
        })}
      </div>

      {Object.keys(health.celery_queues).length > 0 && (
        <>
          <div className={s.cardTitle} style={{ marginTop: 16 }}>Filas Celery</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {Object.entries(health.celery_queues).map(([q, len]) => (
              <span key={q} className={s.mono} style={{ fontSize: 12 }}>
                {q}: <strong>{len}</strong>
              </span>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
