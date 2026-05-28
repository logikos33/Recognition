/**
 * QualityReportsPage — relatórios e exportações do Quality Gate.
 *
 * Lista de peças aprovadas agrupadas por OP.
 * Status de exportação Wiser (ícone enviado/pendente/erro).
 * Botão "Exportar Wiser" individual e em lote.
 * Botão "Baixar CSV" com filtros de data e OP.
 */
import { useState, useEffect, useCallback } from 'react'
import type { QualityPiece } from '../types/gate'
import { api, getToken } from '../../../services/api'

// ── Tipos internos ────────────────────────────────────────────────────────────

// Agrupamento de peças por OP para exibição
interface OPGroup {
  work_order: string
  pieces: QualityPiece[]
  total: number
  approved: number
  pending_wiser: number
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const fmtDt = (iso: string) =>
  new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })

// Agrupa lista de peças por work_order
function groupByOP(pieces: QualityPiece[]): OPGroup[] {
  const map = new Map<string, QualityPiece[]>()
  for (const p of pieces) {
    const key = p.work_order ?? '(sem OP)'
    if (!map.has(key)) map.set(key, [])
    map.get(key)!.push(p)
  }
  return Array.from(map.entries()).map(([wo, ps]) => ({
    work_order: wo,
    pieces: ps,
    total: ps.length,
    approved: ps.filter(p => p.status === 'approved').length,
    pending_wiser: ps.filter(p => !p.wiser_exported).length,
  }))
}

// ── Componente principal ──────────────────────────────────────────────────────

export function QualityReportsPage() {
  // Filtros
  const [filterDateFrom, setFilterDateFrom] = useState<string>('')
  const [filterDateTo, setFilterDateTo] = useState<string>('')
  const [filterOP, setFilterOP] = useState<string>('')
  const [filterWiser, setFilterWiser] = useState<string>('') // '' | 'pending' | 'exported'

  // Dados
  const [pieces, setPieces] = useState<QualityPiece[]>([])
  const [opGroups, setOpGroups] = useState<OPGroup[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Estados de exportação individuais: piece_id → 'idle'|'loading'|'done'|'error'
  const [exportState, setExportState] = useState<Record<string, string>>({})

  // Estado de exportação em lote
  const [batchLoading, setBatchLoading] = useState(false)
  const [batchResult, setBatchResult] = useState<string | null>(null)

  // Carrega peças aprovadas com filtros
  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    const params = new URLSearchParams({ status: 'approved', per_page: '200' })
    if (filterDateFrom) params.set('date_from', filterDateFrom)
    if (filterDateTo) params.set('date_to', filterDateTo)
    if (filterOP) params.set('work_order', filterOP)
    if (filterWiser === 'pending') params.set('wiser_exported', 'false')
    if (filterWiser === 'exported') params.set('wiser_exported', 'true')

    try {
      const json = await api.get<{ data: { pieces: QualityPiece[] } }>(`/v1/quality/gate/pieces?${params.toString()}`)
      const list = json.data?.pieces ?? []
      setPieces(list)
      setOpGroups(groupByOP(list))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao carregar relatório.')
      console.error('reports_page:load_error', e)
    } finally {
      setLoading(false)
    }
  }, [filterDateFrom, filterDateTo, filterOP, filterWiser])

  useEffect(() => { load() }, [load])

  // Exporta uma peça individual para o Wiser
  const handleExportOne = async (pieceId: string) => {
    setExportState(s => ({ ...s, [pieceId]: 'loading' }))
    try {
      await api.post(`/v1/quality/gate/pieces/${pieceId}/export-wiser`, {})
      {
        setExportState(s => ({ ...s, [pieceId]: 'done' }))
        // Atualiza lista local sem re-fetch
        setPieces(prev =>
          prev.map(p => p.id === pieceId ? { ...p, wiser_exported: true } : p)
        )
        setOpGroups(prev => prev.map(g => ({
          ...g,
          pending_wiser: g.pieces.filter(p =>
            p.id === pieceId ? false : !p.wiser_exported
          ).length,
        })))
      }
    } catch (e) {
      setExportState(s => ({ ...s, [pieceId]: 'error' }))
      console.error('reports_page:export_error', e)
    }
  }

  // Exporta todas as peças pendentes de Wiser em lote
  const handleBatchExport = async () => {
    const pending = pieces.filter(p => !p.wiser_exported).map(p => p.id)
    if (pending.length === 0) return
    setBatchLoading(true)
    setBatchResult(null)
    try {
      const json = await api.post<{ data: { exported: number } }>('/v1/quality/gate/export-wiser/batch', { piece_ids: pending })
      setBatchResult(`${json.data?.exported ?? pending.length} peças exportadas com sucesso.`)
      load()
    } catch (e) {
      setBatchResult(e instanceof Error ? e.message : 'Erro de conexão ao exportar em lote.')
      console.error('reports_page:batch_export_error', e)
    } finally {
      setBatchLoading(false)
    }
  }

  // Gera URL para download de CSV com os filtros atuais
  const handleDownloadCSV = () => {
    const token = getToken()
    const params = new URLSearchParams({ status: 'approved', format: 'csv' })
    if (filterDateFrom) params.set('date_from', filterDateFrom)
    if (filterDateTo) params.set('date_to', filterDateTo)
    if (filterOP) params.set('work_order', filterOP)

    // Abre nova aba para download direto (o backend envia Content-Disposition: attachment)
    const apiBase = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:5001'
    const url = `${apiBase}/api/v1/quality/gate/pieces/export?${params.toString()}`
    const link = document.createElement('a')
    link.href = token ? `${url}&token=${token}` : url
    link.setAttribute('download', 'quality_gate_export.csv')
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  // Ícone de status Wiser
  const wiserIcon = (piece: QualityPiece) => {
    const state = exportState[piece.id]
    if (state === 'loading') return <span style={{ color: '#D97706' }}>⏳</span>
    if (state === 'done' || piece.wiser_exported) return <span title={piece.wiser_exported_at ? fmtDt(piece.wiser_exported_at) : 'Exportado'} style={{ color: '#16A34A', cursor: 'help' }}>✓</span>
    if (state === 'error') return <span style={{ color: '#DC2626' }}>✗</span>
    return <span style={{ color: '#D97706' }}>○</span>
  }

  const pendingWiserCount = pieces.filter(p => !p.wiser_exported).length

  return (
    <div style={{ padding: '24px', maxWidth: 1400, margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, color: '#111827' }}>
          Relatórios — Quality Gate
        </h1>

        {/* Ações globais */}
        <div style={{ display: 'flex', gap: 12 }}>
          {pendingWiserCount > 0 && (
            <button
              onClick={handleBatchExport}
              disabled={batchLoading}
              style={{
                padding: '10px 20px', borderRadius: 8,
                background: batchLoading ? '#6B7280' : '#7C3AED',
                color: '#fff', border: 'none', cursor: batchLoading ? 'not-allowed' : 'pointer',
                fontSize: 14, fontWeight: 600,
              }}
            >
              {batchLoading ? 'Exportando...' : `Exportar Wiser (${pendingWiserCount})`}
            </button>
          )}
          <button
            onClick={handleDownloadCSV}
            style={{
              padding: '10px 20px', borderRadius: 8,
              background: '#2563EB', color: '#fff', border: 'none',
              cursor: 'pointer', fontSize: 14, fontWeight: 600,
            }}
          >
            ↓ Baixar CSV
          </button>
        </div>
      </div>

      {/* Feedback de lote */}
      {batchResult && (
        <div
          style={{
            padding: '12px 16px', borderRadius: 8, marginBottom: 16,
            background: batchResult.startsWith('Erro') ? '#FEF2F2' : '#F0FDF4',
            color: batchResult.startsWith('Erro') ? '#DC2626' : '#16A34A',
          }}
        >
          {batchResult}
        </div>
      )}

      {/* ── Filtros ── */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 24, flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ fontSize: 12, color: '#6B7280', fontWeight: 500 }}>De</label>
          <input
            type="date" value={filterDateFrom}
            onChange={e => setFilterDateFrom(e.target.value)}
            style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid #D1D5DB', fontSize: 14, background: '#fff' }}
          />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ fontSize: 12, color: '#6B7280', fontWeight: 500 }}>Até</label>
          <input
            type="date" value={filterDateTo}
            onChange={e => setFilterDateTo(e.target.value)}
            style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid #D1D5DB', fontSize: 14, background: '#fff' }}
          />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ fontSize: 12, color: '#6B7280', fontWeight: 500 }}>Ordem de Produção</label>
          <input
            type="text" placeholder="Ex: OP-2024-001" value={filterOP}
            onChange={e => setFilterOP(e.target.value)}
            style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid #D1D5DB', fontSize: 14, background: '#fff', minWidth: 200 }}
          />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ fontSize: 12, color: '#6B7280', fontWeight: 500 }}>Wiser</label>
          <select
            value={filterWiser}
            onChange={e => setFilterWiser(e.target.value)}
            style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid #D1D5DB', fontSize: 14, background: '#fff' }}
          >
            <option value="">Todos</option>
            <option value="pending">Pendente</option>
            <option value="exported">Exportado</option>
          </select>
        </div>
        {(filterDateFrom || filterDateTo || filterOP || filterWiser) && (
          <button
            onClick={() => { setFilterDateFrom(''); setFilterDateTo(''); setFilterOP(''); setFilterWiser('') }}
            style={{ padding: '8px 16px', borderRadius: 8, border: '1px solid #D1D5DB', fontSize: 14, background: '#fff', cursor: 'pointer', color: '#6B7280' }}
          >
            Limpar filtros
          </button>
        )}
      </div>

      {/* ── Loading / Erro ── */}
      {loading && <div style={{ color: '#6B7280', padding: '20px 0' }}>Carregando relatório...</div>}
      {error && (
        <div style={{ color: '#DC2626', padding: '12px 16px', background: '#FEF2F2', borderRadius: 8, marginBottom: 16 }}>
          {error}
        </div>
      )}

      {/* ── Grupos por OP ── */}
      {!loading && opGroups.length === 0 && (
        <div style={{ color: '#9CA3AF', textAlign: 'center', padding: 60 }}>
          Nenhuma peça aprovada encontrada com os filtros selecionados.
        </div>
      )}

      {!loading && opGroups.map(group => (
        <div
          key={group.work_order}
          style={{ marginBottom: 24 }}
        >
          {/* Cabeçalho do grupo */}
          <div
            style={{
              display: 'flex', alignItems: 'center', gap: 16,
              padding: '12px 16px',
              background: '#F9FAFB', border: '1px solid #E5E7EB',
              borderRadius: '12px 12px 0 0',
            }}
          >
            <div style={{ fontWeight: 700, fontSize: 16, color: '#111827' }}>
              {group.work_order}
            </div>
            <span style={{ fontSize: 13, color: '#16A34A' }}>
              {group.approved} aprovadas
            </span>
            {group.pending_wiser > 0 && (
              <span style={{ fontSize: 13, color: '#D97706' }}>
                {group.pending_wiser} pendente Wiser
              </span>
            )}
            <div style={{ flex: 1 }} />
            {group.pending_wiser > 0 && (
              <button
                onClick={() => {
                  group.pieces
                    .filter(p => !p.wiser_exported)
                    .forEach(p => handleExportOne(p.id))
                }}
                style={{
                  padding: '6px 14px', borderRadius: 6,
                  background: '#7C3AED20', color: '#7C3AED',
                  border: '1px solid #7C3AED40', cursor: 'pointer',
                  fontSize: 12, fontWeight: 600,
                }}
              >
                Exportar OP para Wiser
              </button>
            )}
          </div>

          {/* Tabela de peças da OP */}
          <div
            style={{
              background: '#fff', border: '1px solid #E5E7EB',
              borderTop: 'none', borderRadius: '0 0 12px 12px', overflow: 'hidden',
            }}
          >
            {group.pieces.map((piece, idx) => (
              <div
                key={piece.id}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1.5fr 1fr 1fr 1fr 0.5fr',
                  padding: '12px 16px',
                  borderBottom: idx < group.pieces.length - 1 ? '1px solid #F3F4F6' : 'none',
                  alignItems: 'center',
                  fontSize: 14,
                }}
              >
                <span style={{ fontWeight: 600, color: '#111827' }}>{piece.piece_number}</span>
                <span style={{ color: '#6B7280', fontSize: 13 }}>
                  {piece.completed_at ? fmtDt(piece.completed_at) : '—'}
                </span>
                <span style={{ color: piece.total_rework_count > 0 ? '#D97706' : '#9CA3AF', fontSize: 13 }}>
                  {piece.total_rework_count > 0 ? `${piece.total_rework_count} retrabalho(s)` : 'Sem retrabalho'}
                </span>
                {/* Ícone de status Wiser */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  {wiserIcon(piece)}
                  <span style={{ fontSize: 12, color: '#6B7280' }}>
                    {exportState[piece.id] === 'loading'
                      ? 'Exportando...'
                      : piece.wiser_exported
                        ? 'Wiser OK'
                        : 'Pendente Wiser'}
                  </span>
                </div>
                {/* Botão exportar individual */}
                {!piece.wiser_exported && exportState[piece.id] !== 'done' && (
                  <button
                    onClick={() => handleExportOne(piece.id)}
                    disabled={exportState[piece.id] === 'loading'}
                    style={{
                      padding: '4px 10px', borderRadius: 6,
                      background: 'transparent',
                      border: '1px solid #7C3AED',
                      color: '#7C3AED', cursor: 'pointer', fontSize: 12,
                    }}
                  >
                    Exportar
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
