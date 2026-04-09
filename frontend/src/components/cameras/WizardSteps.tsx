/**
 * WizardSteps — renders for each of the 4 CameraWizard steps.
 * Kept separate to comply with the 200-line component limit.
 */
import type { CameraFormData, TestResult, TestCheck } from '../../services/cameraService'
import { buildRtspPreview, getDefaultPath } from '../../services/cameraService'
import { Input, Field } from '../ui/Input/Input'
import { Button } from '../ui/Button/Button'
import {
  stepStack, hint, grid2, manufacturerGrid, manufacturerBtn,
  helpText, urlPreview, urlPreviewLabel, urlPreviewCode,
  testCenterBox, testCenterText, resultBanner, resultTitle,
  resultErrorMsg, resultSuggestion, diagnosticBox, diagnosticTitle,
  diagnosticRow, diagnosticLabel, diagnosticDetail, failureActions,
  errorText, diagnosticGap,
} from './CameraWizard.css'

const MANUFACTURERS = [
  { id: 'hikvision', name: 'Hikvision' },
  { id: 'dahua', name: 'Dahua' },
  { id: 'intelbras', name: 'Intelbras' },
  { id: 'axis', name: 'Axis' },
  { id: 'samsung', name: 'Samsung' },
  { id: 'generic', name: 'Outra marca' },
]

const CHECK_LABELS: Record<string, string> = {
  url_format: 'Formato da URL RTSP',
  host_reachable: 'Câmera acessível na rede',
  port_open: 'Porta RTSP aberta',
  rtsp_response: 'Resposta ao protocolo RTSP',
  stream_available: 'Stream de vídeo disponível',
}

function CheckIcon({ check }: { check: TestCheck }) {
  const icons = { ok: '✓', error: '✗', warning: '!', pending: '○' }
  const colors = { ok: '#22c55e', error: '#ef4444', warning: '#f59e0b', pending: '#475569' }
  return <span style={{ color: colors[check.status] ?? '#475569' }}>{icons[check.status] ?? '○'}</span>
}

interface StepProps {
  form: CameraFormData
  errors: Record<string, string>
  set: (field: keyof CameraFormData, value: string | number) => void
  isEdit: boolean
}

export function StepManufacturer({ form, errors, set }: StepProps) {
  return (
    <div>
      <p className={hint}>
        Selecione o fabricante para configuração automática do caminho RTSP.
      </p>
      <div className={manufacturerGrid}>
        {MANUFACTURERS.map(m => (
          <button
            key={m.id}
            type="button"
            onClick={() => set('manufacturer', m.id)}
            className={manufacturerBtn({ selected: form.manufacturer === m.id })}
          >
            {m.name}
          </button>
        ))}
      </div>
      {errors.manufacturer && <p className={errorText}>{errors.manufacturer}</p>}
    </div>
  )
}

export function StepConnection({ form, errors, set, isEdit }: StepProps) {
  return (
    <div className={stepStack}>
      <p className={hint}>
        💡 O IP está nas configurações de rede da câmera. Usuário/senha são os mesmos usados para acessá-la pelo navegador.
      </p>
      <Field label="Endereço IP *" error={errors.ip}>
        <Input value={form.ip} placeholder="192.168.1.100" onChange={e => set('ip', e.target.value)} error={errors.ip} />
      </Field>
      <div className={grid2}>
        <Field label="Porta" error={errors.port}>
          <Input type="number" value={form.port} onChange={e => set('port', parseInt(e.target.value) || 554)} error={errors.port} />
        </Field>
        <Field label="Usuário">
          <Input value={form.username} placeholder="admin" onChange={e => set('username', e.target.value)} />
        </Field>
      </div>
      <Field label="Senha">
        <Input type="password" value={form.password} placeholder={isEdit ? '(deixe vazio para manter)' : 'Senha de acesso'} onChange={e => set('password', e.target.value)} />
      </Field>
      <Field label="Caminho do stream (opcional)">
        <Input value={form.path} placeholder={`Padrão: ${getDefaultPath(form.manufacturer)}`} onChange={e => set('path', e.target.value)} />
        <p className={helpText}>Deixe em branco para usar o padrão do fabricante</p>
      </Field>
    </div>
  )
}

export function StepIdentity({ form, errors, set }: StepProps) {
  return (
    <div className={stepStack}>
      <Field label="Nome da câmera *" error={errors.name}>
        <Input value={form.name} placeholder="Ex: Entrada Principal, Baia 1..." onChange={e => set('name', e.target.value)} error={errors.name} />
      </Field>
      <Field label="Localização (opcional)">
        <Input value={form.location || ''} placeholder="Ex: Bloco A, Térreo..." onChange={e => set('location', e.target.value)} />
      </Field>
      <div className={urlPreview}>
        <p className={urlPreviewLabel}>URL RTSP QUE SERÁ USADA</p>
        <code className={urlPreviewCode}>{buildRtspPreview(form)}</code>
      </div>
    </div>
  )
}

interface StepTestProps {
  testing: boolean
  testResult: TestResult | null
  onRunTest: () => void
  onRetry: () => void
  onBack: () => void
}

export function StepTest({ testing, testResult, onRunTest, onRetry, onBack }: StepTestProps) {
  if (testing) {
    return (
      <div className={testCenterBox}>
        <div style={{ fontSize: 32, marginBottom: 12 }}>⏳</div>
        <p className={testCenterText}>Testando conexão...</p>
      </div>
    )
  }

  if (!testResult) {
    return (
      <div className={testCenterBox}>
        <p className={testCenterText}>Clique abaixo para verificar se a câmera está acessível na rede.</p>
        <Button variant="primary" onClick={onRunTest}>Testar Conexão</Button>
      </div>
    )
  }

  return (
    <div className={stepStack}>
      <div className={resultBanner({ success: testResult.success })}>
        <div className={resultTitle({ success: testResult.success })}>
          {testResult.success ? '✓ Conexão estabelecida!' : '✗ Falha na conexão'}
        </div>
        {testResult.error && <p className={resultErrorMsg}>{testResult.error}</p>}
        {testResult.suggestion && <p className={resultSuggestion}>💡 {testResult.suggestion}</p>}
      </div>

      <div className={diagnosticBox}>
        <p className={diagnosticTitle}>DIAGNÓSTICO</p>
        <div className={diagnosticGap}>
          {Object.entries(testResult.checks).map(([key, check]) => (
            <div key={key} className={diagnosticRow}>
              <CheckIcon check={check} />
              <span className={diagnosticLabel({ isError: check.status === 'error' })}>
                {CHECK_LABELS[key] ?? key}
              </span>
              {check.message && <span className={diagnosticDetail}>{check.message}</span>}
            </div>
          ))}
        </div>
      </div>

      {!testResult.success && (
        <div className={failureActions}>
          <Button variant="secondary" onClick={onBack}>← Corrigir dados</Button>
          <Button variant="primary" onClick={onRetry}>Testar novamente</Button>
        </div>
      )}
    </div>
  )
}
