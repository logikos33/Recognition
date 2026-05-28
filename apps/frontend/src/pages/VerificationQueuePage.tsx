/**
 * VerificationQueuePage — Fila de revisão humana de alertas pré-filtrados pela IA.
 *
 * Mostra apenas alertas que o agente Claude classificou como "needs_human".
 * Aprovados e rejeitados automaticamente nunca chegam aqui.
 */
import { useState, useEffect, useCallback } from 'react'
import { CheckCircle, XCircle, RefreshCw, ShieldAlert } from 'lucide-react'
import { useToast } from '../components/ui/Toast/useToast'
import { api } from '../services/api'
import { Skeleton } from '../components/ui/Skeleton/Skeleton'

interface VerificationItem {
  id: string
  camera_id: string
  camera_name?: string
  class_name?: string
  confidence: number
  violations: Array<{ class: string; confidence: number; bbox: number[] }>
  verification_reason?: string
  created_at: string
  timestamp: string
}

function classLabel(cls: string): string {
  const labels: Record<string, string> = {
    no_helmet: 'Sem capacete',
    no_vest: 'Sem colete',
    no_gloves: 'Sem luvas',
    no_glasses: 'Sem óculos',
    helmet: 'Capacete detectado',
    vest: 'Colete detectado',
  }
  return labels[cls] ?? cls
}

function confidenceColor(conf: number): string {
  if (conf < 0.5) return '#ef4444'
  if (conf < 0.7) return '#f59e0b'
  return '#22c55e'
}

export function VerificationQueuePage() {
  const toast = useToast()
  const [items, setItems] = useState<VerificationItem[]>([])
  const [loading, setLoading] = useState(true)
  const [reviewing, setReviewing] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const res = await api.get<any>('/verification/queue')
      const data = res?.data || res
      setItems(data?.items || [])
    } catch (err) {
      console.error('Failed to load queue:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    const interval = setInterval(load, 15000)
    return () => clearInterval(interval)
  }, [load])

  const review = async (alertId: string, verdict: 'approve' | 'reject') => {
    setReviewing(alertId)
    try {
      await api.post(`/verification/${alertId}/review`, { verdict })
      toast.success(verdict === 'approve' ? 'Alerta confirmado' : 'Alerta rejeitado')
      setItems(prev => prev.filter(item => item.id !== alertId))
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Erro ao revisar alerta')
    } finally {
      setReviewing(null)
    }
  }

  if (loading) return (
    <div style={{ padding: 24, maxWidth: 800, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 12 }}>
      <Skeleton variant="title" width={220} />
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: 16, border: '1px solid transparent' }}>
          <Skeleton variant="text" width="80%" />
          <Skeleton variant="text" width="55%" />
          <Skeleton variant="rect" width={120} height={28} />
        </div>
      ))}
    </div>
  )

  return (
    <div style={{ padding: 24, maxWidth: 800, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <ShieldAlert size={22} style={{ color: '#a78bfa' }} />
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: '#f1f5f9' }}>
            Fila de Verificação
          </h2>
          {items.length > 0 && (
            <span style={{
              background: '#7c3aed',
              color: '#fff',
              borderRadius: 999,
              padding: '2px 10px',
              fontSize: 12,
              fontWeight: 700,
            }}>
              {items.length}
            </span>
          )}
        </div>
        <button
          onClick={load}
          style={{
            background: 'transparent',
            border: '1px solid #334155',
            borderRadius: 6,
            color: '#94a3b8',
            padding: '6px 12px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 5,
            fontSize: 12,
          }}
        >
          <RefreshCw size={13} /> Atualizar
        </button>
      </div>

      <p style={{ color: '#64748b', fontSize: 13, marginBottom: 20, marginTop: -12 }}>
        Alertas que o agente IA classificou como ambíguos. Confirme ou rejeite abaixo.
      </p>

      {/* Empty state */}
      {items.length === 0 && (
        <div style={{
          textAlign: 'center',
          padding: '60px 20px',
          color: '#475569',
          border: '1px dashed #1e293b',
          borderRadius: 12,
        }}>
          <CheckCircle size={40} style={{ opacity: 0.3, marginBottom: 12 }} />
          <p style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>Fila vazia</p>
          <p style={{ margin: '6px 0 0', fontSize: 13 }}>
            Nenhum alerta aguardando revisão humana no momento.
          </p>
        </div>
      )}

      {/* Alert list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {items.map(item => {
          const cls = item.class_name || item.violations?.[0]?.class || '—'
          const conf = item.confidence ?? item.violations?.[0]?.confidence ?? 0
          const isReviewing = reviewing === item.id

          return (
            <div
              key={item.id}
              style={{
                background: '#0f172a',
                border: '1px solid #1e293b',
                borderRadius: 10,
                padding: 16,
                display: 'flex',
                gap: 16,
                alignItems: 'flex-start',
              }}
            >
              {/* Confidence indicator */}
              <div style={{ flexShrink: 0, textAlign: 'center', minWidth: 52 }}>
                <div style={{
                  fontSize: 18,
                  fontWeight: 700,
                  color: confidenceColor(conf),
                  fontFamily: 'monospace',
                }}>
                  {Math.round(conf * 100)}%
                </div>
                <div style={{ fontSize: 10, color: '#475569', marginTop: 2 }}>confiança</div>
              </div>

              {/* Content */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 4 }}>
                  <span style={{ fontWeight: 600, color: '#f1f5f9', fontSize: 14 }}>
                    {classLabel(cls)}
                  </span>
                  <span style={{ color: '#475569', fontSize: 12 }}>·</span>
                  <span style={{ color: '#64748b', fontSize: 12 }}>
                    {item.camera_name || item.camera_id.slice(0, 8)}
                  </span>
                </div>

                {item.verification_reason && (
                  <p style={{
                    margin: '4px 0 0',
                    fontSize: 12,
                    color: '#94a3b8',
                    fontStyle: 'italic',
                  }}>
                    IA: {item.verification_reason}
                  </p>
                )}

                <div style={{ fontSize: 11, color: '#334155', marginTop: 6 }}>
                  {new Date(item.created_at || item.timestamp).toLocaleString('pt-BR')}
                </div>
              </div>

              {/* Actions */}
              <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                <button
                  onClick={() => review(item.id, 'approve')}
                  disabled={isReviewing}
                  title="Confirmar alerta"
                  style={{
                    background: 'rgba(34,197,94,0.1)',
                    border: '1px solid rgba(34,197,94,0.3)',
                    borderRadius: 6,
                    color: '#22c55e',
                    padding: '6px 12px',
                    cursor: isReviewing ? 'default' : 'pointer',
                    fontSize: 12,
                    fontWeight: 600,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 4,
                    opacity: isReviewing ? 0.5 : 1,
                  }}
                >
                  <CheckCircle size={13} /> Confirmar
                </button>
                <button
                  onClick={() => review(item.id, 'reject')}
                  disabled={isReviewing}
                  title="Rejeitar alerta"
                  style={{
                    background: 'rgba(239,68,68,0.1)',
                    border: '1px solid rgba(239,68,68,0.3)',
                    borderRadius: 6,
                    color: '#ef4444',
                    padding: '6px 12px',
                    cursor: isReviewing ? 'default' : 'pointer',
                    fontSize: 12,
                    fontWeight: 600,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 4,
                    opacity: isReviewing ? 0.5 : 1,
                  }}
                >
                  <XCircle size={13} /> Rejeitar
                </button>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
