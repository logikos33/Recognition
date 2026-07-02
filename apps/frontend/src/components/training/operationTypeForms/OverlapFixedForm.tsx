/**
 * Formulário de configuração para OverlapFixedOperation.
 */
import type { RoiPoint } from '../../../types/operations'
import { vars } from '../../../styles/theme.css'

interface OverlapFixedFormProps {
  config: Record<string, unknown>
  onChange: (config: Record<string, unknown>) => void
  targetClasses?: string[]
  roiPoints?: RoiPoint[]
}

export function OverlapFixedForm({
  config,
  onChange,
  targetClasses = ['person', 'vehicle', 'forklift', 'pallet'],
  roiPoints = [],
}: OverlapFixedFormProps) {
  const set = (key: string, value: unknown) => onChange({ ...config, [key]: value })

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <label style={{ display: 'block', marginBottom: 4, fontSize: 13, fontWeight: 500 }}>
          Classe monitorada *
        </label>
        <select
          value={(config.target_class as string) ?? ''}
          onChange={e => set('target_class', e.target.value)}
          style={{ width: '100%', padding: '8px 10px', borderRadius: 6, border: `1px solid ${vars.color.borderDefault}`, background: vars.color.bgCard, color: vars.color.textPrimary }}
        >
          <option value="">Selecione uma classe</option>
          {targetClasses.map(cls => (
            <option key={cls} value={cls}>{cls}</option>
          ))}
        </select>
      </div>

      <div>
        <label style={{ display: 'block', marginBottom: 4, fontSize: 13, fontWeight: 500 }}>
          ROI ({roiPoints.length} pontos) *
        </label>
        <div style={{ padding: '8px 12px', background: vars.color.bgSurface, borderRadius: 6, border: `1px solid ${vars.color.borderDefault}`, fontSize: 12, color: vars.color.textMuted }}>
          {roiPoints.length < 3
            ? 'Desenhe o ROI no vídeo ao lado (mínimo 3 pontos)'
            : `Polígono com ${roiPoints.length} pontos definido`}
        </div>
      </div>

      <div>
        <label style={{ display: 'block', marginBottom: 4, fontSize: 13, fontWeight: 500 }}>Métrica de saída</label>
        <select
          value={(config.metric as string) ?? 'time_seconds'}
          onChange={e => set('metric', e.target.value)}
          style={{ width: '100%', padding: '8px 10px', borderRadius: 6, border: `1px solid ${vars.color.borderDefault}`, background: vars.color.bgCard, color: vars.color.textPrimary }}
        >
          <option value="time_seconds">Tempo (segundos)</option>
          <option value="coverage_percent">Cobertura (%)</option>
          <option value="entry_exit_count">Entradas/Saídas</option>
        </select>
      </div>

      <div>
        <label style={{ display: 'block', marginBottom: 4, fontSize: 13, fontWeight: 500 }}>
          Threshold de tempo: {(config.threshold_seconds as number) ?? 5}s
        </label>
        <input
          type="range"
          min={1}
          max={60}
          step={1}
          value={(config.threshold_seconds as number) ?? 5}
          onChange={e => set('threshold_seconds', Number(e.target.value))}
          style={{ width: '100%' }}
        />
        <small style={{ color: vars.color.textMuted, fontSize: 11 }}>Tempo mínimo para condition_satisfied = true</small>
      </div>
    </div>
  )
}
