/**
 * CameraWizard — wizard em 4 passos para criar/editar câmeras.
 *
 * Passo 1: Fabricante
 * Passo 2: Dados de conexão (IP, porta, usuário, senha, path)
 * Passo 3: Identificação (nome, localização) + preview da URL
 * Passo 4: Teste de conectividade com checklist diagnóstico
 *
 * Modo dual: criação (camera prop ausente) e edição (camera prop presente).
 * Em modo criação, a câmera é criada no banco no passo 4 antes de testar.
 * Em modo edição, os campos são atualizados antes de testar.
 */
import { useState } from 'react'
import toast from 'react-hot-toast'
import type { Camera } from '../../types'
import {
  cameraService,
  buildRtspPreview,
  getDefaultPath,
  type CameraFormData,
  type TestResult,
  type TestCheck,
} from '../../services/cameraService'

interface CameraWizardProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: () => void
  camera?: Camera
}

const MANUFACTURERS = [
  { id: 'hikvision', name: 'Hikvision' },
  { id: 'dahua', name: 'Dahua' },
  { id: 'intelbras', name: 'Intelbras' },
  { id: 'axis', name: 'Axis' },
  { id: 'samsung', name: 'Samsung' },
  { id: 'generic', name: 'Outra marca' },
]

const STEP_LABELS = ['Fabricante', 'Conexão', 'Identificação', 'Teste']

function emptyForm(cam?: Camera): CameraFormData {
  return {
    manufacturer: cam?.manufacturer || '',
    ip: cam?.host || '',
    port: cam?.port || 554,
    username: cam?.username || 'admin',
    password: '',
    path: cam?.rtsp_url_override || '',
    name: cam?.name || '',
    location: cam?.location || '',
  }
}

function CheckIcon({ check }: { check: TestCheck }) {
  if (check.status === 'ok') return <span style={{ color: '#22c55e' }}>✓</span>
  if (check.status === 'error') return <span style={{ color: '#ef4444' }}>✗</span>
  if (check.status === 'warning') return <span style={{ color: '#f59e0b' }}>!</span>
  return <span style={{ color: '#475569' }}>○</span>
}

const CHECK_LABELS: Record<string, string> = {
  url_format: 'Formato da URL RTSP',
  host_reachable: 'Câmera acessível na rede',
  port_open: 'Porta RTSP aberta',
  rtsp_response: 'Resposta ao protocolo RTSP',
  stream_available: 'Stream de vídeo disponível',
}

export function CameraWizard({ isOpen, onClose, onSuccess, camera: editCamera }: CameraWizardProps) {
  const [step, setStep] = useState(1)
  const [form, setForm] = useState<CameraFormData>(() => emptyForm(editCamera))
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [createdId, setCreatedId] = useState<string | undefined>(editCamera?.id)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<TestResult | null>(null)

  if (!isOpen) return null

  const isEdit = Boolean(editCamera)

  function set(field: keyof CameraFormData, value: string | number) {
    setForm(f => ({ ...f, [field]: value }))
    setErrors(e => ({ ...e, [field]: '' }))
  }

  function validate(): boolean {
    const errs: Record<string, string> = {}
    if (step === 1 && !form.manufacturer) errs.manufacturer = 'Selecione o fabricante'
    if (step === 2) {
      if (!form.ip) errs.ip = 'Informe o IP da câmera'
      else if (!/^\d{1,3}(\.\d{1,3}){3}$/.test(form.ip)) errs.ip = 'IP inválido (ex: 192.168.1.100)'
      if (!form.port || form.port < 1 || form.port > 65535) errs.port = 'Porta inválida (1–65535)'
    }
    if (step === 3 && !form.name.trim()) errs.name = 'Dê um nome para a câmera'
    setErrors(errs)
    return Object.keys(errs).length === 0
  }

  function next() {
    if (validate()) setStep(s => Math.min(s + 1, 4))
  }

  function back() {
    if (step > 1) {
      setStep(s => s - 1)
      setTestResult(null)
    } else {
      handleClose()
    }
  }

  function handleClose() {
    setStep(1)
    setForm(emptyForm(editCamera))
    setErrors({})
    setCreatedId(editCamera?.id)
    setTestResult(null)
    onClose()
  }

  async function runTest() {
    setTesting(true)
    setTestResult(null)
    try {
      let id = createdId
      if (!id) {
        // Criação: salvar câmera antes de testar
        const cam = await cameraService.create(form)
        id = cam.id
        setCreatedId(id)
      } else {
        // Edição ou câmera já criada neste wizard: atualizar campos
        await cameraService.update(id, form)
      }
      const result = await cameraService.test(id)
      setTestResult(result)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Erro ao testar'
      setTestResult({
        camera_id: createdId || '',
        success: false,
        error: msg,
        suggestion: 'Verifique os dados e tente novamente',
        checks: {
          url_format: { status: 'error', message: msg },
          host_reachable: { status: 'pending', message: '' },
          port_open: { status: 'pending', message: '' },
          rtsp_response: { status: 'pending', message: '' },
          stream_available: { status: 'pending', message: '' },
        },
      })
    } finally {
      setTesting(false)
    }
  }

  async function finish() {
    if (testResult?.success) {
      toast.success(isEdit ? 'Câmera atualizada com sucesso' : 'Câmera adicionada com sucesso')
      onSuccess()
      handleClose()
    }
  }

  // Styles
  const overlay: React.CSSProperties = {
    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    zIndex: 1000, padding: 16,
  }
  const modal: React.CSSProperties = {
    background: '#1e293b', borderRadius: 14, border: '1px solid #334155',
    width: '100%', maxWidth: 520, maxHeight: '90vh',
    display: 'flex', flexDirection: 'column', overflow: 'hidden',
  }
  const inp = (hasErr?: boolean): React.CSSProperties => ({
    width: '100%', padding: '9px 12px', borderRadius: 8,
    border: `1px solid ${hasErr ? '#ef4444' : '#334155'}`,
    background: '#0f172a', color: '#e2e8f0', fontSize: 14,
    boxSizing: 'border-box',
  })
  const btn = (bg: string, fg = '#fff', disabled = false): React.CSSProperties => ({
    padding: '9px 20px', borderRadius: 8, border: 'none',
    background: disabled ? '#334155' : bg, color: disabled ? '#64748b' : fg,
    fontWeight: 600, fontSize: 14, cursor: disabled ? 'not-allowed' : 'pointer',
  })
  const label: React.CSSProperties = {
    display: 'block', fontSize: 12, fontWeight: 600,
    color: '#94a3b8', marginBottom: 5,
  }
  const errText: React.CSSProperties = { color: '#f87171', fontSize: 11, marginTop: 4 }

  return (
    <div style={overlay} onClick={e => e.target === e.currentTarget && handleClose()}>
      <div style={modal}>
        {/* Header */}
        <div style={{ padding: '16px 20px', borderBottom: '1px solid #334155', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ color: '#e2e8f0', fontWeight: 700, fontSize: 16 }}>
              {isEdit ? 'Editar Câmera' : 'Nova Câmera'}
            </div>
            <div style={{ color: '#64748b', fontSize: 12, marginTop: 2 }}>
              Passo {step} de 4 — {STEP_LABELS[step - 1]}
            </div>
          </div>
          <button onClick={handleClose} style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: 20, lineHeight: 1 }}>×</button>
        </div>

        {/* Progress bar */}
        <div style={{ display: 'flex', padding: '12px 20px 0', gap: 6 }}>
          {STEP_LABELS.map((_, i) => (
            <div key={i} style={{ flex: 1, height: 3, borderRadius: 2, background: i < step ? '#3b82f6' : '#334155', transition: 'background 0.2s' }} />
          ))}
        </div>

        {/* Content */}
        <div style={{ padding: 20, overflowY: 'auto', flex: 1 }}>

          {/* ── Passo 1: Fabricante ── */}
          {step === 1 && (
            <div>
              <p style={{ color: '#94a3b8', fontSize: 13, marginBottom: 16 }}>
                Selecione o fabricante para configuração automática do caminho RTSP.
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                {MANUFACTURERS.map(m => (
                  <button
                    key={m.id}
                    onClick={() => set('manufacturer', m.id)}
                    style={{
                      padding: '12px 14px', borderRadius: 8, cursor: 'pointer', textAlign: 'left',
                      border: `2px solid ${form.manufacturer === m.id ? '#3b82f6' : '#334155'}`,
                      background: form.manufacturer === m.id ? '#1e3a5f' : '#0f172a',
                      color: '#e2e8f0', fontWeight: 600, fontSize: 14,
                      transition: 'border-color 0.15s, background 0.15s',
                    }}
                  >
                    {m.name}
                  </button>
                ))}
              </div>
              {errors.manufacturer && <p style={errText}>{errors.manufacturer}</p>}
            </div>
          )}

          {/* ── Passo 2: Conexão ── */}
          {step === 2 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div style={{ padding: '10px 14px', background: '#1e3a5f', borderRadius: 8, fontSize: 12, color: '#93c5fd' }}>
                💡 O IP está nas configurações de rede da câmera. Usuário/senha são os mesmos usados para acessá-la pelo navegador.
              </div>
              <div>
                <label style={label}>Endereço IP *</label>
                <input style={inp(!!errors.ip)} value={form.ip} placeholder="192.168.1.100" onChange={e => set('ip', e.target.value)} />
                {errors.ip && <p style={errText}>{errors.ip}</p>}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <label style={label}>Porta</label>
                  <input style={inp(!!errors.port)} type="number" value={form.port} onChange={e => set('port', parseInt(e.target.value) || 554)} />
                  {errors.port && <p style={errText}>{errors.port}</p>}
                </div>
                <div>
                  <label style={label}>Usuário</label>
                  <input style={inp()} value={form.username} placeholder="admin" onChange={e => set('username', e.target.value)} />
                </div>
              </div>
              <div>
                <label style={label}>Senha</label>
                <input style={inp()} type="password" value={form.password} placeholder={isEdit ? '(deixe vazio para manter)' : 'Senha de acesso'} onChange={e => set('password', e.target.value)} />
              </div>
              <div>
                <label style={label}>Caminho do stream (opcional)</label>
                <input
                  style={inp()}
                  value={form.path}
                  placeholder={`Padrão: ${getDefaultPath(form.manufacturer)}`}
                  onChange={e => set('path', e.target.value)}
                />
                <p style={{ color: '#475569', fontSize: 11, marginTop: 4 }}>Deixe em branco para usar o padrão do fabricante</p>
              </div>
            </div>
          )}

          {/* ── Passo 3: Identificação ── */}
          {step === 3 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div>
                <label style={label}>Nome da câmera *</label>
                <input style={inp(!!errors.name)} value={form.name} placeholder="Ex: Entrada Principal, Baia 1..." onChange={e => set('name', e.target.value)} />
                {errors.name && <p style={errText}>{errors.name}</p>}
              </div>
              <div>
                <label style={label}>Localização (opcional)</label>
                <input style={inp()} value={form.location || ''} placeholder="Ex: Bloco A, Térreo..." onChange={e => set('location', e.target.value)} />
              </div>
              <div style={{ padding: 12, background: '#0f172a', borderRadius: 8 }}>
                <p style={{ color: '#64748b', fontSize: 11, marginBottom: 6, fontWeight: 600 }}>URL RTSP que será usada:</p>
                <code style={{ color: '#93c5fd', fontSize: 11, wordBreak: 'break-all' }}>
                  {buildRtspPreview(form)}
                </code>
              </div>
            </div>
          )}

          {/* ── Passo 4: Teste ── */}
          {step === 4 && (
            <div>
              {!testResult && !testing && (
                <div style={{ textAlign: 'center', padding: '24px 0' }}>
                  <p style={{ color: '#94a3b8', marginBottom: 20 }}>
                    Clique abaixo para verificar se a câmera está acessível na rede.
                  </p>
                  <button onClick={runTest} style={btn('#3b82f6')}>
                    Testar Conexão
                  </button>
                </div>
              )}

              {testing && (
                <div style={{ textAlign: 'center', padding: '24px 0' }}>
                  <div style={{ fontSize: 32, marginBottom: 12 }}>⏳</div>
                  <p style={{ color: '#94a3b8' }}>Testando conexão...</p>
                </div>
              )}

              {testResult && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  {/* Banner resultado */}
                  <div style={{
                    padding: '12px 16px', borderRadius: 8,
                    background: testResult.success ? '#22c55e15' : '#ef444415',
                    border: `1px solid ${testResult.success ? '#22c55e40' : '#ef444440'}`,
                  }}>
                    <div style={{ color: testResult.success ? '#86efac' : '#fca5a5', fontWeight: 700, fontSize: 14 }}>
                      {testResult.success ? '✓ Conexão estabelecida!' : '✗ Falha na conexão'}
                    </div>
                    {testResult.error && (
                      <div style={{ color: '#fca5a5', fontSize: 12, marginTop: 4 }}>{testResult.error}</div>
                    )}
                    {testResult.suggestion && (
                      <div style={{ color: '#94a3b8', fontSize: 12, marginTop: 6 }}>
                        💡 {testResult.suggestion}
                      </div>
                    )}
                  </div>

                  {/* Checklist */}
                  <div style={{ background: '#0f172a', borderRadius: 8, padding: '10px 14px' }}>
                    <p style={{ color: '#64748b', fontSize: 11, fontWeight: 700, marginBottom: 8 }}>DIAGNÓSTICO</p>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {Object.entries(testResult.checks).map(([key, check]) => (
                        <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
                          <CheckIcon check={check} />
                          <span style={{ color: check.status === 'error' ? '#fca5a5' : '#94a3b8', flex: 1 }}>
                            {CHECK_LABELS[key] || key}
                          </span>
                          {check.message && (
                            <span style={{ color: '#475569', fontSize: 11 }}>{check.message}</span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Ações em caso de falha */}
                  {!testResult.success && (
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button onClick={() => { setStep(2); setTestResult(null) }} style={btn('#334155', '#94a3b8')}>
                        ← Corrigir dados
                      </button>
                      <button onClick={runTest} style={btn('#3b82f6')}>
                        Testar novamente
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{ padding: '12px 20px', borderTop: '1px solid #334155', background: '#0f172a', display: 'flex', justifyContent: 'space-between' }}>
          <button onClick={back} style={btn('#334155', '#94a3b8')}>
            {step === 1 ? 'Cancelar' : '← Voltar'}
          </button>

          {step < 4 ? (
            <button onClick={next} style={btn('#3b82f6')}>
              Próximo →
            </button>
          ) : (
            <button
              onClick={finish}
              disabled={!testResult?.success}
              style={btn('#16a34a', '#fff', !testResult?.success)}
            >
              Concluir
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export default CameraWizard
