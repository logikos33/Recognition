/**
 * ZoneTuningControls — campos compartilhados de "per-camera tuning" (task-039).
 *
 * Reusados pelo ScenarioEditor (editor visual, com canvas de desenho) e pelo
 * OperationEditModal (edição pós-criação, sem canvas — via training/operationTypeForms).
 *
 * Escopo: exclude_zones (lista de polígonos de exclusão) e day_night_profile
 * (confidence diferente por período). Válido apenas para operações do tipo
 * epi_zone e defect_trigger (únicos com suporte no backend — ver PR #73).
 *
 * Backend de referência (fonte da verdade dos nomes de campo):
 *   services/api/app/domain/services/operations/canonical/epi_zone.py
 *   services/api/app/domain/services/operations/canonical/defect_trigger.py
 */
import type { RoiPoint } from '../../types/operations'
import { vars } from '../../styles/theme.css'

export const CONFIDENCE_MIN = 0.1
export const CONFIDENCE_MAX = 1.0

/** Garante que o valor de confidence enviado ao backend está sempre em [0.1, 1.0]. */
export function clampConfidence(value: number): number {
  if (Number.isNaN(value)) return CONFIDENCE_MIN
  return Math.min(CONFIDENCE_MAX, Math.max(CONFIDENCE_MIN, value))
}

export function isZoneTuningTypeId(typeId: string | undefined | null): boolean {
  return typeId === 'epi_zone' || typeId === 'defect_trigger'
}

/** Converte polígonos RoiPoint[][] (frontend) para o formato [x,y][][] esperado pelo config. */
export function excludeZonesToConfig(zones: RoiPoint[][]): number[][][] {
  return zones
    .filter(zone => zone.length >= 3)
    .map(zone => zone.map(p => [p.x, p.y]))
}

/** Converte o formato de config ([x,y][][]) de volta para RoiPoint[][], tolerante a formatos inválidos. */
export function excludeZonesFromConfig(raw: unknown): RoiPoint[][] {
  if (!Array.isArray(raw)) return []
  const zones: RoiPoint[][] = []
  for (const zone of raw) {
    if (!Array.isArray(zone)) continue
    const pts: RoiPoint[] = []
    for (const p of zone) {
      if (Array.isArray(p) && p.length === 2 && typeof p[0] === 'number' && typeof p[1] === 'number') {
        pts.push({ x: p[0], y: p[1] })
      }
    }
    if (pts.length >= 3) zones.push(pts)
  }
  return zones
}

export interface DayNightProfileValue {
  day: { confidence: number }
  night: { confidence: number }
}

/** Lê day_night_profile de um config bruto, tolerante a formatos ausentes/inválidos. */
export function dayNightProfileFromConfig(raw: unknown): DayNightProfileValue | null {
  if (!raw || typeof raw !== 'object') return null
  const obj = raw as Record<string, unknown>
  const day = obj.day as Record<string, unknown> | undefined
  const night = obj.night as Record<string, unknown> | undefined
  const dayConf = day && typeof day.confidence === 'number' ? day.confidence : null
  const nightConf = night && typeof night.confidence === 'number' ? night.confidence : null
  if (dayConf === null || nightConf === null) return null
  return { day: { confidence: dayConf }, night: { confidence: nightConf } }
}

interface ExcludeZoneListProps {
  zones: RoiPoint[][]
  onRemove: (index: number) => void
  emptyHint?: string
}

/** Lista de zonas de exclusão já confirmadas, com remoção individual. Sem desenho (apenas leitura + remover). */
export function ExcludeZoneList({ zones, onRemove, emptyHint = 'Nenhuma zona de exclusão adicionada' }: ExcludeZoneListProps) {
  if (zones.length === 0) {
    return (
      <div style={{ padding: '4px 16px 6px', fontSize: 12, color: vars.color.textMuted }}>
        {emptyHint}
      </div>
    )
  }
  return (
    <div style={{ padding: '2px 16px 6px', display: 'flex', flexDirection: 'column', gap: 4 }}>
      {zones.map((zone, idx) => (
        <div
          key={idx}
          data-testid={`exclude-zone-item-${idx}`}
          style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '4px 8px', background: vars.color.bgSurface, borderRadius: 4,
            border: `1px solid ${vars.color.borderDefault}`,
          }}
        >
          <span style={{ fontSize: 12, color: vars.color.textSecondary }}>
            Zona {idx + 1} — {zone.length} pontos
          </span>
          <button
            type="button"
            onClick={() => onRemove(idx)}
            aria-label={`Remover zona de exclusão ${idx + 1}`}
            style={{
              background: 'transparent', border: 'none', cursor: 'pointer',
              color: vars.color.danger, fontSize: 13, lineHeight: 1, padding: 2,
            }}
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  )
}

interface DayNightProfileInputsProps {
  enabled: boolean
  day: number
  night: number
  onEnabledChange: (enabled: boolean) => void
  onDayChange: (value: number) => void
  onNightChange: (value: number) => void
}

/** Checkbox de ativação + dois campos numéricos de confidence (dia/noite). */
export function DayNightProfileInputs({
  enabled, day, night, onEnabledChange, onDayChange, onNightChange,
}: DayNightProfileInputsProps) {
  return (
    <div style={{ padding: '2px 16px 6px', display: 'flex', flexDirection: 'column', gap: 8 }}>
      <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: vars.color.textSecondary, cursor: 'pointer' }}>
        <input
          type="checkbox"
          checked={enabled}
          onChange={e => onEnabledChange(e.target.checked)}
          aria-label="Habilitar perfil dia/noite"
          data-testid="day-night-enabled-checkbox"
          style={{ accentColor: vars.color.primary }}
        />
        Usar confiança diferente por período (dia 6h-18h / noite 18h-6h)
      </label>
      {enabled && (
        <div style={{ display: 'flex', gap: 12 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <label htmlFor="day-night-confidence-day" style={{ fontSize: 11, color: vars.color.textMuted }}>
              Confiança (dia)
            </label>
            <input
              id="day-night-confidence-day"
              type="number"
              min={CONFIDENCE_MIN}
              max={CONFIDENCE_MAX}
              step={0.05}
              value={day}
              onChange={e => onDayChange(clampConfidence(Number(e.target.value)))}
              aria-label="Confiança de dia"
              data-testid="day-confidence-input"
              style={{ ...numberInputStyle }}
            />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <label htmlFor="day-night-confidence-night" style={{ fontSize: 11, color: vars.color.textMuted }}>
              Confiança (noite)
            </label>
            <input
              id="day-night-confidence-night"
              type="number"
              min={CONFIDENCE_MIN}
              max={CONFIDENCE_MAX}
              step={0.05}
              value={night}
              onChange={e => onNightChange(clampConfidence(Number(e.target.value)))}
              aria-label="Confiança de noite"
              data-testid="night-confidence-input"
              style={{ ...numberInputStyle }}
            />
          </div>
        </div>
      )}
    </div>
  )
}

const numberInputStyle: React.CSSProperties = {
  width: 80,
  padding: '6px 8px',
  background: vars.color.bgSurface,
  border: `1px solid ${vars.color.borderDefault}`,
  borderRadius: 6,
  color: vars.color.textOnPrimary,
  fontSize: 13,
  boxSizing: 'border-box',
}
