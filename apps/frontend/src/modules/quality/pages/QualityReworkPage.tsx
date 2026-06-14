/**
 * QualityReworkPage — histórico e análise de retrabalhos do Quality Gate.
 *
 * Tabela paginada com filtros por tipo de validação, data e operador.
 * Click na linha abre modal com foto antes/depois.
 * Métricas: qual validação falha mais, tempo médio de retrabalho por tipo.
 */
import { useState, useEffect, useCallback } from 'react'
import type { QualityRework, ValidationType } from '../types/gate'
import { api } from '../../../services/api'

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:5001'

// ── Tipos de resposta ─────────────────────────────────────────────────────────

interface ReworkMetrics {
  by_validation: Array<{ validation_type: string; count: number; avg_duration_seconds: number }>
  total_reworks: number
  avg_duration_seconds: number
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const VALIDATION_LABEL: Record<string, string> = {
  v1: 'V1 — Fio Alinhado no Anel',
  v2: 'V2 — Saída Isolada',
  v3: 'V3 — Anel Encapado',
}

const fmtDuration = (secs: number | null) => {
  if (!secs) return '—'
  if (secs < 60) return `${secs}s`
  return `${Math.floor(secs / 60)}m ${secs % 60}s`
}

const fmtDt = (iso: string) =>
  new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })

// Cor por tipo de validação — usada tanto nos cards quanto na tabela
const METRIC_COLORS: Record<string, string> = {
  v1: '#D97706', v2: '#7C3AED', v3: '#2563EB',
}

// ── Componente principal ──────────────────────────────────────────────────────

export function QualityReworkPage() {
  // Filtros
  const [filterValidation, setFilterValidation] = useState<string>('')
  const [filterDate, setFilterDate] = useState<string>('')
  const [filterOperator, setFilterOperator] = useState<string>('')

  // Dados
  const [reworks, setReworks] = useState<QualityRework[]>([])
  const [metrics, setMetrics] = useState<ReworkMetrics | null>(null)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const perPage = 20

  // UI
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Modal de foto antes/depois
  const [modalRework, setModalRework] = useState<QualityRework | null>(null)

  // Carrega lista e métricas em paralelo
  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    const params = new URLSearchParams({ page: String(page), per_page: String(perPage) })
    if (filterValidation) params.set('validation_type', filterValidation)
    if (filterDate) params.set('date', filterDate)
    if (filterOperator) params.set('operator_id', filterOperator)

    try {
      const [listJson, metricsJson] = await Promise.all([
        api.get<{ data: { reworks: QualityRework[]; total: number } }>(`/v1/quality/gate/reworks?${params.toString()}`),
        api.get<{ data: ReworkMetrics }>('/v1/quality/gate/stats/rework'),
      ])
      setReworks(listJson.data?.reworks ?? [])
      setTotal(listJson.data?.total ?? 0)
      const rawMetrics = metricsJson.data ?? null
      setMetrics(rawMetrics ? { ...rawMetrics, by_validation: rawMetrics.by_validation ?? [] } : null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao carregar retrabalhos.')
      console.error('rework_page:load_error', e)
    } finally {
      setLoading(false)
    }
  }, [page, filterValidation, filterDate, filterOperator])

  useEffect(() => { load() }, [load])

  const totalPages = Math.max(1, Math.ceil(total / perPage))

  return (
    <div style={{ padding: '24px', maxWidth: 1400, margin: '0 auto' }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 24, color: '#111827' }}>
        Retrabalhos — Quality Gate
      </h1>

      {/* ── Cards de métricas ── */}
      {metrics && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 28 }}>
          {/* Total geral */}
          <div
            style={{
              background: '#F9FAFB', border: '1px solid #E5E7EB',
              borderRadius: 12, padding: '18px 20px',
            }}
          >
            <div style={{ fontSize: 12, color: '#6B7280', marginBottom: 4 }}>Total de Retrabalhos</div>
            <div style={{ fontSize: 32, fontWeight: 700, color: '#DC2626' }}>
              {metrics.total_reworks}
            </div>
          </div>
          {/* Tempo médio geral */}
          <div
            style={{
              background: '#F9FAFB', border: '1px solid #E5E7EB',
              borderRadius: 12, padding: '18px 20px',
            }}
          >
            <div style={{ fontSize: 12, color: '#6B7280', marginBottom: 4 }}>Tempo Médio</div>
            <div style={{ fontSize: 32, fontWeight: 700, color: '#D97706' }}>
              {fmtDuration(Math.round(metrics.avg_duration_seconds))}
            </div>
          </div>
          {/* Por validação */}
          {metrics.by_validation.slice(0, 2).map(bv => (
            <div
              key={bv.validation_type}
              style={{
                background: '#F9FAFB', border: '1px solid #E5E7EB',
                borderRadius: 12, padding: '18px 20px',
              }}
            >
              <div style={{ fontSize: 12, color: '#6B7280', marginBottom: 4 }}>
                Retrabalhos {bv.validation_type.toUpperCase()}
              </div>
              <div
                style={{
                  fontSize: 32, fontWeight: 700,
                  color: METRIC_COLORS[bv.validation_type] ?? '#374151',
                }}
              >
                {bv.count}
              </div>
              <div style={{ fontSize: 12, color: '#9CA3AF', marginTop: 2 }}>
                Avg {fmtDuration(Math.round(bv.avg_duration_seconds))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Gráfico de barras inline: qual validação falha mais ── */}
      {metrics && metrics.by_validation.length > 0 && (
        <div
          style={{
            background: '#F9FAFB', border: '1px solid #E5E7EB',
            borderRadius: 12, padding: '20px 24px', marginBottom: 24,
          }}
        >
          <div style={{ fontSize: 14, fontWeight: 600, color: '#374151', marginBottom: 16 }}>
            Distribuição por Validação
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {metrics.by_validation.map(bv => {
              const maxCount = Math.max(...metrics.by_validation.map(x => x.count), 1)
              const pct = (bv.count / maxCount) * 100
              return (
                <div key={bv.validation_type}>
                  <div
                    style={{
                      display: 'flex', justifyContent: 'space-between',
                      marginBottom: 4, fontSize: 13,
                    }}
                  >
                    <span style={{ color: '#374151' }}>
                      {VALIDATION_LABEL[bv.validation_type] ?? bv.validation_type.toUpperCase()}
                    </span>
                    <span style={{ color: '#6B7280' }}>
                      {bv.count} · avg {fmtDuration(Math.round(bv.avg_duration_seconds))}
                    </span>
                  </div>
                  <div
                    style={{
                      height: 8, background: '#E5E7EB', borderRadius: 4, overflow: 'hidden',
                    }}
                  >
                    <div
                      style={{
                        height: '100%', width: `${pct}%`,
                        background: METRIC_COLORS[bv.validation_type] ?? '#6B7280',
                        borderRadius: 4, transition: 'width 0.6s ease',
                      }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* ── Filtros ── */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label htmlFor="filter-validation" style={{ fontSize: 12, color: '#6B7280', fontWeight: 500 }}>Validação</label>
          <select
            id="filter-validation"
            name="filter-validation"
            value={filterValidation}
            onChange={e => { setFilterValidation(e.target.value); setPage(1) }}
            style={{
              padding: '8px 12px', borderRadius: 8, border: '1px solid #D1D5DB',
              fontSize: 14, background: '#fff',
            }}
          >
            <option value="">Todas</option>
            {(['v1', 'v2', 'v3'] as ValidationType[]).map(v => (
              <option key={v} value={v}>{v.toUpperCase()}</option>
            ))}
          </select>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label htmlFor="filter-date" style={{ fontSize: 12, color: '#6B7280', fontWeight: 500 }}>Data</label>
          <input
            id="filter-date"
            name="filter-date"
            type="date"
            value={filterDate}
            onChange={e => { setFilterDate(e.target.value); setPage(1) }}
            style={{
              padding: '8px 12px', borderRadius: 8, border: '1px solid #D1D5DB',
              fontSize: 14, background: '#fff',
            }}
          />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label htmlFor="filter-operator" style={{ fontSize: 12, color: '#6B7280', fontWeight: 500 }}>Operador (ID)</label>
          <input
            id="filter-operator"
            name="filter-operator"
            type="text"
            placeholder="ID do operador"
            value={filterOperator}
            onChange={e => { setFilterOperator(e.target.value); setPage(1) }}
            style={{
              padding: '8px 12px', borderRadius: 8, border: '1px solid #D1D5DB',
              fontSize: 14, background: '#fff', minWidth: 180,
            }}
          />
        </div>

        {(filterValidation || filterDate || filterOperator) && (
          <button
            onClick={() => { setFilterValidation(''); setFilterDate(''); setFilterOperator(''); setPage(1) }}
            style={{
              padding: '8px 16px', borderRadius: 8, border: '1px solid #D1D5DB',
              fontSize: 14, background: '#fff', cursor: 'pointer', color: '#6B7280',
            }}
          >
            Limpar filtros
          </button>
        )}
      </div>

      {/* ── Loading / Erro ── */}
      {loading && <div style={{ color: '#6B7280', padding: '20px 0' }}>Carregando retrabalhos...</div>}
      {error && (
        <div style={{ color: '#DC2626', padding: '12px 16px', background: '#FEF2F2', borderRadius: 8, marginBottom: 16 }}>
          {error}
        </div>
      )}

      {/* ── Tabela de retrabalhos ── */}
      {!loading && (
        <div style={{ background: '#fff', border: '1px solid #E5E7EB', borderRadius: 12, overflow: 'hidden' }}>
          {/* Cabeçalho */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr 1.5fr 1fr 1fr 1fr 0.6fr',
              padding: '12px 16px',
              background: '#F9FAFB', borderBottom: '1px solid #E5E7EB',
              fontSize: 12, fontWeight: 600, color: '#6B7280',
              textTransform: 'uppercase', letterSpacing: 0.5,
            }}
          >
            <span>Peça</span>
            <span>Validação</span>
            <span>Defeito</span>
            <span>Tentativa</span>
            <span>Duração</span>
            <span>Iniciado</span>
            <span>Fotos</span>
          </div>

          {reworks.length === 0 && !loading && (
            <div style={{ padding: '40px 16px', textAlign: 'center', color: '#9CA3AF' }}>
              Nenhum retrabalho encontrado.
            </div>
          )}

          {reworks.map(rw => (
            <div
              key={rw.id}
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr 1.5fr 1fr 1fr 1fr 0.6fr',
                padding: '14px 16px',
                borderBottom: '1px solid #F3F4F6',
                alignItems: 'center',
                fontSize: 14,
              }}
            >
              <span style={{ fontWeight: 600, color: '#111827' }}>{rw.piece_id.slice(-8)}</span>
              <span>
                <span
                  style={{
                    padding: '3px 10px', borderRadius: 20, fontSize: 12, fontWeight: 600,
                    background: (METRIC_COLORS[rw.validation_type] ?? '#6B7280') + '20',
                    color: METRIC_COLORS[rw.validation_type] ?? '#6B7280',
                  }}
                >
                  {rw.validation_type.toUpperCase()}
                </span>
              </span>
              <span style={{ color: '#374151' }}>{rw.defect_type ?? rw.defect_description ?? '—'}</span>
              <span style={{ color: '#6B7280' }}>#{rw.attempt_number}</span>
              <span style={{ color: '#6B7280' }}>{fmtDuration(rw.duration_seconds)}</span>
              <span style={{ color: '#6B7280', fontSize: 13 }}>{fmtDt(rw.started_at)}</span>
              <span>
                {(rw.photo_before_path || rw.photo_after_path) ? (
                  <button
                    onClick={() => setModalRework(rw)}
                    style={{
                      padding: '4px 10px', borderRadius: 6, border: '1px solid #D1D5DB',
                      background: '#fff', cursor: 'pointer', fontSize: 12, color: '#2563EB',
                    }}
                  >
                    Ver fotos
                  </button>
                ) : (
                  <span style={{ color: '#D1D5DB', fontSize: 12 }}>—</span>
                )}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* ── Paginação ── */}
      {!loading && total > perPage && (
        <div style={{ display: 'flex', gap: 8, marginTop: 16, alignItems: 'center', justifyContent: 'flex-end' }}>
          <span style={{ fontSize: 13, color: '#6B7280' }}>
            {total} retrabalhos · página {page} de {totalPages}
          </span>
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            style={{
              padding: '6px 14px', borderRadius: 8, border: '1px solid #D1D5DB',
              background: '#fff', cursor: page === 1 ? 'not-allowed' : 'pointer',
              color: page === 1 ? '#D1D5DB' : '#374151', fontSize: 14,
            }}
          >
            ← Anterior
          </button>
          <button
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            style={{
              padding: '6px 14px', borderRadius: 8, border: '1px solid #D1D5DB',
              background: '#fff', cursor: page === totalPages ? 'not-allowed' : 'pointer',
              color: page === totalPages ? '#D1D5DB' : '#374151', fontSize: 14,
            }}
          >
            Próxima →
          </button>
        </div>
      )}

      {/* ── Modal de fotos antes/depois ── */}
      {modalRework && (
        <div
          onClick={() => setModalRework(null)}
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
          }}
        >
          <div
            onClick={e => e.stopPropagation()}
            style={{
              background: '#fff', borderRadius: 16, padding: 32, maxWidth: 800, width: '90%',
              boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
              <h2 style={{ fontSize: 18, fontWeight: 700, color: '#111827' }}>
                Fotos do Retrabalho — {modalRework.validation_type.toUpperCase()}
              </h2>
              <button
                onClick={() => setModalRework(null)}
                style={{
                  background: 'none', border: 'none', fontSize: 24,
                  cursor: 'pointer', color: '#6B7280', lineHeight: 1,
                }}
              >
                ×
              </button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
              {/* Foto antes */}
              <div>
                <div style={{ fontSize: 12, fontWeight: 600, color: '#6B7280', marginBottom: 8, textTransform: 'uppercase' }}>
                  Antes do retrabalho
                </div>
                {modalRework.photo_before_path ? (
                  <img
                    src={`${API_BASE}/api/v1/quality/gate/photos/${encodeURIComponent(modalRework.photo_before_path)}`}
                    alt="Antes"
                    style={{
                      width: '100%', borderRadius: 8,
                      border: '2px solid #EF4444', objectFit: 'contain', maxHeight: 280,
                    }}
                  />
                ) : (
                  <div style={{
                    height: 200, borderRadius: 8, background: '#F3F4F6',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9CA3AF',
                  }}>
                    Sem foto
                  </div>
                )}
              </div>

              {/* Foto depois */}
              <div>
                <div style={{ fontSize: 12, fontWeight: 600, color: '#6B7280', marginBottom: 8, textTransform: 'uppercase' }}>
                  Após o retrabalho
                </div>
                {modalRework.photo_after_path ? (
                  <img
                    src={`${API_BASE}/api/v1/quality/gate/photos/${encodeURIComponent(modalRework.photo_after_path)}`}
                    alt="Depois"
                    style={{
                      width: '100%', borderRadius: 8,
                      border: '2px solid #22C55E', objectFit: 'contain', maxHeight: 280,
                    }}
                  />
                ) : (
                  <div style={{
                    height: 200, borderRadius: 8, background: '#F3F4F6',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9CA3AF',
                  }}>
                    Sem foto
                  </div>
                )}
              </div>
            </div>

            {/* Notas */}
            {modalRework.notes && (
              <div style={{ marginTop: 16, padding: '12px 16px', background: '#F9FAFB', borderRadius: 8 }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: '#6B7280' }}>Observações: </span>
                <span style={{ fontSize: 14, color: '#374151' }}>{modalRework.notes}</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
