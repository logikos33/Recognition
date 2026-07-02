import { useState } from 'react'
import type { CSSProperties } from 'react'
import { api } from '../../services/api'

interface ProbeResult {
  ok: boolean | null
  method?: string
  codec?: string | null
  resolution?: string | null
  fps?: number | null
  substream_url_sugerida?: string | null
  gateway_available?: boolean
  warning?: string | null
  error?: string | null
  message?: string
}

/** Envelope padrão retornado pelo backend: { status, data } */
type ApiEnvelope<T> = { status: string; data: T; error?: string }

interface WizardProps {
  onComplete: (camera: Record<string, unknown>) => void
  onCancel: () => void
}

const MANUFACTURERS = [
  { id: 'intelbras', name: 'Intelbras', desc: 'Câmeras IP Intelbras (VIP, Mibo)' },
  { id: 'hikvision', name: 'Hikvision', desc: 'Câmeras Hikvision DS-2CD / DS-2DE' },
  { id: 'dahua', name: 'Dahua', desc: 'Câmeras Dahua IPC / SD' },
  { id: 'generic', name: 'Genérico / ONVIF', desc: 'Qualquer câmera compatível com RTSP' },
]

const STEP_LABELS = ['Fabricante', 'Acesso', 'Verificação', 'Confirmar']

export function CameraOnboardingWizard({ onComplete, onCancel }: WizardProps) {
  const [step, setStep] = useState(0)
  const [manufacturer, setManufacturer] = useState('')
  const [form, setForm] = useState({
    name: '',
    ip_or_host: '',
    port: '554',
    username: 'admin',
    password: '',
    channel: '1',
    is_behind_nat: false,
  })
  const [probing, setProbing] = useState(false)
  const [probeResult, setProbeResult] = useState<ProbeResult | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function updateForm(field: string, value: string | boolean) {
    setForm(f => ({ ...f, [field]: value }))
  }

  async function runProbe() {
    setProbing(true)
    setError(null)
    setProbeResult(null)
    try {
      const res = await api.post<ApiEnvelope<ProbeResult>>(
        '/cameras/probe',
        {
          manufacturer,
          ip_or_host: form.ip_or_host,
          port: parseInt(form.port) || 554,
          username: form.username,
          password: form.password,
          channel: parseInt(form.channel) || 1,
          is_behind_nat: form.is_behind_nat,
        },
      )
      if (res.status === 'success') {
        setProbeResult(res.data)
        setStep(2)
      } else {
        setError(res.error || 'Erro ao verificar câmera')
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Erro ao verificar câmera')
    } finally {
      setProbing(false)
    }
  }

  async function saveCamera() {
    setSaving(true)
    setError(null)
    try {
      const res = await api.post<ApiEnvelope<Record<string, unknown>>>(
        '/cameras',
        {
          name: form.name,
          manufacturer,
          host: form.ip_or_host,
          port: parseInt(form.port) || 554,
          username: form.username,
          password: form.password,
          channel: parseInt(form.channel) || 1,
          detection_stream_url: probeResult?.substream_url_sugerida || undefined,
          video_codec: probeResult?.codec || undefined,
        },
      )
      if (res.status === 'success') {
        onComplete(res.data)
      } else {
        setError(res.error || 'Erro ao salvar câmera')
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Erro ao salvar câmera')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={styles.overlay}>
      <div style={styles.modal}>
        <div style={styles.header}>
          <h2 style={styles.title}>Adicionar Câmera</h2>
          <button onClick={onCancel} style={styles.closeBtn}>✕</button>
        </div>

        {/* Progress bar */}
        <div style={styles.progress}>
          {STEP_LABELS.map((label, i) => (
            <div key={label} style={styles.progressStep}>
              <div style={{
                ...styles.progressDot,
                background: i <= step ? '#2563eb' : '#e5e7eb',
              }}>
                {i < step ? '✓' : i + 1}
              </div>
              <span style={{ fontSize: 11, color: i <= step ? '#2563eb' : '#9ca3af' }}>{label}</span>
            </div>
          ))}
        </div>

        {/* Step 0 — Fabricante */}
        {step === 0 && (
          <div style={styles.body}>
            <p style={styles.subtitle}>Selecione o fabricante da câmera</p>
            <div style={styles.grid}>
              {MANUFACTURERS.map(m => (
                <button
                  key={m.id}
                  onClick={() => setManufacturer(m.id)}
                  style={{
                    ...styles.mfrBtn,
                    border: manufacturer === m.id ? '2px solid #2563eb' : '2px solid #e5e7eb',
                    background: manufacturer === m.id ? '#eff6ff' : '#fff',
                  }}
                >
                  <span style={styles.mfrName}>{m.name}</span>
                  <span style={styles.mfrDesc}>{m.desc}</span>
                </button>
              ))}
            </div>
            <div style={styles.actions}>
              <button onClick={onCancel} style={styles.btnSecondary}>Cancelar</button>
              <button
                onClick={() => { setError(null); setStep(1) }}
                disabled={!manufacturer}
                style={{ ...styles.btnPrimary, opacity: manufacturer ? 1 : 0.4 }}
              >
                Próximo →
              </button>
            </div>
          </div>
        )}

        {/* Step 1 — Acesso */}
        {step === 1 && (
          <div style={styles.body}>
            <p style={styles.subtitle}>Informe o endereço e credenciais da câmera</p>
            <label style={styles.label}>Nome da câmera *</label>
            <input
              style={styles.input}
              value={form.name}
              onChange={e => updateForm('name', e.target.value)}
              placeholder="Ex: Portão principal"
            />
            <label style={styles.label}>IP ou hostname *</label>
            <input
              style={styles.input}
              value={form.ip_or_host}
              onChange={e => updateForm('ip_or_host', e.target.value)}
              placeholder="192.168.1.100 ou camera.local"
            />
            <div style={styles.row}>
              <div style={{ flex: 1 }}>
                <label style={styles.label}>Porta</label>
                <input style={styles.input} value={form.port}
                  onChange={e => updateForm('port', e.target.value)} placeholder="554" />
              </div>
              <div style={{ flex: 1, marginLeft: 8 }}>
                <label style={styles.label}>Canal</label>
                <input style={styles.input} value={form.channel}
                  onChange={e => updateForm('channel', e.target.value)} placeholder="1" />
              </div>
            </div>
            <label style={styles.label}>Usuário</label>
            <input style={styles.input} value={form.username}
              onChange={e => updateForm('username', e.target.value)} placeholder="admin" />
            <label style={styles.label}>Senha</label>
            <input style={styles.input} type="password" value={form.password}
              onChange={e => updateForm('password', e.target.value)} placeholder="••••••••" />
            <label style={{ ...styles.label, display: 'flex', alignItems: 'center', gap: 8, marginTop: 12 }}>
              <input type="checkbox" checked={form.is_behind_nat}
                onChange={e => updateForm('is_behind_nat', e.target.checked)} />
              Câmera sem IP público / atrás de NAT
            </label>
            {error && <p style={styles.errorMsg}>{error}</p>}
            <div style={styles.actions}>
              <button onClick={() => setStep(0)} style={styles.btnSecondary}>← Voltar</button>
              <button
                onClick={runProbe}
                disabled={probing || !form.ip_or_host || !form.name}
                style={{ ...styles.btnPrimary, opacity: (probing || !form.ip_or_host || !form.name) ? 0.4 : 1 }}
              >
                {probing ? 'Verificando...' : 'Verificar conexão →'}
              </button>
            </div>
          </div>
        )}

        {/* Step 2 — Resultado do probe */}
        {step === 2 && probeResult && (
          <div style={styles.body}>
            {probeResult.method === 'nat' ? (
              <>
                <div style={styles.infoBox}>
                  <p style={{ fontWeight: 600, marginBottom: 4 }}>Câmera atrás de NAT</p>
                  <p style={{ fontSize: 13 }}>{probeResult.message}</p>
                  {probeResult.gateway_available && (
                    <p style={{ color: '#16a34a', fontSize: 13, marginTop: 4 }}>
                      ✓ Gateway ativo detectado para este tenant.
                    </p>
                  )}
                </div>
                <p style={{ fontSize: 13, color: '#6b7280', marginTop: 8 }}>
                  Você pode salvar a câmera agora e a conexão será estabelecida via gateway.
                </p>
              </>
            ) : probeResult.ok ? (
              <div style={styles.successBox}>
                <p style={{ fontWeight: 600, color: '#16a34a', marginBottom: 8 }}>
                  ✓ Câmera encontrada!
                </p>
                {probeResult.codec && (
                  <p style={{ fontSize: 13 }}>Codec: <b>{probeResult.codec?.toUpperCase()}</b></p>
                )}
                {probeResult.resolution && (
                  <p style={{ fontSize: 13 }}>Resolução: <b>{probeResult.resolution}</b></p>
                )}
                {probeResult.fps && (
                  <p style={{ fontSize: 13 }}>FPS: <b>{probeResult.fps}</b></p>
                )}
                {probeResult.warning && (
                  <p style={{ fontSize: 12, color: '#d97706', marginTop: 4 }}>⚠ {probeResult.warning}</p>
                )}
              </div>
            ) : (
              <div style={styles.errorBox}>
                <p style={{ fontWeight: 600, color: '#dc2626', marginBottom: 4 }}>
                  ✗ Não foi possível conectar
                </p>
                <p style={{ fontSize: 13 }}>{probeResult.error}</p>
              </div>
            )}
            {error && <p style={styles.errorMsg}>{error}</p>}
            <div style={styles.actions}>
              <button onClick={() => { setStep(1); setProbeResult(null) }} style={styles.btnSecondary}>
                ← Corrigir dados
              </button>
              <button
                onClick={() => setStep(3)}
                disabled={probeResult.ok === false}
                style={{ ...styles.btnPrimary, opacity: probeResult.ok === false ? 0.4 : 1 }}
              >
                Confirmar →
              </button>
            </div>
          </div>
        )}

        {/* Step 3 — Confirmar e salvar */}
        {step === 3 && (
          <div style={styles.body}>
            <p style={styles.subtitle}>Revise os dados antes de salvar</p>
            <div style={styles.summary}>
              <Row label="Nome" value={form.name} />
              <Row label="Fabricante" value={MANUFACTURERS.find(m => m.id === manufacturer)?.name || manufacturer} />
              <Row label="Host" value={`${form.ip_or_host}:${form.port}`} />
              <Row label="Canal" value={form.channel} />
              <Row label="Usuário" value={form.username} />
              {probeResult?.codec && <Row label="Codec detectado" value={probeResult.codec?.toUpperCase() || ''} />}
              {probeResult?.resolution && <Row label="Resolução" value={probeResult.resolution || ''} />}
            </div>
            {error && <p style={styles.errorMsg}>{error}</p>}
            <div style={styles.actions}>
              <button onClick={() => setStep(2)} style={styles.btnSecondary}>← Voltar</button>
              <button onClick={saveCamera} disabled={saving}
                style={{ ...styles.btnPrimary, opacity: saving ? 0.4 : 1 }}>
                {saving ? 'Salvando...' : 'Salvar câmera'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0',
      borderBottom: '1px solid #f3f4f6' }}>
      <span style={{ color: '#6b7280', fontSize: 13 }}>{label}</span>
      <span style={{ fontWeight: 500, fontSize: 13 }}>{value}</span>
    </div>
  )
}

const styles: Record<string, CSSProperties> = {
  overlay: {
    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
    display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
  },
  modal: {
    background: '#fff', borderRadius: 12, width: '100%', maxWidth: 480,
    boxShadow: '0 20px 60px rgba(0,0,0,0.2)', overflow: 'hidden',
  },
  header: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '16px 20px', borderBottom: '1px solid #e5e7eb',
  },
  title: { margin: 0, fontSize: 18, fontWeight: 700 },
  closeBtn: {
    background: 'none', border: 'none', cursor: 'pointer', fontSize: 18,
    color: '#6b7280', padding: 4, lineHeight: 1,
  },
  progress: {
    display: 'flex', justifyContent: 'space-around', padding: '12px 20px',
    borderBottom: '1px solid #f3f4f6', background: '#fafafa',
  },
  progressStep: { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 },
  progressDot: {
    width: 28, height: 28, borderRadius: '50%', display: 'flex',
    alignItems: 'center', justifyContent: 'center', color: '#fff',
    fontSize: 12, fontWeight: 700, transition: 'background 0.2s',
  },
  body: { padding: '20px' },
  subtitle: { color: '#6b7280', fontSize: 14, marginBottom: 16, marginTop: 0 },
  grid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 20 },
  mfrBtn: {
    display: 'flex', flexDirection: 'column', alignItems: 'flex-start',
    padding: 12, borderRadius: 8, cursor: 'pointer', textAlign: 'left',
    transition: 'all 0.15s',
  },
  mfrName: { fontWeight: 600, fontSize: 14, marginBottom: 2 },
  mfrDesc: { fontSize: 11, color: '#6b7280' },
  label: { display: 'block', fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 4, marginTop: 12 },
  input: {
    width: '100%', padding: '8px 10px', border: '1px solid #d1d5db',
    borderRadius: 6, fontSize: 14, boxSizing: 'border-box', outline: 'none',
  },
  row: { display: 'flex', gap: 0 },
  actions: { display: 'flex', justifyContent: 'space-between', marginTop: 20, gap: 8 },
  btnPrimary: {
    background: '#2563eb', color: '#fff', border: 'none', borderRadius: 8,
    padding: '10px 20px', fontWeight: 600, fontSize: 14, cursor: 'pointer', flex: 1,
  },
  btnSecondary: {
    background: '#f3f4f6', color: '#374151', border: '1px solid #e5e7eb',
    borderRadius: 8, padding: '10px 20px', fontWeight: 600, fontSize: 14, cursor: 'pointer',
  },
  successBox: {
    background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 8,
    padding: 16, marginBottom: 12,
  },
  errorBox: {
    background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8,
    padding: 16, marginBottom: 12,
  },
  infoBox: {
    background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 8,
    padding: 16, marginBottom: 12,
  },
  errorMsg: { color: '#dc2626', fontSize: 13, marginTop: 8 },
  summary: { background: '#fafafa', borderRadius: 8, padding: '8px 12px', marginBottom: 16 },
}
