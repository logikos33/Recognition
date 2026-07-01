import { FlaskConical, Play, RefreshCw, Square } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { adminService } from '../services/adminService'
import * as s from '../components/admin.css'
import type { HarnessEvidence, HarnessModel, HarnessStatus } from '../types/admin'

const POLL_INTERVAL_MS = 10_000
const MAX_CAMERAS = 28

export function AdminTestConsolePage() {
  const [status, setStatus] = useState<HarnessStatus | null>(null)
  const [models, setModels] = useState<HarnessModel[]>([])
  const [evidence, setEvidence] = useState<HarnessEvidence[]>([])
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [info, setInfo] = useState<string | null>(null)

  const [cameras, setCameras] = useState(4)
  const [modelId, setModelId] = useState<string>('')

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const loadAll = () => {
    setLoading(true)
    Promise.all([
      adminService.getHarnessStatus(),
      adminService.getHarnessModels(),
      adminService.getHarnessEvidence(20),
    ])
      .then(([st, mdl, ev]) => {
        setStatus(st)
        setModels(mdl.models)
        setEvidence(ev.evidence)
        setError(null)
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }

  const loadStatus = () => {
    adminService.getHarnessStatus()
      .then((st) => { setStatus(st); setError(null) })
      .catch((e: Error) => setError(e.message))
    adminService.getHarnessEvidence(20)
      .then((ev) => setEvidence(ev.evidence))
      .catch(() => {})
  }

  useEffect(() => {
    loadAll()
  }, [])

  useEffect(() => {
    if (pollRef.current) clearInterval(pollRef.current)
    if (status?.active) {
      pollRef.current = setInterval(loadStatus, POLL_INTERVAL_MS)
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [status?.active])

  const handleStart = () => {
    setActionLoading(true)
    setError(null)
    setInfo(null)
    adminService.startHarness(cameras, modelId || undefined)
      .then(() => {
        setInfo(`Harness iniciado com ${cameras} câmeras.`)
        loadAll()
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setActionLoading(false))
  }

  const handleStop = () => {
    setActionLoading(true)
    setError(null)
    setInfo(null)
    adminService.stopHarness()
      .then((r) => {
        setInfo(`Harness parado. ${r.cameras_stopped} câmeras encerradas.`)
        loadAll()
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setActionLoading(false))
  }

  const isActive = status?.active === true

  return (
    <div className={s.pageRoot}>
      <div className={s.pageHeader}>
        <div>
          <div className={s.pageTitle}>
            <FlaskConical size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} />
            Console de Teste E2E
          </div>
          <div className={s.pageSubtitle}>
            Harness de câmeras sintéticas — tenant isolado de teste
          </div>
        </div>
        <button className={s.btnGhost} onClick={loadAll} disabled={loading || actionLoading}>
          <RefreshCw size={14} /> Atualizar
        </button>
      </div>

      {error && <div className={s.alertBanner.danger}>{error}</div>}
      {info  && <div className={s.alertBanner.info}>{info}</div>}

      {/* ── Status ── */}
      <div className={s.metricsGrid}>
        <div className={s.metricCard}>
          <div className={s.metricValue}>{isActive ? status!.active_streams ?? '—' : '0'}</div>
          <div className={s.metricLabel}>Streams ativos</div>
        </div>
        <div className={s.metricCard}>
          <div className={s.metricValue}>{isActive ? status!.n_cameras ?? '—' : '0'}</div>
          <div className={s.metricLabel}>Câmeras registradas</div>
        </div>
        <div className={s.metricCard}>
          <div className={s.metricValue}>{isActive ? status!.alerts_generated ?? '0' : '0'}</div>
          <div className={s.metricLabel}>Alertas gerados</div>
        </div>
        <div className={s.metricCard}>
          <div className={s.metricValue} style={{ color: isActive ? '#16a34a' : '#6b7280' }}>
            {isActive ? 'ATIVO' : 'INATIVO'}
          </div>
          <div className={s.metricLabel}>Status</div>
        </div>
      </div>

      {/* ── Controls ── */}
      <div className={s.card}>
        <div className={s.cardTitle}>Configuração do Harness</div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span style={{ fontSize: 13, color: '#6b7280' }}>
              Número de câmeras: <strong>{cameras}</strong>
            </span>
            <input
              type="range"
              min={1}
              max={MAX_CAMERAS}
              value={cameras}
              disabled={isActive || actionLoading}
              onChange={(e) => setCameras(Number(e.target.value))}
              style={{ width: '100%', maxWidth: 320 }}
            />
            <span style={{ fontSize: 11, color: '#9ca3af' }}>1 – {MAX_CAMERAS} câmeras</span>
          </label>

          <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span style={{ fontSize: 13, color: '#6b7280' }}>Modelo</span>
            <select
              value={modelId}
              disabled={isActive || actionLoading}
              onChange={(e) => setModelId(e.target.value)}
              style={{
                padding: '6px 10px', borderRadius: 6, border: '1px solid #e5e7eb',
                fontSize: 13, maxWidth: 360, background: '#fff',
              }}
            >
              <option value="">Padrão do tenant de teste</option>
              {models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}{m.is_default ? ' (padrão)' : ''}
                </option>
              ))}
            </select>
          </label>

          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            {!isActive ? (
              <button
                className={s.btnPrimary}
                onClick={handleStart}
                disabled={actionLoading || loading}
              >
                <Play size={14} /> Iniciar Harness
              </button>
            ) : (
              <button
                className={s.btnDanger}
                onClick={handleStop}
                disabled={actionLoading}
              >
                <Square size={14} /> Parar Harness
              </button>
            )}
            {actionLoading && <span className={s.muted}>Aguardando...</span>}
          </div>

          {isActive && (
            <div style={{ fontSize: 12, color: '#6b7280', lineHeight: 1.6 }}>
              <strong>Iniciado:</strong> {status!.started_at ? new Date(status!.started_at).toLocaleString('pt-BR') : '—'}
              {' · '}
              <strong>Template RTSP:</strong> {status!.rtsp_template}
              {' · '}
              <strong>Classes:</strong> {status!.violation_classes}
            </div>
          )}
        </div>
      </div>

      {/* ── Models ── */}
      {models.length > 0 && (
        <div className={s.card}>
          <div className={s.cardTitle}>Modelos Disponíveis (registry)</div>
          <table className={s.table} style={{ width: '100%' }}>
            <thead>
              <tr>
                <th className={s.th}>Nome</th>
                <th className={s.th}>Chave R2</th>
                <th className={s.th}>Padrão</th>
                <th className={s.th}>Criado em</th>
              </tr>
            </thead>
            <tbody>
              {models.map((m) => (
                <tr key={m.id} className={s.trHover}>
                  <td className={s.td}>{m.name}</td>
                  <td className={s.td} style={{ fontFamily: 'monospace', fontSize: 12 }}>{m.model_key}</td>
                  <td className={s.td}>
                    {m.is_default && <span className={s.badge} style={{ background: 'rgba(34,197,94,0.15)', color: '#16a34a' }}>sim</span>}
                  </td>
                  <td className={s.td} style={{ color: '#9ca3af', fontSize: 12 }}>
                    {m.created_at ? new Date(m.created_at).toLocaleString('pt-BR') : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Evidence ── */}
      <div className={s.card}>
        <div className={s.cardTitle}>Evidências Recentes (R2)</div>
        {evidence.length === 0 ? (
          <div className={s.muted}>Nenhuma evidência gerada ainda.</div>
        ) : (
          <table className={s.table} style={{ width: '100%' }}>
            <thead>
              <tr>
                <th className={s.th}>Câmera</th>
                <th className={s.th}>Chave R2</th>
                <th className={s.th}>Confiança</th>
                <th className={s.th}>Detectado em</th>
              </tr>
            </thead>
            <tbody>
              {evidence.map((ev) => (
                <tr key={ev.id} className={s.trHover}>
                  <td className={s.td}>{ev.camera_name ?? ev.camera_id ?? '—'}</td>
                  <td className={s.td} style={{ fontFamily: 'monospace', fontSize: 12 }}>{ev.evidence_key}</td>
                  <td className={s.td}>
                    {ev.confidence != null
                      ? <span style={{ color: ev.confidence >= 0.8 ? '#16a34a' : '#ca8a04' }}>
                          {(ev.confidence * 100).toFixed(1)}%
                        </span>
                      : '—'}
                  </td>
                  <td className={s.td} style={{ color: '#9ca3af', fontSize: 12 }}>
                    {ev.created_at ? new Date(ev.created_at).toLocaleString('pt-BR') : '—'}
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
