/**
 * Formulário de configuração para PositionOperation.
 * Renderiza campos baseados no config_schema do backend.
 * RoiDrawer é passado como prop (separação de responsabilidades).
 */
import type { RoiPoint } from '../../../types/operations'

interface PositionFormProps {
  config: Record<string, unknown>
  onChange: (config: Record<string, unknown>) => void
  targetClasses?: string[]
  roiPoints?: RoiPoint[]
  onRoiChange?: (points: RoiPoint[]) => void
}

export function PositionForm({
  config,
  onChange,
  targetClasses = ['person', 'vehicle', 'helmet', 'vest'],
  roiPoints = [],
  onRoiChange: _onRoiChange,
}: PositionFormProps) {
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
          style={{ width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid #333', background: '#1a1a1a', color: '#fff' }}
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
        <div style={{ padding: '8px 12px', background: '#111', borderRadius: 6, border: '1px solid #333', fontSize: 12, color: '#888' }}>
          {roiPoints.length < 3
            ? 'Desenhe o ROI no vídeo ao lado (mínimo 3 pontos)'
            : `Polígono com ${roiPoints.length} pontos definido`}
        </div>
      </div>

      <div>
        <label style={{ display: 'block', marginBottom: 4, fontSize: 13, fontWeight: 500 }}>Métrica</label>
        <select
          value={(config.metric as string) ?? 'state'}
          onChange={e => set('metric', e.target.value)}
          style={{ width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid #333', background: '#1a1a1a', color: '#fff' }}
        >
          <option value="state">Estado (dentro/fora)</option>
          <option value="coordinates">Coordenadas</option>
          <option value="both">Ambos</option>
        </select>
      </div>

      <div>
        <label style={{ display: 'block', marginBottom: 4, fontSize: 13, fontWeight: 500 }}>
          Confiança mínima: {Math.round(((config.confidence_threshold as number) ?? 0.5) * 100)}%
        </label>
        <input
          type="range"
          min={10}
          max={95}
          step={5}
          value={Math.round(((config.confidence_threshold as number) ?? 0.5) * 100)}
          onChange={e => set('confidence_threshold', Number(e.target.value) / 100)}
          style={{ width: '100%' }}
        />
      </div>
    </div>
  )
}
