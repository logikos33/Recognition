/**
 * Modal de edição de operação existente.
 * Mesma estrutura do OperationCreateModal, mas pré-preenchido.
 * Step 0 omitido (tipo não pode ser alterado).
 */
import { useEffect, useState } from 'react'
import { Modal } from '../../ui/Modal/Modal'
import { Stepper } from '../../ui/Stepper/Stepper'
import { PositionForm } from '../operationTypeForms/PositionForm'
import { OverlapFixedForm } from '../operationTypeForms/OverlapFixedForm'
import { OverlapDynamicForm } from '../operationTypeForms/OverlapDynamicForm'
import { CountStaticForm } from '../operationTypeForms/CountStaticForm'
import { getOperationIcon } from '../icons/operationTypeIcons'
import type { Operation, OperationUpdate, RoiPoint } from '../../../types/operations'
import { vars } from '../../../styles/theme.css'

const STEPS = [{ label: 'Configuração' }, { label: 'Revisão' }]

interface OperationEditModalProps {
  open: boolean
  onClose: () => void
  onUpdated: (data: OperationUpdate) => Promise<void>
  operation: Operation | null
  loading?: boolean
}

function EditConfigForm({ typeId, config, onChange, roiPoints, onRoiChange }: {
  typeId: string; config: Record<string, unknown>; onChange: (c: Record<string, unknown>) => void;
  roiPoints: RoiPoint[]; onRoiChange: (pts: RoiPoint[]) => void
}) {
  switch (typeId) {
    case 'position': return <PositionForm config={config} onChange={onChange} roiPoints={roiPoints} onRoiChange={onRoiChange} />
    case 'overlap_fixed': return <OverlapFixedForm config={config} onChange={onChange} roiPoints={roiPoints} />
    case 'overlap_dynamic': return <OverlapDynamicForm config={config} onChange={onChange} />
    case 'count_static': return <CountStaticForm config={config} onChange={onChange} roiPoints={roiPoints} />
    default:
      return (
        <textarea
          value={JSON.stringify(config, null, 2)}
          onChange={e => { try { onChange(JSON.parse(e.target.value)) } catch { } }}
          rows={8}
          style={{ width: '100%', background: vars.color.bgSurface, border: `1px solid ${vars.color.borderDefault}`, borderRadius: 6, color: vars.color.textPrimary, fontFamily: 'monospace', fontSize: 12, padding: 8 }}
        />
      )
  }
}

export function OperationEditModal({ open, onClose, onUpdated, operation, loading = false }: OperationEditModalProps) {
  const [step, setStep] = useState(0)
  const [name, setName] = useState('')
  const [config, setConfig] = useState<Record<string, unknown>>({})
  const [roiPoints, setRoiPoints] = useState<RoiPoint[]>([])
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (operation && open) {
      setName(operation.name)
      setConfig(operation.config ?? {})
      const rawRoi = (operation.config as Record<string, unknown>)?.roi_points
      if (Array.isArray(rawRoi)) {
        setRoiPoints(rawRoi.map((p: unknown) => { const pair = p as [number, number]; return { x: pair[0], y: pair[1] } }))
      } else {
        setRoiPoints([])
      }
      setStep(0)
      setError(null)
    }
  }, [operation, open])

  const handleClose = () => { setError(null); onClose() }

  const handleNext = () => {
    setError(null)
    if (!name.trim()) { setError('Nome é obrigatório'); return }
    if (['position', 'overlap_fixed', 'count_static'].includes(operation?.type_id ?? '') && roiPoints.length < 3) {
      setError('ROI precisa ter pelo menos 3 pontos'); return
    }
    if (roiPoints.length >= 3) {
      setConfig(prev => ({ ...prev, roi_points: roiPoints.map(p => [p.x, p.y]) }))
    }
    setStep(1)
  }

  const handleSubmit = async () => {
    if (!operation) return
    setSubmitting(true)
    setError(null)
    try {
      const finalConfig = roiPoints.length >= 3
        ? { ...config, roi_points: roiPoints.map(p => [p.x, p.y]) }
        : config
      await onUpdated({ name: name.trim(), config: finalConfig })
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao atualizar operação')
    } finally {
      setSubmitting(false)
    }
  }

  if (!operation) return null

  const footer = (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
      <div style={{ flex: 1 }}>
        {error && <span style={{ color: '#ef4444', fontSize: 12 }}>{error}</span>}
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        {step > 0 && (
          <button onClick={() => setStep(0)} style={{ padding: '8px 16px', background: 'transparent', border: `1px solid ${vars.color.borderDefault}`, borderRadius: 6, color: vars.color.textSecondary, fontSize: 13, cursor: 'pointer' }}>
            ← Voltar
          </button>
        )}
        {step === 0 ? (
          <button onClick={handleNext} style={{ padding: '8px 16px', background: vars.color.primary, border: 'none', borderRadius: 6, color: vars.color.textOnPrimary, fontSize: 13, cursor: 'pointer', fontWeight: 500 }}>
            Próximo: Revisar →
          </button>
        ) : (
          <button onClick={handleSubmit} disabled={submitting || loading} style={{ padding: '8px 16px', background: vars.color.primary, border: 'none', borderRadius: 6, color: vars.color.textOnPrimary, fontSize: 13, cursor: 'pointer', fontWeight: 500, opacity: submitting ? 0.6 : 1 }}>
            {submitting ? 'Salvando...' : 'Salvar alterações'}
          </button>
        )}
      </div>
    </div>
  )

  return (
    <Modal open={open} onClose={handleClose} title={`Editar: ${operation.name}`} footer={footer} maxWidth="520px">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 20, minHeight: 260 }}>
        <Stepper steps={STEPS} current={step} />

        {step === 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px', background: vars.color.bgSurface, borderRadius: 6, border: `1px solid ${vars.color.borderDefault}` }}>
              {getOperationIcon(operation.type_id, { size: 16, color: vars.color.primary })}
              <span style={{ fontSize: 12, color: vars.color.textMuted }}>Tipo: <span style={{ color: vars.color.textSecondary, fontFamily: 'monospace' }}>{operation.type_id}</span></span>
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: 4, fontSize: 13, fontWeight: 500 }}>Nome *</label>
              <input value={name} onChange={e => setName(e.target.value)} style={{ width: '100%', padding: '8px 10px', background: vars.color.bgSurface, border: `1px solid ${vars.color.borderDefault}`, borderRadius: 6, color: vars.color.textPrimary, fontSize: 13, boxSizing: 'border-box' }} />
            </div>
            <EditConfigForm typeId={operation.type_id} config={config} onChange={setConfig} roiPoints={roiPoints} onRoiChange={setRoiPoints} />
          </div>
        )}

        {step === 1 && (
          <div style={{ background: vars.color.bgSurface, borderRadius: 6, border: `1px solid ${vars.color.borderDefault}`, padding: 14 }}>
            <div style={{ marginBottom: 10 }}>
              <span style={{ fontSize: 11, color: vars.color.textMuted }}>v{operation.version} → v{operation.version + 1}</span>
            </div>
            <div style={{ fontSize: 13, color: vars.color.textSecondary, marginBottom: 6 }}>Nome: <strong>{name}</strong></div>
            {roiPoints.length > 0 && <div style={{ fontSize: 13, color: vars.color.textSecondary, marginBottom: 6 }}>ROI: {roiPoints.length} pontos</div>}
            <details style={{ color: vars.color.textMuted, fontSize: 12 }}>
              <summary style={{ cursor: 'pointer', color: vars.color.textMuted }}>Ver configuração JSON</summary>
              <pre style={{ marginTop: 6, padding: 10, background: vars.color.bgBase, borderRadius: 4, overflowX: 'auto', fontSize: 11 }}>
                {JSON.stringify(config, null, 2)}
              </pre>
            </details>
          </div>
        )}
      </div>
    </Modal>
  )
}
