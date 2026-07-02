/**
 * CameraFpsConfig — seletor de FPS alvo e qualidade por câmera.
 *
 * Exibe aviso health-aware: estimativa de carga do worker com base no
 * número de câmeras ativas e o FPS selecionado.
 * Fórmula: load% = fps * n_cameras * 0.02 (estimativa simples).
 */
import { useState } from 'react'
import { Zap } from 'lucide-react'
import { Button } from '../ui/Button/Button'
import { cameraService } from '../../services/cameraService'
import type { Camera } from '../../types'
import { vars } from '../../styles/theme.css'

const FPS_OPTIONS = [1, 5, 10, 15, 30] as const
const QUALITY_OPTIONS = [
  { value: 'low',    label: 'Baixa'  },
  { value: 'medium', label: 'Média'  },
  { value: 'high',   label: 'Alta'   },
] as const

type FpsOption = typeof FPS_OPTIONS[number]
type QualityOption = 'low' | 'medium' | 'high'

interface Props {
  camera: Camera
  totalActiveCameras: number
  onSaved: (updated: Camera) => void
}

function estimateLoad(fps: number, nCameras: number): number {
  return Math.min(100, Math.round(fps * nCameras * 2))
}

function loadColor(pct: number): string {
  if (pct >= 80) return '#ef4444'
  if (pct >= 50) return '#f59e0b'
  return vars.color.success
}

export function CameraFpsConfig({ camera, totalActiveCameras, onSaved }: Props) {
  const [fps, setFps] = useState<FpsOption>(
    (camera.fps_target ?? 5) as FpsOption
  )
  const [quality, setQuality] = useState<QualityOption>(
    (camera.quality_preset ?? 'medium') as QualityOption
  )
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const load = estimateLoad(fps, totalActiveCameras)
  const color = loadColor(load)

  async function handleSave() {
    setSaving(true)
    setErr(null)
    try {
      const updated = await cameraService.patchConfig(camera.id, fps, quality)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
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

  return (
    <div style={{
      background: 'rgba(255,255,255,0.04)',
      border: '1px solid rgba(255,255,255,0.08)',
      borderRadius: 8,
      padding: '12px 14px',
      display: 'flex',
      flexDirection: 'column',
      gap: 10,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600, fontSize: 13 }}>
        <Zap size={14} style={{ color: vars.color.primaryLight }} />
        Desempenho por câmera
      </div>

      {/* FPS selector */}
      <div>
        <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.5)', marginBottom: 5 }}>
          FPS de inferência
        </div>
        <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
          {FPS_OPTIONS.map(f => (
            <button
              key={f}
              onClick={() => setFps(f)}
              style={{
                padding: '4px 10px',
                borderRadius: 5,
                border: fps === f
                  ? `1px solid ${vars.color.primaryLight}`
                  : '1px solid rgba(255,255,255,0.12)',
                background: fps === f ? 'rgba(167,139,250,0.18)' : 'transparent',
                color: fps === f ? '#c4b5fd' : 'rgba(255,255,255,0.6)',
                cursor: 'pointer',
                fontSize: 12,
                fontWeight: fps === f ? 600 : 400,
              }}
            >
              {f} fps
            </button>
          ))}
        </div>
      </div>

      {/* Quality selector */}
      <div>
        <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.5)', marginBottom: 5 }}>
          Qualidade do stream
        </div>
        <div style={{ display: 'flex', gap: 5 }}>
          {QUALITY_OPTIONS.map(q => (
            <button
              key={q.value}
              onClick={() => setQuality(q.value)}
              style={{
                padding: '4px 10px',
                borderRadius: 5,
                border: quality === q.value
                  ? `1px solid ${vars.color.primaryLight}`
                  : '1px solid rgba(255,255,255,0.12)',
                background: quality === q.value ? 'rgba(167,139,250,0.18)' : 'transparent',
                color: quality === q.value ? '#c4b5fd' : 'rgba(255,255,255,0.6)',
                cursor: 'pointer',
                fontSize: 12,
                fontWeight: quality === q.value ? 600 : 400,
              }}
            >
              {q.label}
            </button>
          ))}
        </div>
      </div>

      {/* Health-aware warning */}
      <div style={{
        background: 'rgba(0,0,0,0.2)',
        borderRadius: 6,
        padding: '7px 10px',
        fontSize: 11,
        color: 'rgba(255,255,255,0.65)',
        borderLeft: `3px solid ${color}`,
      }}>
        <span style={{ color, fontWeight: 600 }}>{load}% de carga estimada</span>
        {' '}no worker com {totalActiveCameras} câmera{totalActiveCameras !== 1 ? 's' : ''} a {fps} fps.
        {load >= 80 && (
          <span style={{ color: '#ef4444', display: 'block', marginTop: 3 }}>
            Carga alta — considere reduzir o FPS ou o numero de cameras ativas.
          </span>
        )}
        {load >= 50 && load < 80 && (
          <span style={{ color: '#f59e0b', display: 'block', marginTop: 3 }}>
            Carga moderada — fique de olho na performance do worker.
          </span>
        )}
      </div>

      {/* Error */}
      {err && (
        <div style={{ fontSize: 11, color: '#ef4444' }}>{err}</div>
      )}

      {/* Save button */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Button
          size="sm"
          variant="primary"
          onClick={handleSave}
          disabled={saving || !changed}
        >
          {saving ? 'Salvando...' : saved ? 'Salvo!' : 'Salvar configuração'}
        </Button>
        {!changed && (
          <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.35)' }}>
            Sem alterações
          </span>
        )}
      </div>
    </div>
  )
}
