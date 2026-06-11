/**
 * Editor visual de cenário — módulo, tipo de operação, ferramentas de desenho,
 * configuração e salvamento via operations API. Gerencia undo/redo internamente.
 *
 * Decisão: background do canvas usa placeholder em dev (sem JWT em query param de HLS).
 * Undo: máx 100 entradas no histórico para evitar crescimento ilimitado.
 * task-039: máscara de exclusão (exclude_zones) + perfil dia/noite (day_night_profile).
 */
import { useCallback, useReducer, useState } from 'react'
import { useOperations, useOperationTypes } from '../../hooks/useOperations'
import type { Operation, OperationCreate, RoiPoint } from '../../types/operations'
import { DrawingCanvas } from './DrawingCanvas'
import type { DrawingTool } from './DrawingCanvas'

const MAX_HISTORY = 100

const EPI_CLASSES = [
  'helmet', 'no_helmet', 'vest', 'no_vest',
  'gloves', 'no_gloves', 'glasses', 'no_glasses',
]

const TOOL_LABELS: Record<DrawingTool, string> = {
  zone: 'Zona (polígono)',
  line: 'Linha',
  point: 'Ponto',
  mask: 'Máscara (exclusão)',
}

// --- Undo/redo via reducer ---

type HistoryState = { stack: RoiPoint[][]; index: number }
type HistoryAction =
  | { type: 'push'; points: RoiPoint[] }
  | { type: 'undo' }
  | { type: 'redo' }
  | { type: 'reset' }

function historyReducer(state: HistoryState, action: HistoryAction): HistoryState {
  switch (action.type) {
    case 'push': {
      const trimmed = state.stack.slice(0, state.index + 1)
      const next = [...trimmed, action.points]
      const capped = next.length > MAX_HISTORY + 1 ? next.slice(next.length - (MAX_HISTORY + 1)) : next
      return { stack: capped, index: capped.length - 1 }
    }
    case 'undo':
      return { ...state, index: Math.max(0, state.index - 1) }
    case 'redo':
      return { ...state, index: Math.min(state.stack.length - 1, state.index + 1) }
    case 'reset':
      return { stack: [[]], index: 0 }
  }
}

// ---

export interface ScenarioEditorProps {
  cameraId: string
  defaultModuleId?: string
}

export function ScenarioEditor({ cameraId, defaultModuleId = 'ppe' }: ScenarioEditorProps) {
  const [moduleId, setModuleId] = useState(defaultModuleId)
  const [selectedTypeId, setSelectedTypeId] = useState('')
  const [tool, setTool] = useState<DrawingTool>('zone')
  const [name, setName] = useState('')
  const [threshold, setThreshold] = useState(0.5)
  const [selectedClasses, setSelectedClasses] = useState<string[]>([])
  const [excludeZones, setExcludeZones] = useState<RoiPoint[][]>([])
  const [maskInProgress, setMaskInProgress] = useState<RoiPoint[]>([])
  const [dayConfidence, setDayConfidence] = useState('')
  const [nightConfidence, setNightConfidence] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saveSuccess, setSaveSuccess] = useState(false)

  const [history, dispatch] = useReducer(historyReducer, { stack: [[]], index: 0 })
  const currentPoints = history.stack[history.index] ?? []

  const { types, loading: typesLoading } = useOperationTypes({ moduleId })
  const { operations, loading: opsLoading, error: opsError, createOperation } =
    useOperations({ cameraId, moduleId })

  const selectedType = types.find(t => t.type_id === selectedTypeId)
  const availableClasses =
    Array.isArray(selectedType?.config_schema?.classes)
      ? (selectedType.config_schema.classes as string[])
      : EPI_CLASSES

  const handleModuleChange = useCallback((mod: string) => {
    setModuleId(mod)
    setSelectedTypeId('')
    setTool('zone')
    setExcludeZones([])
    setMaskInProgress([])
    dispatch({ type: 'reset' })
  }, [])

  const handleTypeChange = useCallback((typeId: string) => {
    setSelectedTypeId(typeId)
    setMaskInProgress([])
    dispatch({ type: 'reset' })
    if (typeId.includes('line')) setTool('line')
    else if (typeId.includes('point') || typeId.includes('position')) setTool('point')
    else setTool('zone')
  }, [])

  const handleToolChange = useCallback((newTool: DrawingTool) => {
    if (newTool === 'mask' || tool === 'mask') {
      setMaskInProgress([])
    }
    setTool(newTool)
  }, [tool])

  // Canvas points and onChange depend on the active tool
  const canvasPoints = tool === 'mask' ? maskInProgress : currentPoints
  const handleCanvasChange = useCallback((pts: RoiPoint[]) => {
    if (tool === 'mask') {
      setMaskInProgress(pts)
    } else {
      dispatch({ type: 'push', points: pts })
    }
  }, [tool])

  const handleUndo = useCallback(() => dispatch({ type: 'undo' }), [])
  const handleRedo = useCallback(() => dispatch({ type: 'redo' }), [])

  const handleAddMask = useCallback(() => {
    if (maskInProgress.length >= 3) {
      setExcludeZones(prev => [...prev, maskInProgress])
      setMaskInProgress([])
    }
  }, [maskInProgress])

  const toggleClass = useCallback((cls: string) => {
    setSelectedClasses(prev =>
      prev.includes(cls) ? prev.filter(c => c !== cls) : [...prev, cls]
    )
  }, [])

  const handleThresholdChange = useCallback((raw: string) => {
    if (!raw.trim()) return
    const n = Number(raw)
    if (!isNaN(n)) setThreshold(n)
  }, [])

  const handleSave = useCallback(async () => {
    if (!selectedTypeId || !name.trim()) return
    setSaving(true)
    setSaveError(null)
    setSaveSuccess(false)
    try {
      const config: Record<string, unknown> = {
        roi: currentPoints,
        classes: selectedClasses,
        threshold,
      }
      if (excludeZones.length > 0) {
        config.exclude_zones = excludeZones.map(zone => zone.map(p => [p.x, p.y]))
      }
      const profile: Record<string, { confidence: number }> = {}
      const dayConf = parseFloat(dayConfidence)
      const nightConf = parseFloat(nightConfidence)
      if (dayConfidence !== '' && !isNaN(dayConf)) profile.day = { confidence: dayConf }
      if (nightConfidence !== '' && !isNaN(nightConf)) profile.night = { confidence: nightConf }
      if (Object.keys(profile).length > 0) config.day_night_profile = profile

      const payload: OperationCreate = {
        module_id: moduleId,
        type_id: selectedTypeId,
        name: name.trim(),
        config,
      }
      await createOperation(payload)
      setName('')
      setSelectedClasses([])
      setExcludeZones([])
      setMaskInProgress([])
      setDayConfidence('')
      setNightConfidence('')
      dispatch({ type: 'reset' })
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 2000)
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Erro ao salvar operação')
    } finally {
      setSaving(false)
    }
  }, [
    selectedTypeId, name, moduleId, currentPoints, selectedClasses, threshold,
    excludeZones, dayConfidence, nightConfidence, createOperation,
  ])

  const canSave = !!selectedTypeId && name.trim().length > 0 && !saving

  return (
    <div style={{ display: 'flex', gap: 16, height: '100%', minHeight: 0 }}>
      {/* Coluna principal */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12, minWidth: 0, overflowY: 'auto' }}>

        {/* Barra de ferramentas */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <label htmlFor="module-select" style={{ fontSize: 12, color: '#888' }}>Módulo:</label>
          <select
            id="module-select"
            value={moduleId}
            onChange={e => handleModuleChange(e.target.value)}
            aria-label="Selecionar módulo"
            style={{ fontSize: 13, background: '#1a1a1a', border: '1px solid #333', color: '#e0e0e0', borderRadius: 4, padding: '3px 6px' }}
          >
            <option value="ppe">EPI Monitor</option>
            <option value="fueling">Fueling Control</option>
          </select>

          <label htmlFor="type-select" style={{ fontSize: 12, color: '#888' }}>Tipo:</label>
          <select
            id="type-select"
            value={selectedTypeId}
            onChange={e => handleTypeChange(e.target.value)}
            aria-label="Selecionar tipo de operação"
            disabled={typesLoading}
            style={{ fontSize: 13, background: '#1a1a1a', border: '1px solid #333', color: '#e0e0e0', borderRadius: 4, padding: '3px 6px' }}
          >
            <option value="">— Selecione um tipo —</option>
            {types.map(t => (
              <option key={t.type_id} value={t.type_id}>{t.type_label}</option>
            ))}
          </select>

          <span style={{ fontSize: 12, color: '#888' }}>Ferramenta:</span>
          {(['zone', 'line', 'point', 'mask'] as DrawingTool[]).map(t => (
            <button
              key={t}
              onClick={() => handleToolChange(t)}
              aria-pressed={tool === t}
              style={{
                fontSize: 12, padding: '3px 10px', borderRadius: 4, cursor: 'pointer',
                background: tool === t ? (t === 'mask' ? '#f59e0b' : '#3b82f6') : '#1a1a1a',
                border: `1px solid ${tool === t ? (t === 'mask' ? '#f59e0b' : '#3b82f6') : '#333'}`,
                color: '#e0e0e0',
              }}
            >
              {TOOL_LABELS[t]}
            </button>
          ))}

          <button
            onClick={handleUndo}
            disabled={history.index === 0}
            aria-label="Desfazer (Ctrl+Z)"
            title="Ctrl+Z"
            style={{ fontSize: 12, padding: '3px 8px', borderRadius: 4, background: '#1a1a1a', border: '1px solid #333', color: '#e0e0e0', cursor: 'pointer' }}
          >
            ↩ Desfazer
          </button>
          <button
            onClick={handleRedo}
            disabled={history.index >= history.stack.length - 1}
            aria-label="Refazer (Ctrl+Shift+Z)"
            title="Ctrl+Shift+Z"
            style={{ fontSize: 12, padding: '3px 8px', borderRadius: 4, background: '#1a1a1a', border: '1px solid #333', color: '#e0e0e0', cursor: 'pointer' }}
          >
            ↪ Refazer
          </button>
        </div>

        {/* Canvas de desenho */}
        <DrawingCanvas
          tool={tool}
          points={canvasPoints}
          onChange={handleCanvasChange}
          onUndo={handleUndo}
          onRedo={handleRedo}
          existingOperations={operations}
          excludeZones={excludeZones}
        />

        {/* Botão de confirmar máscara (visível quando tool=mask e ≥3 pontos) */}
        {tool === 'mask' && maskInProgress.length >= 3 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <button
              onClick={handleAddMask}
              aria-label="Adicionar zona de exclusão"
              style={{
                fontSize: 12, padding: '4px 12px', borderRadius: 4, cursor: 'pointer',
                background: '#f59e0b', border: '1px solid #f59e0b', color: '#000', fontWeight: 600,
              }}
            >
              + Adicionar zona de exclusão ({maskInProgress.length} vértices)
            </button>
          </div>
        )}

        {/* Resumo de zonas de exclusão */}
        {excludeZones.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 12, color: '#f59e0b' }}>
              {excludeZones.length} zona(s) de exclusão
            </span>
            <button
              onClick={() => setExcludeZones([])}
              aria-label="Remover todas as zonas de exclusão"
              style={{
                fontSize: 11, padding: '2px 8px', borderRadius: 4, cursor: 'pointer',
                background: '#1a1a1a', border: '1px solid #444', color: '#888',
              }}
            >
              Limpar máscaras
            </button>
          </div>
        )}

        {/* Formulário de configuração */}
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <label htmlFor="op-name" style={{ fontSize: 12, color: '#888' }}>Nome da operação *</label>
            <input
              id="op-name"
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="ex: Zona EPI Linha 1"
              aria-label="Nome da operação"
              style={{ fontSize: 13, background: '#1a1a1a', border: '1px solid #333', color: '#e0e0e0', borderRadius: 4, padding: '4px 8px', width: 220 }}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <label htmlFor="op-threshold" style={{ fontSize: 12, color: '#888' }}>Limiar de confiança</label>
            <input
              id="op-threshold"
              type="number"
              min={0} max={1} step={0.05}
              value={threshold}
              onChange={e => handleThresholdChange(e.target.value)}
              aria-label="Limiar de confiança"
              style={{ fontSize: 13, background: '#1a1a1a', border: '1px solid #333', color: '#e0e0e0', borderRadius: 4, padding: '4px 8px', width: 100 }}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <label htmlFor="op-day-conf" style={{ fontSize: 12, color: '#888' }}>Confidence (dia)</label>
            <input
              id="op-day-conf"
              type="number"
              min={0.1} max={1} step={0.05}
              value={dayConfidence}
              placeholder="—"
              onChange={e => setDayConfidence(e.target.value)}
              aria-label="Confidence (dia)"
              style={{ fontSize: 13, background: '#1a1a1a', border: '1px solid #333', color: '#e0e0e0', borderRadius: 4, padding: '4px 8px', width: 100 }}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <label htmlFor="op-night-conf" style={{ fontSize: 12, color: '#888' }}>Confidence (noite)</label>
            <input
              id="op-night-conf"
              type="number"
              min={0.1} max={1} step={0.05}
              value={nightConfidence}
              placeholder="—"
              onChange={e => setNightConfidence(e.target.value)}
              aria-label="Confidence (noite)"
              style={{ fontSize: 13, background: '#1a1a1a', border: '1px solid #333', color: '#e0e0e0', borderRadius: 4, padding: '4px 8px', width: 100 }}
            />
          </div>
        </div>

        {/* Seleção de classes */}
        {selectedTypeId && (
          <div>
            <span style={{ fontSize: 12, color: '#888', display: 'block', marginBottom: 6 }}>
              Classes a vigiar:
            </span>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {availableClasses.map(cls => (
                <button
                  key={cls}
                  onClick={() => toggleClass(cls)}
                  aria-pressed={selectedClasses.includes(cls)}
                  style={{
                    fontSize: 11, padding: '2px 8px', borderRadius: 12, cursor: 'pointer',
                    background: selectedClasses.includes(cls) ? '#3b82f6' : '#1a1a1a',
                    border: `1px solid ${selectedClasses.includes(cls) ? '#3b82f6' : '#444'}`,
                    color: '#e0e0e0',
                  }}
                >
                  {cls}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Botão de salvar + feedback */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button
            onClick={handleSave}
            disabled={!canSave}
            aria-label="Salvar operação"
            style={{
              padding: '6px 18px', borderRadius: 5,
              cursor: canSave ? 'pointer' : 'not-allowed',
              background: canSave ? '#3b82f6' : '#222',
              border: `1px solid ${canSave ? '#3b82f6' : '#333'}`,
              color: '#fff', fontWeight: 600, fontSize: 13,
            }}
          >
            {saving ? 'Salvando…' : 'Salvar operação'}
          </button>
          {saveSuccess && (
            <span role="status" style={{ color: '#22c55e', fontSize: 13 }}>
              Operação salva!
            </span>
          )}
          {saveError && (
            <span role="alert" style={{ color: '#ef4444', fontSize: 13 }}>
              {saveError}
            </span>
          )}
        </div>
      </div>

      {/* Sidebar: lista de operações */}
      <div style={{ width: 240, borderLeft: '1px solid #1e1e1e', paddingLeft: 12, overflowY: 'auto', flexShrink: 0 }}>
        <h3 style={{ fontSize: 13, color: '#888', marginBottom: 8, fontWeight: 500 }}>
          Operações salvas
        </h3>
        {opsLoading && <p style={{ fontSize: 12, color: '#666' }}>Carregando…</p>}
        {opsError && (
          <p role="alert" style={{ fontSize: 12, color: '#ef4444' }}>{opsError}</p>
        )}
        {!opsLoading && operations.length === 0 && !opsError && (
          <p style={{ fontSize: 12, color: '#555' }}>Nenhuma operação configurada.</p>
        )}
        <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
          {operations.map(op => <OperationItem key={op.id} op={op} />)}
        </ul>
      </div>
    </div>
  )
}

function OperationItem({ op }: { op: Operation }) {
  const pts = Array.isArray(op.config?.roi) ? (op.config.roi as RoiPoint[]) : []
  const shape = pts.length >= 3 ? 'zona' : pts.length === 2 ? 'linha' : pts.length === 1 ? 'ponto' : '—'
  const statusColor: Record<string, string> = {
    active: '#22c55e', warning: '#eab308', error: '#ef4444', inactive: '#6b7280',
  }
  const exclusions = Array.isArray(op.config?.exclude_zones)
    ? (op.config.exclude_zones as unknown[]).length
    : 0
  return (
    <li
      data-testid={`operation-item-${op.id}`}
      style={{ padding: '6px 8px', background: '#111', borderRadius: 4, border: '1px solid #1e1e1e' }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
        <span
          aria-hidden="true"
          style={{ width: 8, height: 8, borderRadius: '50%', background: statusColor[op.status] ?? '#6b7280', flexShrink: 0 }}
        />
        <span style={{ fontSize: 12, color: '#e0e0e0', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {op.name}
        </span>
      </div>
      <div style={{ fontSize: 11, color: '#555' }}>
        {op.type_label ?? op.type_id} — {shape}
        {exclusions > 0 && ` · ${exclusions} máscara(s)`}
      </div>
    </li>
  )
}
