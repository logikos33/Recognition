/**
 * Treino — a sub-rota "Treino ao Vivo" do Estúdio (`Estúdio.dc.html`, seção
 * "Treinos"). RENASCE a aba "treino" de `pages/TrainingPage.tsx` (fonte da
 * paridade, lida função a função) — a ORQUESTRAÇÃO é a mesma:
 *
 *  · banner honesto quando `gpu_enabled` vem `false` do status atual (o treino
 *    FALHA, não simula mais silenciosamente);
 *  · poll de 3s em `/training/jobs/current/status` ({job, gpu_enabled, live})
 *    + WebSocket via `useTrainingSocket` (mesmo hook, importado como está);
 *  · histórico com `current_epoch` — o REAL número de épocas rodadas — nunca
 *    `total_epochs` (o pedido). Um job que para cedo (early stop / falha) tem
 *    os dois diferentes, e mostrar o pedido no lugar do real é a mentira que
 *    a task "treino honesto" (C2) já baniu da aba Modelo; aqui é a mesma regra.
 *  · `metrics.simulated === true` é a única proveniência que ESTA aba conhece
 *    (`SelosSimulacao`) — `origin`/`worker_commit` vivem em `TrainedModel`,
 *    não em `TrainingJob`, e pertencem à aba Modelo (PR seguinte da F5).
 *
 * Os componentes pesados (`AnnotationStudio`, `TrainingGallery`) não entram
 * aqui — são da rota `dados`. Esta tela só fala com `/training/jobs*`.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { AlertTriangle, Play, RefreshCw, Square, Zap } from 'lucide-react'

import { useAuth } from '../../hooks/useAuth'
import { api, getToken } from '../../services/api'
import { useToast } from '../../components/ui/Toast/useToast'
import { useTrainingSocket } from '../../hooks/useTrainingSocket'
import { InfoTooltip } from '../../components/ui/InfoTooltip/InfoTooltip'
import {
  FIELD_HELP,
  PRESET_LABELS,
  TRAINING_STATUS_OVERRIDES,
  humanize,
  labelForModule,
  statusToLabel,
} from '../../utils/labels'
import type { ApiResponse, TrainingJob } from '../../types'
import { LogikosLoader } from '../shell/LogikosLoader'
import * as s from './Treino.css'

const WS_URL = (import.meta.env.VITE_WS_URL as string | undefined)
  || (import.meta.env.VITE_API_URL as string | undefined)
  || ''

interface CurrentJobStatus {
  job: TrainingJob | null
  gpu_enabled: boolean
  live: {
    job_id: string
    stage: string
    progress: number
    epoch: number
    metrics: Record<string, number>
    error?: string
  } | null
}

function displayModelName(name: string): string {
  return name
    .replace(/yolo26n/gi, 'LGKV26n')
    .replace(/yolo26s/gi, 'LGKV26s')
    .replace(/yolo26m/gi, 'LGKV26m')
}

function formatEta(seconds: number): string {
  if (seconds <= 0) return ''
  const m = Math.floor(seconds / 60)
  const sec = seconds % 60
  return `${m}:${String(sec).padStart(2, '0')} restantes`
}

function fmtDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
  } catch {
    return iso
  }
}

/** Cor por status — mesma semântica de `estado` (ok/atenção/nc), sem Badge antigo. */
function pilulaDoStatus(status: string): string {
  switch (status) {
    case 'completed': return s.pilulaOk
    case 'failed': return s.pilulaNc
    case 'running': case 'pending': return s.pilulaAtencao
    default: return s.pilulaNeutra
  }
}

/** Marcação indelével de simulação (task "treino honesto", C2). */
function SeloSimulacao() {
  return (
    <span className={s.pilulaSimulacao}>
      <AlertTriangle size={10} style={{ marginRight: 3 }} /> SIMULAÇÃO — não é treino real
    </span>
  )
}

/** Sparkline local (renasce `MiniChart` da TrainingPage) — só lk.estado nas linhas. */
function GraficoLinha({ dados, corClasse, rotulo }: { dados: number[]; corClasse: string; rotulo: string }) {
  if (dados.length < 2) return null
  const max = Math.max(...dados)
  const min = Math.min(...dados)
  const amplitude = max - min || 1
  const LARGURA = 280
  const ALTURA = 80
  const pontos = dados
    .map((v, i) => `${(i / (dados.length - 1)) * LARGURA},${ALTURA - ((v - min) / amplitude) * ALTURA}`)
    .join(' ')
  return (
    <div className={s.cardGrafico}>
      <span className={s.rotuloGrafico}>{rotulo}</span>
      <svg viewBox={`0 0 ${LARGURA} ${ALTURA}`} className={s.svgGrafico} aria-hidden="true">
        <polyline points={pontos} className={corClasse} fill="none" strokeWidth={2} />
      </svg>
    </div>
  )
}

export function Treino() {
  const toast = useToast()
  const { modules, isSuperAdmin } = useAuth()
  const trainingModules = ['epi', 'quality', 'counting'].filter((m) => modules.includes(m))

  const [jobs, setJobs] = useState<TrainingJob[]>([])
  const [currentStatus, setCurrentStatus] = useState<CurrentJobStatus | null>(null)
  const [gpuEnabled, setGpuEnabled] = useState(true)
  const [trainLogs, setTrainLogs] = useState<string[]>([])
  const logsEndRef = useRef<HTMLDivElement>(null)

  // Config do novo treino — os mesmos campos e defaults da TrainingPage.
  const [showConfig, setShowConfig] = useState(false)
  const [cfgEpochs, setCfgEpochs] = useState(50)
  const [cfgBatch, setCfgBatch] = useState(16)
  const [cfgLr, setCfgLr] = useState(0.01)
  const [cfgModel, setCfgModel] = useState('yolo26n')
  const [cfgModule, setCfgModule] = useState(() => trainingModules[0] ?? 'epi')
  const [creating, setCreating] = useState(false)
  const [stopping, setStopping] = useState(false)

  const token = getToken() || ''
  const { jobs: liveJobs } = useTrainingSocket({ wsUrl: WS_URL, token })

  const pollCurrentStatus = useCallback(async () => {
    try {
      const res = await api.get<ApiResponse<CurrentJobStatus>>('/training/jobs/current/status')
      const d = res?.data
      if (!d) return
      setCurrentStatus(d)
      setGpuEnabled(d.gpu_enabled)
      if (d.live) {
        const { stage, epoch, metrics } = d.live
        const map50 = metrics?.mAP50 ?? metrics?.map50
        const loss = metrics?.loss
        const msg = [
          `[${new Date().toLocaleTimeString('pt-BR')}]`,
          `stage=${stage}`,
          epoch ? `epoch=${epoch}` : '',
          loss != null ? `loss=${Number(loss).toFixed(4)}` : '',
          map50 != null ? `mAP50=${Number(map50).toFixed(4)}` : '',
        ].filter(Boolean).join(' ')
        setTrainLogs((prev) => [...prev.slice(-99), msg])
      }
    } catch { /* silent — próxima passagem de poll re-tenta */ }
  }, [])

  const loadJobs = useCallback(async () => {
    try {
      const res = await api.get<ApiResponse<TrainingJob[]>>('/training/jobs')
      setJobs(res?.data || [])
    } catch { /* silent */ }
  }, [])

  useEffect(() => {
    pollCurrentStatus()
    loadJobs()
  }, [pollCurrentStatus, loadJobs])

  useEffect(() => {
    const id = setInterval(pollCurrentStatus, 3000)
    return () => clearInterval(id)
  }, [pollCurrentStatus])

  // Eventos do WebSocket também viram log — mesma fonte que os sparklines.
  useEffect(() => {
    const liveEntries = Object.entries(liveJobs)
    if (!liveEntries.length) return
    const [, live] = liveEntries[liveEntries.length - 1]
    if (!live) return
    const loss = live.metrics?.loss
    const map50 = live.metrics?.map50
    const msg = [
      `[WS ${new Date().toLocaleTimeString('pt-BR')}]`,
      `status=${live.status}`,
      `epoch=${live.epoch}/${live.total_epochs}`,
      loss != null ? `loss=${Number(loss).toFixed(4)}` : '',
      map50 != null ? `mAP50=${Number(map50).toFixed(4)}` : '',
      live.eta_seconds > 0 ? formatEta(live.eta_seconds) : '',
    ].filter(Boolean).join(' ')
    setTrainLogs((prev) => [...prev.slice(-99), msg])
  }, [liveJobs])

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [trainLogs])

  const createJob = async () => {
    setCreating(true)
    try {
      await api.post('/training/jobs', {
        preset: 'balanced',
        module: cfgModule,
        model_size: cfgModel,
        total_epochs: cfgEpochs,
        batch_size: cfgBatch,
        learning_rate: cfgLr,
      })
      toast.success('Treinamento iniciado')
      setShowConfig(false)
      setTrainLogs([])
      await Promise.all([loadJobs(), pollCurrentStatus()])
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Erro ao criar job')
    } finally {
      setCreating(false)
    }
  }

  const stopJob = async (jobId: string) => {
    setStopping(true)
    try {
      await api.post(`/training/jobs/${jobId}/stop`, {})
      toast.success('Job interrompido')
      await Promise.all([loadJobs(), pollCurrentStatus()])
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Erro ao parar job')
    } finally {
      setStopping(false)
    }
  }

  const currentJob = currentStatus?.job ?? null
  const isRunning = !!currentJob && ['pending', 'running'].includes(currentJob.status)
  const liveJobEntry = currentJob ? liveJobs[currentJob.id] : null

  return (
    <div className={s.raiz}>
      <div className={s.cabecalho}>
        <h1 className={s.titulo}>Treinos</h1>
        <div className={s.espacador} />
        {!isRunning && (
          <button className={s.botaoPrimario} onClick={() => setShowConfig((v) => !v)}>
            <Zap size={13} /> Novo treino
          </button>
        )}
        <button className={s.botaoIcone} onClick={() => { pollCurrentStatus(); loadJobs() }} title="Atualizar">
          <RefreshCw size={14} />
        </button>
      </div>

      {/* GPU/Vast.ai off — link só para superadmin. `/admin/*` é o front ANTIGO
          (AdminRoute, fora do prefixo novo): âncora HTML pura de propósito, não
          o componente Link de rotas com destino absoluto — o teste de
          coexistência barra justamente esse componente apontando pra fora do
          prefixo (regra certa: SAIR do front novo é o que esta navegação
          precisa fazer de verdade). */}
      {!gpuEnabled && (
        <div className={s.bannerGpu}>
          <AlertTriangle size={16} style={{ flexShrink: 0 }} />
          <span>
            Chave de GPU não configurada — o treino vai falhar até uma GPU real ser configurada
            (não roda mais em simulação automaticamente).{' '}
          </span>
          {isSuperAdmin ? (
            <a href="/admin/integrations?type=vast_ai" className={s.linkBanner}>
              Administração → Integrações
            </a>
          ) : (
            <span>Solicite ao administrador da plataforma a configuração da chave de GPU.</span>
          )}
        </div>
      )}

      {showConfig && !isRunning && (
        <div className={s.formulario}>
          <div className={s.grade}>
            <div className={s.campo}>
              <label className={s.rotuloCampo}>Módulo <InfoTooltip text={FIELD_HELP.module} /></label>
              <select className={s.selectCampo} value={cfgModule} onChange={(e) => setCfgModule(e.target.value)}>
                {(trainingModules.length ? trainingModules : ['epi']).map((m) => (
                  <option key={m} value={m}>{labelForModule(m)}</option>
                ))}
              </select>
            </div>
            <div className={s.campo}>
              <label className={s.rotuloCampo}>Modelo Base <InfoTooltip text={FIELD_HELP.base_model} /></label>
              <select className={s.selectCampo} value={cfgModel} onChange={(e) => setCfgModel(e.target.value)}>
                <option value="yolo26n">LGKV26n (nano)</option>
                <option value="yolo26s">LGKV26s (small)</option>
                <option value="yolo26m">LGKV26m (medium)</option>
              </select>
            </div>
            <div className={s.campo}>
              <label className={s.rotuloCampo}>Épocas <InfoTooltip text={FIELD_HELP.epochs} /></label>
              <input className={s.inputCampo} type="number" value={cfgEpochs} min={5} max={300}
                onChange={(e) => setCfgEpochs(Number(e.target.value))} />
            </div>
            <div className={s.campo}>
              <label className={s.rotuloCampo}>Tamanho do lote <InfoTooltip text={FIELD_HELP.batch_size} /></label>
              <input className={s.inputCampo} type="number" value={cfgBatch} min={1} max={64}
                onChange={(e) => setCfgBatch(Number(e.target.value))} />
            </div>
            <div className={s.campo}>
              <label className={s.rotuloCampo}>Taxa de aprendizado <InfoTooltip text={FIELD_HELP.learning_rate} /></label>
              <input className={s.inputCampo} type="number" value={cfgLr} min={0.0001} max={0.1} step={0.001}
                onChange={(e) => setCfgLr(Number(e.target.value))} />
            </div>
          </div>
          <div className={s.acoesFormulario}>
            <button className={s.botaoPrimario} onClick={createJob} disabled={creating}>
              <Play size={13} /> {creating ? 'Iniciando...' : 'Iniciar Treinamento'}
            </button>
            <button className={s.botaoSecundario} onClick={() => setShowConfig(false)}>Cancelar</button>
          </div>
        </div>
      )}

      <div className={isRunning ? `${s.cartao} ${s.cartaoAoVivo}` : s.cartao}>
        {currentJob ? (
          <>
            <div className={s.linhaAoVivo}>
              {isRunning && <LogikosLoader variante="spinner" estado="waiting" />}
              <span className={s.nomeJob}>{displayModelName(currentJob.model_size)}</span>
              {isRunning && <span className={s.pilulaAoVivo}>AO VIVO</span>}
              <span className={pilulaDoStatus(currentJob.status)}>
                {statusToLabel(currentJob.status, TRAINING_STATUS_OVERRIDES)}
              </span>
              {currentJob.metrics?.simulated === true && <SeloSimulacao />}
              <span className={s.infoMono}>{PRESET_LABELS[currentJob.preset] ?? humanize(currentJob.preset)}</span>
              {isRunning && (
                <button className={s.botaoParar} onClick={() => stopJob(currentJob.id)} disabled={stopping}>
                  <Square size={12} /> {stopping ? 'Parando...' : 'Parar'}
                </button>
              )}
              <span className={s.dataJob}>{fmtDate(currentJob.created_at)}</span>
            </div>

            {(currentJob.status === 'running' || currentJob.status === 'pending') && (
              <div className={s.progressoLinha}>
                <div className={s.progressoTrilho}>
                  <div className={s.progressoPreenchido} style={{ width: `${liveJobEntry?.progress ?? currentJob.progress}%` }} />
                </div>
                <span className={s.progressoLabel}>
                  ÉPOCA <span className={s.progressoValor}>{liveJobEntry?.epoch ?? currentJob.current_epoch}/{liveJobEntry?.total_epochs ?? currentJob.total_epochs}</span>
                  {' '}({liveJobEntry?.progress ?? currentJob.progress}%)
                  {liveJobEntry && liveJobEntry.eta_seconds > 0 && ` · ${formatEta(liveJobEntry.eta_seconds)}`}
                </span>
              </div>
            )}

            {liveJobEntry && (liveJobEntry.lossHistory.length >= 2 || liveJobEntry.map50History.length >= 2) && (
              <div className={s.grade2}>
                {liveJobEntry.lossHistory.length >= 2 && (
                  <GraficoLinha dados={liveJobEntry.lossHistory} corClasse={s.linhaPerda} rotulo="ERRO DE TREINO ↓" />
                )}
                {liveJobEntry.map50History.length >= 2 && (
                  <GraficoLinha dados={liveJobEntry.map50History} corClasse={s.linhaAcerto} rotulo="ACERTO NA VALIDAÇÃO ↑" />
                )}
              </div>
            )}

            {currentJob.status === 'completed' && currentJob.metrics && Object.keys(currentJob.metrics).length > 0 && (
              <div className={s.metricas}>
                {currentJob.metrics.map50 != null && (
                  <div className={s.metrica}>
                    <span className={s.metricaRotulo}>mAP@50</span>
                    <span className={`${s.metricaValor} ${s.metricaDestaque}`}>{(currentJob.metrics.map50 * 100).toFixed(1)}%</span>
                  </div>
                )}
                {currentJob.metrics.precision != null && (
                  <div className={s.metrica}>
                    <span className={s.metricaRotulo}>Precisão</span>
                    <span className={s.metricaValor}>{(currentJob.metrics.precision * 100).toFixed(1)}%</span>
                  </div>
                )}
                {currentJob.metrics.recall != null && (
                  <div className={s.metrica}>
                    <span className={s.metricaRotulo}>Cobertura</span>
                    <span className={s.metricaValor}>{(currentJob.metrics.recall * 100).toFixed(1)}%</span>
                  </div>
                )}
              </div>
            )}

            {currentJob.status === 'failed' && currentJob.error_message && (
              <div className={s.erroJob}>{currentJob.error_message}</div>
            )}
          </>
        ) : (
          <p className={s.vazio}>Nenhum job em andamento. Clique em &quot;Novo treino&quot; para iniciar.</p>
        )}
      </div>

      <div>
        <div className={s.logsCabecalho}>
          <span className={s.logsTitulo}>Log de Eventos</span>
          <button className={s.limparLogs} onClick={() => setTrainLogs([])}>limpar</button>
        </div>
        <div className={s.logsCaixa}>
          {trainLogs.length === 0 ? (
            <span className={s.logsTitulo}>Aguardando eventos de treinamento...</span>
          ) : (
            trainLogs.map((line, i) => (
              <div key={i} className={line.startsWith('[WS') ? s.logLinhaWs : s.logLinha}>{line}</div>
            ))
          )}
          <div ref={logsEndRef} />
        </div>
      </div>

      <div className={s.historicoLista}>
        <span className={s.historicoTitulo}>Histórico</span>
        {jobs.length === 0 ? (
          <p className={s.vazio}>Nenhum job de treinamento ainda.</p>
        ) : (
          jobs.map((job) => (
            <div
              key={job.id}
              className={job.status === 'failed' ? `${s.historicoLinha} ${s.historicoLinhaFalhou}` : s.historicoLinha}
            >
              <span className={s.historicoNome}>
                {displayModelName(job.model_size)} · {PRESET_LABELS[job.preset] ?? humanize(job.preset)}
              </span>
              <span className={s.historicoData}>{fmtDate(job.created_at)}</span>
              <div className={s.espacador} />
              {/* current_epoch é o REAL rodado — nunca total_epochs (o pedido). */}
              <span className={s.historicoEpocas}>{job.current_epoch}/{job.total_epochs} ép.</span>
              {job.metrics?.map50 != null && (
                <span className={s.historicoEpocas}>mAP@50 {(job.metrics.map50 * 100).toFixed(1)}%</span>
              )}
              <span className={pilulaDoStatus(job.status)}>{statusToLabel(job.status, TRAINING_STATUS_OVERRIDES)}</span>
              {job.metrics?.simulated === true && <SeloSimulacao />}
              {job.status === 'failed' && job.error_message && (
                <span className={s.historicoErro}>✕ {job.error_message}</span>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
