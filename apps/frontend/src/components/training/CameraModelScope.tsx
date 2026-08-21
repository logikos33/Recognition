/**
 * CameraModelScope — aba "Modelos por câmera" (Treinamento).
 *
 * Por câmera: qual modelo treinado responde e quais classes dele valem
 * (escopo). Contrato REUSADO sem rota nova (WS-C2, migration 100):
 *   GET  /api/cameras/<id>/model-config?module=<m>  → deployment ativo (ou
 *        null = sem deployment) — 1 chamada por câmera ativa ao abrir a aba;
 *        é a FONTE DE VERDADE do que está gravado.
 *   POST /api/cameras/<id>/model-config             → novo deployment
 *        {model_id, module_code:<m>, config:{classes:[...], roi?, line?, thresholds?}}
 * `<m>` = `camera.active_module` (fallback 'epi') — o MESMO módulo pelo qual
 * o resolver do worker (tasks/inference.py::_resolve_camera_model) lê o
 * deployment; mandar 'epi' fixo pra câmera `quality` criaria deployment que
 * ninguém lê. Os modelos oferecidos são os do módulo da câmera.
 * O escopo É `config.classes` (validator exige ≥1 — "nenhuma classe" não é
 * representável). Não há rota de desativar deployment: câmera SEM deployment
 * cai no detector padrão do ambiente (DETECTOR_BACKEND/DETECTOR_MODEL_PATH do
 * worker), não num "ativo do módulo". Lista de modelos vem de GET
 * /api/v1/models (só os com artefato ONNX) e as classes de cada modelo de
 * GET /api/v1/models/<id> → lineage.dataset_version.class_distribution (o que
 * o detector de fato emite — menos as listadas em `__sem_suporte_treino__`).
 *
 * Gate: `training:approve` (hoje só superadmin) — sem ele, somente leitura.
 *
 * Honestidade: o escopo gravado aqui é lido pelo resolver do worker cloud
 * (model_deployments vence cameras.model_epi_id); o box edge RVB ainda NÃO
 * consome modelo/classes por câmera (poll_edge_config não envia).
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../../services/api'
import { cameraService } from '../../services/cameraService'
import { useToast } from '../ui/Toast/useToast'
import { useAuth } from '../../hooks/useAuth'
import { Badge } from '../ui/Badge/Badge'
import { Button } from '../ui/Button/Button'
import type { Camera, YoloClass } from '../../types'
import { vars } from '../../styles/theme.css'

export interface DeploymentConfig {
  classes?: string[]
  roi?: unknown
  line?: unknown
  thresholds?: Record<string, number>
}

export interface ModelDeployment {
  id: string
  model_id: string
  camera_id: string
  module_code: string
  config: DeploymentConfig | null
  status: string
  created_at: string
}

export interface RegistryModel {
  id: string
  name: string | null
  framework?: string | null
  r2_onnx_key?: string | null
  is_active: boolean
  module_code?: string | null
  created_at?: string
}

interface Envelope<T> { success: boolean; message?: string; data?: T }

interface ModelDetail {
  model: RegistryModel
  lineage: { dataset_version: { class_distribution?: Record<string, unknown> } | null }
}

interface Draft { modelId: string; classes: string[] }

const MODULO_PADRAO = 'epi'
const FRAMEWORK_LABELS: Record<string, string> = { yolox: 'YOLOX', rfdetr: 'RF-DETR' }

const SEM_SUPORTE = '__sem_suporte_treino__'

/** Nomes de classe que o modelo DE FATO prevê, a partir de class_distribution:
 * ignora chaves reservadas `__*` E subtrai as listadas em
 * `__sem_suporte_treino__` (contadas na distribuição mas excluídas do treino —
 * versioning_v2.py). Fallback = catálogo. */
export function classesDoModelo(
  dist: Record<string, unknown> | null | undefined,
  fallback: string[],
): string[] {
  const raw = dist?.[SEM_SUPORTE]
  const semSuporte = new Set(Array.isArray(raw) ? raw.filter((x): x is string => typeof x === 'string') : [])
  const names = Object.keys(dist ?? {}).filter(k => !k.startsWith('__') && !semSuporte.has(k))
  return names.length ? names : fallback
}

/** Módulo pelo qual o worker resolve o deployment desta câmera. */
export function moduloDaCamera(cam: Pick<Camera, 'active_module'>): string {
  return cam.active_module?.trim() || MODULO_PADRAO
}

/** Config a enviar: espalha a existente (roi/line preservados), troca
 * `classes` e poda `thresholds` pra ⊆ classes (validator rejeita fora). */
export function montarConfig(base: DeploymentConfig | null | undefined, classes: string[]): DeploymentConfig {
  const config: DeploymentConfig = { ...(base ?? {}), classes }
  if (base?.thresholds) {
    config.thresholds = Object.fromEntries(
      Object.entries(base.thresholds).filter(([k]) => classes.includes(k)),
    )
  }
  return config
}

function mesmoConjunto(a: string[], b: string[]): boolean {
  return a.length === b.length && a.every(x => b.includes(x))
}

function draftDoDeployment(dep: ModelDeployment | undefined, todas: string[]): Draft {
  if (!dep) return { modelId: '', classes: [] }
  return { modelId: dep.model_id, classes: dep.config?.classes ?? todas }
}

export function CameraModelScope({ classesCatalogo }: { classesCatalogo: YoloClass[] }) {
  const toast = useToast()
  const { can } = useAuth()
  const podeEditar = can('training:approve')

  const [loading, setLoading] = useState(true)
  const [cameras, setCameras] = useState<Camera[]>([])
  const [models, setModels] = useState<RegistryModel[]>([])
  const [classesByModel, setClassesByModel] = useState<Record<string, string[]>>({})
  const [deploymentByCamera, setDeploymentByCamera] = useState<Record<string, ModelDeployment>>({})
  const [drafts, setDrafts] = useState<Record<string, Draft>>({})
  const [saving, setSaving] = useState<string | null>(null)

  const fallback = useMemo(() => classesCatalogo.map(c => c.name), [classesCatalogo])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [cams, modelsRes] = await Promise.all([
        cameraService.list(),
        api.get<Envelope<{ models: RegistryModel[] }>>('/v1/models'),
      ])
      const comArtefato = (modelsRes.data?.models ?? []).filter(m => !!m.r2_onnx_key)
      const ativas = cams.filter(c => c.is_active)
      // ponytail: 1 GET por modelo com ONNX (hoje ≤3) + 1 GET por câmera ativa
      // (≤28); se doer, criar GET /api/cameras/model-config (lista do tenant).
      const [details, deployments] = await Promise.all([
        Promise.allSettled(comArtefato.map(m => api.get<Envelope<ModelDetail>>(`/v1/models/${m.id}`))),
        Promise.all(ativas.map(c =>
          api.get<Envelope<{ deployment: ModelDeployment | null }>>(
            `/cameras/${c.id}/model-config?module=${encodeURIComponent(moduloDaCamera(c))}`,
          ),
        )),
      ])
      const porModelo: Record<string, string[]> = {}
      details.forEach((r, i) => {
        const d = r.status === 'fulfilled' ? r.value.data : undefined
        porModelo[comArtefato[i].id] = classesDoModelo(d?.lineage?.dataset_version?.class_distribution, fallback)
      })
      const porCamera: Record<string, ModelDeployment> = {}
      deployments.forEach((r, i) => {
        const dep = r.data?.deployment
        if (dep) porCamera[ativas[i].id] = dep
      })
      const novos: Record<string, Draft> = {}
      for (const c of ativas) {
        const dep = porCamera[c.id]
        novos[c.id] = draftDoDeployment(dep, dep ? porModelo[dep.model_id] ?? fallback : [])
      }
      setCameras(ativas)
      setModels(comArtefato)
      setClassesByModel(porModelo)
      setDeploymentByCamera(porCamera)
      setDrafts(novos)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao carregar modelos por câmera')
    } finally {
      setLoading(false)
    }
  }, [toast, fallback])

  useEffect(() => { load() }, [load])

  const setDraft = (camId: string, patch: Partial<Draft>) =>
    setDrafts(prev => ({ ...prev, [camId]: { ...prev[camId], ...patch } }))

  const salvar = async (cam: Camera) => {
    const draft = drafts[cam.id]
    if (!podeEditar || !draft?.modelId || draft.classes.length === 0) return
    const dep = deploymentByCamera[cam.id]
    setSaving(cam.id)
    try {
      const res = await api.post<Envelope<{ deployment: ModelDeployment }>>(
        `/cameras/${cam.id}/model-config`,
        { model_id: draft.modelId, module_code: moduloDaCamera(cam), config: montarConfig(dep?.config, draft.classes) },
      )
      const novo = res.data?.deployment
      if (novo) {
        setDeploymentByCamera(prev => ({ ...prev, [cam.id]: novo }))
        setDraft(cam.id, draftDoDeployment(novo, classesByModel[novo.model_id] ?? fallback))
      }
      toast.success(`Modelo e escopo salvos para ${cam.name}`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao salvar')
    } finally {
      setSaving(null)
    }
  }

  const cell: React.CSSProperties = {
    padding: '8px 10px', borderBottom: `1px solid ${vars.color.borderDefault}`,
    verticalAlign: 'top', fontSize: 13, color: vars.color.textPrimary,
  }
  const th: React.CSSProperties = {
    ...cell, fontSize: 11, fontWeight: 600, textTransform: 'uppercase',
    letterSpacing: '0.05em', color: vars.color.textMuted, textAlign: 'left',
  }
  const selectStyle: React.CSSProperties = {
    background: vars.color.bgSurface, border: `1px solid ${vars.color.borderStrong}`,
    borderRadius: 6, color: vars.color.textPrimary, padding: '6px 10px', fontSize: 13,
    minWidth: 220, cursor: podeEditar ? 'pointer' : 'default',
  }

  if (loading) {
    return <p style={{ margin: 0, fontSize: 12, color: vars.color.textMuted }}>Carregando modelos por câmera...</p>
  }

  return (
    <div style={{ background: vars.color.bgElevated, borderRadius: 8, overflowX: 'auto' }}>
      <div style={{ padding: '10px 12px', fontSize: 12, color: vars.color.textMuted, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <span>Modelo + classes que valem em cada câmera (escopo). Sem deployment = detector padrão do ambiente (não há como desativar por aqui — só trocar).</span>
        {!podeEditar && <span style={{ color: vars.color.warning }}>(somente leitura — requer permissão de aprovação)</span>}
        {models.length === 0 && <span style={{ color: vars.color.warning }}>Nenhum modelo com artefato ONNX no tenant.</span>}
      </div>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th style={th}>Câmera</th>
            <th style={th}>Modelo</th>
            <th style={th}>Classes no escopo</th>
            <th style={th}>Último deploy</th>
            <th style={th} />
          </tr>
        </thead>
        <tbody>
          {cameras.map(cam => {
            const draft = drafts[cam.id] ?? { modelId: '', classes: [] }
            const dep = deploymentByCamera[cam.id]
            const modulo = moduloDaCamera(cam)
            const modelosDoModulo = models.filter(m => (m.module_code || MODULO_PADRAO) === modulo)
            const model = models.find(m => m.id === draft.modelId)
            const todas = draft.modelId ? classesByModel[draft.modelId] ?? fallback : []
            const base = draftDoDeployment(dep, dep ? classesByModel[dep.model_id] ?? fallback : [])
            const mudou = draft.modelId !== base.modelId || !mesmoConjunto(draft.classes, base.classes)
            const podeSalvar = podeEditar && saving !== cam.id && mudou && !!draft.modelId && draft.classes.length > 0
            const framework = model?.framework ? FRAMEWORK_LABELS[model.framework] ?? model.framework : null
            return (
              <tr key={cam.id}>
                <td style={cell}>{cam.name}</td>
                <td style={cell}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <select
                      aria-label={`Modelo da câmera ${cam.name}`}
                      value={draft.modelId}
                      disabled={!podeEditar || saving === cam.id}
                      style={selectStyle}
                      onChange={e => {
                        const id = e.target.value
                        setDraft(cam.id, { modelId: id, classes: id ? [...(classesByModel[id] ?? fallback)] : [] })
                      }}
                    >
                      {/* Sem rota de desativar: com deployment gravado, "sem" não é escolha válida. */}
                      <option value="" disabled={!!dep}>— sem deployment (detector padrão do ambiente)</option>
                      {modelosDoModulo.map(m => (
                        <option key={m.id} value={m.id}>{m.name || `Modelo ${m.id.slice(0, 8)}`}</option>
                      ))}
                    </select>
                    {modulo !== MODULO_PADRAO && <Badge variant="neutral">{modulo}</Badge>}
                    {framework && <Badge variant="accent">{framework}</Badge>}
                  </div>
                </td>
                <td style={cell}>
                  {draft.modelId ? (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 12px' }}>
                      {todas.map(cls => {
                        const marcada = draft.classes.includes(cls)
                        return (
                          <label key={cls} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, cursor: podeEditar ? 'pointer' : 'default' }}>
                            <input
                              type="checkbox"
                              aria-label={`Classe ${cls} em ${cam.name}`}
                              checked={marcada}
                              disabled={!podeEditar || saving === cam.id}
                              onChange={() => setDraft(cam.id, {
                                classes: marcada ? draft.classes.filter(c => c !== cls) : [...draft.classes, cls],
                              })}
                            />
                            {cls}
                          </label>
                        )
                      })}
                      {draft.classes.length === 0 && (
                        <span style={{ fontSize: 11, color: vars.color.warning }}>marque ≥1 classe</span>
                      )}
                    </div>
                  ) : (
                    <span style={{ color: vars.color.textMuted }}>—</span>
                  )}
                </td>
                <td style={{ ...cell, color: vars.color.textMuted, whiteSpace: 'nowrap' }}>
                  {dep ? new Date(dep.created_at).toLocaleString('pt-BR') : '—'}
                </td>
                <td style={cell}>
                  <Button
                    size="sm"
                    variant="primary"
                    aria-label={`Salvar escopo de ${cam.name}`}
                    disabled={!podeSalvar}
                    loading={saving === cam.id}
                    onClick={() => salvar(cam)}
                  >
                    Salvar
                  </Button>
                </td>
              </tr>
            )
          })}
          {cameras.length === 0 && (
            <tr><td style={cell} colSpan={5}>Nenhuma câmera ativa no tenant.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
