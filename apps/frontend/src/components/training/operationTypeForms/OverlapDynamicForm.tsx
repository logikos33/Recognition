/**
 * Formulário de configuração para OverlapDynamicOperation.
 */

interface OverlapDynamicFormProps {
  config: Record<string, unknown>
  onChange: (config: Record<string, unknown>) => void
  availableClasses?: string[]
}

export function OverlapDynamicForm({
  config,
  onChange,
  availableClasses = ['person', 'vehicle', 'forklift', 'helmet', 'vest', 'pallet'],
}: OverlapDynamicFormProps) {
  const set = (key: string, value: unknown) => onChange({ ...config, [key]: value })

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div>
          <label style={{ display: 'block', marginBottom: 4, fontSize: 13, fontWeight: 500 }}>Classe A *</label>
          <select
            value={(config.class_a as string) ?? ''}
            onChange={e => set('class_a', e.target.value)}
            style={{ width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid #333', background: '#1a1a1a', color: '#fff' }}
          >
            <option value="">Selecione</option>
            {availableClasses.map(cls => (
              <option key={cls} value={cls}>{cls}</option>
            ))}
          </select>
        </div>
        <div>
          <label style={{ display: 'block', marginBottom: 4, fontSize: 13, fontWeight: 500 }}>Classe B *</label>
          <select
            value={(config.class_b as string) ?? ''}
            onChange={e => set('class_b', e.target.value)}
            style={{ width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid #333', background: '#1a1a1a', color: '#fff' }}
          >
            <option value="">Selecione</option>
            {availableClasses.map(cls => (
              <option key={cls} value={cls}>{cls}</option>
            ))}
          </select>
        </div>
      </div>

      <div>
        <label style={{ display: 'block', marginBottom: 4, fontSize: 13, fontWeight: 500 }}>Métrica</label>
        <select
          value={(config.metric as string) ?? 'iou_percent'}
          onChange={e => set('metric', e.target.value)}
          style={{ width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid #333', background: '#1a1a1a', color: '#fff' }}
        >
          <option value="iou_percent">Sobreposição IoU (%)</option>
          <option value="min_distance">Distância mínima</option>
          <option value="overlap_time_seconds">Tempo de sobreposição (s)</option>
        </select>
      </div>

      <div>
        <label style={{ display: 'block', marginBottom: 4, fontSize: 13, fontWeight: 500 }}>
          Threshold IoU: {(config.iou_threshold as number) ?? 10}%
        </label>
        <input
          type="range"
          min={1}
          max={80}
          step={1}
          value={(config.iou_threshold as number) ?? 10}
          onChange={e => set('iou_threshold', Number(e.target.value))}
          style={{ width: '100%' }}
        />
      </div>
    </div>
  )
}
