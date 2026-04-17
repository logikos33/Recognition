/**
 * Listagem de inspeções com filtros e paginação.
 * Filtros: câmera, resultado, categoria defeito, feedback_status, turno, período, ordem.
 * Export CSV via link direto.
 */
import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { qualityService } from '../services/qualityService'
import { ResultBadge, FeedbackBadge, DefectBadge } from '../components/DefectBadge'
import { table, th, td, trHover } from '../components/quality.css'
import type { QualityInspection, QualityCamera, QualityClass } from '../types/quality'

const SHIFT_LABELS: Record<string, string> = {
  morning: 'Manhã', afternoon: 'Tarde', night: 'Noite',
}

export function QualityInspectionsPage() {
  const navigate = useNavigate()
  const [inspections, setInspections] = useState<QualityInspection[]>([])
  const [cameras, setCameras] = useState<QualityCamera[]>([])
  const [classes, setClasses] = useState<QualityClass[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)

  // Filtros
  const [filters, setFilters] = useState({
    camera_id: '',
    result: '',
    feedback_status: '',
    shift: '',
    from: '',
    to: '',
    production_order: '',
  })

  const PER_PAGE = 25

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await qualityService.getInspections({
        ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== '')),
        page,
        per_page: PER_PAGE,
      })
      setInspections(res.data.inspections)
      setTotal(res.data.total)
    } catch { /* silent */ }
    setLoading(false)
  }, [filters, page])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    Promise.all([
      qualityService.getCameras(),
      qualityService.getClasses(),
    ]).then(([camsRes, clsRes]) => {
      setCameras(camsRes.data.cameras)
      setClasses(clsRes.data.classes)
    }).catch(() => {})
  }, [])

  function setFilter(key: string, value: string) {
    setFilters(f => ({ ...f, [key]: value }))
    setPage(1)
  }

  const totalPages = Math.ceil(total / PER_PAGE)

  const selectStyle: React.CSSProperties = {
    padding: '6px 10px', borderRadius: '4px', border: '1px solid #333',
    background: '#111', color: '#ccc', fontSize: '12px',
  }

  return (
    <div style={{ padding: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <h2 style={{ fontSize: '18px', fontWeight: 700 }}>Inspeções</h2>
        <span style={{ fontSize: '13px', color: '#888' }}>{total} registros</span>
      </div>

      {/* Filtros */}
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '16px' }}>
        <select value={filters.camera_id} onChange={e => setFilter('camera_id', e.target.value)} style={selectStyle}>
          <option value="">Todas as câmeras</option>
          {cameras.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>

        <select value={filters.result} onChange={e => setFilter('result', e.target.value)} style={selectStyle}>
          <option value="">OK + NOK</option>
          <option value="ok">Apenas OK</option>
          <option value="nok">Apenas NOK</option>
        </select>

        <select value={filters.feedback_status} onChange={e => setFilter('feedback_status', e.target.value)} style={selectStyle}>
          <option value="">Todos feedbacks</option>
          <option value="pending">Pendente</option>
          <option value="confirmed">Confirmado</option>
          <option value="rejected">Rejeitado</option>
        </select>

        <select value={filters.shift} onChange={e => setFilter('shift', e.target.value)} style={selectStyle}>
          <option value="">Todos turnos</option>
          <option value="morning">Manhã</option>
          <option value="afternoon">Tarde</option>
          <option value="night">Noite</option>
        </select>

        <input
          type="text"
          placeholder="Ordem de produção"
          value={filters.production_order}
          onChange={e => setFilter('production_order', e.target.value)}
          style={{ ...selectStyle, width: '160px' }}
        />

        <input
          type="date"
          value={filters.from}
          onChange={e => setFilter('from', e.target.value)}
          style={selectStyle}
        />
        <input
          type="date"
          value={filters.to}
          onChange={e => setFilter('to', e.target.value)}
          style={selectStyle}
        />

        <button
          onClick={() => { setFilters({ camera_id: '', result: '', feedback_status: '', shift: '', from: '', to: '', production_order: '' }); setPage(1) }}
          style={{ ...selectStyle, cursor: 'pointer', color: '#888' }}
        >
          Limpar
        </button>
      </div>

      {/* Tabela */}
      <div style={{ overflowX: 'auto' }}>
        <table className={table}>
          <thead>
            <tr>
              <th className={th}>Data/Hora</th>
              <th className={th}>Câmera</th>
              <th className={th}>Resultado</th>
              <th className={th}>Defeito</th>
              <th className={th}>Conf.</th>
              <th className={th}>Turno</th>
              <th className={th}>Lote</th>
              <th className={th}>Feedback</th>
              <th className={th}>NOK/1h</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td className={td} colSpan={9} style={{ textAlign: 'center', color: '#888' }}>Carregando…</td>
              </tr>
            ) : inspections.length === 0 ? (
              <tr>
                <td className={td} colSpan={9} style={{ textAlign: 'center', color: '#888' }}>Nenhuma inspeção encontrada.</td>
              </tr>
            ) : (
              inspections.map(insp => {
                const cls = classes.find(c => c.id === insp.defect_class)
                return (
                  <tr
                    key={insp.id}
                    className={trHover}
                    onClick={() => navigate(`/quality/inspections/${insp.id}`)}
                  >
                    <td className={td} style={{ fontSize: '12px', color: '#888', whiteSpace: 'nowrap' }}>
                      {new Date(insp.created_at).toLocaleString('pt-BR')}
                    </td>
                    <td className={td} style={{ fontSize: '12px' }}>{insp.camera_name ?? '—'}</td>
                    <td className={td}><ResultBadge result={insp.result} /></td>
                    <td className={td}>
                      {cls ? <DefectBadge classId={cls.id} label={cls.label} color={cls.color} /> : '—'}
                    </td>
                    <td className={td} style={{ fontSize: '12px' }}>{(insp.confidence * 100).toFixed(0)}%</td>
                    <td className={td} style={{ fontSize: '12px' }}>{SHIFT_LABELS[insp.shift] ?? insp.shift}</td>
                    <td className={td} style={{ fontSize: '12px', color: '#888' }}>{insp.production_order ?? '—'}</td>
                    <td className={td}><FeedbackBadge status={insp.feedback_status} /></td>
                    <td className={td} style={{ fontSize: '12px', color: insp.rolling_nok_rate_1h && insp.rolling_nok_rate_1h > 0.1 ? '#EF5350' : '#ccc' }}>
                      {insp.rolling_nok_rate_1h !== null ? `${((insp.rolling_nok_rate_1h ?? 0) * 100).toFixed(1)}%` : '—'}
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Paginação */}
      {totalPages > 1 && (
        <div style={{ display: 'flex', gap: '8px', justifyContent: 'center', marginTop: '16px' }}>
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            style={{ padding: '6px 14px', borderRadius: '4px', border: '1px solid #333', background: 'transparent', color: page === 1 ? '#555' : '#ccc', cursor: page === 1 ? 'not-allowed' : 'pointer', fontSize: '12px' }}
          >
            ← Anterior
          </button>
          <span style={{ padding: '6px 14px', fontSize: '12px', color: '#888' }}>
            {page} / {totalPages}
          </span>
          <button
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            style={{ padding: '6px 14px', borderRadius: '4px', border: '1px solid #333', background: 'transparent', color: page === totalPages ? '#555' : '#ccc', cursor: page === totalPages ? 'not-allowed' : 'pointer', fontSize: '12px' }}
          >
            Próxima →
          </button>
        </div>
      )}
    </div>
  )
}
