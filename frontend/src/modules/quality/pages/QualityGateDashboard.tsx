/**
 * QualityGateDashboard — painel principal do Quality Gate RVB.
 *
 * Exibe KPIs do turno, lista de peças ativas (live) e status das bancadas.
 * Usa fetch direto com token JWT (mesmo padrão das outras páginas do módulo).
 */
import { useState, useEffect } from 'react'
import type { QualityPiece, QualityStation } from '../types/gate'
import { api } from '../../../services/api'

// ── Tipos de resposta ─────────────────────────────────────────────────────────

interface GateStats {
  pieces_today: number
  approved_today: number
  approval_rate: number
  rework_count: number
  pending_wiser: number
}

// ── Helpers de cor/label ──────────────────────────────────────────────────────

const STATUS_COLOR: Record<string, string> = {
  idle: '#6B7280',
  identified: '#2563EB',
  validating_v1: '#D97706',
  validating_v2: '#D97706',
  validating_v3: '#D97706',
  rework_v1: '#DC2626',
  rework_v2: '#DC2626',
  rework_v3: '#DC2626',
  waiting_bench_b: '#7C3AED',
  approved: '#16A34A',
  rejected: '#991B1B',
}

const STATUS_LABEL: Record<string, string> = {
  idle: 'Aguardando',
  identified: 'Identificada',
  validating_v1: 'V1 Analisando',
  validating_v2: 'V2 Analisando',
  validating_v3: 'V3 Analisando',
  rework_v1: 'Retrabalho V1',
  rework_v2: 'Retrabalho V2',
  rework_v3: 'Retrabalho V3',
  waiting_bench_b: 'Aguardando Bancada B',
  approved: 'Aprovada',
  rejected: 'Rejeitada',
}

export function QualityGateDashboard() {
  const [stats, setStats] = useState<GateStats | null>(null)
  const [activePieces, setActivePieces] = useState<QualityPiece[]>([])
  const [stations, setStations] = useState<QualityStation[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Carrega dados do overview ao montar — polling simples a cada 15s
  useEffect(() => {
    let cancelled = false

    const load = async () => {
      try {
        const [statsJson, piecesJson, stationsJson] = await Promise.all([
          api.get<{ data: GateStats }>('/v1/quality/gate/stats/overview'),
          api.get<{ data: { pieces: QualityPiece[] } }>('/v1/quality/gate/pieces?status=active&limit=10'),
          api.get<{ data: { stations: QualityStation[] } }>('/v1/quality/gate/stations'),
        ])

        if (!cancelled) {
          setStats(statsJson.data)
          setActivePieces(piecesJson.data?.pieces ?? [])
          setStations(stationsJson.data?.stations ?? [])
        }
      } catch (e) {
        if (!cancelled) setError('Não foi possível carregar os dados do Quality Gate.')
        console.error('gate_dashboard:load_error', e)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    const interval = setInterval(load, 15_000)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [])

  if (loading) {
    return (
      <div style={{ padding: 32, color: '#6B7280' }}>Carregando Quality Gate...</div>
    )
  }

  if (error) {
    return (
      <div style={{ padding: 32, color: '#DC2626' }}>{error}</div>
    )
  }

  // KPIs do turno
  const kpis = stats
    ? [
        { label: 'Peças Hoje', value: stats.pieces_today, color: '#2563EB' },
        { label: 'Aprovadas', value: stats.approved_today, color: '#16A34A' },
        {
          label: 'Taxa Aprovação',
          value: `${(stats.approval_rate * 100).toFixed(1)}%`,
          color: '#16A34A',
        },
        { label: 'Retrabalhos', value: stats.rework_count, color: '#D97706' },
        { label: 'Pendente Wiser', value: stats.pending_wiser, color: '#7C3AED' },
      ]
    : []

  return (
    <div style={{ padding: '24px', maxWidth: 1400, margin: '0 auto' }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 24, color: '#111827' }}>
        Quality Gate
      </h1>

      {/* ── KPIs ── */}
      {stats && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(5, 1fr)',
            gap: 16,
            marginBottom: 32,
          }}
        >
          {kpis.map((kpi, i) => (
            <div
              key={i}
              style={{
                background: '#F9FAFB',
                border: '1px solid #E5E7EB',
                borderRadius: 12,
                padding: '20px 24px',
              }}
            >
              <div style={{ fontSize: 13, color: '#6B7280', marginBottom: 4 }}>
                {kpi.label}
              </div>
              <div style={{ fontSize: 32, fontWeight: 700, color: kpi.color }}>
                {kpi.value}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Grid principal: peças ativas + bancadas ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 24 }}>

        {/* Peças em andamento */}
        <div
          style={{
            background: '#F9FAFB',
            border: '1px solid #E5E7EB',
            borderRadius: 12,
            padding: 20,
          }}
        >
          <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16, color: '#111827' }}>
            Peças em Andamento
          </h2>

          {activePieces.length === 0 ? (
            <div style={{ color: '#9CA3AF', textAlign: 'center', padding: 40 }}>
              Nenhuma peça ativa no momento
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {activePieces.map(piece => {
                const color = STATUS_COLOR[piece.status] ?? '#6B7280'
                return (
                  <div
                    key={piece.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '12px 16px',
                      background: '#fff',
                      borderRadius: 8,
                      border: '1px solid #E5E7EB',
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 600, color: '#111827' }}>
                        {piece.piece_number}
                      </div>
                      {piece.work_order && (
                        <div style={{ fontSize: 12, color: '#6B7280' }}>
                          OP {piece.work_order}
                        </div>
                      )}
                    </div>

                    {/* Badge de status colorido */}
                    <span
                      style={{
                        padding: '4px 10px',
                        borderRadius: 20,
                        fontSize: 12,
                        fontWeight: 600,
                        background: color + '20',
                        color,
                      }}
                    >
                      {STATUS_LABEL[piece.status] ?? piece.status}
                    </span>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Status das Bancadas */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {(['bench_a', 'bench_b'] as const).map(code => {
            const station = stations.find(s => s.station_code === code)
            const piece = station?.current_piece ?? null

            return (
              <div
                key={code}
                style={{
                  background: '#F9FAFB',
                  border: '1px solid #E5E7EB',
                  borderRadius: 12,
                  padding: 20,
                  flex: 1,
                }}
              >
                <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12, color: '#111827' }}>
                  {code === 'bench_a' ? '🔵 Bancada A' : '🟢 Bancada B'}
                </h3>

                {piece ? (
                  <>
                    <div style={{ fontWeight: 600, color: '#111827' }}>
                      {piece.piece_number}
                    </div>
                    <div style={{ fontSize: 12, color: '#6B7280', marginTop: 4 }}>
                      {STATUS_LABEL[piece.status] ?? piece.status}
                    </div>
                    {piece.work_order && (
                      <div style={{ fontSize: 12, color: '#9CA3AF', marginTop: 2 }}>
                        OP {piece.work_order}
                      </div>
                    )}
                  </>
                ) : (
                  <div style={{ color: '#9CA3AF', fontSize: 14 }}>Vazia</div>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
