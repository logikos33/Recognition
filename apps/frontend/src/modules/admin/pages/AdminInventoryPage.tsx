/**
 * AdminInventoryPage — Inventário de câmeras/edge com onboarding em lote.
 *
 * Funcionalidades:
 *   - Tabela de câmeras com colunas: name, brand, ip, probe_status, codec_detected, substream_ok
 *   - Botão "Importar CSV" (parseia CSV client-side)
 *   - Botão "Testar" por linha (probe single)
 *   - Botão "Testar Selecionadas" (probe-batch, max 5 simultâneos no servidor)
 *
 * Usa api.ts — NÃO fetch raw.
 */
import { type ChangeEvent, type CSSProperties, useCallback, useRef, useState } from 'react'
import { api } from '../../../services/api'

// ── Types ─────────────────────────────────────────────────────────────────────

interface Camera {
  id: string
  name: string
  brand: string | null
  model: string | null
  ip: string | null
  host: string
  port: number
  manufacturer: string | null
  probe_status: string | null
  codec_detected: string | null
  substream_ok: boolean | null
  last_probe_at: string | null
  is_active: boolean
  tenant_name: string | null
  notes: string | null
}

interface InventoryResponse {
  status: string
  data: {
    cameras: Camera[]
    total: number
  }
}

interface ProbeResult {
  camera_id: string
  probe_status: string
  codec_detected: string | null
  substream_ok: boolean
  detail?: string
}

interface ProbeBatchResponse {
  status: string
  data: { results: ProbeResult[] }
}

interface ImportResponse {
  status: string
  data: { created: number; errors: Array<{ row: number; reason: string }> }
}

// ── CSV parser ────────────────────────────────────────────────────────────────

interface CsvRow {
  name: string
  brand: string
  ip: string
  port: string
  username: string
  module: string
  tenant_id?: string
  [key: string]: string | undefined
}

function parseCsv(text: string): CsvRow[] {
  const lines = text.trim().split(/\r?\n/)
  if (lines.length < 2) return []
  const headers = lines[0].split(',').map((h) => h.trim().toLowerCase())
  return lines.slice(1).map((line) => {
    const values = line.split(',').map((v) => v.trim())
    const row: CsvRow = { name: '', brand: '', ip: '', port: '554', username: 'admin', module: 'epi' }
    headers.forEach((h, i) => {
      row[h] = values[i] ?? ''
    })
    return row
  })
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const STATUS_BADGE: Record<string, { bg: string; color: string; label: string }> = {
  ok:      { bg: '#d1fae5', color: '#065f46', label: 'OK' },
  error:   { bg: '#fee2e2', color: '#991b1b', label: 'Erro' },
  timeout: { bg: '#fef3c7', color: '#92400e', label: 'Timeout' },
  pending: { bg: '#e5e7eb', color: '#374151', label: 'Pendente' },
}

function ProbeStatusBadge({ status }: { status: string | null }) {
  const s = status ?? 'pending'
  const cfg = STATUS_BADGE[s] ?? STATUS_BADGE['pending']
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '2px 8px',
        borderRadius: 12,
        fontSize: 11,
        fontWeight: 600,
        background: cfg.bg,
        color: cfg.color,
      }}
    >
      {cfg.label}
    </span>
  )
}

function BoolBadge({ value }: { value: boolean | null }) {
  if (value === null) return <span style={{ color: '#9ca3af' }}>—</span>
  return value
    ? <span style={{ color: '#059669', fontWeight: 600 }}>Sim</span>
    : <span style={{ color: '#dc2626', fontWeight: 600 }}>Não</span>
}

// ── Component ─────────────────────────────────────────────────────────────────

export function AdminInventoryPage() {
  const [cameras, setCameras] = useState<Camera[]>([])
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [probingIds, setProbingIds] = useState<Set<string>>(new Set())
  const [importLog, setImportLog] = useState<string | null>(null)
  const [importError, setImportError] = useState<string | null>(null)

  // Filters
  const [filterTenant, setFilterTenant] = useState('')
  const [filterBrand, setFilterBrand] = useState('')
  const [filterProbeStatus, setFilterProbeStatus] = useState('')

  const fileInputRef = useRef<HTMLInputElement>(null)

  // ── Load inventory ──────────────────────────────────────────────────────────

  const loadInventory = useCallback(async () => {
    setLoading(true)
    setLoadError(null)
    try {
      const params = new URLSearchParams()
      if (filterTenant) params.set('tenant_id', filterTenant)
      if (filterBrand) params.set('brand', filterBrand)
      if (filterProbeStatus) params.set('probe_status', filterProbeStatus)
      const qs = params.toString()
      const res = await api.get<InventoryResponse>(`/v1/admin/inventory${qs ? `?${qs}` : ''}`)
      setCameras(res.data.cameras)
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : 'Erro ao carregar inventário')
    } finally {
      setLoading(false)
    }
  }, [filterTenant, filterBrand, filterProbeStatus])

  // ── Selection ───────────────────────────────────────────────────────────────

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleSelectAll = () => {
    if (selectedIds.size === cameras.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(cameras.map((c) => c.id)))
    }
  }

  // ── Probe single ────────────────────────────────────────────────────────────

  const probeOne = async (cameraId: string) => {
    setProbingIds((prev) => new Set(prev).add(cameraId))
    try {
      const res = await api.post<{ status: string; data: ProbeResult }>(
        `/v1/admin/cameras/${cameraId}/probe`,
      )
      const result = res.data
      setCameras((prev) =>
        prev.map((c) =>
          c.id === cameraId
            ? {
                ...c,
                probe_status: result.probe_status,
                codec_detected: result.codec_detected,
                substream_ok: result.substream_ok,
                last_probe_at: new Date().toISOString(),
              }
            : c,
        ),
      )
    } catch (e) {
      setCameras((prev) =>
        prev.map((c) => (c.id === cameraId ? { ...c, probe_status: 'error' } : c)),
      )
    } finally {
      setProbingIds((prev) => {
        const next = new Set(prev)
        next.delete(cameraId)
        return next
      })
    }
  }

  // ── Probe batch ─────────────────────────────────────────────────────────────

  const probeSelected = async () => {
    const ids = Array.from(selectedIds)
    if (!ids.length) return
    ids.forEach((id) =>
      setProbingIds((prev) => new Set(prev).add(id)),
    )
    try {
      const res = await api.post<ProbeBatchResponse>('/v1/admin/cameras/probe-batch', {
        camera_ids: ids,
      })
      const results = res.data.results
      setCameras((prev) =>
        prev.map((c) => {
          const r = results.find((x) => x.camera_id === c.id)
          if (!r) return c
          return {
            ...c,
            probe_status: r.probe_status,
            codec_detected: r.codec_detected,
            substream_ok: r.substream_ok,
            last_probe_at: new Date().toISOString(),
          }
        }),
      )
    } catch (e) {
      // best-effort
    } finally {
      setProbingIds((prev) => {
        const next = new Set(prev)
        ids.forEach((id) => next.delete(id))
        return next
      })
    }
  }

  // ── CSV Import ──────────────────────────────────────────────────────────────

  const handleFileChange = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setImportLog(null)
    setImportError(null)

    try {
      const text = await file.text()
      const rows = parseCsv(text)
      if (!rows.length) {
        setImportError('CSV vazio ou sem linhas de dados')
        return
      }

      const camerasPayload = rows.map((r) => ({
        name: r['name'] || '',
        brand: r['brand'] || '',
        ip: r['ip'] || '',
        port: parseInt(r['port'] || '554', 10),
        username: r['username'] || 'admin',
        module: r['module'] || 'epi',
        tenant_id: r['tenant_id'] || '',
        manufacturer: r['brand'] || 'generic',
      }))

      const res = await api.post<ImportResponse>('/v1/admin/cameras/import', {
        cameras: camerasPayload,
      })
      const { created, errors } = res.data
      let msg = `Importação concluída: ${created} câmera(s) criada(s).`
      if (errors.length > 0) {
        msg += ` ${errors.length} erro(s):\n` + errors.map((e) => `  Linha ${e.row}: ${e.reason}`).join('\n')
        setImportError(msg)
      } else {
        setImportLog(msg)
      }
      // Reload inventory
      await loadInventory()
    } catch (err) {
      setImportError(err instanceof Error ? err.message : 'Erro na importação')
    } finally {
      // Reset file input so the same file can be re-imported
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div style={{ padding: '24px 32px', maxWidth: 1400, margin: '0 auto' }}>
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>
        Inventário de Câmeras
      </h1>
      <p style={{ color: '#6b7280', fontSize: 14, marginBottom: 24 }}>
        Onboarding em lote e diagnóstico de conectividade por câmera.
      </p>

      {/* ── Filters ── */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ fontSize: 12, color: '#6b7280' }}>Tenant ID</label>
          <input
            type="text"
            placeholder="UUID do tenant"
            value={filterTenant}
            onChange={(e) => setFilterTenant(e.target.value)}
            style={inputStyle}
          />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ fontSize: 12, color: '#6b7280' }}>Marca</label>
          <input
            type="text"
            placeholder="Ex: Intelbras"
            value={filterBrand}
            onChange={(e) => setFilterBrand(e.target.value)}
            style={inputStyle}
          />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ fontSize: 12, color: '#6b7280' }}>Status Probe</label>
          <select
            value={filterProbeStatus}
            onChange={(e) => setFilterProbeStatus(e.target.value)}
            style={{ ...inputStyle, background: '#fff' }}
          >
            <option value="">Todos</option>
            <option value="pending">Pendente</option>
            <option value="ok">OK</option>
            <option value="error">Erro</option>
            <option value="timeout">Timeout</option>
          </select>
        </div>
        <button onClick={loadInventory} disabled={loading} style={btnPrimary}>
          {loading ? 'Carregando...' : 'Buscar'}
        </button>
      </div>

      {/* ── Action bar ── */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 16, alignItems: 'center', flexWrap: 'wrap' }}>
        <button
          disabled={selectedIds.size === 0 || probingIds.size > 0}
          onClick={probeSelected}
          style={selectedIds.size > 0 ? btnPrimary : btnDisabled}
        >
          Testar Selecionadas ({selectedIds.size})
        </button>

        <button onClick={() => fileInputRef.current?.click()} style={btnSecondary}>
          Importar CSV
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,text/csv"
          onChange={handleFileChange}
          style={{ display: 'none' }}
        />
        <span style={{ fontSize: 12, color: '#9ca3af' }}>
          CSV: name,brand,ip,port,username,module,tenant_id
        </span>
      </div>

      {/* ── Import log ── */}
      {importLog && (
        <div style={{ background: '#d1fae5', border: '1px solid #6ee7b7', borderRadius: 6, padding: '10px 14px', marginBottom: 12, fontSize: 13, color: '#065f46', whiteSpace: 'pre-wrap' }}>
          {importLog}
        </div>
      )}
      {importError && (
        <div style={{ background: '#fee2e2', border: '1px solid #fca5a5', borderRadius: 6, padding: '10px 14px', marginBottom: 12, fontSize: 13, color: '#991b1b', whiteSpace: 'pre-wrap' }}>
          {importError}
        </div>
      )}
      {loadError && (
        <div style={{ background: '#fee2e2', border: '1px solid #fca5a5', borderRadius: 6, padding: '10px 14px', marginBottom: 12, fontSize: 13, color: '#991b1b' }}>
          {loadError}
        </div>
      )}

      {/* ── Table ── */}
      {cameras.length === 0 && !loading ? (
        <div style={{ textAlign: 'center', color: '#9ca3af', padding: '48px 0', fontSize: 14 }}>
          {loadError ? null : 'Clique em "Buscar" para carregar o inventário.'}
        </div>
      ) : (
        <div style={{ overflowX: 'auto', border: '1px solid #e5e7eb', borderRadius: 8 }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#f9fafb', borderBottom: '1px solid #e5e7eb' }}>
                <th style={th}>
                  <input
                    type="checkbox"
                    checked={selectedIds.size === cameras.length && cameras.length > 0}
                    onChange={toggleSelectAll}
                  />
                </th>
                <th style={th}>Nome</th>
                <th style={th}>Marca</th>
                <th style={th}>IP / Host</th>
                <th style={th}>Porta</th>
                <th style={th}>Módulo</th>
                <th style={th}>Probe</th>
                <th style={th}>Codec</th>
                <th style={th}>Substream</th>
                <th style={th}>Tenant</th>
                <th style={th}>Ações</th>
              </tr>
            </thead>
            <tbody>
              {cameras.map((cam) => (
                <tr
                  key={cam.id}
                  style={{
                    borderBottom: '1px solid #f3f4f6',
                    background: selectedIds.has(cam.id) ? '#eff6ff' : undefined,
                  }}
                >
                  <td style={td}>
                    <input
                      type="checkbox"
                      checked={selectedIds.has(cam.id)}
                      onChange={() => toggleSelect(cam.id)}
                    />
                  </td>
                  <td style={td}>
                    <div style={{ fontWeight: 600 }}>{cam.name}</div>
                    {cam.model && <div style={{ fontSize: 11, color: '#9ca3af' }}>{cam.model}</div>}
                  </td>
                  <td style={td}>{cam.brand ?? cam.manufacturer ?? '—'}</td>
                  <td style={td}>
                    <code style={{ fontSize: 12 }}>{cam.ip ?? cam.host}</code>
                  </td>
                  <td style={td}>{cam.port}</td>
                  <td style={td}>
                    <span style={{ fontSize: 12, color: '#6366f1', fontWeight: 500 }}>
                      {cam.is_active ? '' : '(draft) '}
                    </span>
                  </td>
                  <td style={td}>
                    <ProbeStatusBadge status={cam.probe_status} />
                    {cam.last_probe_at && (
                      <div style={{ fontSize: 10, color: '#9ca3af', marginTop: 2 }}>
                        {new Date(cam.last_probe_at).toLocaleString('pt-BR')}
                      </div>
                    )}
                  </td>
                  <td style={td}>
                    {cam.codec_detected
                      ? <code style={{ fontSize: 12 }}>{cam.codec_detected}</code>
                      : <span style={{ color: '#9ca3af' }}>—</span>}
                  </td>
                  <td style={td}>
                    <BoolBadge value={cam.substream_ok} />
                  </td>
                  <td style={td}>
                    <div style={{ fontSize: 12 }}>{cam.tenant_name ?? '—'}</div>
                  </td>
                  <td style={td}>
                    <button
                      disabled={probingIds.has(cam.id)}
                      onClick={() => probeOne(cam.id)}
                      style={probingIds.has(cam.id) ? btnDisabled : btnSmall}
                    >
                      {probingIds.has(cam.id) ? '...' : 'Testar'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div style={{ marginTop: 12, fontSize: 12, color: '#9ca3af' }}>
        {cameras.length > 0 && `${cameras.length} câmera(s) encontrada(s)`}
      </div>
    </div>
  )
}

// ── Styles ────────────────────────────────────────────────────────────────────

const inputStyle: CSSProperties = {
  padding: '6px 10px',
  border: '1px solid #d1d5db',
  borderRadius: 6,
  fontSize: 13,
  minWidth: 180,
}

const btnBase: CSSProperties = {
  padding: '7px 14px',
  borderRadius: 6,
  border: 'none',
  cursor: 'pointer',
  fontSize: 13,
  fontWeight: 500,
  transition: 'opacity 0.15s',
}

const btnPrimary: CSSProperties = {
  ...btnBase,
  background: '#4f46e5',
  color: '#fff',
}

const btnSecondary: CSSProperties = {
  ...btnBase,
  background: '#f3f4f6',
  color: '#374151',
  border: '1px solid #d1d5db',
}

const btnSmall: CSSProperties = {
  ...btnBase,
  padding: '4px 10px',
  fontSize: 12,
  background: '#f0fdf4',
  color: '#166534',
  border: '1px solid #bbf7d0',
}

const btnDisabled: CSSProperties = {
  ...btnBase,
  background: '#f3f4f6',
  color: '#9ca3af',
  cursor: 'not-allowed',
  opacity: 0.7,
}

const th: CSSProperties = {
  padding: '10px 12px',
  textAlign: 'left',
  fontWeight: 600,
  color: '#374151',
  fontSize: 12,
  whiteSpace: 'nowrap',
}

const td: CSSProperties = {
  padding: '10px 12px',
  verticalAlign: 'middle',
}
