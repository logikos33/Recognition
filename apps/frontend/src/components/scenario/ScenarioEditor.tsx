/**
 * ScenarioEditor — editor visual de cenário para câmera.
 *
 * Fluxo: escolher módulo → tipo de operação → desenhar geometria (zona/linha/ponto)
 * → nomear + configurar classes → salvar via operations CRUD.
 *
 * Decisão de UX: background usa CameraPlayer (HLS) se hlsUrl fornecida;
 * sem stream, exibe placeholder escuro com aviso — editor não bloqueia.
 * Ferramenta de desenho é determinada pelo config_schema do operation-type
 * (roi_points → zona, line_points → linha, point → ponto; default zona).
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useScenario, useScenarioOperationTypes } from '../../hooks/useScenario'
import { useOperations } from '../../hooks/useOperations'
import { CameraPlayer } from '../monitoring/CameraPlayer'
import { DrawingCanvas, type DrawingTool } from './DrawingCanvas'
import type { OperationType, RoiPoint } from '../../types/operations'
import { vars } from '../../styles/theme.css'

interface ScenarioEditorProps {
  cameraId: string
  hlsUrl?: string
  onBack?: () => void
}

type DrawHistory = RoiPoint[][]

function inferTool(type: OperationType | null): DrawingTool {
  if (!type) return 'zone'
  const schema = type.config_schema
  if ('line_points' in schema) return 'line'
  if ('point' in schema) return 'point'
  return 'zone'
}

function buildConfig(
  tool: DrawingTool,
  points: RoiPoint[],
  params: Record<string, unknown>
): Record<string, unknown> {
  if (tool === 'zone' && points.length >= 3)
    return { ...params, roi_points: points.map(p => [p.x, p.y]) }
  if (tool === 'line' && points.length === 2)
    return { ...params, line_points: points.map(p => [p.x, p.y]) }
  if (tool === 'point' && points.length === 1)
    return { ...params, point: [points[0].x, points[0].y] }
  return params
}

function isDrawingComplete(tool: DrawingTool, points: RoiPoint[]): boolean {
  if (tool === 'zone') return points.length >= 3
  if (tool === 'line') return points.length === 2
  return points.length === 1
}

export function ScenarioEditor({ cameraId, hlsUrl, onBack }: ScenarioEditorProps) {
  const { scenario, loading: scenarioLoading, error: scenarioError, refetch } = useScenario({ cameraId })

  const [selectedModule, setSelectedModule] = useState('')
  const [selectedType, setSelectedType] = useState<OperationType | null>(null)
  const [opName, setOpName] = useState('')
  const [targetClasses, setTargetClasses] = useState<string[]>([])
  const [params, setParams] = useState<Record<string, unknown>>({})

  // Undo/redo drawing history
  const [history, setHistory] = useState<DrawHistory>([[]])
  const [historyIdx, setHistoryIdx] = useState(0)

  const currentPoints = history[historyIdx]

  const pushHistory = useCallback((pts: RoiPoint[]) => {
    setHistory(prev => {
      const next = prev.slice(0, historyIdx + 1)
      return [...next, pts]
    })
    setHistoryIdx(idx => idx + 1)
  }, [historyIdx])

  const undo = useCallback(() => setHistoryIdx(i => Math.max(0, i - 1)), [])
  const redo = useCallback(() => setHistoryIdx(i => Math.min(history.length - 1, i + 1)), [history.length])

  const resetDraw = useCallback(() => { setHistory([[]]); setHistoryIdx(0) }, [])

  const tool: DrawingTool = useMemo(() => inferTool(selectedType), [selectedType])

  // Auto-select first enabled module when scenario loads
  useEffect(() => {
    if (!scenario || selectedModule) return
    const first = scenario.modules.find(m => m.enabled)
    if (first) setSelectedModule(first.module_code)
  }, [scenario, selectedModule])

  // Reset type + drawing when module changes
  useEffect(() => { setSelectedType(null); resetDraw() }, [selectedModule, resetDraw])

  // Reset drawing when type changes
  useEffect(() => { resetDraw(); setParams({}) }, [selectedType, resetDraw])

  const { types: opTypes, loading: typesLoading } = useScenarioOperationTypes({
    moduleCode: selectedModule,
    enabled: !!selectedModule,
  })

  const { operations, loading: opsLoading, createOperation, refetch: refetchOps } = useOperations({
    cameraId,
    moduleId: selectedModule,
    enabled: !!selectedModule,
  })

  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saveSuccess, setSaveSuccess] = useState(false)

  const availableClasses = useMemo(
    () => scenario?.modules.find(m => m.module_code === selectedModule)?.classes ?? [],
    [scenario, selectedModule]
  )

  const canSave = !!selectedType && !!opName.trim() && isDrawingComplete(tool, currentPoints)

  const handleSave = useCallback(async () => {
    if (!selectedType || !canSave) return
    setSaving(true)
    setSaveError(null)
    setSaveSuccess(false)
    try {
      const finalConfig = buildConfig(tool, currentPoints, {
        ...params,
        ...(targetClasses.length > 0 ? { target_classes: targetClasses } : {}),
      })
      await createOperation({
        module_id: selectedModule,
        type_id: selectedType.type_id,
        name: opName.trim(),
        config: finalConfig,
      })
      setOpName('')
      setTargetClasses([])
      setParams({})
      resetDraw()
      setSaveSuccess(true)
      refetch()
      refetchOps()
      setTimeout(() => setSaveSuccess(false), 3000)
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Erro ao salvar operação')
    } finally {
      setSaving(false)
    }
  }, [selectedType, canSave, tool, currentPoints, params, targetClasses, selectedModule, opName, createOperation, refetch, refetchOps, resetDraw])

  const toggleClass = useCallback((cls: string) => {
    setTargetClasses(prev => prev.includes(cls) ? prev.filter(c => c !== cls) : [...prev, cls])
  }, [])

  const handleSelectModule = useCallback((code: string) => {
    setSelectedModule(code)
  }, [])

  const handleSelectType = useCallback((type: OperationType) => {
    setSelectedType(type)
  }, [])

  return (
    <div
      data-testid="scenario-editor"
      style={{ display: 'flex', flexDirection: 'column', height: '100%', background: vars.color.bgBase }}
    >
      {/* Header */}
      <header
        style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '10px 16px', borderBottom: `1px solid ${vars.color.borderDefault}`,
          background: vars.color.bgBase, flexShrink: 0,
        }}
      >
        {onBack && (
          <button
            onClick={onBack}
            aria-label="Voltar"
            style={{ display: 'flex', alignItems: 'center', gap: 4, background: 'transparent', border: 'none', color: vars.color.textMuted, cursor: 'pointer', fontSize: 13 }}
          >
            ← Voltar
          </button>
        )}
        <span style={{ color: vars.color.textPrimary, fontSize: 12 }}>/</span>
        <h1 style={{ margin: 0, fontSize: 14, color: vars.color.textSecondary, fontWeight: 600 }}>
          Editor de Cenário
        </h1>
        {scenario?.camera.name && (
          <>
            <span style={{ color: vars.color.textPrimary, fontSize: 12 }}>/</span>
            <span style={{ fontSize: 13, color: vars.color.textMuted }}>{scenario.camera.name}</span>
          </>
        )}
        <div style={{ flex: 1 }} />
        {saveError && (
          <span role="alert" style={{ fontSize: 12, color: '#ef4444' }}>{saveError}</span>
        )}
        {saveSuccess && (
          <span role="status" style={{ fontSize: 12, color: vars.color.success }}>Operação salva com sucesso!</span>
        )}
      </header>

      {/* Loading */}
      {scenarioLoading && (
        <div
          role="status"
          aria-live="polite"
          style={{ padding: 32, color: vars.color.textMuted, textAlign: 'center', fontSize: 13 }}
        >
          Carregando cenário...
        </div>
      )}

      {/* Error */}
      {!scenarioLoading && scenarioError && (
        <div
          role="alert"
          style={{ padding: 32, color: '#ef4444', textAlign: 'center', fontSize: 13 }}
        >
          {scenarioError}
        </div>
      )}

      {/* Main content */}
      {!scenarioLoading && !scenarioError && (
        <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
          {/* Sidebar */}
          <aside
            aria-label="Painel de configuração"
            style={{
              width: 260, flexShrink: 0,
              borderRight: `1px solid ${vars.color.borderDefault}`,
              overflowY: 'auto',
              background: vars.color.bgBase,
            }}
          >
            {/* Módulo */}
            <SideSection title="Módulo">
              <div role="radiogroup" aria-label="Selecionar módulo">
                {(scenario?.modules ?? []).length === 0 && (
                  <EmptyHint>Nenhum módulo habilitado</EmptyHint>
                )}
                {(scenario?.modules ?? []).map(mod => (
                  <SideButton
                    key={mod.module_code}
                    active={selectedModule === mod.module_code}
                    role="radio"
                    aria-checked={selectedModule === mod.module_code}
                    onClick={() => handleSelectModule(mod.module_code)}
                    data-testid={`module-btn-${mod.module_code}`}
                  >
                    {mod.module_code}
                  </SideButton>
                ))}
              </div>
            </SideSection>

            {/* Tipo de operação */}
            {selectedModule && (
              <SideSection title="Tipo de Operação">
                <div role="radiogroup" aria-label="Selecionar tipo de operação">
                  {typesLoading && <EmptyHint>Carregando...</EmptyHint>}
                  {!typesLoading && opTypes.length === 0 && (
                    <EmptyHint>Nenhum tipo disponível</EmptyHint>
                  )}
                  {opTypes.map(type => (
                    <SideButton
                      key={type.type_id}
                      active={selectedType?.type_id === type.type_id}
                      role="radio"
                      aria-checked={selectedType?.type_id === type.type_id}
                      onClick={() => handleSelectType(type)}
                      data-testid={`type-btn-${type.type_id}`}
                    >
                      <span style={{ fontSize: 11, color: 'inherit', opacity: 0.6, marginRight: 6, fontFamily: 'monospace' }}>▶</span>
                      <span>
                        <div>{type.type_label}</div>
                        {type.description && (
                          <div style={{ fontSize: 10, opacity: 0.5, marginTop: 1 }}>{type.description}</div>
                        )}
                      </span>
                    </SideButton>
                  ))}
                </div>
              </SideSection>
            )}

            {/* Ferramenta (indicador) */}
            {selectedType && (
              <SideSection title="Ferramenta de Desenho">
                <div style={{ padding: '4px 16px', display: 'flex', gap: 6 }}>
                  {(['zone', 'line', 'point'] as DrawingTool[]).map(t => (
                    <span
                      key={t}
                      aria-label={`Ferramenta ${t}${tool === t ? ' (ativa)' : ''}`}
                      style={{
                        padding: '4px 8px', borderRadius: 4, fontSize: 11, fontWeight: 500,
                        background: tool === t ? 'rgba(59,130,246,0.2)' : vars.color.bgSurface,
                        border: `1px solid ${tool === t ? vars.color.primary : vars.color.bgCard}`,
                        color: tool === t ? vars.color.primary : vars.color.borderStrong,
                      }}
                    >
                      {t === 'zone' ? '⬡ Zona' : t === 'line' ? '— Linha' : '• Ponto'}
                    </span>
                  ))}
                </div>
                <div style={{ padding: '2px 16px 6px', fontSize: 11, color: vars.color.textPrimary }}>
                  Definida pelo tipo selecionado
                </div>
              </SideSection>
            )}

            {/* Nome */}
            {selectedType && (
              <SideSection title="Nome da Operação">
                <div style={{ padding: '4px 16px' }}>
                  <input
                    value={opName}
                    onChange={e => setOpName(e.target.value)}
                    placeholder={`Ex: ${selectedType.type_label}`}
                    aria-label="Nome da operação"
                    data-testid="op-name-input"
                    style={inputStyle}
                  />
                </div>
              </SideSection>
            )}

            {/* Classes */}
            {selectedType && availableClasses.length > 0 && (
              <SideSection title="Classes a Monitorar">
                <div style={{ padding: '4px 16px', display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {availableClasses.map(cls => (
                    <label
                      key={cls.class_name}
                      style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: vars.color.textSecondary, cursor: 'pointer' }}
                    >
                      <input
                        type="checkbox"
                        checked={targetClasses.includes(cls.class_name)}
                        onChange={() => toggleClass(cls.class_name)}
                        aria-label={`Classe ${cls.display_name ?? cls.class_name}`}
                        style={{ accentColor: vars.color.primary }}
                      />
                      {cls.display_name ?? cls.class_name}
                    </label>
                  ))}
                </div>
              </SideSection>
            )}

            {/* Parâmetro threshold (genérico) */}
            {selectedType && (
              <SideSection title="Threshold de Alerta">
                <div style={{ padding: '4px 16px' }}>
                  <input
                    type="number"
                    min={0}
                    value={(params.threshold as number) ?? 1}
                    onChange={e => setParams(p => ({ ...p, threshold: Number(e.target.value) }))}
                    aria-label="Threshold de alerta"
                    style={{ ...inputStyle, width: 80 }}
                  />
                </div>
              </SideSection>
            )}

            {/* Botão salvar */}
            {selectedType && (
              <div style={{ padding: '8px 16px' }}>
                <button
                  onClick={handleSave}
                  disabled={!canSave || saving}
                  aria-label="Salvar operação"
                  data-testid="save-btn"
                  style={{
                    width: '100%', padding: '10px 0',
                    background: canSave && !saving ? vars.color.primary : vars.color.bgCard,
                    border: 'none', borderRadius: 6,
                    color: canSave && !saving ? vars.color.textOnPrimary : vars.color.borderStrong,
                    fontSize: 13, fontWeight: 500,
                    cursor: canSave && !saving ? 'pointer' : 'not-allowed',
                    transition: 'background 0.15s',
                  }}
                >
                  {saving ? 'Salvando...' : 'Salvar Operação'}
                </button>
              </div>
            )}

            {/* Divisor */}
            <div style={{ borderTop: '1px solid #181818', margin: '4px 0 8px' }} />

            {/* Operações salvas */}
            <SideSection title={`Operações (${operations.length})`}>
              {opsLoading && <EmptyHint>Carregando...</EmptyHint>}
              {!opsLoading && operations.length === 0 && (
                <EmptyHint>Nenhuma operação cadastrada</EmptyHint>
              )}
              {operations.map(op => (
                <div
                  key={op.id}
                  style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 16px' }}
                >
                  <span
                    style={{
                      width: 6, height: 6, borderRadius: '50%', flexShrink: 0,
                      background: op.status === 'active' ? vars.color.success
                        : op.status === 'error' ? '#ef4444'
                          : op.status === 'warning' ? '#f59e0b'
                            : vars.color.textMuted,
                    }}
                  />
                  <span style={{ fontSize: 12, color: vars.color.textMuted, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {op.name}
                  </span>
                </div>
              ))}
            </SideSection>
          </aside>

          {/* Área do canvas */}
          <main
            aria-label="Área de desenho"
            style={{
              flex: 1, display: 'flex', alignItems: 'flex-start', justifyContent: 'center',
              padding: 24, overflowY: 'auto', background: vars.color.bgBase,
            }}
          >
            <div
              style={{
                position: 'relative', width: 640, height: 360, flexShrink: 0,
                borderRadius: 8, overflow: 'hidden', background: '#000',
                border: '1px solid #1e3a5f',
              }}
            >
              {/* Layer 1: câmera */}
              {hlsUrl ? (
                <CameraPlayer
                  cameraId={cameraId}
                  hlsUrl={hlsUrl}
                  width={640}
                  height={360}
                />
              ) : (
                <div
                  style={{
                    position: 'absolute', inset: 0,
                    background: 'linear-gradient(135deg, #0a0e1a 0%, #0d1420 100%)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}
                >
                  <span style={{ color: '#2a4a6a', fontSize: 13, fontFamily: 'monospace', textAlign: 'center' }}>
                    Stream não disponível<br />
                    <span style={{ fontSize: 11, opacity: 0.6 }}>desenhe no placeholder ou conecte um stream</span>
                  </span>
                </div>
              )}

              {/* Layer 2: DrawingCanvas overlay */}
              <DrawingCanvas
                points={currentPoints}
                tool={tool}
                onChange={pushHistory}
                onUndo={undo}
                onRedo={redo}
                canUndo={historyIdx > 0}
                canRedo={historyIdx < history.length - 1}
                existingOperations={operations}
              />
            </div>
          </main>
        </div>
      )}
    </div>
  )
}

// Sub-componentes locais

function SideSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{
        padding: '6px 16px 4px',
        fontSize: 10, fontWeight: 600, color: vars.color.textPrimary,
        textTransform: 'uppercase', letterSpacing: '0.07em',
      }}>
        {title}
      </div>
      {children}
    </div>
  )
}

function SideButton({
  active, children, ...rest
}: { active: boolean; children: React.ReactNode } & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...rest}
      style={{
        display: 'flex', alignItems: 'flex-start', width: '100%',
        padding: '7px 16px',
        background: active ? 'rgba(59,130,246,0.1)' : 'transparent',
        border: 'none',
        borderLeft: active ? `2px solid ${vars.color.primary}` : '2px solid transparent',
        color: active ? vars.color.textSecondary : vars.color.textMuted,
        fontSize: 13, cursor: 'pointer', textAlign: 'left',
        transition: 'color 0.1s',
      }}
    >
      {children}
    </button>
  )
}

function EmptyHint({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ padding: '4px 16px 6px', fontSize: 12, color: vars.color.textPrimary }}>
      {children}
    </div>
  )
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '7px 10px',
  background: vars.color.bgSurface,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: 6,
  color: vars.color.textOnPrimary,
  fontSize: 13,
  boxSizing: 'border-box',
}
