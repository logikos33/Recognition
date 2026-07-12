/**
 * Modal multi-step para criação de nova operação.
 * Steps: Tipo → Configuração → Revisão
 * Usa Stepper + Modal existentes. Padrão espelha CameraWizard.tsx.
 */
import { useState } from 'react'
import { Modal } from '../../ui/Modal/Modal'
import { Stepper } from '../../ui/Stepper/Stepper'
import { PositionForm } from '../operationTypeForms/PositionForm'
import { OverlapFixedForm } from '../operationTypeForms/OverlapFixedForm'
import { OverlapDynamicForm } from '../operationTypeForms/OverlapDynamicForm'
import { CountStaticForm } from '../operationTypeForms/CountStaticForm'
import { getOperationIcon } from '../icons/operationTypeIcons'
import type { OperationType, OperationCreate, RoiPoint } from '../../../types/operations'
import { vars } from '../../../styles/theme.css'

const STEPS = [
  { label: 'Tipo' },
  { label: 'Configuração' },
  { label: 'Revisão' },
]

interface OperationCreateModalProps {
  open: boolean
  onClose: () => void
  onCreated: (data: OperationCreate) => Promise<unknown>
  availableTypes: OperationType[]
  moduleId: string
  loading?: boolean
}

function ConfigForm({ typeId, config, onChange, roiPoints, onRoiChange }: {
  typeId: string
  config: Record<string, unknown>
  onChange: (c: Record<string, unknown>) => void
  roiPoints: RoiPoint[]
  onRoiChange: (pts: RoiPoint[]) => void
}) {
  switch (typeId) {
    case 'position':
      return <PositionForm config={config} onChange={onChange} roiPoints={roiPoints} onRoiChange={onRoiChange} />
    case 'overlap_fixed':
      return <OverlapFixedForm config={config} onChange={onChange} roiPoints={roiPoints} />
    case 'overlap_dynamic':
      return <OverlapDynamicForm config={config} onChange={onChange} />
    case 'count_static':
      return <CountStaticForm config={config} onChange={onChange} roiPoints={roiPoints} />
    default:
      return (
        <div style={{ padding: 16, color: vars.color.textMuted, fontSize: 13 }}>
          Tipo "{typeId}" — configure via JSON:
          <textarea
            value={JSON.stringify(config, null, 2)}
            onChange={e => { try { onChange(JSON.parse(e.target.value)) } catch { } }}
            rows={8}
            style={{ width: '100%', marginTop: 8, background: vars.color.bgSurface, border: `1px solid ${vars.color.borderDefault}`, borderRadius: 6, color: vars.color.textPrimary, fontFamily: 'monospace', fontSize: 12, padding: 8 }}
          />
        </div>
      )
  }
}

export function OperationCreateModal({
  open,
  onClose,
  onCreated,
  availableTypes,
  moduleId,
  loading = false,
}: OperationCreateModalProps) {
  const [step, setStep] = useState(0)
  const [selectedType, setSelectedType] = useState<OperationType | null>(null)
  const [name, setName] = useState('')
  const [config, setConfig] = useState<Record<string, unknown>>({})
  const [roiPoints, setRoiPoints] = useState<RoiPoint[]>([])
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const reset = () => {
    setStep(0); setSelectedType(null); setName(''); setConfig({}); setRoiPoints([]); setError(null)
  }

  const handleClose = () => { reset(); onClose() }

  const handleSelectType = (type: OperationType) => {
    setSelectedType(type)
    setConfig({})
    setRoiPoints([])
  }

  const handleNext = () => {
    setError(null)
    if (step === 0) {
      if (!selectedType) { setError('Selecione um tipo de operação'); return }
      setStep(1)
    } else if (step === 1) {
      if (!name.trim()) { setError('Nome é obrigatório'); return }
      // ROI required for roi-based types
      if (['position', 'overlap_fixed', 'count_static'].includes(selectedType?.type_id ?? '') && roiPoints.length < 3) {
        setError('Desenhe o ROI com pelo menos 3 pontos'); return
      }
      // Merge roi_points into config
      if (roiPoints.length >= 3) {
        setConfig(prev => ({ ...prev, roi_points: roiPoints.map(p => [p.x, p.y]) }))
      }
      setStep(2)
    }
  }

  const handleBack = () => setStep(s => Math.max(0, s - 1))

  const handleSubmit = async () => {
    if (!selectedType) return
    setSubmitting(true)
    setError(null)
    try {
      const finalConfig = roiPoints.length >= 3
        ? { ...config, roi_points: roiPoints.map(p => [p.x, p.y]) }
        : config
      await onCreated({ module_id: moduleId, type_id: selectedType.type_id, name: name.trim(), config: finalConfig })
      reset()
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao criar operação')
    } finally {
      setSubmitting(false)
    }
  }

  const footer = (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
      <div style={{ flex: 1 }}>
        {error && <span style={{ color: '#ef4444', fontSize: 12 }}>{error}</span>}
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        {step > 0 && (
          <button
            onClick={handleBack}
            disabled={submitting}
            style={{ padding: '8px 16px', background: 'transparent', border: `1px solid ${vars.color.borderDefault}`, borderRadius: 6, color: vars.color.textSecondary, fontSize: 13, cursor: 'pointer' }}
          >
            ← Voltar
          </button>
        )}
        {step < 2 ? (
          <button
            onClick={handleNext}
            style={{ padding: '8px 16px', background: vars.color.primary, border: 'none', borderRadius: 6, color: vars.color.textOnPrimary, fontSize: 13, cursor: 'pointer', fontWeight: 500 }}
          >
            {step === 1 ? 'Próximo: Revisar →' : 'Próximo: Configurar →'}
          </button>
        ) : (
          <button
            onClick={handleSubmit}
            disabled={submitting || loading}
            style={{ padding: '8px 16px', background: vars.color.primary, border: 'none', borderRadius: 6, color: vars.color.textOnPrimary, fontSize: 13, cursor: 'pointer', fontWeight: 500, opacity: submitting ? 0.6 : 1 }}
          >
            {submitting ? 'Criando...' : 'Criar operação'}
          </button>
        )}
      </div>
    </div>
  )

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title="Nova Operação"
      footer={footer}
      maxWidth="520px"
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 20, minHeight: 300 }}>
        <Stepper steps={STEPS} current={step} />

        {/* Step 0: seleção de tipo */}
        {step === 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {availableTypes.map(type => (
              <button
                key={type.type_id}
                onClick={() => handleSelectType(type)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px',
                  background: selectedType?.type_id === type.type_id ? 'rgba(59,130,246,0.15)' : vars.color.bgSurface,
                  border: `1px solid ${selectedType?.type_id === type.type_id ? vars.color.primary : vars.color.borderDefault}`,
                  borderRadius: 6, color: 'inherit', cursor: 'pointer', textAlign: 'left', width: '100%',
                }}
              >
                <span style={{ color: vars.color.primary, flexShrink: 0 }}>
                  {getOperationIcon(type.type_id, { size: 18, color: vars.color.primary })}
                </span>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 500, color: vars.color.textSecondary }}>{type.type_label}</div>
                  {type.description && <div style={{ fontSize: 11, color: vars.color.textMuted }}>{type.description}</div>}
                </div>
              </button>
            ))}
          </div>
        )}

        {/* Step 1: configuração */}
        {step === 1 && selectedType && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div>
              <label style={{ display: 'block', marginBottom: 4, fontSize: 13, fontWeight: 500 }}>Nome da operação *</label>
              <input
                value={name}
                onChange={e => setName(e.target.value)}
                placeholder={`Ex: ${selectedType.type_label} - Câmera 01`}
                style={{ width: '100%', padding: '8px 10px', background: vars.color.bgSurface, border: `1px solid ${vars.color.borderDefault}`, borderRadius: 6, color: vars.color.textPrimary, fontSize: 13, boxSizing: 'border-box' }}
              />
            </div>
            <ConfigForm
              typeId={selectedType.type_id}
              config={config}
              onChange={setConfig}
              roiPoints={roiPoints}
              onRoiChange={setRoiPoints}
            />
          </div>
        )}

        {/* Step 2: revisão */}
        {step === 2 && selectedType && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ background: vars.color.bgSurface, borderRadius: 6, border: `1px solid ${vars.color.borderDefault}`, padding: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                {getOperationIcon(selectedType.type_id, { size: 20, color: vars.color.primary })}
                <span style={{ fontSize: 14, fontWeight: 600, color: vars.color.textSecondary }}>{selectedType.type_label}</span>
              </div>
              <Row label="Nome" value={name} />
              <Row label="Tipo" value={selectedType.type_id} mono />
              <Row label="Módulo" value={moduleId} mono />
              {roiPoints.length > 0 && <Row label="ROI" value={`${roiPoints.length} pontos`} />}
            </div>
            <details style={{ color: vars.color.textMuted, fontSize: 12 }}>
              <summary style={{ cursor: 'pointer', color: vars.color.textMuted }}>Ver configuração JSON</summary>
              <pre style={{ marginTop: 6, padding: 10, background: vars.color.bgBase, borderRadius: 4, overflowX: 'auto', fontSize: 11 }}>
                {JSON.stringify({ ...config, ...(roiPoints.length > 0 ? { roi_points: roiPoints.map(p => [p.x, p.y]) } : {}) }, null, 2)}
              </pre>
            </details>
          </div>
        )}
      </div>
    </Modal>
  )
}

function Row({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div style={{ display: 'flex', gap: 8, marginBottom: 6, fontSize: 13 }}>
      <span style={{ color: vars.color.textMuted, minWidth: 70 }}>{label}:</span>
      <span style={{ color: vars.color.textSecondary, fontFamily: mono ? 'monospace' : 'inherit', fontSize: mono ? 12 : 13 }}>{value}</span>
    </div>
  )
}
