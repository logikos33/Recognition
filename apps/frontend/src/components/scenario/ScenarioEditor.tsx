/**
 * ScenarioEditor — wizard de 6 passos para configurar um modelo treinado.
 *
 * Passos:
 *   1. Identificação  — nome do modelo + descrição
 *   2. Classes        — checkboxes das classes a detectar
 *   3. Linha          — DrawingCanvas (linha de cruzamento p/ contagem)
 *   4. Zona/ROI       — RoiDrawer (polígono de área de interesse)
 *   5. Confiança      — slider 0.10–0.99
 *   6. Câmera         — dropdown de câmeras disponíveis
 *
 * Salva via PUT /api/training/scenarios/{modelId}/config.
 * Carrega config atual via GET /api/training/scenarios/{modelId}/config.
 *
 * Regras obrigatórias:
 *   - Usa api wrapper (sem fetch raw)
 *   - TypeScript strict (zero any implícito)
 *   - pointerEvents:'none' nos shapes SVG (delegado a DrawingCanvas e RoiDrawer)
 */
import { useCallback, useEffect, useState } from 'react'
import { X, ChevronLeft, ChevronRight, Check, Loader2 } from 'lucide-react'
import { Stepper } from '../ui/Stepper/Stepper'
import { Button } from '../ui/Button/Button'
import { DrawingCanvas } from './DrawingCanvas'
import type { CountingLine } from './DrawingCanvas'
import { RoiDrawer } from '../training/canvas/RoiDrawer'
import type { RoiPoint } from '../../types/operations'
import { api } from '../../services/api'
import type { Camera } from '../../types'

// ─── Constantes ───────────────────────────────────────────────────────────────

const EPI_CLASS_OPTIONS: { value: string; label: string }[] = [
  { value: 'helmet',    label: 'Capacete' },
  { value: 'no_helmet', label: 'Sem Capacete' },
  { value: 'vest',      label: 'Colete' },
  { value: 'no_vest',   label: 'Sem Colete' },
  { value: 'gloves',    label: 'Luvas' },
  { value: 'no_gloves', label: 'Sem Luvas' },
  { value: 'glasses',   label: 'Óculos' },
  { value: 'no_glasses',label: 'Sem Óculos' },
]

const STEPS = [
  { label: 'Identificação' },
  { label: 'Classes' },
  { label: 'Linha' },
  { label: 'Zona/ROI' },
  { label: 'Confiança' },
  { label: 'Câmera' },
]

// ─── Tipos ────────────────────────────────────────────────────────────────────

interface ScenarioConfig {
  classes: string[]
  counting_line: CountingLine | null
  roi: RoiPoint[]
  confidence_threshold: number
  camera_id: string | null
}

type ApiEnvelope<T> = { status: string; data: T }

interface ScenarioConfigResponse {
  model_id: string
  scenario_config: ScenarioConfig | null
}

interface CameraListData {
  cameras: Camera[]
}

export interface ScenarioEditorProps {
  modelId: string
  modelName: string
  onClose: () => void
  onSaved?: () => void
}

// ─── Componente ───────────────────────────────────────────────────────────────

export function ScenarioEditor({ modelId, modelName, onClose, onSaved }: ScenarioEditorProps) {
  const [step, setStep] = useState(0)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [savedOk, setSavedOk] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)

  // Step 1 — Identificação
  const [description, setDescription] = useState('')

  // Step 2 — Classes
  const [classes, setClasses] = useState<string[]>([])

  // Step 3 — Linha de cruzamento
  const [countingLine, setCountingLine] = useState<CountingLine | null>(null)

  // Step 4 — ROI
  const [roi, setRoi] = useState<RoiPoint[]>([])

  // Step 5 — Confiança
  const [confidence, setConfidence] = useState(0.5)

  // Step 6 — Câmera
  const [cameraId, setCameraId] = useState<string | null>(null)
  const [cameras, setCameras] = useState<Camera[]>([])

  // ─── Carregar config existente + câmeras ──────────────────────────────────

  useEffect(() => {
    let cancelled = false

    const loadAll = async () => {
      setLoading(true)
      setLoadError(null)
      try {
        const [configRes, camerasRes] = await Promise.allSettled([
          api.get<ApiEnvelope<ScenarioConfigResponse>>(`/training/scenarios/${modelId}/config`),
          api.get<ApiEnvelope<CameraListData>>('/cameras'),
        ])

        if (!cancelled) {
          if (configRes.status === 'fulfilled') {
            const cfg = configRes.value.data?.scenario_config
            if (cfg) {
              setClasses(cfg.classes ?? [])
              setCountingLine(cfg.counting_line ?? null)
              setRoi(cfg.roi ?? [])
              setConfidence(cfg.confidence_threshold ?? 0.5)
              setCameraId(cfg.camera_id ?? null)
            }
          }
          if (camerasRes.status === 'fulfilled') {
            setCameras(camerasRes.value.data?.cameras ?? [])
          }
        }
      } catch {
        if (!cancelled) setLoadError('Falha ao carregar configuração existente.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    loadAll()
    return () => { cancelled = true }
  }, [modelId])

  // ─── Navegação ────────────────────────────────────────────────────────────

  const next = useCallback(() => setStep(s => Math.min(s + 1, STEPS.length - 1)), [])
  const back = useCallback(() => setStep(s => Math.max(s - 1, 0)), [])

  // ─── Salvar ───────────────────────────────────────────────────────────────

  const handleSave = useCallback(async () => {
    setSaving(true)
    setSaveError(null)
    try {
      await api.put<ApiEnvelope<ScenarioConfigResponse>>(
        `/training/scenarios/${modelId}/config`,
        {
          classes,
          counting_line: countingLine,
          roi,
          confidence_threshold: confidence,
          camera_id: cameraId,
        },
      )
      setSavedOk(true)
      onSaved?.()
      setTimeout(() => onClose(), 1200)
    } catch (err: unknown) {
      setSaveError(err instanceof Error ? err.message : 'Erro ao salvar configuração')
    } finally {
      setSaving(false)
    }
  }, [modelId, classes, countingLine, roi, confidence, cameraId, onSaved, onClose])

  // ─── Toggle de classe ─────────────────────────────────────────────────────

  const toggleClass = useCallback((value: string) => {
    setClasses(prev =>
      prev.includes(value) ? prev.filter(c => c !== value) : [...prev, value],
    )
  }, [])

  // ─── Snapshot da câmera (futuro: real snapshot URL) ───────────────────────
  // Por ora: sem snapshot real — canvas mostra fundo escuro como placeholder.
  // Quando o endpoint GET /cameras/{id}/snapshot existir, passar a URL aqui.

  // ─── Render ───────────────────────────────────────────────────────────────

  return (
    /* Overlay */
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 300,
        background: 'rgba(0,0,0,0.8)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 16,
      }}
      onClick={onClose}
    >
      {/* Modal */}
      <div
        style={{
          background: '#0f172a',
          border: '1px solid #1e293b',
          borderRadius: 14,
          width: '100%',
          maxWidth: 620,
          maxHeight: '92vh',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '18px 24px 14px',
          borderBottom: '1px solid #1e293b',
          flexShrink: 0,
        }}>
          <div>
            <h2 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: '#f1f5f9' }}>
              Configurar Cenário
            </h2>
            <p style={{ margin: '2px 0 0', fontSize: 12, color: '#64748b' }}>
              {modelName}
            </p>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'transparent', border: 'none', cursor: 'pointer',
              color: '#64748b', display: 'flex', alignItems: 'center',
              padding: 4, borderRadius: 4,
            }}
            aria-label="Fechar"
          >
            <X size={18} />
          </button>
        </div>

        {/* Stepper */}
        <div style={{ padding: '14px 24px 0', flexShrink: 0, overflowX: 'auto' }}>
          <Stepper steps={STEPS} current={step} orientation="horizontal" />
        </div>

        {/* Corpo do passo */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px' }}>
          {loading ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: '#64748b', fontSize: 14 }}>
              <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
              Carregando configuração...
            </div>
          ) : loadError ? (
            <p style={{ color: '#f59e0b', fontSize: 13 }}>{loadError}</p>
          ) : (
            <>
              {/* Passo 1: Identificação */}
              {step === 0 && (
                <StepIdentification
                  modelName={modelName}
                  description={description}
                  onDescriptionChange={setDescription}
                />
              )}

              {/* Passo 2: Classes */}
              {step === 1 && (
                <StepClasses
                  selected={classes}
                  onToggle={toggleClass}
                />
              )}

              {/* Passo 3: Linha de cruzamento */}
              {step === 2 && (
                <StepCountingLine
                  line={countingLine}
                  onChange={setCountingLine}
                />
              )}

              {/* Passo 4: Zona / ROI */}
              {step === 3 && (
                <StepRoi roi={roi} onChange={setRoi} />
              )}

              {/* Passo 5: Limiar de confiança */}
              {step === 4 && (
                <StepConfidence
                  value={confidence}
                  onChange={setConfidence}
                />
              )}

              {/* Passo 6: Câmera vinculada */}
              {step === 5 && (
                <StepCamera
                  cameras={cameras}
                  selectedId={cameraId}
                  onSelect={setCameraId}
                />
              )}
            </>
          )}
        </div>

        {/* Footer de navegação */}
        {!loading && !loadError && (
          <div style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '14px 24px',
            borderTop: '1px solid #1e293b',
            flexShrink: 0,
          }}>
            <Button
              variant="secondary"
              onClick={back}
              disabled={step === 0}
            >
              <ChevronLeft size={14} /> Anterior
            </Button>

            <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              {saveError && (
                <span style={{ fontSize: 12, color: '#ef4444' }}>{saveError}</span>
              )}
              {savedOk && (
                <span style={{ fontSize: 12, color: '#22c55e', display: 'flex', alignItems: 'center', gap: 4 }}>
                  <Check size={14} /> Salvo!
                </span>
              )}

              {step < STEPS.length - 1 ? (
                <Button variant="primary" onClick={next}>
                  Próximo <ChevronRight size={14} />
                </Button>
              ) : (
                <Button
                  variant="primary"
                  onClick={handleSave}
                  disabled={saving || savedOk}
                >
                  {saving ? (
                    <><Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> Salvando...</>
                  ) : (
                    <><Check size={14} /> Salvar Configuração</>
                  )}
                </Button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Sub-componentes de cada passo ────────────────────────────────────────────

function StepIdentification({
  modelName,
  description,
  onDescriptionChange,
}: {
  modelName: string
  description: string
  onDescriptionChange: (v: string) => void
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <p style={{ margin: 0, fontSize: 13, color: '#94a3b8' }}>
        Revise o nome do modelo e adicione uma descrição opcional do cenário de uso.
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <label style={{ fontSize: 12, fontWeight: 600, color: '#64748b' }}>
          Nome do Modelo
        </label>
        <div style={{
          padding: '8px 12px',
          background: 'rgba(255,255,255,0.04)',
          border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: 6,
          fontSize: 14,
          color: '#f1f5f9',
        }}>
          {modelName}
        </div>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <label style={{ fontSize: 12, fontWeight: 600, color: '#64748b' }}>
          Descrição do Cenário (opcional)
        </label>
        <textarea
          value={description}
          onChange={e => onDescriptionChange(e.target.value)}
          placeholder="Ex: Detectar capacete e colete em área de manufatura..."
          rows={3}
          style={{
            padding: '8px 12px',
            background: 'rgba(255,255,255,0.04)',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 6,
            fontSize: 13,
            color: '#f1f5f9',
            resize: 'vertical',
            fontFamily: 'inherit',
          }}
        />
      </div>
    </div>
  )
}

function StepClasses({
  selected,
  onToggle,
}: {
  selected: string[]
  onToggle: (value: string) => void
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <p style={{ margin: 0, fontSize: 13, color: '#94a3b8' }}>
        Selecione as classes que este modelo deve detectar.
        Deixe vazio para usar todas as classes do modelo.
      </p>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        {EPI_CLASS_OPTIONS.map(opt => {
          const isSelected = selected.includes(opt.value)
          return (
            <label
              key={opt.value}
              style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '10px 14px',
                borderRadius: 8,
                cursor: 'pointer',
                border: `1px solid ${isSelected ? 'rgba(124,58,237,0.6)' : 'rgba(255,255,255,0.07)'}`,
                background: isSelected ? 'rgba(124,58,237,0.12)' : 'transparent',
                userSelect: 'none',
              }}
            >
              <input
                type="checkbox"
                checked={isSelected}
                onChange={() => onToggle(opt.value)}
                style={{ accentColor: '#7c3aed', width: 14, height: 14, flexShrink: 0 }}
              />
              <span style={{ fontSize: 13, color: isSelected ? '#c4b5fd' : '#94a3b8' }}>
                {opt.label}
              </span>
            </label>
          )
        })}
      </div>
      {selected.length > 0 && (
        <p style={{ margin: 0, fontSize: 11, color: '#64748b' }}>
          {selected.length} classe{selected.length !== 1 ? 's' : ''} selecionada{selected.length !== 1 ? 's' : ''}
        </p>
      )}
    </div>
  )
}

function StepCountingLine({
  line,
  onChange,
}: {
  line: CountingLine | null
  onChange: (line: CountingLine | null) => void
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <p style={{ margin: 0, fontSize: 13, color: '#94a3b8' }}>
        Defina a linha de cruzamento para contagem de objetos.
        Selecione a câmera no próximo passo para ver o frame de referência.
      </p>
      <DrawingCanvas
        line={line}
        onChange={onChange}
        width={560}
        height={315}
        color="#f59e0b"
      />
      {line && (
        <p style={{ margin: 0, fontSize: 11, color: '#64748b', fontFamily: 'monospace' }}>
          ({line.x1.toFixed(3)}, {line.y1.toFixed(3)}) → ({line.x2.toFixed(3)}, {line.y2.toFixed(3)})
        </p>
      )}
    </div>
  )
}

function StepRoi({
  roi,
  onChange,
}: {
  roi: RoiPoint[]
  onChange: (points: RoiPoint[]) => void
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <p style={{ margin: 0, fontSize: 13, color: '#94a3b8' }}>
        Defina a zona de interesse (ROI) onde o modelo deve atuar.
        Clique para adicionar pontos e feche o polígono clicando no ponto inicial.
      </p>
      <RoiDrawer
        points={roi}
        onChange={onChange}
        width={560}
        height={315}
        color="#3b82f6"
      />
      {roi.length > 0 && (
        <p style={{ margin: 0, fontSize: 11, color: '#64748b' }}>
          {roi.length} ponto{roi.length !== 1 ? 's' : ''} — ROI {roi.length >= 3 ? 'fechado' : 'incompleto (mín. 3)'}
        </p>
      )}
    </div>
  )
}

function StepConfidence({
  value,
  onChange,
}: {
  value: number
  onChange: (v: number) => void
}) {
  const pct = Math.round(value * 100)

  const level =
    value >= 0.75 ? { label: 'Alta precisão', color: '#22c55e' }
    : value >= 0.5  ? { label: 'Balanceado', color: '#3b82f6' }
    : value >= 0.35 ? { label: 'Sensível (mais detecções)', color: '#f59e0b' }
    :                 { label: 'Muito sensível', color: '#ef4444' }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <p style={{ margin: 0, fontSize: 13, color: '#94a3b8' }}>
        Defina o limiar mínimo de confiança para uma detecção ser considerada válida.
        Valores mais altos reduzem falsos positivos; valores mais baixos detectam mais objetos.
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: 13, color: '#94a3b8' }}>Limiar de confiança</span>
          <span style={{ fontSize: 22, fontWeight: 700, color: level.color, fontFamily: 'monospace' }}>
            {pct}%
          </span>
        </div>
        <input
          type="range"
          min={10}
          max={99}
          step={1}
          value={pct}
          onChange={e => onChange(Number(e.target.value) / 100)}
          style={{ width: '100%', accentColor: '#7c3aed', cursor: 'pointer' }}
        />
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#475569' }}>
          <span>10% (sensível)</span>
          <span style={{ color: level.color, fontWeight: 600 }}>{level.label}</span>
          <span>99% (preciso)</span>
        </div>
      </div>
    </div>
  )
}

function StepCamera({
  cameras,
  selectedId,
  onSelect,
}: {
  cameras: Camera[]
  selectedId: string | null
  onSelect: (id: string | null) => void
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <p style={{ margin: 0, fontSize: 13, color: '#94a3b8' }}>
        Vincule este modelo a uma câmera específica.
        O frame de referência da câmera será usado nas etapas de linha e ROI.
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <label style={{ fontSize: 12, fontWeight: 600, color: '#64748b' }}>
          Câmera vinculada
        </label>
        <select
          value={selectedId ?? ''}
          onChange={e => onSelect(e.target.value || null)}
          style={{
            padding: '8px 12px',
            background: '#1e293b',
            border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: 6,
            fontSize: 13,
            color: '#f1f5f9',
            cursor: 'pointer',
          }}
        >
          <option value="">Nenhuma câmera (genérico)</option>
          {cameras.map(cam => (
            <option key={cam.id} value={cam.id}>
              {cam.name}{cam.location ? ` — ${cam.location}` : ''}
            </option>
          ))}
        </select>
      </div>

      {selectedId && (
        <div style={{
          padding: '10px 14px',
          background: 'rgba(59,130,246,0.08)',
          border: '1px solid rgba(59,130,246,0.2)',
          borderRadius: 8,
          fontSize: 12,
          color: '#93c5fd',
        }}>
          Câmera vinculada: <strong>{cameras.find(c => c.id === selectedId)?.name ?? selectedId}</strong>
        </div>
      )}

      {cameras.length === 0 && (
        <p style={{ margin: 0, fontSize: 12, color: '#f59e0b' }}>
          Nenhuma câmera cadastrada. Cadastre câmeras em Câmeras para vinculá-las.
        </p>
      )}
    </div>
  )
}
