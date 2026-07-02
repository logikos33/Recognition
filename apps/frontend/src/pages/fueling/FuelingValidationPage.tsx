/**
 * FuelingValidationPage — Validação/Aceite de contagem (CD-07).
 *
 * Compara contagem do sistema (DeepSORT) vs contagem manual por sessão:
 *   - Filtros: período (start/end), baia e threshold de erro (%)
 *   - Cards de resumo: sessões validadas, erro agregado, pass/fail geral
 *   - Tabela de sessões: placa, baia, system_count, manual_count editável
 *     (PATCH /counting/sessions/<id>), erro %, badge passed/failed e aceite
 *   - Seção diária: agregado por dia
 *
 * Rota: /fueling/validation
 */
import { useState, useEffect, useCallback } from 'react'
import { ClipboardCheck, RefreshCw, Check, X, Save } from 'lucide-react'
import { countingService } from '../../services/countingService'
import { useToast } from '../../components/ui/Toast/useToast'
import { LoadingSpinner } from '../../components/shared/LoadingSpinner'
import { Badge } from '../../components/ui/Badge/Badge'
import type {
  AcceptanceStatus,
  ValidationDailyRow,
  ValidationReport,
  ValidationSessionRow,
} from '../../types/counting'
import { vars } from '../../styles/theme.css'

// ── Helpers ───────────────────────────────────────────────────────────────────

const DIRECTION_LABELS: Record<string, string> = { load: 'Carga', unload: 'Descarga' }

const ACCEPTANCE_META: Record<AcceptanceStatus, { label: string; variant: 'success' | 'warning' | 'danger' }> = {
  pending: { label: 'Pendente', variant: 'warning' },
  accepted: { label: 'Aceita', variant: 'success' },
  rejected: { label: 'Rejeitada', variant: 'danger' },
}

function isoDate(d: Date): string {
  return d.toISOString().slice(0, 10)
}

function fmtPct(v: number | null): string {
  return v === null ? '—' : `${v.toFixed(2)}%`
}

function fmtDateTime(v: string | null): string {
  return v ? new Date(v).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—'
}

function shortId(v: string | null): string {
  return v ? v.slice(0, 8) : '—'
}

/** Formata o dia do agregado diário — aceita 'YYYY-MM-DD' ou datas serializadas pelo Flask. */
function fmtDay(v: string): string {
  const normalized = /^\d{4}-\d{2}-\d{2}$/.test(v) ? `${v}T00:00:00` : v
  const parsed = new Date(normalized)
  return Number.isNaN(parsed.getTime()) ? v : parsed.toLocaleDateString('pt-BR')
}

// ── Estilos compartilhados ────────────────────────────────────────────────────

const cardStyle: React.CSSProperties = {
  background: vars.color.bgBase, border: `1px solid ${vars.color.bgSurface}`, borderRadius: 10, padding: '18px 22px',
}

const thStyle: React.CSSProperties = {
  padding: '10px 14px', textAlign: 'left', fontSize: 11, fontWeight: 600,
  color: vars.color.textMuted, textTransform: 'uppercase', letterSpacing: '0.05em',
}

const tdStyle: React.CSSProperties = {
  padding: '10px 14px', fontSize: 13, color: vars.color.textSecondary,
}

const inputStyle: React.CSSProperties = {
  background: vars.color.bgSurface, border: `1px solid ${vars.color.borderStrong}`, borderRadius: 6,
  color: '#f1f5f9', padding: '6px 10px', fontSize: 13, outline: 'none',
}

// ── Subcomponents ─────────────────────────────────────────────────────────────

function SummaryCard({ label, value, sub, accent = '#f1f5f9' }: {
  label: string; value: string; sub?: string; accent?: string
}) {
  return (
    <div style={cardStyle}>
      <div style={{ fontSize: 11, fontWeight: 600, color: vars.color.textMuted, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8 }}>
        {label}
      </div>
      <div style={{ fontSize: 26, fontWeight: 700, color: accent, fontFamily: 'monospace' }}>{value}</div>
      {sub && <div style={{ fontSize: 12, color: vars.color.textMuted, marginTop: 4 }}>{sub}</div>}
    </div>
  )
}

function PassedBadge({ passed }: { passed: boolean }) {
  return <Badge variant={passed ? 'success' : 'danger'}>{passed ? 'Aprovado' : 'Reprovado'}</Badge>
}

/** Linha da tabela de sessões com input editável de manual_count. */
function SessionRow({ row, striped, onSaved }: {
  row: ValidationSessionRow
  striped: boolean
  onSaved: () => void
}) {
  const toast = useToast()
  const [manualValue, setManualValue] = useState<string>(String(row.manual_count))
  const [saving, setSaving] = useState(false)
  const [updatingAcceptance, setUpdatingAcceptance] = useState(false)

  // Re-sincroniza o input quando o relatório recarrega
  useEffect(() => { setManualValue(String(row.manual_count)) }, [row.manual_count])

  const dirty = manualValue !== String(row.manual_count)

  const saveManual = async () => {
    const parsed = Number(manualValue)
    if (!Number.isInteger(parsed) || parsed < 0) {
      toast.error('Contagem manual deve ser um inteiro >= 0')
      return
    }
    setSaving(true)
    try {
      await countingService.updateSession(row.id, { manual_count: parsed })
      toast.success('Contagem manual atualizada')
      onSaved()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao salvar contagem manual')
    } finally {
      setSaving(false)
    }
  }

  const setAcceptance = async (status: AcceptanceStatus) => {
    setUpdatingAcceptance(true)
    try {
      await countingService.updateSession(row.id, { acceptance_status: status })
      toast.success(status === 'accepted' ? 'Sessão aceita' : 'Sessão rejeitada')
      onSaved()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao atualizar aceite')
    } finally {
      setUpdatingAcceptance(false)
    }
  }

  const acceptance = ACCEPTANCE_META[row.acceptance_status ?? 'pending']

  return (
    <tr style={{ borderBottom: `1px solid ${vars.color.bgBase}`, background: striped ? 'rgba(255,255,255,0.015)' : 'transparent' }}>
      <td style={{ ...tdStyle, fontFamily: 'monospace', color: '#f1f5f9', fontWeight: 600 }}>
        {row.truck_plate ?? '—'}
      </td>
      <td style={{ ...tdStyle, fontFamily: 'monospace', fontSize: 12 }}>{shortId(row.bay_id)}</td>
      <td style={tdStyle}>{row.direction ? DIRECTION_LABELS[row.direction] ?? row.direction : '—'}</td>
      <td style={{ ...tdStyle, fontSize: 12, color: vars.color.textMuted }}>{fmtDateTime(row.started_at)}</td>
      <td style={{ ...tdStyle, fontFamily: 'monospace', color: '#a5b4fc', textAlign: 'right' }}>{row.system_count}</td>
      <td style={tdStyle}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <input
            type="number"
            min={0}
            value={manualValue}
            onChange={e => setManualValue(e.target.value)}
            disabled={saving}
            style={{ ...inputStyle, width: 76, fontFamily: 'monospace', textAlign: 'right' }}
            aria-label={`Contagem manual da sessão ${shortId(row.id)}`}
          />
          <button
            onClick={saveManual}
            disabled={saving || !dirty}
            title="Salvar contagem manual"
            style={{
              background: dirty ? 'rgba(99,102,241,0.15)' : 'transparent',
              border: `1px solid ${dirty ? 'rgba(99,102,241,0.4)' : vars.color.bgSurface}`,
              borderRadius: 6, padding: '5px 8px',
              color: dirty ? '#a5b4fc' : vars.color.textMuted,
              cursor: saving || !dirty ? 'not-allowed' : 'pointer',
              display: 'flex', alignItems: 'center',
              opacity: saving ? 0.5 : 1,
            }}
          >
            <Save size={13} />
          </button>
        </div>
      </td>
      <td style={{ ...tdStyle, fontFamily: 'monospace', textAlign: 'right' }}>{row.abs_error}</td>
      <td style={{ ...tdStyle, fontFamily: 'monospace', textAlign: 'right', color: row.passed ? vars.color.success : '#f87171' }}>
        {fmtPct(row.error_pct)}
      </td>
      <td style={tdStyle}><PassedBadge passed={row.passed} /></td>
      <td style={tdStyle}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Badge variant={acceptance.variant}>{acceptance.label}</Badge>
          {row.acceptance_status !== 'accepted' && (
            <button
              onClick={() => setAcceptance('accepted')}
              disabled={updatingAcceptance}
              title="Aceitar sessão"
              style={{
                background: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.3)',
                borderRadius: 6, padding: '4px 6px', color: vars.color.success,
                cursor: updatingAcceptance ? 'not-allowed' : 'pointer',
                display: 'flex', alignItems: 'center',
              }}
            >
              <Check size={12} />
            </button>
          )}
          {row.acceptance_status !== 'rejected' && (
            <button
              onClick={() => setAcceptance('rejected')}
              disabled={updatingAcceptance}
              title="Rejeitar sessão"
              style={{
                background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
                borderRadius: 6, padding: '4px 6px', color: '#ef4444',
                cursor: updatingAcceptance ? 'not-allowed' : 'pointer',
                display: 'flex', alignItems: 'center',
              }}
            >
              <X size={12} />
            </button>
          )}
        </div>
      </td>
    </tr>
  )
}

// ── Main Component ────────────────────────────────────────────────────────────

export function FuelingValidationPage() {
  const toast = useToast()

  // Filtros
  const [startDate, setStartDate] = useState(() => {
    const d = new Date()
    d.setDate(d.getDate() - 7)
    return isoDate(d)
  })
  const [endDate, setEndDate] = useState(() => isoDate(new Date()))
  const [bayId, setBayId] = useState('')
  const [threshold, setThreshold] = useState('5')

  // Relatório
  const [report, setReport] = useState<ValidationReport | null>(null)
  const [loading, setLoading] = useState(true)
  // Opções de baia acumuladas a partir dos relatórios carregados sem filtro
  const [bayOptions, setBayOptions] = useState<string[]>([])

  const loadReport = useCallback(async () => {
    setLoading(true)
    try {
      const parsedThreshold = Number(threshold)
      const res = await countingService.getValidationReport({
        start: startDate || undefined,
        end: endDate || undefined,
        bay_id: bayId || undefined,
        threshold: Number.isFinite(parsedThreshold) && parsedThreshold >= 0 ? parsedThreshold : undefined,
      })
      const data = res?.data ?? null
      setReport(data)
      if (data && !bayId) {
        const ids = Array.from(new Set(
          data.sessions.map(s => s.bay_id).filter((b): b is string => b !== null),
        ))
        setBayOptions(prev => Array.from(new Set([...prev, ...ids])))
      }
    } catch (err) {
      setReport(null)
      toast.error(err instanceof Error ? err.message : 'Erro ao carregar relatório de validação')
    } finally {
      setLoading(false)
    }
    // toast é estável (hook de contexto) — fora das deps para evitar loop
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startDate, endDate, bayId, threshold])

  useEffect(() => { loadReport() }, [loadReport])

  const summary = report?.summary
  const sessions: ValidationSessionRow[] = report?.sessions ?? []
  const daily: ValidationDailyRow[] = report?.daily ?? []

  const filterLabel: React.CSSProperties = {
    display: 'block', fontSize: 11, color: vars.color.textMuted, fontWeight: 600,
    textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 6,
  }

  return (
    <div style={{ padding: 24, maxWidth: 1100, margin: '0 auto' }}>
      {/* ── Header ── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <ClipboardCheck size={22} style={{ color: vars.color.success }} />
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: '#f1f5f9' }}>
            Validação de Contagem
          </h2>
        </div>
        <button
          onClick={loadReport}
          style={{
            background: 'transparent', border: `1px solid ${vars.color.borderStrong}`, borderRadius: 6,
            color: vars.color.textSecondary, padding: '6px 12px', cursor: 'pointer',
            display: 'flex', alignItems: 'center', gap: 5, fontSize: 12,
          }}
        >
          <RefreshCw size={13} /> Atualizar
        </button>
      </div>

      <p style={{ color: vars.color.textMuted, fontSize: 13, marginBottom: 24, marginTop: 4 }}>
        Aceite das contagens do sistema vs conferência manual (CD-07). Sessões com erro
        acima do threshold são reprovadas.
      </p>

      {/* ── Filtros ── */}
      <div style={{
        ...cardStyle, padding: 16, marginBottom: 24,
        display: 'flex', gap: 14, alignItems: 'flex-end', flexWrap: 'wrap',
      }}>
        <div>
          <label style={filterLabel}>Início</label>
          <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} style={inputStyle} />
        </div>
        <div>
          <label style={filterLabel}>Fim</label>
          <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} style={inputStyle} />
        </div>
        <div>
          <label style={filterLabel}>Baia</label>
          <select value={bayId} onChange={e => setBayId(e.target.value)} style={{ ...inputStyle, minWidth: 140, cursor: 'pointer' }}>
            <option value="">Todas</option>
            {bayOptions.map(b => (
              <option key={b} value={b}>Baia {b.slice(0, 8)}</option>
            ))}
          </select>
        </div>
        <div>
          <label style={filterLabel}>Threshold (%)</label>
          <input
            type="number" min={0} step={0.5} value={threshold}
            onChange={e => setThreshold(e.target.value)}
            style={{ ...inputStyle, width: 90, fontFamily: 'monospace' }}
          />
        </div>
      </div>

      {loading ? (
        <LoadingSpinner />
      ) : !report ? (
        <div style={{ textAlign: 'center', padding: '64px 20px', color: vars.color.textMuted }}>
          <ClipboardCheck size={36} style={{ opacity: 0.25, marginBottom: 12 }} />
          <p style={{ margin: 0, fontSize: 15, fontWeight: 600, color: vars.color.textMuted }}>
            Não foi possível carregar o relatório
          </p>
        </div>
      ) : (
        <>
          {/* ── Cards de resumo ── */}
          {summary && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 28 }}>
              <SummaryCard
                label="Sessões Validadas"
                value={String(summary.sessions_validated)}
                sub={`threshold ${report.threshold_pct}%`}
              />
              <SummaryCard
                label="Sistema vs Manual"
                value={`${summary.system_count} / ${summary.manual_count}`}
                sub="itens contados"
                accent="#6366f1"
              />
              <SummaryCard
                label="Erro Agregado"
                value={fmtPct(summary.error_pct)}
                sub={`${summary.abs_error} itens de diferença`}
                accent={summary.passed ? vars.color.success : '#f87171'}
              />
              <div style={{ ...cardStyle, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 8 }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: vars.color.textMuted, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Resultado Geral
                </div>
                <div><PassedBadge passed={summary.passed} /></div>
              </div>
            </div>
          )}

          {/* ── Tabela de sessões ── */}
          <div style={{ ...cardStyle, padding: 0, overflow: 'hidden', marginBottom: 24 }}>
            <div style={{ padding: '14px 20px', borderBottom: `1px solid ${vars.color.bgSurface}`, fontSize: 13, fontWeight: 600, color: vars.color.textSecondary }}>
              Sessões com conferência manual
            </div>
            {sessions.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '48px 20px', color: vars.color.textMuted }}>
                <p style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>Nenhuma sessão validada no período</p>
                <p style={{ margin: '6px 0 0', fontSize: 12 }}>
                  Sessões aparecem aqui após o registro da contagem manual.
                </p>
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ borderBottom: `1px solid ${vars.color.bgSurface}` }}>
                      <th style={thStyle}>Placa</th>
                      <th style={thStyle}>Baia</th>
                      <th style={thStyle}>Direção</th>
                      <th style={thStyle}>Início</th>
                      <th style={{ ...thStyle, textAlign: 'right' }}>Sistema</th>
                      <th style={thStyle}>Manual</th>
                      <th style={{ ...thStyle, textAlign: 'right' }}>Erro abs.</th>
                      <th style={{ ...thStyle, textAlign: 'right' }}>Erro %</th>
                      <th style={thStyle}>Resultado</th>
                      <th style={thStyle}>Aceite</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sessions.map((row, idx) => (
                      <SessionRow key={row.id} row={row} striped={idx % 2 === 1} onSaved={loadReport} />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* ── Agregado diário ── */}
          <div style={{ ...cardStyle, padding: 0, overflow: 'hidden' }}>
            <div style={{ padding: '14px 20px', borderBottom: `1px solid ${vars.color.bgSurface}`, fontSize: 13, fontWeight: 600, color: vars.color.textSecondary }}>
              Agregado diário
            </div>
            {daily.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '36px 20px', color: vars.color.textMuted, fontSize: 13 }}>
                Sem dados diários no período.
              </div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: `1px solid ${vars.color.bgSurface}` }}>
                    <th style={thStyle}>Dia</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>Sessões</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>Sistema</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>Manual</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>Erro abs.</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>Erro %</th>
                    <th style={thStyle}>Resultado</th>
                  </tr>
                </thead>
                <tbody>
                  {daily.map((d, idx) => (
                    <tr key={d.day} style={{
                      borderBottom: `1px solid ${vars.color.bgBase}`,
                      background: idx % 2 === 1 ? 'rgba(255,255,255,0.015)' : 'transparent',
                    }}>
                      <td style={{ ...tdStyle, color: '#f1f5f9' }}>
                        {fmtDay(d.day)}
                      </td>
                      <td style={{ ...tdStyle, fontFamily: 'monospace', textAlign: 'right' }}>{d.sessions}</td>
                      <td style={{ ...tdStyle, fontFamily: 'monospace', textAlign: 'right', color: '#a5b4fc' }}>{d.system_total}</td>
                      <td style={{ ...tdStyle, fontFamily: 'monospace', textAlign: 'right' }}>{d.manual_total}</td>
                      <td style={{ ...tdStyle, fontFamily: 'monospace', textAlign: 'right' }}>{d.abs_error}</td>
                      <td style={{ ...tdStyle, fontFamily: 'monospace', textAlign: 'right', color: d.passed ? vars.color.success : '#f87171' }}>
                        {fmtPct(d.error_pct)}
                      </td>
                      <td style={tdStyle}><PassedBadge passed={d.passed} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </div>
  )
}
