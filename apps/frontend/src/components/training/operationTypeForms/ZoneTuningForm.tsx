/**
 * Formulário de configuração para EpiZoneOperation e DefectTriggerOperation (task-039).
 *
 * Diferente dos demais formulários desta pasta, estas operações não têm um
 * componente de desenho ativo dentro do modal (o mesmo já valia para roi_points
 * antes desta mudança — veja OperationEditModal: onRoiChange nunca era usado
 * nos outros forms). Por isso:
 *   - exclude_zones: lista somente-leitura com remoção individual (sem desenhar
 *     novas zonas aqui — use o Editor de Cenário, que tem canvas).
 *   - day_night_profile: totalmente editável (não depende de canvas).
 *   - Demais campos específicos do tipo (zone_points, watch_classes, roi_points,
 *     trigger_class, defect_classes, confidence_threshold) seguem editáveis via
 *     JSON avançado — evita regressão de capacidade em relação ao textarea cru
 *     que existia antes (default: do switch em OperationEditModal).
 */
import { useState } from 'react'
import {
  ExcludeZoneList,
  DayNightProfileInputs,
  excludeZonesFromConfig,
  excludeZonesToConfig,
  dayNightProfileFromConfig,
  clampConfidence,
} from '../../scenario/ZoneTuningControls'
import { vars } from '../../../styles/theme.css'

interface ZoneTuningFormProps {
  typeId: string
  config: Record<string, unknown>
  onChange: (config: Record<string, unknown>) => void
}

export function ZoneTuningForm({ typeId, config, onChange }: ZoneTuningFormProps) {
  const excludeZones = excludeZonesFromConfig(config.exclude_zones)
  const profile = dayNightProfileFromConfig(config.day_night_profile)
  const [jsonError, setJsonError] = useState<string | null>(null)

  const removeZone = (idx: number) => {
    const next = excludeZones.filter((_, i) => i !== idx)
    onChange({ ...config, exclude_zones: excludeZonesToConfig(next) })
  }

  const setDayNightEnabled = (enabled: boolean) => {
    if (!enabled) {
      const rest = { ...config }
      delete rest.day_night_profile
      onChange(rest)
      return
    }
    onChange({
      ...config,
      day_night_profile: { day: { confidence: 0.5 }, night: { confidence: 0.5 } },
    })
  }

  const setConfidence = (period: 'day' | 'night', value: number) => {
    const clamped = clampConfidence(value)
    const current = profile ?? { day: { confidence: 0.5 }, night: { confidence: 0.5 } }
    onChange({
      ...config,
      day_night_profile: {
        day: { confidence: period === 'day' ? clamped : current.day.confidence },
        night: { confidence: period === 'night' ? clamped : current.night.confidence },
      },
    })
  }

  // Campos avançados restantes (tudo exceto exclude_zones/day_night_profile,
  // já cobertos pelos controles estruturados acima).
  const { exclude_zones: _ez, day_night_profile: _dnp, ...restConfig } = config

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div
        style={{
          padding: '8px 10px', background: vars.color.bgSurface, borderRadius: 6,
          border: `1px solid ${vars.color.borderDefault}`, fontSize: 11, color: vars.color.textMuted,
        }}
      >
        Tipo <strong style={{ fontFamily: 'monospace' }}>{typeId}</strong>: os campos de geometria/classes
        (zone_points, watch_classes, roi_points, trigger_class, defect_classes, confidence_threshold)
        são editados no JSON avançado abaixo. Novas zonas de exclusão são desenhadas no Editor de Cenário.
      </div>

      <div>
        <label style={{ display: 'block', marginBottom: 4, fontSize: 13, fontWeight: 500 }}>
          Zonas de exclusão ({excludeZones.length})
        </label>
        <ExcludeZoneList
          zones={excludeZones}
          onRemove={removeZone}
          emptyHint="Nenhuma zona de exclusão. Desenhe no Editor de Cenário."
        />
      </div>

      <div>
        <label style={{ display: 'block', marginBottom: 4, fontSize: 13, fontWeight: 500 }}>
          Perfil dia/noite
        </label>
        <DayNightProfileInputs
          enabled={!!profile}
          day={profile?.day.confidence ?? 0.5}
          night={profile?.night.confidence ?? 0.5}
          onEnabledChange={setDayNightEnabled}
          onDayChange={v => setConfidence('day', v)}
          onNightChange={v => setConfidence('night', v)}
        />
      </div>

      <div>
        <label style={{ display: 'block', marginBottom: 4, fontSize: 13, fontWeight: 500 }}>
          Configuração avançada (JSON)
        </label>
        <textarea
          value={JSON.stringify(restConfig, null, 2)}
          onChange={e => {
            try {
              const parsed = JSON.parse(e.target.value)
              setJsonError(null)
              onChange({
                ...parsed,
                ...(config.exclude_zones !== undefined ? { exclude_zones: config.exclude_zones } : {}),
                ...(config.day_night_profile !== undefined ? { day_night_profile: config.day_night_profile } : {}),
              })
            } catch {
              setJsonError('JSON inválido — alterações não aplicadas')
            }
          }}
          rows={6}
          aria-label="Configuração avançada (JSON)"
          data-testid="zone-tuning-advanced-json"
          style={{
            width: '100%', background: vars.color.bgSurface, border: `1px solid ${vars.color.borderDefault}`,
            borderRadius: 6, color: vars.color.textPrimary, fontFamily: 'monospace', fontSize: 12, padding: 8,
            boxSizing: 'border-box',
          }}
        />
        {jsonError && (
          <div role="alert" style={{ fontSize: 11, color: vars.color.danger, marginTop: 4 }}>
            {jsonError}
          </div>
        )}
      </div>
    </div>
  )
}
