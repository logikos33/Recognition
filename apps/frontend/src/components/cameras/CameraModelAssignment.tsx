/**
 * CameraModelAssignment — atribuição de modelo YOLO por módulo da câmera (Task 045).
 *
 * Consome GET/PUT /api/cameras/<id>/models:
 *   - 3 selects (EPI / Qualidade / Contagem) populados com modelos treinados
 *     do tenant (GET /training/models)
 *   - Seleção vazia = modelo padrão do serviço (model_id null remove atribuição)
 *
 * Papéis: PUT /api/cameras/<id>/models é admin/superadmin only no backend
 * (fix de segurança — Task 045). operator/viewer veem os selects em modo
 * somente-leitura (mesmo padrão de CameraFpsConfig/HealthFooter — useAuth).
 *
 * Backend efetivo (task-083): a resolução por câmera de model_deployments →
 * cameras.model_{module}_id → trained_models.framework já existe no worker
 * (tasks/inference.py::_get_detector_for_camera, WS-A6) e aplica hot-reload
 * via camera:model_change — sem restart. O que faltava era a UI mostrar qual
 * arquitetura (RF-DETR/YOLOX) está efetivamente atribuída; o badge abaixo lê
 * `framework` do modelo selecionado (GET /training/models agora inclui essa
 * coluna — antes o payload não a carregava).
 */
import { useState, useEffect, useCallback } from 'react'
import { Cpu } from 'lucide-react'
import { countingService } from '../../services/countingService'
import { trainingService } from '../../services/trainingService'
import { nomeInternoOuCliente } from '../../services/modelDisplay'
import { metricaAusente } from '../../utils/labels'
import { useToast } from '../ui/Toast/useToast'
import { useAuth } from '../../hooks/useAuth'
import { Badge } from '../ui/Badge/Badge'
import type { CameraModelAssignment as ModelAssignment } from '../../types/counting'
import { vars } from '../../styles/theme.css'

const MODULES = [
  { key: 'epi', label: 'EPI' },
  { key: 'quality', label: 'Qualidade' },
  { key: 'counting', label: 'Contagem' },
] as const

type ModuleKey = (typeof MODULES)[number]['key']

interface ModelOption {
  id: string
  name?: string
  /** Nome voltado ao cliente (migration 129) — ver `nomeParaCliente`. */
  display_name?: string | null
  map50?: number | null
  /** trained_models.framework — "yolox" | "rfdetr" (task-083). */
  framework?: string | null
}

const EMPTY_ASSIGNMENT: ModelAssignment = { epi: null, quality: null, counting: null }

/** Rótulo de exibição do backend de detecção efetivo (task-083). */
const FRAMEWORK_LABELS: Record<string, string> = {
  yolox: 'YOLOX',
  rfdetr: 'RF-DETR',
}

function modelLabel(m: ModelOption, isSuperAdmin: boolean): string {
  const name = nomeInternoOuCliente(m, isSuperAdmin)
  // 0 é tratado como não registrada (LEI DA CASA) — nunca "(mAP50 0%)".
  return metricaAusente(m.map50) ? name : `${name} (mAP50 ${((m.map50 as number) * 100).toFixed(0)}%)`
}

export function CameraModelAssignment({ cameraId }: { cameraId: string }) {
  const toast = useToast()
  const { isAdmin, isSuperAdmin } = useAuth()
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
    if (!isAdmin) return // defesa em profundidade — selects já ficam disabled
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
    fontSize: 11, fontWeight: 600, color: vars.color.textMuted,
    textTransform: 'uppercase', letterSpacing: '0.05em',
  }

  const selectStyle: React.CSSProperties = {
    background: vars.color.bgSurface, border: `1px solid ${vars.color.borderStrong}`, borderRadius: 6,
    color: '#f1f5f9', padding: '6px 10px', fontSize: 13, outline: 'none',
    width: '100%', cursor: 'pointer',
  }

  return (
    <div>
      <h4 style={{
        margin: '0 0 10px', fontSize: 13, fontWeight: 600, color: vars.color.textSecondary,
        display: 'flex', alignItems: 'center', gap: 6,
      }}>
        <Cpu size={14} /> Modelos de IA por módulo
        {!isAdmin && (
          <span style={{ fontSize: 10, fontWeight: 400, color: vars.color.textMuted }}>
            (somente leitura)
          </span>
        )}
      </h4>
      {loading ? (
        <p style={{ margin: 0, fontSize: 12, color: vars.color.textMuted }}>Carregando modelos...</p>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
          {MODULES.map(({ key, label }) => {
            const assignedModel = models.find(m => m.id === assignment[key])
            const framework = assignedModel?.framework
              ? FRAMEWORK_LABELS[assignedModel.framework] ?? assignedModel.framework
              : null
            return (
              <div key={key} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <span style={{ ...labelStyle, display: 'flex', alignItems: 'center', gap: 6 }}>
                  {label}{savingModule === key ? ' — salvando...' : ''}
                  {/* framework (YOLOX/RF-DETR) é stack interno — SÓ superadmin. */}
                  {framework && isSuperAdmin && <Badge variant="accent">{framework}</Badge>}
                </span>
                <select
                  value={assignment[key] ?? ''}
                  onChange={e => handleChange(key, e.target.value)}
                  disabled={!isAdmin || savingModule !== null}
                  style={{ ...selectStyle, opacity: (!isAdmin || savingModule !== null) ? 0.6 : 1 }}
                  aria-label={`Modelo do módulo ${label}`}
                  title={!isAdmin ? 'Sem permissão para alterar' : undefined}
                >
                  <option value="">Modelo padrão</option>
                  {models.map(m => (
                    <option key={m.id} value={m.id}>{modelLabel(m, isSuperAdmin)}</option>
                  ))}
                </select>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
