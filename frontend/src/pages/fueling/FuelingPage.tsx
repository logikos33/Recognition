/**
 * FuelingPage — Módulo de controle de abastecimento.
 *
 * Exibe KPIs do dia e tabela de eventos recentes para o módulo fueling.
 * Polling a cada 30 segundos.
 */
import { useState, useEffect, useCallback } from 'react'
import { Fuel, Truck, RefreshCw } from 'lucide-react'
import { api } from '../../services/api'
import { LoadingSpinner } from '../../components/shared/LoadingSpinner'

interface FuelingStats {
  events_today: number
  active_cameras: number
  module_status: string
}

interface FuelingEvent {
  id: string
  camera_id: string
  class_name: string
  confidence: number | null
  created_at: string | null
}

const CLASS_LABELS: Record<string, string> = {
  truck: 'Caminhão',
  plate: 'Placa',
  fuel_nozzle: 'Bico Combustível',
  product_box: 'Caixa',
  pallet: 'Pallet',
}

function classLabel(cls: string): string {
  return CLASS_LABELS[cls] ?? cls
}

function confidenceColor(conf: number | null): string {
  if (conf === null) return '#64748b'
  if (conf < 0.5) return '#ef4444'
  if (conf < 0.7) return '#f59e0b'
  return '#22c55e'
}

export function FuelingPage() {
  const [stats, setStats] = useState<FuelingStats | null>(null)
  const [events, setEvents] = useState<FuelingEvent[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      const [statsRes, eventsRes] = await Promise.all([
        api.get<any>('/fueling/stats'),
        api.get<any>('/fueling/events?limit=20'),
      ])
      const statsData = statsRes?.data || statsRes
      const eventsData = eventsRes?.data || eventsRes
      setStats(statsData)
      setEvents(eventsData?.events || [])
    } catch (err) {
      console.error('Failed to load fueling data:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    const interval = setInterval(load, 30000)
    return () => clearInterval(interval)
  }, [load])

  if (loading) return <LoadingSpinner />

  return (
    <div style={{ padding: 24, maxWidth: 900, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Fuel size={22} style={{ color: '#f59e0b' }} />
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: '#f1f5f9' }}>
            Fueling Control
          </h2>
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

      {/* Banner — módulo em configuração */}
      <div style={{
        background: 'rgba(245,158,11,0.1)',
        border: '1px solid rgba(245,158,11,0.35)',
        borderRadius: 8,
        padding: '10px 16px',
        marginBottom: 24,
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        fontSize: 13,
        color: '#fbbf24',
      }}>
        <Truck size={15} style={{ flexShrink: 0 }} />
        <span>
          <strong>Módulo em configuração</strong> — modelos YOLO ativos:{' '}
          <code style={{ background: 'rgba(245,158,11,0.15)', borderRadius: 4, padding: '1px 6px', fontSize: 12 }}>
            truck
          </code>{' '}
          <code style={{ background: 'rgba(245,158,11,0.15)', borderRadius: 4, padding: '1px 6px', fontSize: 12 }}>
            plate
          </code>{' '}
          <code style={{ background: 'rgba(245,158,11,0.15)', borderRadius: 4, padding: '1px 6px', fontSize: 12 }}>
            fuel_nozzle
          </code>
        </span>
      </div>

      {/* KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 28 }}>
        {/* Eventos Hoje */}
        <div style={{
          background: '#0f172a',
          border: '1px solid #1e293b',
          borderRadius: 10,
          padding: '20px 24px',
        }}>
          <div style={{ fontSize: 12, color: '#64748b', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8 }}>
            Eventos Hoje
          </div>
          <div style={{ fontSize: 32, fontWeight: 700, color: '#f1f5f9', fontFamily: 'monospace' }}>
            {stats?.events_today ?? 0}
          </div>
          <div style={{ fontSize: 12, color: '#475569', marginTop: 4 }}>
            detecções registradas hoje
          </div>
        </div>

        {/* Câmeras Ativas */}
        <div style={{
          background: '#0f172a',
          border: '1px solid #1e293b',
          borderRadius: 10,
          padding: '20px 24px',
        }}>
          <div style={{ fontSize: 12, color: '#64748b', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8 }}>
            Câmeras Ativas
          </div>
          <div style={{ fontSize: 32, fontWeight: 700, color: '#f1f5f9', fontFamily: 'monospace' }}>
            {stats?.active_cameras ?? 0}
          </div>
          <div style={{ fontSize: 12, color: '#475569', marginTop: 4 }}>
            com detecções hoje
          </div>
        </div>
      </div>

      {/* Tabela de Eventos Recentes */}
      <div style={{
        background: '#0f172a',
        border: '1px solid #1e293b',
        borderRadius: 10,
        overflow: 'hidden',
      }}>
        <div style={{
          padding: '14px 20px',
          borderBottom: '1px solid #1e293b',
          fontSize: 13,
          fontWeight: 600,
          color: '#94a3b8',
        }}>
          Eventos Recentes
        </div>

        {events.length === 0 ? (
          <div style={{
            textAlign: 'center',
            padding: '48px 20px',
            color: '#475569',
          }}>
            <Fuel size={32} style={{ opacity: 0.25, marginBottom: 10 }} />
            <p style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>Sem eventos registrados ainda</p>
            <p style={{ margin: '6px 0 0', fontSize: 12 }}>
              Os eventos aparecerão aqui quando câmeras de abastecimento forem configuradas.
            </p>
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #1e293b' }}>
                {['Classe', 'Confiança', 'Câmera', 'Horário'].map(col => (
                  <th
                    key={col}
                    style={{
                      padding: '10px 20px',
                      textAlign: 'left',
                      fontSize: 11,
                      fontWeight: 600,
                      color: '#475569',
                      textTransform: 'uppercase',
                      letterSpacing: '0.05em',
                    }}
                  >
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {events.map((evt, idx) => (
                <tr
                  key={evt.id}
                  style={{
                    borderBottom: idx < events.length - 1 ? '1px solid #0f172a' : 'none',
                    background: idx % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.015)',
                  }}
                >
                  <td style={{ padding: '11px 20px', fontSize: 13, color: '#f1f5f9', fontWeight: 500 }}>
                    {classLabel(evt.class_name)}
                  </td>
                  <td style={{ padding: '11px 20px', fontSize: 13, fontFamily: 'monospace', color: confidenceColor(evt.confidence) }}>
                    {evt.confidence !== null ? `${Math.round(evt.confidence * 100)}%` : '—'}
                  </td>
                  <td style={{ padding: '11px 20px', fontSize: 12, color: '#64748b', fontFamily: 'monospace' }}>
                    {evt.camera_id.slice(0, 8)}
                  </td>
                  <td style={{ padding: '11px 20px', fontSize: 12, color: '#475569' }}>
                    {evt.created_at
                      ? new Date(evt.created_at).toLocaleString('pt-BR')
                      : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
