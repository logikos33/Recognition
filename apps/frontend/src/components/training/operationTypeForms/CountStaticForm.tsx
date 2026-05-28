/**
 * Formulário de configuração para CountStaticOperation.
 */
import type { RoiPoint } from '../../../types/operations'

interface CountStaticFormProps {
  config: Record<string, unknown>
  onChange: (config: Record<string, unknown>) => void
  targetClasses?: string[]
  roiPoints?: RoiPoint[]
}

export function CountStaticForm({
  config,
  onChange,
  targetClasses = ['person', 'vehicle', 'pallet', 'product', 'helmet'],
  roiPoints = [],
}: CountStaticFormProps) {
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
          value={(config.metric as string) ?? 'count'}
          onChange={e => set('metric', e.target.value)}
          style={{ width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid #333', background: '#1a1a1a', color: '#fff' }}
        >
          <option value="count">Contagem absoluta</option>
          <option value="boolean_above">Booleano (acima do threshold)</option>
          <option value="boolean_below">Booleano (abaixo do threshold)</option>
        </select>
      </div>

      <div>
        <label style={{ display: 'block', marginBottom: 4, fontSize: 13, fontWeight: 500 }}>
          Threshold de contagem: {(config.count_threshold as number) ?? 1}
        </label>
        <input
          type="number"
          min={0}
          max={100}
          value={(config.count_threshold as number) ?? 1}
          onChange={e => set('count_threshold', Number(e.target.value))}
          style={{ width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid #333', background: '#1a1a1a', color: '#fff' }}
        />
      </div>
    </div>
  )
}
