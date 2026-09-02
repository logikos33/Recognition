/**
 * Modelo — aba "Modelo" do Estúdio (`Estúdio.dc.html`, seção "Modelos").
 *
 * A ORQUESTRAÇÃO é a de `pages/TrainingPage.tsx`, aba "Modelo" (fonte da
 * paridade, lida função a função): lista de modelos treinados
 * (GET /training/models — envelope, `.data` já é o array), modelo ATIVO
 * destacado com mAP@50/precisão/recall, classes de detecção do tenant
 * (GET /classes), ativação via `POST /v1/models/<id>/activate` — NUNCA o
 * alias legado `/training/models/<id>/activate`, que ativa sem passar pelo
 * gate campeão×desafiante — e o `ModelScenarioWizard` (NÚCLEO COMPARTILHADO,
 * `components/scenario`, nunca editado daqui).
 *
 * 409 `eval_rejected`: o backend já devolve mensagem legível
 * (`registry_handlers.py` ativação, "Este modelo foi reprovado na avaliação
 * ...") e o toast global de `services/api.ts` a mostra sozinho — replicamos o
 * `if (status !== 409)` do antigo só para não duplicar o aviso.
 *
 * GRÁFICOS "acerto por classe" / "acerto por câmera" da prancha: NÃO
 * construídos aqui.
 *  · por classe — o dado existe (`GET /v1/models/<id>/eval` →
 *    `evaluation.metrics.per_class[classe] = {ap, precision, recall, ...}`,
 *    calculado em `services/api/app/domain/services/eval_metrics.py:157-186`
 *    e persistido por `infrastructure/queue/tasks/model_evaluation.py`) mas
 *    não está "pronto" no sentido do brief: é 1 avaliação POR MODELO, 404 se
 *    o modelo nunca rodou uma (`registry_handlers.py:356-359`), e puxar isso
 *    pra cada card da lista vira N chamadas extras sem nenhum item de
 *    paridade pedindo — fica para quando o card do modelo tiver tela própria.
 *  · por câmera — o dado NÃO existe: `model_evaluations`
 *    (`infra/migrations/101_model_eval_drift.sql`) não tem `camera_id`
 *    nenhum. A única tabela com câmera é `model_drift_metrics`, e ela mede
 *    confiança/distribuição de classe (drift), não acerto contra gabarito —
 *    não é a mesma coisa. Aguarda backend/medição.
 */
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, CheckCircle2, Settings } from 'lucide-react'

import { api } from '../../services/api'
import { nomeParaCliente } from '../../services/modelDisplay'
import {
  formatarMetricaAvaliacao,
  formatarMetricaModelo,
  metricaAusente,
  METRICA_AUSENTE_ROTULO,
  MODEL_EVAL_STATUS_LABELS,
  modelEvalStatusBadgeVariant,
} from '../../utils/labels'
import { useToast } from '../../components/ui/Toast/useToast'
import { Badge } from '../../components/ui/Badge/Badge'
import { EmptyState } from '../../components/ui/EmptyState/EmptyState'
import { Tooltip } from '../../components/ui/Tooltip/Tooltip'
import { ModelScenarioWizard } from '../../components/scenario/ModelScenarioWizard'
import type { ApiResponse, TrainedModel, YoloClass } from '../../types'
import { LogikosLoader } from '../shell/LogikosLoader'
import { rotaNova } from '../RotasNovas'
import { lk } from '../tokens/lk.css'
import { isSimulatedArtifact, originLabel, OwnerInfo, SeloSimulacao } from './selos'
import * as s from './Modelo.css'

/** Tooltips pt-BR das métricas de modelo (mAP@50 / Precisão / Cobertura). */
const METRIC_HELP: Record<string, string> = {
  'mAP@50': 'mAP@50: acerto médio das detecções com sobreposição ≥ 50% — quanto maior, melhor',
  Precisão: 'Precisão: das detecções feitas, quantas estavam certas',
  Cobertura: 'Cobertura: dos objetos presentes, quantos o modelo encontrou',
}

function dataFormatada(iso: string): string {
  try {
    return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
  } catch {
    return iso
  }
}

function Metrica({ rotulo, valor, ausente }: { rotulo: string; valor: string; ausente: boolean }) {
  const pilula = (
    // aria-label sobrepõe a leitura "mAP@50 —" (confusa em leitor de tela)
    // por "mAP@50: métrica não registrada" — não depende de hover, ao
    // contrário do Tooltip abaixo.
    <div className={s.metrica} aria-label={ausente ? `${rotulo}: ${METRICA_AUSENTE_ROTULO}` : undefined}>
      <span className={s.metricaRotulo}>{rotulo}</span>
      <span className={s.metricaValor}>{valor}</span>
    </div>
  )
  // Ausente ganha seu próprio rótulo de ajuda ("métrica não registrada") em
  // vez da explicação normal da métrica — a explicação não faz sentido para
  // um valor que não existe.
  const ajuda = ausente ? METRICA_AUSENTE_ROTULO : METRIC_HELP[rotulo]
  if (!ajuda) return pilula
  return <Tooltip label={ajuda}>{pilula}</Tooltip>
}

function Metricas({ modelo }: { modelo: TrainedModel }) {
  // eval_status presente = GET /training/models já enriqueceu com a
  // avaliação real (model_evaluations) — honesta por construção (ap=None
  // vira ausente, ap=0.0 real fica 0,0%). Ausente (mocks antigos/testes)
  // cai no legado trained_models.map50 (0 literal tratado como ausente —
  // LEI DA CASA, ver metricaAusente).
  const honesto = modelo.eval_status !== undefined
  const n = modelo.eval_images_evaluated
  return (
    <div className={s.metricas}>
      <Metrica
        rotulo="mAP@50"
        valor={honesto ? formatarMetricaAvaliacao(modelo.eval_map50, n) : formatarMetricaModelo(modelo.map50)}
        ausente={honesto ? modelo.eval_map50 == null : metricaAusente(modelo.map50)}
      />
      <Metrica
        rotulo="Precisão"
        valor={honesto ? formatarMetricaAvaliacao(modelo.eval_precision, n) : formatarMetricaModelo(modelo.precision)}
        ausente={honesto ? modelo.eval_precision == null : metricaAusente(modelo.precision)}
      />
      <Metrica
        rotulo="Cobertura"
        valor={honesto ? formatarMetricaAvaliacao(modelo.eval_recall, n) : formatarMetricaModelo(modelo.recall)}
        ausente={honesto ? modelo.eval_recall == null : metricaAusente(modelo.recall)}
      />
    </div>
  )
}

/** Badge Funcional/Parcial/Não avaliado — null quando o backend ainda não
 * manda eval_status (mocks antigos/testes sem o campo). */
function BadgeAvaliacao({ modelo }: { modelo: TrainedModel }) {
  if (!modelo.eval_status) return null
  return (
    <Badge variant={modelEvalStatusBadgeVariant(modelo.eval_status)}>
      {MODEL_EVAL_STATUS_LABELS[modelo.eval_status]}
    </Badge>
  )
}

/** Linha de `GET /api/cameras/model-config` (só os campos usados aqui —
 * `model_config_handlers.py::list_camera_model_configs`, tenant-escopado). */
type DeploymentMinimo = {
  model_id: string
  status?: string
  config?: { mode?: string } | null
}

/**
 * Modelo em observação = maior contagem de câmeras com deployment
 * `status='active'` e `config.mode==='shadow'` (dado real, não inferido —
 * "shadow" e "mode" nunca aparecem em texto de tela, só aqui na leitura do
 * campo). Só é chamado quando NÃO há modelo em produção (`ativo`).
 */
function modeloEmObservacao(
  modelos: TrainedModel[],
  deployments: DeploymentMinimo[],
): { modelo: TrainedModel; cameras: number } | null {
  const contagem = new Map<string, number>()
  for (const d of deployments) {
    if (d.status === 'active' && d.config?.mode === 'shadow') {
      contagem.set(d.model_id, (contagem.get(d.model_id) ?? 0) + 1)
    }
  }
  let melhor: { modelId: string; cameras: number } | null = null
  for (const [modelId, cameras] of contagem) {
    if (!melhor || cameras > melhor.cameras) melhor = { modelId, cameras }
  }
  if (!melhor) return null
  const { modelId, cameras } = melhor
  const modelo = modelos.find((m) => m.id === modelId)
  return modelo ? { modelo, cameras } : null
}

export function Modelo() {
  const toast = useToast()
  const [modelos, setModelos] = useState<TrainedModel[] | null>(null)
  const [classes, setClasses] = useState<YoloClass[]>([])
  const [deployments, setDeployments] = useState<DeploymentMinimo[]>([])
  const [erro, setErro] = useState<string | null>(null)
  const [ativando, setAtivando] = useState<string | null>(null)
  const [modeloCenario, setModeloCenario] = useState<TrainedModel | null>(null)

  const carregar = useCallback(() => {
    setErro(null)
    setModelos(null)
    Promise.allSettled([
      api.get<ApiResponse<TrainedModel[]>>('/training/models'),
      api.get<ApiResponse<YoloClass[]>>('/classes'),
      api.get<ApiResponse<{ deployments: Record<string, DeploymentMinimo> }>>(
        '/cameras/model-config',
      ),
    ]).then(([modRes, clsRes, depRes]) => {
      if (modRes.status === 'fulfilled') {
        setModelos(modRes.value?.data ?? [])
      } else {
        setModelos([])
        setErro(modRes.reason instanceof Error ? modRes.reason.message : 'Erro ao carregar')
      }
      if (clsRes.status === 'fulfilled') setClasses(clsRes.value?.data ?? [])
      // Câmeras em observação são um extra do card "modelo ativo" — se a
      // rota falhar, a tela não quebra por isso, só não mostra o extra.
      if (depRes.status === 'fulfilled') {
        setDeployments(Object.values(depRes.value?.data?.deployments ?? {}))
      } else {
        setDeployments([])
      }
    })
  }, [])

  useEffect(carregar, [carregar])

  const ativar = async (modeloId: string) => {
    setAtivando(modeloId)
    try {
      // /api/v1/models/<id>/activate, NÃO /training/models/<id>/activate —
      // só este passa pelo gate campeão×desafiante.
      await api.post(`/v1/models/${modeloId}/activate`, {})
      toast.success('Modelo ativado')
      carregar()
    } catch (err: unknown) {
      // 409 eval_rejected já chega legível do backend via toast global do
      // api.ts — não duplicar aqui.
      const status = (err as { status?: number })?.status
      if (status !== 409) {
        toast.error(err instanceof Error ? err.message : 'Erro ao ativar modelo')
      }
    } finally {
      setAtivando(null)
    }
  }

  if (erro) {
    return (
      <div className={s.centro}>
        <AlertTriangle size={36} strokeWidth={1.5} color={lk.estado.nc} aria-hidden="true" />
        <span className={s.centroTitulo}>Não foi possível carregar os modelos</span>
        <span className={s.centroTecnico}>GET /api/training/models · {erro}</span>
        <button className={s.botaoRetry} onClick={carregar}>Tentar novamente</button>
      </div>
    )
  }

  if (modelos === null) {
    return <LogikosLoader estado="waiting" variante="tile" rotulo="CARREGANDO MODELOS" />
  }

  const ativo = modelos.find((m) => m.is_active) ?? null
  const observacao = ativo ? null : modeloEmObservacao(modelos, deployments)

  return (
    <div className={s.raiz}>
      <div className={s.cabecalho}>
        <h2 className={s.titulo}>Modelos</h2>
        <span className={s.espacador} />
        <Link className={s.linkContorno} to={rotaNova('/estudio/classes')}>
          <Settings size={13} strokeWidth={2} aria-hidden="true" /> Configurar Classes
        </Link>
      </div>

      <div
        className={`${s.cartaoAtivo}${ativo ? ` ${s.cartaoAtivoComModelo}` : ''}${observacao ? ` ${s.cartaoAtivoEmObservacao}` : ''}`}
      >
        <span className={s.secaoTitulo}>Modelo ativo</span>
        {ativo ? (
          <>
            <div className={s.nomeAtivo}>{nomeParaCliente(ativo)} <BadgeAvaliacao modelo={ativo} /></div>
            <Metricas modelo={ativo} />
            <div className={s.rodapeAtivo}>
              <span>Origem: {originLabel(ativo.origin)}</span>
              {isSimulatedArtifact(ativo.origin, ativo.metrics) && <SeloSimulacao />}
              <OwnerInfo model={ativo} />
            </div>
            <span className={s.dataAtivo}>Criado em {dataFormatada(ativo.created_at)}</span>
          </>
        ) : observacao ? (
          <>
            <div className={s.nomeAtivo}>{nomeParaCliente(observacao.modelo)}</div>
            <Metricas modelo={observacao.modelo} />
            <p className={s.semAtivo}>
              Em observação em {observacao.cameras} {observacao.cameras === 1 ? 'câmera' : 'câmeras'} —
              ainda não gera aviso para a equipe.
            </p>
          </>
        ) : (
          <p className={s.semAtivo}>Nenhum modelo ativo. Ative um modelo abaixo.</p>
        )}
      </div>

      {classes.length > 0 && (
        <>
          <span className={s.secaoTitulo}>Classes de detecção</span>
          <div className={s.classesGrid}>
            {classes.map((c) => (
              <div key={c.id} className={s.classeChip}>
                <span className={s.classeCor} style={{ background: c.color || lk.cor.bordaForte }} />
                <span>{c.name}</span>
              </div>
            ))}
          </div>
        </>
      )}

      <span className={s.secaoTitulo}>Modelos treinados</span>
      {modelos.length === 0 ? (
        <EmptyState
          title="Nenhum modelo treinado ainda"
          description='Inicie um treino na aba "Treino ao Vivo" para o primeiro modelo aparecer aqui.'
        />
      ) : (
        <div className={s.modelosGrid}>
          {modelos.map((modelo) => (
            <div
              key={modelo.id}
              className={`${s.modeloCartao}${modelo.is_active ? ` ${s.modeloCartaoAtivo}` : ''}`}
            >
              <div className={s.modeloLinha}>
                <span className={s.modeloNome}>
                  {nomeParaCliente(modelo)}
                  {/* nome interno era o único distintivo entre modelos sem
                      apelido próprio — job id curto substitui (não é framework). */}
                  <span className={s.dataModelo}> #{(modelo.job_id || modelo.id).slice(0, 8)}</span>
                  {modelo.is_active && (
                    <span className={s.badgeAtivo}>
                      <CheckCircle2 size={10} strokeWidth={2.5} aria-hidden="true" /> ativo
                    </span>
                  )}
                  {' '}<BadgeAvaliacao modelo={modelo} />
                </span>
              </div>
              <Metricas modelo={modelo} />
              <div className={s.rodapeAtivo}>
                <span>Origem: {originLabel(modelo.origin)}</span>
                {isSimulatedArtifact(modelo.origin, modelo.metrics) && <SeloSimulacao />}
                <OwnerInfo model={modelo} />
              </div>
              {/* Gate Funcional/Parcial/Não avaliado: o backend já recusa
                  (409) — mostrar o motivo aqui evita o usuário descobrir
                  isso só depois de clicar Ativar. */}
              {modelo.eval_status && modelo.eval_status !== 'funcional' && modelo.eval_motivo && (
                <p className={s.semAtivo}>{modelo.eval_motivo}</p>
              )}
              <div className={s.acoes}>
                <button className={s.botaoAcao} onClick={() => setModeloCenario(modelo)}>
                  <Settings size={12} strokeWidth={2} aria-hidden="true" /> Configurar cenário
                </button>
                {!modelo.is_active && (
                  <button
                    className={s.botaoAcao}
                    onClick={() => ativar(modelo.id)}
                    disabled={
                      ativando === modelo.id ||
                      (modelo.eval_status !== undefined && modelo.eval_status !== 'funcional')
                    }
                    title={
                      modelo.eval_status && modelo.eval_status !== 'funcional'
                        ? (modelo.eval_motivo ?? undefined)
                        : undefined
                    }
                  >
                    {ativando === modelo.id ? '...' : 'Ativar'}
                  </button>
                )}
              </div>
              <span className={s.dataModelo}>{dataFormatada(modelo.created_at)}</span>
            </div>
          ))}
        </div>
      )}

      {modeloCenario && (
        <ModelScenarioWizard
          modelId={modeloCenario.id}
          modelName={nomeParaCliente(modeloCenario)}
          onClose={() => setModeloCenario(null)}
          onSaved={() => {
            toast.success('Cenário do modelo salvo')
            carregar()
          }}
        />
      )}
    </div>
  )
}
