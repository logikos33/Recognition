/**
 * CameraFpsConfig — seletor de FPS alvo e qualidade por câmera (WS10).
 *
 * Health-aware REAL: busca GET /cameras/<id>/health-context (telemetria do
 * site — GPU/VRAM/CPU/fila/FPS medido/latência/térmica/decode + demanda de
 * FPS das câmeras ativas). Sem telemetria → heurística aproximada com
 * disclaimer explícito.
 *
 * Papéis: superadmin/admin/operator editam (control_cameras); viewer vê
 * read-only com tooltip. Salvar: loading → Toast de sucesso (menciona
 * propagação ao edge quando enfileirada) → erro inline.
 *
 * Visual: tokens do tema (zero cor hardcoded), container do UI kit.
 */
import { useCallback, useEffect, useState, type CSSProperties } from 'react'
import { Activity, RefreshCw, Zap } from 'lucide-react'
import { Button } from '../ui/Button/Button'
import { Skeleton } from '../ui/Skeleton/Skeleton'
import { Tooltip } from '../ui/Tooltip/Tooltip'
import { useToast } from '../ui/Toast/useToast'
import { useAuth } from '../../hooks/useAuth'
import { cameraService } from '../../services/cameraService'
import type { Camera } from '../../types'
import type { CameraHealthContext } from '../../types/edge'
import { vars } from '../../styles/theme.css'

const FPS_OPTIONS = [1, 5, 10, 15, 30] as const
const QUALITY_OPTIONS = [
  { value: 'low',    label: 'Baixa'  },
  { value: 'medium', label: 'Média'  },
  { value: 'high',   label: 'Alta'   },
] as const

type FpsOption = typeof FPS_OPTIONS[number]
type QualityOption = 'low' | 'medium' | 'high'
type Severity = 'ok' | 'warning' | 'critical'

const EDIT_ROLES = ['superadmin', 'admin', 'operator']

interface Props {
  camera: Camera
  /** Fallback para a heurística quando não há telemetria do site. */
  totalActiveCameras?: number
  onSaved: (updated: Camera) => void
  /** Notifica o pai quando o health-context carrega (ex: aba Info do VMS). */
  onHealthContext?: (ctx: CameraHealthContext) => void
}

/** Heurística usada APENAS quando não há telemetria (disclaimer na UI). */
function estimateLoad(fps: number, nCameras: number): number {
  return Math.min(100, Math.round(fps * nCameras * 2))
}

function severityFromTelemetry(ctx: CameraHealthContext): Severity {
  const m = ctx.metrics
  const gpu = m?.gpu_pct ?? 0
  const vram = m?.gpu_mem_pct ?? 0
  if (
    gpu >= 85 ||
    vram >= 90 ||
    ctx.derived_status === 'critical' ||
    ctx.derived_status === 'offline'
  ) {
    return 'critical'
  }
  if (gpu >= 60 || ctx.derived_status === 'degraded') return 'warning'
  return 'ok'
}

function severityFromEstimate(load: number): Severity {
  if (load >= 80) return 'critical'
  if (load >= 50) return 'warning'
  return 'ok'
}

function severityColor(sev: Severity): string {
  if (sev === 'critical') return vars.color.danger
  if (sev === 'warning') return vars.color.warning
  return vars.color.success
}

const STATUS_LABELS: Record<string, string> = {
  healthy: 'Saudável',
  degraded: 'Degradado',
  critical: 'Crítico',
  offline: 'Offline',
}

function fmt(value: number | null | undefined, suffix = ''): string {
  if (value == null) return '—'
  return `${Math.round(value * 10) / 10}${suffix}`
}

function MetricItem({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 74 }}>
      <span style={{ fontSize: 10, color: vars.color.textMuted }}>{label}</span>
      <span style={{ fontSize: 12, fontWeight: 600, color: vars.color.textPrimary }}>
        {value}
      </span>
    </div>
  )
}

export function CameraFpsConfig({
  camera,
  totalActiveCameras,
  onSaved,
  onHealthContext,
}: Props) {
  const { user } = useAuth()
  const toast = useToast()
  const canEdit = user != null && EDIT_ROLES.includes(user.role)

  const [fps, setFps] = useState<FpsOption>(
    (camera.fps_target ?? 5) as FpsOption
  )
  const [quality, setQuality] = useState<QualityOption>(
    (camera.quality_preset ?? 'medium') as QualityOption
  )
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const [ctx, setCtx] = useState<CameraHealthContext | null>(null)
  const [ctxLoading, setCtxLoading] = useState(true)

  const fetchContext = useCallback(async () => {
    setCtxLoading(true)
    try {
      const data = await cameraService.getHealthContext(camera.id)
      setCtx(data)
      onHealthContext?.(data)
    } catch {
      setCtx(null) // sem endpoint/erro → fallback heurístico
    } finally {
      setCtxLoading(false)
    }
    // onHealthContext intencionalmente fora das deps (callback do pai)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [camera.id])

  useEffect(() => {
    void fetchContext()
  }, [fetchContext])

  async function handleSave() {
    setSaving(true)
    setErr(null)
    try {
      const updated = await cameraService.patchConfig(camera.id, {
        fps_target: fps,
        quality_preset: quality,
      })
      toast.success(
        'Configuração salva',
        updated.propagation?.queued === true
          ? 'Propagação ao edge enfileirada'
          : undefined,
      )
      onSaved(updated)
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : 'Erro ao salvar configuração')
    } finally {
      setSaving(false)
    }
  }

  const changed =
    fps !== ((camera.fps_target ?? 5) as FpsOption) ||
    quality !== ((camera.quality_preset ?? 'medium') as QualityOption)

  const hasTelemetry = ctx?.has_telemetry === true

  // Demanda de FPS do site + simulação do delta com a seleção atual
  const currentFps = camera.fps_target ?? 5
  const demandTotal = ctx?.fps_demand_total ?? 0
  const projectedDemand = Math.max(0, demandTotal - currentFps + fps)
  const activeCameras =
    ctx != null && ctx.cameras_active_count > 0
      ? ctx.cameras_active_count
      : Math.max(1, totalActiveCameras ?? 1)

  const estimatedLoad = estimateLoad(fps, activeCameras)
  const severity: Severity = hasTelemetry && ctx != null
    ? severityFromTelemetry(ctx)
    : severityFromEstimate(estimatedLoad)
  const color = severityColor(severity)

  const optionButton = (selected: boolean): CSSProperties => ({
    padding: '4px 10px',
    borderRadius: 5,
    border: selected
      ? `1px solid ${vars.color.primaryLight}`
      : `1px solid ${vars.color.borderDefault}`,
    background: selected ? vars.color.primaryAlpha : 'transparent',
    color: selected ? vars.color.primaryLight : vars.color.textSecondary,
    cursor: canEdit ? 'pointer' : 'not-allowed',
    fontSize: 12,
    fontWeight: selected ? 600 : 400,
    opacity: canEdit ? 1 : 0.55,
  })

  const metrics = ctx?.metrics

  return (
    <div
      style={{
        background: vars.color.bgCard,
        border: `1px solid ${vars.color.borderSubtle}`,
        borderRadius: 8,
        padding: '12px 14px',
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          fontWeight: 600,
          fontSize: 13,
          color: vars.color.textPrimary,
        }}
      >
        <Zap size={14} style={{ color: vars.color.primaryLight }} />
        Desempenho por câmera
        {!canEdit && (
          <span style={{ fontSize: 10, fontWeight: 400, color: vars.color.textMuted }}>
            (somente leitura)
          </span>
        )}
      </div>

      {/* FPS selector */}
      <div>
        <div style={{ fontSize: 11, color: vars.color.textMuted, marginBottom: 5 }}>
          FPS de inferência
        </div>
        <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
          {FPS_OPTIONS.map(f => {
            const btn = (
              <button
                onClick={() => canEdit && setFps(f)}
                disabled={!canEdit}
                aria-label={`${f} fps`}
                style={optionButton(fps === f)}
              >
                {f} fps
              </button>
            )
            if (canEdit) return <span key={f}>{btn}</span>
            return (
              <Tooltip key={f} label="Sem permissão para alterar">
                {/* span: tooltip funciona mesmo com botão disabled */}
                <span style={{ display: 'inline-flex' }}>{btn}</span>
              </Tooltip>
            )
          })}
        </div>
      </div>

      {/* Quality selector */}
      <div>
        <div style={{ fontSize: 11, color: vars.color.textMuted, marginBottom: 5 }}>
          Qualidade do stream
        </div>
        <div style={{ display: 'flex', gap: 5 }}>
          {QUALITY_OPTIONS.map(q => {
            const btn = (
              <button
                onClick={() => canEdit && setQuality(q.value)}
                disabled={!canEdit}
                style={optionButton(quality === q.value)}
              >
                {q.label}
              </button>
            )
            if (canEdit) return <span key={q.value}>{btn}</span>
            return (
              <Tooltip key={q.value} label="Sem permissão para alterar">
                <span style={{ display: 'inline-flex' }}>{btn}</span>
              </Tooltip>
            )
          })}
        </div>
      </div>

      {/* Health-aware panel */}
      <div
        style={{
          background: vars.color.bgSurface,
          borderRadius: 6,
          padding: '8px 10px',
          fontSize: 11,
          color: vars.color.textSecondary,
          borderLeft: `3px solid ${color}`,
          display: 'flex',
          flexDirection: 'column',
          gap: 6,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Activity size={12} style={{ color }} />
          <span style={{ fontWeight: 600, color: vars.color.textPrimary }}>
            Saúde do edge
          </span>
          {hasTelemetry && ctx?.derived_status != null && (
            <span style={{ color, fontWeight: 600 }}>
              {STATUS_LABELS[ctx.derived_status] ?? ctx.derived_status}
            </span>
          )}
          <span style={{ flex: 1 }} />
          <button
            onClick={() => void fetchContext()}
            disabled={ctxLoading}
            aria-label="Atualizar telemetria"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              background: 'transparent',
              border: `1px solid ${vars.color.borderDefault}`,
              borderRadius: 5,
              color: vars.color.textSecondary,
              cursor: ctxLoading ? 'wait' : 'pointer',
              fontSize: 10,
              padding: '2px 8px',
            }}
          >
            <RefreshCw size={10} />
            Atualizar
          </button>
        </div>

        {ctxLoading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <Skeleton variant="text" width="70%" />
            <Skeleton variant="text" width="50%" />
          </div>
        ) : hasTelemetry && metrics != null ? (
          <>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px 14px' }}>
              <MetricItem label="GPU" value={fmt(metrics.gpu_pct, '%')} />
              <MetricItem label="VRAM" value={fmt(metrics.gpu_mem_pct, '%')} />
              <MetricItem label="CPU" value={fmt(metrics.cpu_pct, '%')} />
              <MetricItem label="Fila" value={fmt(metrics.queue_depth)} />
              <MetricItem label="FPS medido" value={fmt(metrics.inference_fps)} />
              <MetricItem label="Latência" value={fmt(metrics.inference_latency_ms, ' ms')} />
              <MetricItem label="Térmica" value={fmt(metrics.gpu_temp_c, ' °C')} />
              <MetricItem label="Decode" value={fmt(metrics.decode_pct, '%')} />
            </div>
            <div>
              Demanda de FPS do site: <strong>{demandTotal} fps</strong> em{' '}
              {ctx.cameras_active_count} câmera{ctx.cameras_active_count !== 1 ? 's' : ''}
              {fps !== currentFps && (
                <span style={{ color: vars.color.textPrimary }}>
                  {' '}→ passará a ~<strong>{projectedDemand} fps</strong> com esta alteração
                </span>
              )}
            </div>
            {severity === 'critical' && (
              <span style={{ color: vars.color.danger, fontWeight: 600 }}>
                Aumentar o FPS pode saturar o edge.
              </span>
            )}
            {severity === 'warning' && (
              <span style={{ color: vars.color.warning }}>
                Carga moderada no edge — acompanhe antes de aumentar o FPS.
              </span>
            )}
          </>
        ) : (
          <>
            <div>
              <span style={{ color, fontWeight: 600 }}>
                {estimatedLoad}% de carga estimada
              </span>{' '}
              com {activeCameras} câmera{activeCameras !== 1 ? 's' : ''} a {fps} fps.
            </div>
            {severity === 'critical' && (
              <span style={{ color: vars.color.danger }}>
                Carga alta — considere reduzir o FPS ou o número de câmeras ativas.
              </span>
            )}
            <span style={{ color: vars.color.textMuted, fontStyle: 'italic' }}>
              Estimativa aproximada — sem telemetria do edge para este site.
            </span>
          </>
        )}
      </div>

      {/* Error */}
      {err && (
        <div role="alert" style={{ fontSize: 11, color: vars.color.danger }}>
          {err}
        </div>
      )}

      {/* Save */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {canEdit ? (
          <Button
            size="sm"
            variant="primary"
            onClick={handleSave}
            disabled={saving || !changed}
          >
            {saving ? 'Salvando...' : 'Salvar configuração'}
          </Button>
        ) : (
          <Tooltip label="Sem permissão para alterar">
            <span>
              <Button size="sm" variant="primary" disabled>
                Salvar configuração
              </Button>
            </span>
          </Tooltip>
        )}
        {canEdit && !changed && (
          <span style={{ fontSize: 11, color: vars.color.textDim }}>
            Sem alterações
          </span>
        )}
      </div>
    </div>
  )
}
