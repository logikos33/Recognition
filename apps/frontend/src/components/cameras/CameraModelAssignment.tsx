/**
 * CameraModelAssignment — atribuição de modelo YOLO por módulo da câmera (Task 045).
 *
 * Consome GET/PUT /api/cameras/<id>/models:
 *   - 3 selects (EPI / Qualidade / Contagem) populados com modelos treinados
 *     do tenant (GET /training/models)
 *   - Seleção vazia = modelo padrão do serviço (model_id null remove atribuição)
 */
import { useState, useEffect, useCallback } from 'react'
import { Cpu } from 'lucide-react'
import { countingService } from '../../services/countingService'
import { trainingService } from '../../services/trainingService'
import { useToast } from '../ui/Toast/useToast'
import type { CameraModelAssignment as ModelAssignment } from '../../types/counting'

const MODULES = [
  { key: 'epi', label: 'EPI' },
  { key: 'quality', label: 'Qualidade' },
  { key: 'counting', label: 'Contagem' },
] as const

type ModuleKey = (typeof MODULES)[number]['key']

interface ModelOption {
  id: string
  name?: string
  map50?: number | null
}

const EMPTY_ASSIGNMENT: ModelAssignment = { epi: null, quality: null, counting: null }

function modelLabel(m: ModelOption): string {
  const name = m.name || `Modelo ${m.id.slice(0, 8)}`
  return m.map50 != null ? `${name} (mAP50 ${(m.map50 * 100).toFixed(0)}%)` : name
}

export function CameraModelAssignment({ cameraId }: { cameraId: string }) {
  const toast = useToast()
  const [assignment, setAssignment] = useState<ModelAssignment>(EMPTY_ASSIGNMENT)
  const [models, setModels] = useState<ModelOption[]>([])
  const [loading, setLoading] = useState(true)
  const [savingModule, setSavingModule] = useState<ModuleKey | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [assignRes, modelsRes] = await Promise.all([
        countingService.getCameraModels(cameraId),
        trainingService.listModels(),
      ])
      setAssignment(assignRes?.data?.models ?? EMPTY_ASSIGNMENT)
      const raw: unknown = modelsRes?.data
      const list = Array.isArray(raw)
        ? raw
        : ((raw as { models?: unknown[] } | undefined)?.models ?? [])
      setModels(list.filter((m): m is ModelOption =>
        typeof m === 'object' && m !== null && typeof (m as ModelOption).id === 'string',
      ))
    } catch {
      // Câmera sem suporte a atribuição / erro de rede — mantém estado vazio
      setAssignment(EMPTY_ASSIGNMENT)
    } finally {
      setLoading(false)
    }
  }, [cameraId])

  useEffect(() => { load() }, [load])

  const handleChange = async (module: ModuleKey, modelId: string) => {
    const previous = assignment
    setSavingModule(module)
    setAssignment(prev => ({ ...prev, [module]: modelId || null }))
    try {
      const res = await countingService.setCameraModel(cameraId, module, modelId || null)
      if (res?.data?.models) setAssignment(res.data.models)
      toast.success(modelId ? 'Modelo atribuído à câmera' : 'Atribuição de modelo removida')
    } catch (err) {
      setAssignment(previous)
      toast.error(err instanceof Error ? err.message : 'Erro ao atribuir modelo')
    } finally {
      setSavingModule(null)
    }
  }

  const labelStyle: React.CSSProperties = {
    fontSize: 11, fontWeight: 600, color: '#64748b',
    textTransform: 'uppercase', letterSpacing: '0.05em',
  }

  const selectStyle: React.CSSProperties = {
    background: '#1e293b', border: '1px solid #334155', borderRadius: 6,
    color: '#f1f5f9', padding: '6px 10px', fontSize: 13, outline: 'none',
    width: '100%', cursor: 'pointer',
  }

  return (
    <div>
      <h4 style={{
        margin: '0 0 10px', fontSize: 13, fontWeight: 600, color: '#94a3b8',
        display: 'flex', alignItems: 'center', gap: 6,
      }}>
        <Cpu size={14} /> Modelos de IA por módulo
      </h4>
      {loading ? (
        <p style={{ margin: 0, fontSize: 12, color: '#475569' }}>Carregando modelos...</p>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
          {MODULES.map(({ key, label }) => (
            <div key={key} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <span style={labelStyle}>
                {label}{savingModule === key ? ' — salvando...' : ''}
              </span>
              <select
                value={assignment[key] ?? ''}
                onChange={e => handleChange(key, e.target.value)}
                disabled={savingModule !== null}
                style={{ ...selectStyle, opacity: savingModule !== null ? 0.6 : 1 }}
                aria-label={`Modelo do módulo ${label}`}
              >
                <option value="">Modelo padrão</option>
                {models.map(m => (
                  <option key={m.id} value={m.id}>{modelLabel(m)}</option>
                ))}
              </select>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
