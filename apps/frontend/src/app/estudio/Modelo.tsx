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
import { useToast } from '../../components/ui/Toast/useToast'
import { EmptyState } from '../../components/ui/EmptyState/EmptyState'
import { ModelScenarioWizard } from '../../components/scenario/ModelScenarioWizard'
import type { ApiResponse, TrainedModel, YoloClass } from '../../types'
import { LogikosLoader } from '../shell/LogikosLoader'
import { rotaNova } from '../RotasNovas'
import { lk } from '../tokens/lk.css'
import * as s from './Modelo.css'

/** `yolo26n/s/m` → `LGKV26n/s/m` — mesmo apelido do antigo (displayModelName). */
function nomeExibicao(nome: string): string {
  return nome
    .replace(/yolo26n/gi, 'LGKV26n')
    .replace(/yolo26s/gi, 'LGKV26s')
    .replace(/yolo26m/gi, 'LGKV26m')
}

function dataFormatada(iso: string): string {
  try {
    return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
  } catch {
    return iso
  }
}

const PORCENTAGEM = (v: number) => `${(v * 100).toFixed(1)}%`

function Metrica({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <div className={s.metrica}>
      <span className={s.metricaRotulo}>{rotulo}</span>
      <span className={s.metricaValor}>{valor}</span>
    </div>
  )
}

function Metricas({ modelo }: { modelo: TrainedModel }) {
  return (
    <div className={s.metricas}>
      {modelo.map50 != null && <Metrica rotulo="mAP@50" valor={PORCENTAGEM(modelo.map50)} />}
      {modelo.precision != null && <Metrica rotulo="Precisão" valor={PORCENTAGEM(modelo.precision)} />}
      {modelo.recall != null && <Metrica rotulo="Cobertura" valor={PORCENTAGEM(modelo.recall)} />}
    </div>
  )
}

export function Modelo() {
  const toast = useToast()
  const [modelos, setModelos] = useState<TrainedModel[] | null>(null)
  const [classes, setClasses] = useState<YoloClass[]>([])
  const [erro, setErro] = useState<string | null>(null)
  const [ativando, setAtivando] = useState<string | null>(null)
  const [modeloCenario, setModeloCenario] = useState<TrainedModel | null>(null)

  const carregar = useCallback(() => {
    setErro(null)
    setModelos(null)
    Promise.allSettled([
      api.get<ApiResponse<TrainedModel[]>>('/training/models'),
      api.get<ApiResponse<YoloClass[]>>('/classes'),
    ]).then(([modRes, clsRes]) => {
      if (modRes.status === 'fulfilled') {
        setModelos(modRes.value?.data ?? [])
      } else {
        setModelos([])
        setErro(modRes.reason instanceof Error ? modRes.reason.message : 'Erro ao carregar')
      }
      if (clsRes.status === 'fulfilled') setClasses(clsRes.value?.data ?? [])
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

  return (
    <div className={s.raiz}>
      <div className={s.cabecalho}>
        <h2 className={s.titulo}>Modelos</h2>
        <span className={s.espacador} />
        <Link className={s.linkContorno} to={rotaNova('/estudio/classes')}>
          <Settings size={13} strokeWidth={2} aria-hidden="true" /> Configurar Classes
        </Link>
      </div>

      <div className={`${s.cartaoAtivo}${ativo ? ` ${s.cartaoAtivoComModelo}` : ''}`}>
        <span className={s.secaoTitulo}>Modelo ativo</span>
        {ativo ? (
          <>
            <div className={s.nomeAtivo}>{nomeExibicao(ativo.name)}</div>
            <Metricas modelo={ativo} />
            <div className={s.rodapeAtivo}>Criado em {dataFormatada(ativo.created_at)}</div>
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
                  {nomeExibicao(modelo.name)}
                  {modelo.is_active && (
                    <span className={s.badgeAtivo}>
                      <CheckCircle2 size={10} strokeWidth={2.5} aria-hidden="true" /> ativo
                    </span>
                  )}
                </span>
              </div>
              <Metricas modelo={modelo} />
              <div className={s.acoes}>
                <button className={s.botaoAcao} onClick={() => setModeloCenario(modelo)}>
                  <Settings size={12} strokeWidth={2} aria-hidden="true" /> Configurar cenário
                </button>
                {!modelo.is_active && (
                  <button
                    className={s.botaoAcao}
                    onClick={() => ativar(modelo.id)}
                    disabled={ativando === modelo.id}
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
          modelName={nomeExibicao(modeloCenario.name)}
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
