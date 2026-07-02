/**
 * CameraWizard — wizard em 4 passos para criar/editar câmeras.
 * Modo dual: criação (camera prop ausente) e edição (camera prop presente).
 */
import { useState } from 'react'
import { useToast } from '../ui/Toast/useToast'
import type { Camera } from '../../types'
import { cameraService, type CameraFormData, type TestResult } from '../../services/cameraService'
import { Button } from '../ui/Button/Button'
import { StepManufacturer, StepConnection, StepIdentity, StepTest } from './WizardSteps'
import {
  overlay, modal, modalHeader, modalTitle, modalSubtitle,
  closeBtn, progressBar, progressSegment, content, footer,
} from './CameraWizard.css'

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

interface CameraWizardProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: () => void
  camera?: Camera
}

export function CameraWizard({ isOpen, onClose, onSuccess, camera: editCamera }: CameraWizardProps) {
  const toast = useToast()
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

  function handleClose() {
    setStep(1); setForm(emptyForm(editCamera)); setErrors({})
    setCreatedId(editCamera?.id); setTestResult(null); onClose()
  }

  function pendingChecks(): TestResult['checks'] {
    const pending = { status: 'pending' as const, message: '' }
    return { url_format: pending, host_reachable: pending, port_open: pending,
      rtsp_response: pending, stream_available: pending }
  }

  async function runTest() {
    setTesting(true); setTestResult(null)
    let id = createdId

    // Fase 1: salvar no servidor — erro aqui é de banco/API, não da câmera
    try {
      if (!id) { const cam = await cameraService.create(form); id = cam.id; setCreatedId(id) }
      else await cameraService.update(id, form)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Erro desconhecido'
      setTestResult({ camera_id: id || '', success: false,
        error: `Erro ao salvar a câmera no servidor: ${msg}`,
        suggestion: 'Falha ao gravar os dados — não é um problema de rede ou da câmera. Tente novamente; se persistir, contate o suporte.',
        checks: pendingChecks() })
      setTesting(false)
      return
    }

    // Fase 2: teste de conectividade RTSP
    try {
      setTestResult(await cameraService.test(id))
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Erro ao testar'
      setTestResult({ camera_id: id || '', success: false,
        error: `Não foi possível executar o teste de conexão: ${msg}`,
        suggestion: 'Verifique os dados e tente novamente',
        checks: pendingChecks() })
    } finally { setTesting(false) }
  }

  async function finish() {
    if (testResult?.success) {
      toast.success(isEdit ? 'Câmera atualizada' : 'Câmera adicionada')
      onSuccess(); handleClose()
    }
  }

  const stepProps = { form, errors, set, isEdit }

  return (
    <div className={overlay} onClick={e => e.target === e.currentTarget && handleClose()}>
      <div className={modal}>
        <div className={modalHeader}>
          <div>
            <div className={modalTitle}>{isEdit ? 'Editar Câmera' : 'Nova Câmera'}</div>
            <div className={modalSubtitle}>Passo {step} de 4 — {STEP_LABELS[step - 1]}</div>
          </div>
          <button className={closeBtn} onClick={handleClose}>×</button>
        </div>

        <div className={progressBar}>
          {STEP_LABELS.map((_, i) => (
            <div key={i} className={progressSegment({ active: i < step })} />
          ))}
        </div>

        <div className={content}>
          {step === 1 && <StepManufacturer {...stepProps} />}
          {step === 2 && <StepConnection {...stepProps} />}
          {step === 3 && <StepIdentity {...stepProps} />}
          {step === 4 && (
            <StepTest testing={testing} testResult={testResult}
              onRunTest={runTest} onRetry={runTest}
              onBack={() => { setStep(2); setTestResult(null) }} />
          )}
        </div>

        <div className={footer}>
          <Button variant="secondary" onClick={step === 1 ? handleClose : () => { setStep(s => s - 1); setTestResult(null) }}>
            {step === 1 ? 'Cancelar' : '← Voltar'}
          </Button>
          {step < 4
            ? <Button variant="primary" onClick={() => validate() && setStep(s => s + 1)}>Próximo →</Button>
            : <Button variant="success" onClick={finish} disabled={!testResult?.success}>Concluir</Button>
          }
        </div>
      </div>
    </div>
  )
}

export default CameraWizard
