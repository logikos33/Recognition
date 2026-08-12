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
import { useCallback, useEffect, useState } from 'react'
import { Activity, AlertTriangle, RefreshCw, Zap } from 'lucide-react'
import { Button } from '../ui/Button/Button'
import { Skeleton } from '../ui/Skeleton/Skeleton'
import { Tooltip } from '../ui/Tooltip/Tooltip'
import { useToast } from '../ui/Toast/useToast'
import { useAuth } from '../../hooks/useAuth'
import { cameraService } from '../../services/cameraService'
import type { CameraConfigPatch } from '../../services/cameraService'
import type { Camera } from '../../types'
import type { CameraHealthContext } from '../../types/edge'
import { vars } from '../../styles/theme.css'
import * as s from './CameraFpsConfig.css'

const FPS_OPTIONS = [1, 5, 10, 15, 30] as const
const QUALITY_OPTIONS = [
  { value: 'low',    label: 'Baixa'  },
  { value: 'medium', label: 'Média'  },
  { value: 'high',   label: 'Alta'   },
] as const

// Eixo COLETA (frame de treino, migration 114) — independente do eixo
// OPERAÇÃO acima (FPS/qualidade do stream de inferência+live view). NUNCA
// fundir os dois num seletor só: são decisões de custo/qualidade diferentes.
const COLLECTION_OPTIONS = [
  { value: 0, label: 'Principal (máxima)'   },
  { value: 1, label: 'Substream (704×480)'  },
] as const

type FpsOption = typeof FPS_OPTIONS[number]
type QualityOption = 'low' | 'medium' | 'high'
type CollectionSubtypeOption = typeof COLLECTION_OPTIONS[number]['value']
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
  // Eixo COLETA — estado independente do FPS/qualidade acima (eixo OPERAÇÃO).
  // Default 0 (principal/alta): anotar em alta é melhor mesmo que o treino
  // rode em baixa (migration 114).
  const [collectionSubtype, setCollectionSubtype] = useState<CollectionSubtypeOption>(
    (camera.collection_subtype ?? 0) as CollectionSubtypeOption
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
      const patch: CameraConfigPatch = {
        fps_target: fps,
        quality_preset: quality,
      }
      // collection_subtype é parcial de verdade: só entra no payload quando
      // muda — eixo COLETA independente do eixo OPERAÇÃO acima.
      if (collectionSubtype !== ((camera.collection_subtype ?? 0) as CollectionSubtypeOption)) {
        patch.collection_subtype = collectionSubtype
      }
      const updated = await cameraService.patchConfig(camera.id, patch)
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

  const collectionChanged =
    collectionSubtype !== ((camera.collection_subtype ?? 0) as CollectionSubtypeOption)

  const changed =
    fps !== ((camera.fps_target ?? 5) as FpsOption) ||
    quality !== ((camera.quality_preset ?? 'medium') as QualityOption) ||
    collectionChanged

  // Alerta de desalinhamento: coleta em alta (0) mas operação (live view) no
  // substream — modelo treina num mundo mais nítido do que o real. Lê o
  // ESTADO LOCAL (seleção atual do usuário, ainda não salva) contra o valor
  // do servidor para live_view_subtype (não editável aqui). Fallback ?? 1:
  // mesmo default do backend (migration 092, DEFAULT 1 = substream).
  const collectionOperationMismatch =
    collectionSubtype === 0 && (camera.live_view_subtype ?? 1) !== 0

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

  const optionButtonClass = (selected: boolean): string =>
    selected ? s.optionBtnActive : s.optionBtn

  const metrics = ctx?.metrics

  return (
    <div className={s.container}>
      <div className={s.title}>
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
        <div className={s.sectionLabel}>
          FPS de inferência
        </div>
        <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
          {FPS_OPTIONS.map(f => {
            const btn = (
              <button
                onClick={() => canEdit && setFps(f)}
                disabled={!canEdit}
                aria-label={`${f} fps`}
                className={optionButtonClass(fps === f)}
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
        <div className={s.sectionLabel}>
          Qualidade do stream
        </div>
        <div style={{ display: 'flex', gap: 5 }}>
          {QUALITY_OPTIONS.map(q => {
            const btn = (
              <button
                onClick={() => canEdit && setQuality(q.value)}
                disabled={!canEdit}
                className={optionButtonClass(quality === q.value)}
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

      {/* Coleta (eixo independente de OPERAÇÃO/FPS/qualidade acima) */}
      <div>
        <div className={s.sectionLabel}>
          Qualidade da coleta (dado de treino)
        </div>
        <div style={{ display: 'flex', gap: 5 }}>
          {COLLECTION_OPTIONS.map(opt => {
            const btn = (
              <button
                onClick={() => canEdit && setCollectionSubtype(opt.value)}
                disabled={!canEdit}
                className={optionButtonClass(collectionSubtype === opt.value)}
              >
                {opt.label}
              </button>
            )
            if (canEdit) return <span key={opt.value}>{btn}</span>
            return (
              <Tooltip key={opt.value} label="Sem permissão para alterar">
                <span style={{ display: 'inline-flex' }}>{btn}</span>
              </Tooltip>
            )
          })}
        </div>
        <div style={{ fontSize: 10, color: vars.color.textMuted, marginTop: 5 }}>
          Coleta é foto (~17/dia por câmera) — custo ~zero. Padrão: o mais alto disponível.
        </div>
        {collectionOperationMismatch && (
          <div role="status" className={s.warningBox}>
            <AlertTriangle size={13} style={{ color: vars.color.warning, flexShrink: 0, marginTop: 1 }} />
            <span>
              Coleta em alta, operação em baixa: o modelo treina num mundo mais nítido do que
              aquele em que vai trabalhar. Ao treinar, use augmentation que simule a entrada real
              (downscale, blur, compressão). Anotar em alta continua certo: caixa precisa em
              1080p continua precisa depois de reduzir — caixa imprecisa em 480p é imprecisa
              para sempre.
            </span>
          </div>
        )}
      </div>

      {/* Health-aware panel */}
      <div className={s.healthBox} style={{ borderLeft: `3px solid ${color}` }}>
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
            className={s.refreshBtn}
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
          <span style={{ fontSize: 11, color: vars.color.textMuted }}>
            Sem alterações
          </span>
        )}
      </div>
    </div>
  )
}
