/**
 * QualityPiecesPage — histórico de peças no fluxo RVB com drill-down.
 *
 * Tabela paginada de peças com filtros por status, data e OP.
 * Click na linha expande detalhes: histórico de validações, retrabalhos e foto.
 */
import { useState, useEffect, useCallback } from 'react'
import type { QualityPiece, PieceStatus } from '../types/gate'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5001'

// ── Helpers ───────────────────────────────────────────────────────────────────

const STATUS_COLOR: Record<string, string> = {
  idle: '#6B7280', identified: '#2563EB',
  validating_v1: '#D97706', validating_v2: '#D97706', validating_v3: '#D97706',
  rework_v1: '#DC2626', rework_v2: '#DC2626', rework_v3: '#DC2626',
  waiting_bench_b: '#7C3AED', approved: '#16A34A', rejected: '#991B1B',
}

const STATUS_LABEL: Record<string, string> = {
  idle: 'Aguardando', identified: 'Identificada',
  validating_v1: 'V1 Analisando', validating_v2: 'V2 Analisando', validating_v3: 'V3 Analisando',
  rework_v1: 'Retrabalho V1', rework_v2: 'Retrabalho V2', rework_v3: 'Retrabalho V3',
  waiting_bench_b: 'Aguardando Bancada B', approved: 'Aprovada', rejected: 'Rejeitada',
}

// Todos os status para o filtro
const ALL_STATUSES: PieceStatus[] = [
  'idle', 'identified', 'validating_v1', 'rework_v1',
  'validating_v2', 'rework_v2', 'waiting_bench_b',
  'validating_v3', 'rework_v3', 'approved', 'rejected',
]

// ── Tipos de resposta ─────────────────────────────────────────────────────────

interface PiecesResponse {
  pieces: QualityPiece[]
  total: number
  page: number
  per_page: number
}

// Detalhe da peça: inclui histórico e reworks
interface PieceDetail extends QualityPiece {
  reworks?: Array<{
    id: string
    validation_type: string
    defect_type: string | null
    duration_seconds: number | null
    attempt_number: number
    started_at: string
    completed_at: string | null
  }>
}

// ── Componente principal ──────────────────────────────────────────────────────

export function QualityPiecesPage() {
  // Filtros
  const [filterStatus, setFilterStatus] = useState<string>('')
  const [filterDate, setFilterDate] = useState<string>('')
  const [filterOP, setFilterOP] = useState<string>('')

  // Dados
  const [pieces, setPieces] = useState<QualityPiece[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const perPage = 20

  // UI
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<PieceDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  // Carrega lista de peças com filtros e paginação
  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    const token = localStorage.getItem('token')
    const headers: Record<string, string> = {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    }

    const params = new URLSearchParams({ page: String(page), per_page: String(perPage) })
    if (filterStatus) params.set('status', filterStatus)
    if (filterDate) params.set('date', filterDate)
    if (filterOP) params.set('work_order', filterOP)

    try {
      const res = await fetch(
        `${API_URL}/api/v1/quality/gate/pieces?${params.toString()}`,
        { headers }
      )
      const json = await res.json()
      if (json.status === 'success') {
        const data = json.data as PiecesResponse
        setPieces(data.pieces ?? [])
        setTotal(data.total ?? 0)
      } else {
        setError(json.message ?? 'Erro ao carregar peças.')
      }
    } catch (e) {
      setError('Não foi possível conectar à API.')
      console.error('pieces_page:load_error', e)
    } finally {
      setLoading(false)
    }
  }, [page, filterStatus, filterDate, filterOP])

  // Re-carrega quando filtros ou página mudam
  useEffect(() => { load() }, [load])

  // Carrega detalhes ao expandir uma linha
  const handleExpand = async (piece: QualityPiece) => {
    if (expandedId === piece.id) {
      setExpandedId(null)
      setDetail(null)
      return
    }
    setExpandedId(piece.id)
    setDetailLoading(true)
    const token = localStorage.getItem('token')
    const headers: Record<string, string> = {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    }
    try {
      const res = await fetch(
        `${API_URL}/api/v1/quality/gate/pieces/${piece.id}`,
        { headers }
      )
      const json = await res.json()
      if (json.status === 'success') {
        setDetail(json.data?.piece ?? json.data ?? null)
      }
    } catch (e) {
      console.error('pieces_page:detail_error', e)
    } finally {
      setDetailLoading(false)
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / perPage))

  // Formata duração em segundos para string legível
  const fmtDuration = (secs: number | null) => {
    if (!secs) return '—'
    if (secs < 60) return `${secs}s`
    return `${Math.floor(secs / 60)}m ${secs % 60}s`
  }

  // Formata ISO datetime para localDateTime
  const fmtDt = (iso: string) =>
    new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })

  return (
    <div style={{ padding: '24px', maxWidth: 1400, margin: '0 auto' }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 24, color: '#111827' }}>
        Peças — Quality Gate
      </h1>

      {/* ── Filtros ── */}
      <div
        style={{
          display: 'flex',
          gap: 12,
          marginBottom: 20,
          flexWrap: 'wrap',
          alignItems: 'flex-end',
        }}
      >
        {/* Filtro de status */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ fontSize: 12, color: '#6B7280', fontWeight: 500 }}>Status</label>
          <select
            value={filterStatus}
            onChange={e => { setFilterStatus(e.target.value); setPage(1) }}
            style={{
              padding: '8px 12px', borderRadius: 8, border: '1px solid #D1D5DB',
              fontSize: 14, background: '#fff', minWidth: 180,
            }}
          >
            <option value="">Todos</option>
            {ALL_STATUSES.map(s => (
              <option key={s} value={s}>{STATUS_LABEL[s] ?? s}</option>
            ))}
          </select>
        </div>

        {/* Filtro de data */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ fontSize: 12, color: '#6B7280', fontWeight: 500 }}>Data</label>
          <input
            type="date"
            value={filterDate}
            onChange={e => { setFilterDate(e.target.value); setPage(1) }}
            style={{
              padding: '8px 12px', borderRadius: 8, border: '1px solid #D1D5DB',
              fontSize: 14, background: '#fff',
            }}
          />
        </div>

        {/* Filtro de OP */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ fontSize: 12, color: '#6B7280', fontWeight: 500 }}>Ordem de Produção</label>
          <input
            type="text"
            placeholder="Ex: OP-2024-001"
            value={filterOP}
            onChange={e => { setFilterOP(e.target.value); setPage(1) }}
            style={{
              padding: '8px 12px', borderRadius: 8, border: '1px solid #D1D5DB',
              fontSize: 14, background: '#fff', minWidth: 200,
            }}
          />
        </div>

        {/* Botão limpar */}
        {(filterStatus || filterDate || filterOP) && (
          <button
            onClick={() => { setFilterStatus(''); setFilterDate(''); setFilterOP(''); setPage(1) }}
            style={{
              padding: '8px 16px', borderRadius: 8, border: '1px solid #D1D5DB',
              fontSize: 14, background: '#fff', cursor: 'pointer', color: '#6B7280',
            }}
          >
            Limpar filtros
          </button>
        )}
      </div>

      {/* ── Estado de loading/erro ── */}
      {loading && (
        <div style={{ color: '#6B7280', padding: '20px 0' }}>Carregando peças...</div>
      )}
      {error && (
        <div style={{ color: '#DC2626', padding: '12px 16px', background: '#FEF2F2', borderRadius: 8, marginBottom: 16 }}>
          {error}
        </div>
      )}

      {/* ── Tabela de peças ── */}
      {!loading && (
        <div
          style={{
            background: '#fff',
            border: '1px solid #E5E7EB',
            borderRadius: 12,
            overflow: 'hidden',
          }}
        >
          {/* Cabeçalho */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr 1.5fr 1fr 1fr 0.8fr',
              padding: '12px 16px',
              background: '#F9FAFB',
              borderBottom: '1px solid #E5E7EB',
              fontSize: 12,
              fontWeight: 600,
              color: '#6B7280',
              textTransform: 'uppercase',
              letterSpacing: 0.5,
            }}
          >
            <span>Peça</span>
            <span>OP</span>
            <span>Status</span>
            <span>Retrabalhos</span>
            <span>Iniciada</span>
            <span>Concluída</span>
          </div>

          {/* Linhas */}
          {pieces.length === 0 && !loading && (
            <div style={{ padding: '40px 16px', textAlign: 'center', color: '#9CA3AF' }}>
              Nenhuma peça encontrada com os filtros aplicados.
            </div>
          )}

          {pieces.map(piece => {
            const color = STATUS_COLOR[piece.status] ?? '#6B7280'
            const isExpanded = expandedId === piece.id

            return (
              <div key={piece.id}>
                {/* Linha principal clicável */}
                <div
                  onClick={() => handleExpand(piece)}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '1fr 1fr 1.5fr 1fr 1fr 0.8fr',
                    padding: '14px 16px',
                    borderBottom: '1px solid #F3F4F6',
                    cursor: 'pointer',
                    background: isExpanded ? '#EFF6FF' : '#fff',
                    transition: 'background 0.15s',
                    alignItems: 'center',
                  }}
                >
                  <span style={{ fontWeight: 600, color: '#111827' }}>
                    {piece.piece_number}
                  </span>
                  <span style={{ color: '#6B7280', fontSize: 13 }}>
                    {piece.work_order ?? '—'}
                  </span>
                  <span>
                    <span
                      style={{
                        padding: '3px 10px', borderRadius: 20, fontSize: 12,
                        fontWeight: 600, background: color + '20', color,
                      }}
                    >
                      {STATUS_LABEL[piece.status] ?? piece.status}
                    </span>
                  </span>
                  <span style={{ color: piece.total_rework_count > 0 ? '#D97706' : '#6B7280', fontSize: 14 }}>
                    {piece.total_rework_count > 0 ? `${piece.total_rework_count}x` : '—'}
                  </span>
                  <span style={{ color: '#6B7280', fontSize: 13 }}>
                    {fmtDt(piece.started_at)}
                  </span>
                  <span style={{ color: '#6B7280', fontSize: 13 }}>
                    {piece.completed_at ? fmtDt(piece.completed_at) : '—'}
                  </span>
                </div>

                {/* Painel de detalhes expandido */}
                {isExpanded && (
                  <div
                    style={{
                      background: '#F8FAFC',
                      borderBottom: '1px solid #E5E7EB',
                      padding: '16px 24px',
                    }}
                  >
                    {detailLoading ? (
                      <div style={{ color: '#6B7280', fontSize: 14 }}>Carregando detalhes...</div>
                    ) : detail ? (
                      <div style={{ display: 'flex', gap: 32, flexWrap: 'wrap' }}>
                        {/* Informações gerais */}
                        <div>
                          <div style={{ fontSize: 12, fontWeight: 600, color: '#6B7280', marginBottom: 8, textTransform: 'uppercase' }}>
                            Informações
                          </div>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13 }}>
                            <div><span style={{ color: '#6B7280' }}>Tipo: </span>{detail.product_type ?? '—'}</div>
                            <div><span style={{ color: '#6B7280' }}>Operador: </span>{detail.operator_id ?? '—'}</div>
                            <div><span style={{ color: '#6B7280' }}>Bancada: </span>{detail.current_station ?? '—'}</div>
                            <div>
                              <span style={{ color: '#6B7280' }}>Wiser: </span>
                              {detail.wiser_exported ? (
                                <span style={{ color: '#16A34A' }}>✓ Exportado</span>
                              ) : (
                                <span style={{ color: '#D97706' }}>Pendente</span>
                              )}
                            </div>
                          </div>
                        </div>

                        {/* Histórico de retrabalhos */}
                        {detail.reworks && detail.reworks.length > 0 && (
                          <div>
                            <div style={{ fontSize: 12, fontWeight: 600, color: '#6B7280', marginBottom: 8, textTransform: 'uppercase' }}>
                              Retrabalhos ({detail.reworks.length})
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                              {detail.reworks.map(r => (
                                <div
                                  key={r.id}
                                  style={{
                                    fontSize: 13, display: 'flex', gap: 12, alignItems: 'center',
                                    padding: '6px 10px', background: '#fff', borderRadius: 6,
                                    border: '1px solid #E5E7EB',
                                  }}
                                >
                                  <span style={{ fontWeight: 600, color: '#D97706' }}>
                                    {r.validation_type.toUpperCase()}
                                  </span>
                                  <span style={{ color: '#374151' }}>{r.defect_type ?? 'Defeito'}</span>
                                  <span style={{ color: '#6B7280' }}>#{r.attempt_number}</span>
                                  <span style={{ color: '#6B7280' }}>{fmtDuration(r.duration_seconds)}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Foto de qualidade */}
                        {detail.photo_quality_path && (
                          <div>
                            <div style={{ fontSize: 12, fontWeight: 600, color: '#6B7280', marginBottom: 8, textTransform: 'uppercase' }}>
                              Foto Final
                            </div>
                            <img
                              src={`${API_URL}/api/v1/quality/gate/photos/${encodeURIComponent(detail.photo_quality_path)}`}
                              alt="Foto de qualidade"
                              style={{ maxWidth: 200, maxHeight: 150, borderRadius: 6, border: '1px solid #E5E7EB', objectFit: 'contain' }}
                            />
                          </div>
                        )}
                      </div>
                    ) : (
                      <div style={{ color: '#9CA3AF', fontSize: 14 }}>Sem detalhes disponíveis.</div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* ── Paginação ── */}
      {!loading && total > perPage && (
        <div style={{ display: 'flex', gap: 8, marginTop: 16, alignItems: 'center', justifyContent: 'flex-end' }}>
          <span style={{ fontSize: 13, color: '#6B7280' }}>
            {total} peças · página {page} de {totalPages}
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
    </div>
  )
}
