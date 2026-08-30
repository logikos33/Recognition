/**
 * Gestão Qualidade — D1 Dashboard · D2 Peças & OPs · D3 Relatórios.
 *
 * Desenho: `Gestão Qualidade.dc.html` (handoff Logikos Vision).
 * Backend: blueprint `quality_bp`, prefixo `/api/v1/quality`, envelope
 * `{success, message, data}`.
 *
 * ⚠️ GESTÃO É PROVA. Todo número desta tela veio de uma rota. Nada é calculado
 * de cabeça, nada é exemplo. O que o backend não serve NÃO aparece — aparece
 * como lacuna declarada, e a ação sem rota fica desabilitada dizendo por quê.
 *
 * ── O QUE DO DESENHO NÃO ESTÁ AQUI, e por quê ──────────────────────────────
 *
 * · **Tudo que é "por PONTO" (P1/P2/P4/P8)**: o gráfico "NC + refazer por
 *   ponto" (D1), a tabela "Tempo médio por ponto × estação" (D1) e a tabela
 *   inteira de D3 (PONTO | INSPEÇÃO | FOTOS | CONFORME | NC | RETRABALHO).
 *   O único campo com noção de ponto é `inspection_sessions.stage`, e não há
 *   endpoint que agregue por ele — `/api/v1/monofatura/sessions` só lista
 *   linhas cruas. Pior: `inspection_sessions.piece_id` é TEXT e
 *   `quality_pieces.id` é UUID, então nem o vínculo peça↔ponto existe. No
 *   lugar do gráfico entra o eixo que EXISTE (`validation_type` v1/v2/v3 =
 *   etapa de validação, de `/gate/stats/rework`), com o rótulo correto — não
 *   com o rótulo do desenho por cima de outro dado.
 *
 * · **KPI "% DÚVIDA"** e a classe "Foto borrada (refazer)".
 *   `quality_inspections.result` é VARCHAR(10) com 'ok'/'nok' e mais nada
 *   (migration 104): não há terceiro veredito "dúvida", nem contador de
 *   "refazer captura" em lugar nenhum da máquina de estados. `feedback_status`
 *   é decisão HUMANA posterior, não incerteza do modelo — usá-lo como "dúvida"
 *   seria inventar um número com cara de medição.
 *
 * · **KPI "LATÊNCIA P95 1,4 s"**. Não existe coluna de latência em
 *   `quality_inspections` nem em `inspection_sessions`.
 *
 * · **"idade máx 38 min" e "decisão média 11 s/item"** da fila de revisão.
 *   `/inspections/summary` devolve `pending_feedback` (a contagem — esse
 *   número está na tela), mas nada agrega `MIN(created_at)` dos pendentes nem
 *   `AVG(feedback_at - created_at)`. As colunas existem; a agregação, não.
 *
 * · **"Tendência 30 dias — % fora de conforme"**. Nenhuma rota devolve série
 *   diária: `/inspections/summary` colapsa o período inteiro em UM agregado e
 *   `/reports/shift` é de um dia+turno. Desenhar a polyline exigiria 30
 *   chamadas — e uma linha com 1 ponto repetido 30× não é tendência, é enfeite.
 *
 * · **Coluna "pontos" ("4/4 ✓")** e a **"META"** dos tempos. `quality_pieces`
 *   não tem contador de etapas concluídas/esperadas, e tempo-alvo por ponto
 *   não é coluna de tabela nenhuma. No lugar de "pontos" a lista mostra
 *   `total_rework_count`, que é o contador que a peça de fato carrega.
 *
 * · **"1º turno"** no cabeçalho do painel de D2. `shift` só existe em
 *   `quality_inspections`; `quality_pieces` não tem turno (migrations 033 e
 *   104) e nem `/gate/pieces` nem `/dashboard/summary` devolvem um.
 *
 * · **`online` e `shift_stats` das estações**. `gate_repository.py:792` devolve
 *   `True` e `{"ok":0,"nok":0}` LITERAIS, hardcoded. Um "online" verde
 *   permanente e um placar zerado são pior que ausência: são um instrumento
 *   quebrado que parece funcionar.
 *
 * ── O QUE ESTÁ AQUI MAS COM OUTRO RÓTULO (o dado é real, o nome do desenho
 * era de outra coisa) ──────────────────────────────────────────────────────
 *
 * · "% CONFORME · das fotos validadas" → `dashboard/summary.ok_pct` conta
 *   PEÇAS com `status='approved'`, não fotos. O KPI diz "% PEÇAS APROVADAS".
 * · "NC + refazer por ponto" → retrabalhos por etapa de validação (v1/v2/v3).
 * · "Por classe" (taxonomia RVB) → `defect_distribution` agrupa pelos 5 slugs
 *   FIXOS de `classes.py` (visual, dimensional, superficie, montagem, outro).
 *   Os nomes vêm de `/defect-categories`, não de um dicionário local.
 * · "Corte: por ponto / classe / turno" (D3) → só "por turno" tem rota.
 *
 * ── SELETOR DE PERÍODO ─────────────────────────────────────────────────────
 * Só `/inspections/summary` aceita `date_from`/`date_to`. `/dashboard/summary`
 * e `/gate/stats/overview` são `CURRENT_DATE` fixo, `/gate/stats/rework` agrega
 * o histórico inteiro e `/gate/pieces` recebe `date_from` e DESCARTA. Por isso
 * o seletor só aparece em D1 (onde muda alguma coisa) e cada cartão que o
 * ignora diz que ignora. Um seletor global que não filtra é a mentira mais
 * barata de se cometer aqui.
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  Clock,
  Inbox,
  Lock,
  RotateCcw,
  XCircle,
} from 'lucide-react'

import { useAuth } from '../../hooks/useAuth'
import { ApiError, api } from '../../services/api'
import { LogikosLoader } from '../shell/LogikosLoader'
import * as s from './GestaoQualidade.css'

// ── Contrato de dados ───────────────────────────────────────────────────────

/** `GET /v1/quality/dashboard/summary` → data.summary */
interface ResumoPainel {
  pieces_total: number
  ok_pct: number
  nok_count: number
  rework_active: number
  stations_active: number
  stations_total: number
}

/** `GET /v1/quality/dashboard/stations` → data.stations[] */
interface Estacao {
  id: string
  station_code: string | null
  name: string | null
  operator: { id: string; name: string | null } | null
  active_piece: {
    op: string | null
    code: string | null
    product_type: string | null
    status: string | null
    status_label: string | null
  } | null
}

/** `GET /v1/quality/gate/stats/rework` → data.stats */
interface EstatisticaRetrabalho {
  by_validation: Record<string, number>
  avg_rework_duration_seconds: number
  most_common_defect: string | null
}

/** `GET /v1/quality/inspections/summary` → as métricas vêm DIRETO em `data`. */
interface ResumoInspecoes {
  total: number
  ok: number
  nok: number
  nok_rate: number
  pending_feedback: number
  confirmed: number
  rejected: number
  retrain_requested: number
  cep_alerts_count: number
  defect_distribution: Record<string, number>
}

/** `GET /v1/quality/gate/pieces` → data.pieces[] (SELECT * de quality_pieces) */
interface Peca {
  id: string
  piece_number: string | null
  work_order: string | null
  product_type: string | null
  status: string
  current_station: string | null
  started_at: string | null
  completed_at: string | null
  total_rework_count: number
  total_rework_time_seconds: number | null
  wiser_exported: boolean | null
  wiser_exported_at: string | null
}

/** `GET /v1/quality/gate/reworks` → data.reworks[] */
interface Retrabalho {
  id: string
  validation_type: string | null
  defect_type: string | null
  defect_description: string | null
  started_at: string | null
  completed_at: string | null
  duration_seconds: number | null
  attempt_number: number | null
  notes: string | null
}

/** `GET /v1/quality/reports/shift` → data */
interface RelatorioTurno {
  shift: string
  date: string
  total: number
  total_ok: number
  total_nok: number
  /** fração 0..1 aqui (round(...,4)) — em /inspections/summary é 0..100. */
  nok_rate: number
  defect_pareto: Array<{ defect_class: string; count: number; pct: number }>
}

type Tom = 'neutro' | 'ok' | 'atencao' | 'nc'

// ── Rotas (uma constante por rota: a mensagem de erro cita a rota real) ──────

const R_RESUMO = '/v1/quality/dashboard/summary'
const R_ESTACOES = '/v1/quality/dashboard/stations'
const R_RETRABALHO = '/v1/quality/gate/stats/rework'
const R_INSPECOES = '/v1/quality/inspections/summary'
const R_PECAS = '/v1/quality/gate/pieces'
const R_REWORKS = '/v1/quality/gate/reworks'
const R_TURNO = '/v1/quality/reports/shift'
const R_CATEGORIAS = '/v1/quality/defect-categories'
const R_CAMERAS = '/v1/quality/cameras'

// ── Helpers ─────────────────────────────────────────────────────────────────

function statusDe(err: unknown): string {
  if (err instanceof ApiError) return String(err.status)
  const m = err instanceof Error ? /HTTP (\d{3})/.exec(err.message) : null
  return m ? m[1] : 'falhou'
}

const inteiro = (n: number) => n.toLocaleString('pt-BR')
const umaCasa = (n: number) => n.toLocaleString('pt-BR', { maximumFractionDigits: 1 })

/** 372 → "6:12". Só para segundos que a API devolveu ou que saem de 2 datas. */
function mmss(segundos: number): string {
  const total = Math.max(0, Math.round(segundos))
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`
}

/** Hora local de um ISO. `null` quando a data não veio ou não é data. */
function hora(iso: string | null): string | null {
  if (!iso) return null
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? null
    : d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
}

/**
 * Tempo de ciclo da peça. Não é dado inventado: é a subtração de dois
 * timestamps que `/gate/pieces` devolve. Peça não concluída não tem ciclo —
 * e nesse caso a coluna fica vazia em vez de mostrar um cronômetro correndo
 * que ninguém pediu.
 */
function ciclo(peca: Peca): string | null {
  if (!peca.started_at || !peca.completed_at) return null
  const ini = new Date(peca.started_at).getTime()
  const fim = new Date(peca.completed_at).getTime()
  if (Number.isNaN(ini) || Number.isNaN(fim) || fim < ini) return null
  return mmss((fim - ini) / 1000)
}

/**
 * Os 11 status da máquina de estados, com o MESMO rótulo do backend
 * (`gate_repository._STATUS_LABEL`) — que só é aplicado em `/dashboard/stations`.
 * Os 3 rótulos do desenho ("Concluída"/"Em revisão"/"NC em revisão") NÃO são
 * bijetivos com estes 11; colapsar 11 em 3 é regra de produto, e regra de
 * produto não se inventa no front. Então: cada status com seu nome.
 */
const STATUS: Record<string, { rotulo: string; tom: Tom }> = {
  idle: { rotulo: 'Aguardando', tom: 'neutro' },
  identified: { rotulo: 'Identificada', tom: 'neutro' },
  validating_v1: { rotulo: 'Inspeção V1', tom: 'neutro' },
  rework_v1: { rotulo: 'Retrabalho V1', tom: 'atencao' },
  validating_v2: { rotulo: 'Inspeção V2', tom: 'neutro' },
  rework_v2: { rotulo: 'Retrabalho V2', tom: 'atencao' },
  waiting_bench_b: { rotulo: 'Aguarda Bancada B', tom: 'neutro' },
  validating_v3: { rotulo: 'Inspeção V3', tom: 'neutro' },
  rework_v3: { rotulo: 'Retrabalho V3', tom: 'atencao' },
  approved: { rotulo: 'Aprovada', tom: 'ok' },
  rejected: { rotulo: 'Rejeitada', tom: 'nc' },
}

const BANCADA: Record<string, string> = { bench_a: 'Bancada A', bench_b: 'Bancada B' }

/** Turnos do backend — `_current_shift()` deriva da hora UTC. */
const TURNOS: Array<[string, string]> = [
  ['morning', 'Manhã (06–14 UTC)'],
  ['afternoon', 'Tarde (14–22 UTC)'],
  ['night', 'Noite (22–06 UTC)'],
]

/** Estado = cor + ÍCONE + palavra. Nunca só a cor. */
function IconeTom({ tom }: { tom: Tom }) {
  const props = { size: 14, strokeWidth: 2, 'aria-hidden': true } as const
  if (tom === 'ok') return <CheckCircle2 {...props} />
  if (tom === 'nc') return <XCircle {...props} />
  if (tom === 'atencao') return <RotateCcw {...props} />
  return <CircleDashed {...props} />
}

// ── Busca: um hook, os quatro estados ───────────────────────────────────────

interface Busca<T> {
  dados: T | null
  carregando: boolean
  erro: string | null
  recarregar: () => void
}

/** `rota = null` → não busca nada (usado quando a aba não está aberta). */
function useRota<T>(rota: string | null): Busca<T> {
  const [dados, setDados] = useState<T | null>(null)
  const [carregando, setCarregando] = useState(rota !== null)
  const [erro, setErro] = useState<string | null>(null)
  const [tentativa, setTentativa] = useState(0)

  useEffect(() => {
    if (rota === null) {
      setDados(null)
      setCarregando(false)
      setErro(null)
      return
    }
    let vivo = true
    setCarregando(true)
    setErro(null)
    api
      .get<{ data: T }>(rota)
      .then((r) => {
        if (vivo) {
          setDados(r.data)
          setErro(null)
        }
      })
      .catch((err) => {
        if (vivo) {
          setDados(null)
          setErro(statusDe(err))
        }
      })
      .finally(() => {
        if (vivo) setCarregando(false)
      })
    return () => {
      vivo = false
    }
  }, [rota, tentativa])

  const recarregar = useCallback(() => setTentativa((t) => t + 1), [])
  return { dados, carregando, erro, recarregar }
}

/** Falha de UM cartão não derruba o painel: ela aparece no lugar do cartão. */
function BlocoErro({ rota, codigo, aoTentar }: { rota: string; codigo: string; aoTentar: () => void }) {
  return (
    <div className={s.centro}>
      <AlertTriangle size={30} strokeWidth={1.5} aria-hidden="true" className={s.aviso.nc} />
      <span className={s.centroTitulo}>Falha ao carregar</span>
      <span className={s.centroCodigo}>
        GET /api{rota} · {codigo}
      </span>
      <button type="button" className={s.botaoCentro} onClick={aoTentar}>
        Tentar novamente
      </button>
    </div>
  )
}

function Carregando({ rotulo }: { rotulo: string }) {
  return (
    <div className={s.centro}>
      <LogikosLoader estado="waiting" variante="tile" rotulo={rotulo} />
    </div>
  )
}

/** Uma barra do gráfico horizontal: rótulo, trilho proporcional e contagem. */
function Barra({
  rotulo,
  mono,
  valor,
  maximo,
  tom,
}: {
  rotulo: string
  mono?: boolean
  valor: number
  maximo: number
  tom: Tom
}) {
  const largura = maximo > 0 ? Math.round((valor / maximo) * 100) : 0
  const preenche = tom === 'nc' ? s.preenchimento.nc : tom === 'atencao' ? s.preenchimento.atencao : s.preenchimento.neutro
  return (
    <div className={s.linhaBarra}>
      <span className={mono ? s.barraCodigo : s.barraNome} title={rotulo}>
        {rotulo}
      </span>
      <div
        className={s.trilho}
        role="img"
        aria-label={`${rotulo}: ${inteiro(valor)}`}
      >
        <div className={preenche} style={{ width: `${largura}%` }} />
      </div>
      <span className={s.barraNumero}>{inteiro(valor)}</span>
    </div>
  )
}

// ── D1 · Dashboard ──────────────────────────────────────────────────────────

type Periodo = 'hoje' | 'sete' | 'trinta'

function intervaloDe(periodo: Periodo): { de: Date; ate: Date } {
  const ate = new Date()
  const de = new Date()
  de.setHours(0, 0, 0, 0)
  if (periodo === 'sete') de.setDate(de.getDate() - 6)
  if (periodo === 'trinta') de.setDate(de.getDate() - 29)
  return { de, ate }
}

function PainelDashboard({ periodo, aoIrParaPecas }: { periodo: Periodo; aoIrParaPecas: () => void }) {
  const resumo = useRota<{ summary: ResumoPainel }>(R_RESUMO)
  const estacoes = useRota<{ stations: Estacao[] }>(R_ESTACOES)
  const retrabalho = useRota<{ stats: EstatisticaRetrabalho }>(R_RETRABALHO)
  const categorias = useRota<{ categories: Array<{ slug: string; label: string }> }>(R_CATEGORIAS)

  const rotaInspecoes = useMemo(() => {
    const { de, ate } = intervaloDe(periodo)
    const q = new URLSearchParams({ date_from: de.toISOString(), date_to: ate.toISOString() })
    return `${R_INSPECOES}?${q.toString()}`
  }, [periodo])
  const inspecoes = useRota<ResumoInspecoes>(rotaInspecoes)

  if (resumo.carregando) return <Carregando rotulo="CARREGANDO GESTÃO" />
  if (resumo.erro || !resumo.dados) {
    return <BlocoErro rota={R_RESUMO} codigo={resumo.erro ?? 'sem dados'} aoTentar={resumo.recarregar} />
  }

  const r = resumo.dados.summary
  const insp = inspecoes.dados
  const rotuloCategoria = (slug: string) =>
    categorias.dados?.categories.find((c) => c.slug === slug)?.label ?? slug

  const distribuicao = Object.entries(insp?.defect_distribution ?? {}).sort((a, b) => b[1] - a[1])
  const maxClasse = distribuicao.length ? distribuicao[0][1] : 0

  const porValidacao = Object.entries(retrabalho.dados?.stats.by_validation ?? {}).sort(
    (a, b) => b[1] - a[1],
  )
  const maxValidacao = porValidacao.length ? porValidacao[0][1] : 0
  const media = retrabalho.dados?.stats.avg_rework_duration_seconds ?? 0

  return (
    <>
      {/*
        Seis KPIs, como no desenho — mas os seis que existem. "% dúvida" e
        "latência p95" saíram (ver cabeçalho); entraram "retrabalho ativo" e
        "estações", que são medidas do mesmo `dashboard/summary`.
      */}
      <div className={s.gradeKpis}>
        <div className={s.kpi.neutro}>
          <span className={s.kpiRotulo}>Peças hoje</span>
          <span className={s.kpiValor.neutro}>{inteiro(r.pieces_total)}</span>
          <span className={s.kpiSub}>criadas desde 00:00 — sempre hoje, a rota não aceita período</span>
        </div>
        <div className={s.kpi.ok}>
          <span className={s.kpiRotulo}>% peças aprovadas</span>
          <span className={s.kpiValor.ok}>{umaCasa(r.ok_pct)}</span>
          <span className={s.kpiSub}>peças com status “aprovada”, não % de fotos</span>
        </div>
        <div className={s.kpi.nc}>
          <span className={s.kpiRotulo}>Peças com NC hoje</span>
          <span className={s.kpiValor.nc}>{inteiro(r.nok_count)}</span>
          <span className={s.kpiSub}>peças que precisaram de retrabalho hoje</span>
        </div>
        <div className={s.kpi.atencao}>
          <span className={s.kpiRotulo}>Retrabalho ativo</span>
          <span className={s.kpiValor.atencao}>{inteiro(r.rework_active)}</span>
          <span className={s.kpiSub}>em retrabalho agora — sem recorte de data</span>
        </div>
        <div className={s.kpi.neutro}>
          <span className={s.kpiRotulo}>Estações ocupadas</span>
          <span className={s.kpiValor.neutro}>
            {inteiro(r.stations_active)}/{inteiro(r.stations_total)}
          </span>
          <span className={s.kpiSub}>com peça em curso, sobre as estações ativas</span>
        </div>
        <div className={s.kpi.atencao}>
          <span className={s.kpiRotulo}>Fila de revisão</span>
          <span className={s.kpiValor.atencao}>
            {inspecoes.erro || !insp ? '—' : inteiro(insp.pending_feedback)}
          </span>
          <span className={s.kpiSub}>
            {inspecoes.erro
              ? `GET /api${R_INSPECOES} · ${inspecoes.erro}`
              : 'inspeções aguardando decisão humana no período'}
          </span>
        </div>
      </div>

      <div className={s.grade3}>
        {/* Onde o desenho pede "por ponto" — e o backend só tem "por etapa". */}
        <section className={s.cartao} aria-labelledby="q-retrabalho">
          <div className={s.eventoLinha}>
            <span className={s.cartaoTitulo} id="q-retrabalho">
              Retrabalho por etapa de validação
            </span>
          </div>
          {retrabalho.carregando && <LogikosLoader estado="waiting" variante="spinner" />}
          {retrabalho.erro && (
            <span className={s.aviso.nc}>
              <AlertTriangle size={15} strokeWidth={1.7} aria-hidden="true" />
              GET /api{R_RETRABALHO} · {retrabalho.erro}
            </span>
          )}
          {!retrabalho.carregando && !retrabalho.erro && porValidacao.length === 0 && (
            <span className={s.aviso.neutro}>
              <Inbox size={15} strokeWidth={1.7} aria-hidden="true" />
              Nenhum retrabalho registrado.
            </span>
          )}
          {porValidacao.map(([tipo, n]) => (
            <Barra key={tipo} rotulo={tipo.toUpperCase()} mono valor={n} maximo={maxValidacao} tom="nc" />
          ))}
          <p className={s.nota}>
            O eixo é <span className={s.dado}>validation_type</span> (V1/V2/V3 = etapa da bancada),
            não o ponto P1/P2/P4/P8 do desenho — nenhuma rota agrega por ponto. Agrega o histórico
            inteiro: a rota não aceita período.
            {media > 0 && (
              <>
                {' '}Duração média de um retrabalho: <span className={s.dado}>{mmss(media)}</span> (média
                única, não por ponto × estação).
              </>
            )}
          </p>
        </section>

        {/* "Por classe" do desenho = defect_category, 5 slugs fixos de classes.py. */}
        <section className={s.cartao} aria-labelledby="q-categoria">
          <div className={s.eventoLinha}>
            <span className={s.cartaoTitulo} id="q-categoria">
              Por categoria de defeito
            </span>
            <button type="button" className={s.ligacao} onClick={aoIrParaPecas}>
              ver peças →
            </button>
          </div>
          {inspecoes.carregando && <LogikosLoader estado="waiting" variante="spinner" />}
          {inspecoes.erro && (
            <span className={s.aviso.nc}>
              <AlertTriangle size={15} strokeWidth={1.7} aria-hidden="true" />
              GET /api{R_INSPECOES} · {inspecoes.erro}
            </span>
          )}
          {!inspecoes.carregando && !inspecoes.erro && distribuicao.length === 0 && (
            <span className={s.aviso.neutro}>
              <Inbox size={15} strokeWidth={1.7} aria-hidden="true" />
              Nenhuma inspeção com categoria de defeito no período.
            </span>
          )}
          {distribuicao.map(([slug, n]) => (
            <Barra key={slug} rotulo={rotuloCategoria(slug)} valor={n} maximo={maxClasse} tom="nc" />
          ))}
          <p className={s.nota}>
            Categorias fixas do módulo (visual, dimensional, superfície, montagem, outro) — não a
            taxonomia RVB. Nenhuma rota cruza categoria com discordância do operador.
          </p>
        </section>

        {/* Fila de revisão: o tamanho existe; a IDADE não. */}
        <section className={s.cartao} aria-labelledby="q-fila">
          <span className={s.cartaoTitulo} id="q-fila">
            Fila de revisão
          </span>
          {inspecoes.carregando && <LogikosLoader estado="waiting" variante="spinner" />}
          {inspecoes.erro && (
            <span className={s.aviso.nc}>
              <AlertTriangle size={15} strokeWidth={1.7} aria-hidden="true" />
              GET /api{R_INSPECOES} · {inspecoes.erro}
            </span>
          )}
          {insp && !inspecoes.erro && (
            <>
              <div className={s.linhaNumeros}>
                <div>
                  <span className={s.numeroGrande}>{inteiro(insp.pending_feedback)}</span>
                  <span className={s.numeroLegenda}> pendentes</span>
                </div>
                <div>
                  <span className={s.numeroGrande}>{inteiro(insp.total)}</span>
                  <span className={s.numeroLegenda}> inspeções no período</span>
                </div>
              </div>
              <span className={s.aviso.neutro}>
                <Clock size={15} strokeWidth={1.7} aria-hidden="true" />
                {inteiro(insp.confirmed)} confirmadas · {inteiro(insp.rejected)} rejeitadas ·{' '}
                {inteiro(insp.retrain_requested)} pedidos de retreino
              </span>
              <p className={s.nota}>
                Idade do item mais antigo e tempo médio de decisão não têm agregação em rota
                nenhuma — as colunas <span className={s.dado}>created_at</span> e{' '}
                <span className={s.dado}>feedback_at</span> existem, a conta não.
              </p>
            </>
          )}
        </section>
      </div>

      {/* No lugar de "tempo médio por ponto × estação": as estações reais. */}
      <section className={s.cartao} aria-labelledby="q-estacoes">
        <span className={s.cartaoTitulo} id="q-estacoes">
          Estações
        </span>
        {estacoes.carregando && <LogikosLoader estado="waiting" variante="spinner" />}
        {estacoes.erro && (
          <span className={s.aviso.nc}>
            <AlertTriangle size={15} strokeWidth={1.7} aria-hidden="true" />
            GET /api{R_ESTACOES} · {estacoes.erro}
          </span>
        )}
        {!estacoes.carregando && !estacoes.erro && (estacoes.dados?.stations.length ?? 0) === 0 && (
          <span className={s.aviso.neutro}>
            <Inbox size={15} strokeWidth={1.7} aria-hidden="true" />
            Nenhuma estação ativa cadastrada.
          </span>
        )}
        {(estacoes.dados?.stations.length ?? 0) > 0 && (
          <div className={s.gradeEstacoes}>
            {estacoes.dados?.stations.map((e) => (
              <div key={e.id} className={s.estacao}>
                <div className={s.estacaoTopo}>
                  <span className={s.estacaoCodigo}>{e.station_code ?? '—'}</span>
                  <span className={s.estacaoNome}>{e.name ?? 'sem nome'}</span>
                </div>
                <span className={s.estacaoNome}>
                  Operador: {e.operator?.name ?? 'sem operador na peça'}
                </span>
                {e.active_piece ? (
                  <span className={s.aviso.neutro}>
                    <IconeTom tom={STATUS[e.active_piece.status ?? '']?.tom ?? 'neutro'} />
                    <span className={s.dado}>{e.active_piece.code ?? 'sem código'}</span> ·{' '}
                    {e.active_piece.op ?? 'sem OP'} · {e.active_piece.status_label || 'sem status'}
                  </span>
                ) : (
                  <span className={s.aviso.neutro}>
                    <CircleDashed size={15} strokeWidth={1.7} aria-hidden="true" />
                    Sem peça em curso
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
        <p className={s.nota}>
          Os campos <span className={s.dado}>online</span> e{' '}
          <span className={s.dado}>shift_stats</span> desta rota são valores fixos no código do
          backend (sempre “true” e sempre 0/0) — por isso não estão na tela. Tempo por ponto ×
          estação e meta por ponto não existem em tabela nenhuma.
        </p>
      </section>
    </>
  )
}

// ── D2 · Peças & OPs ────────────────────────────────────────────────────────

const POR_PAGINA = 20

function PainelPecas() {
  const [status, setStatus] = useState('')
  const [op, setOp] = useState('')
  const [opAplicada, setOpAplicada] = useState('')
  const [pagina, setPagina] = useState(1)
  const [selecionada, setSelecionada] = useState<string | null>(null)

  const rota = useMemo(() => {
    const q = new URLSearchParams({ page: String(pagina), per_page: String(POR_PAGINA) })
    if (status) q.set('status', status)
    if (opAplicada) q.set('work_order', opAplicada)
    return `${R_PECAS}?${q.toString()}`
  }, [status, opAplicada, pagina])

  const pecas = useRota<{ pieces: Peca[] }>(rota)
  const lista = pecas.dados?.pieces ?? []

  // A peça selecionada continua sendo a que o usuário clicou enquanto ela
  // estiver na página; ao trocar de filtro/página, cai para a primeira.
  const atual = lista.find((p) => p.id === selecionada) ?? lista[0] ?? null

  const rotaReworks = atual ? `${R_REWORKS}?piece_id=${encodeURIComponent(atual.id)}&per_page=50` : null
  const reworks = useRota<{ reworks: Retrabalho[] }>(rotaReworks)

  const aplicar = (e: React.FormEvent) => {
    e.preventDefault()
    setPagina(1)
    setOpAplicada(op.trim())
  }

  return (
    <>
      <form className={s.filtros} onSubmit={aplicar}>
        <div className={s.campo}>
          <label className={s.rotulo} htmlFor="q-status">
            Status
          </label>
          <select
            id="q-status"
            className={s.seletor}
            value={status}
            onChange={(e) => {
              setPagina(1)
              setStatus(e.target.value)
            }}
          >
            <option value="">Todos</option>
            {Object.entries(STATUS).map(([chave, v]) => (
              <option key={chave} value={chave}>
                {v.rotulo}
              </option>
            ))}
          </select>
        </div>
        <div className={s.campo}>
          <label className={s.rotulo} htmlFor="q-op">
            Ordem de produção
          </label>
          <input
            id="q-op"
            className={s.entradaTexto}
            value={op}
            placeholder="OP exata"
            onChange={(e) => setOp(e.target.value)}
          />
        </div>
        <button type="submit" className={s.botaoPagina}>
          Filtrar
        </button>
        {/*
          Período fica de fora daqui de propósito: `/gate/pieces` LÊ só `status`
          e `work_order`; `date_from`/`date_to`/`product_type` chegam ao backend
          e são descartados em silêncio. Filtro que não filtra é pior que filtro
          que não existe — o usuário confia no recorte.
        */}
        <span className={s.aviso.neutro}>
          A rota só filtra por status e OP. Data e tipo de produto são ignorados pelo backend.
        </span>
      </form>

      {pecas.carregando && <Carregando rotulo="CARREGANDO PEÇAS" />}

      {pecas.erro && (
        <BlocoErro rota={R_PECAS} codigo={pecas.erro} aoTentar={pecas.recarregar} />
      )}

      {!pecas.carregando && !pecas.erro && lista.length === 0 && (
        <div className={s.centro}>
          <Inbox size={30} strokeWidth={1.5} aria-hidden="true" className={s.aviso.neutro} />
          <span className={s.centroTitulo}>Nenhuma peça neste recorte</span>
          <span className={s.centroTexto}>
            {status || opAplicada
              ? 'Nenhuma peça com esse status/OP. Limpe o filtro para ver todas.'
              : 'Nenhuma peça registrada no quality gate deste tenant.'}
          </span>
          {(status || opAplicada) && (
            <button
              type="button"
              className={s.botaoCentro}
              onClick={() => {
                setStatus('')
                setOp('')
                setOpAplicada('')
                setPagina(1)
              }}
            >
              Limpar filtros
            </button>
          )}
        </div>
      )}

      {!pecas.carregando && !pecas.erro && lista.length > 0 && (
        <div className={s.colunasD2}>
          <div className={s.listaPecas} role="group" aria-label="Peças">
            {lista.map((p) => {
              const st = STATUS[p.status] ?? { rotulo: p.status, tom: 'neutro' as Tom }
              const t = ciclo(p)
              return (
                <button
                  type="button"
                  key={p.id}
                  aria-pressed={atual?.id === p.id}
                  className={atual?.id === p.id ? s.peca.selecionada : s.peca.normal}
                  onClick={() => setSelecionada(p.id)}
                >
                  <span className={s.pecaCodigo}>{p.piece_number ?? 'sem código'}</span>
                  <span className={s.pecaOp}>{p.work_order ?? 'sem OP'}</span>
                  <span className={s.pecaTipo}>{p.product_type ?? 'sem tipo'}</span>
                  <span className={s.pecaRetrabalho}>
                    {p.total_rework_count > 0 ? `${p.total_rework_count} retrab.` : 'sem retrab.'}
                  </span>
                  <span className={s.situacao[st.tom]} title={`status: ${p.status}`}>
                    <IconeTom tom={st.tom} />
                    {st.rotulo}
                  </span>
                  <span className={s.pecaCiclo} title={t ? 'tempo de ciclo (início → conclusão)' : 'peça sem conclusão registrada'}>
                    {t ?? '—'}
                  </span>
                </button>
              )
            })}

            {/*
              `total` desta rota é `len(pieces)` da PÁGINA, não a contagem real —
              então não existe "página 2 de 7" honesta. O que dá para afirmar:
              se a página veio cheia, pode haver mais.
            */}
            <div className={s.paginacao}>
              <button
                type="button"
                className={s.botaoPagina}
                disabled={pagina === 1}
                onClick={() => setPagina((n) => Math.max(1, n - 1))}
              >
                ← Anterior
              </button>
              <span className={s.rotulo}>Página {pagina}</span>
              <button
                type="button"
                className={s.botaoPagina}
                disabled={lista.length < POR_PAGINA}
                onClick={() => setPagina((n) => n + 1)}
              >
                Próxima →
              </button>
              <span className={s.aviso.neutro}>
                A rota não devolve a contagem total — só dá para saber se a página encheu.
              </span>
            </div>
          </div>

          {atual && (
            <aside className={s.painel} aria-label="Detalhe da peça">
              <div className={s.painelTopo}>
                <span className={s.painelCodigo}>{atual.piece_number ?? 'sem código'}</span>
                <span className={s.painelMeta}>
                  {atual.work_order ?? 'sem OP'} · {atual.product_type ?? 'sem tipo'}
                  {atual.current_station && ` · ${BANCADA[atual.current_station] ?? atual.current_station}`}
                </span>
              </div>

              <span className={s.aviso.neutro}>
                <IconeTom tom={(STATUS[atual.status] ?? { tom: 'neutro' as Tom }).tom} />
                {(STATUS[atual.status] ?? { rotulo: atual.status }).rotulo}
                {atual.wiser_exported ? ' · exportada para o WISER' : ' · não exportada para o WISER'}
                {atual.wiser_exported_at && ` (${hora(atual.wiser_exported_at) ?? atual.wiser_exported_at})`}
              </span>

              <span className={s.overline}>Retrabalhos da peça</span>

              {reworks.carregando && <LogikosLoader estado="waiting" variante="spinner" />}
              {reworks.erro && (
                <span className={s.aviso.nc}>
                  <AlertTriangle size={15} strokeWidth={1.7} aria-hidden="true" />
                  GET /api{R_REWORKS} · {reworks.erro}
                </span>
              )}
              {!reworks.carregando && !reworks.erro && (reworks.dados?.reworks.length ?? 0) === 0 && (
                <span className={s.aviso.neutro}>
                  <CheckCircle2 size={15} strokeWidth={1.7} aria-hidden="true" />
                  Nenhum retrabalho registrado para esta peça.
                </span>
              )}

              {(reworks.dados?.reworks.length ?? 0) > 0 && (
                <div className={s.linhaTempo}>
                  {reworks.dados?.reworks.map((rw) => (
                    <div key={rw.id} className={s.evento}>
                      {/*
                        A caixa de foto do desenho fica — vazia. `photo_before_r2_key`
                        e `photo_after_r2_key` são strings, e não existe rota que
                        assine a URL delas (só `/inspections/<id>/evidence-url`, que
                        é de outra tabela). Miniatura quebrada seria pior.
                      */}
                      <span
                        className={s.semFoto}
                        title="Sem rota que assine a URL das fotos do gate — o backend guarda só o caminho no R2."
                      >
                        sem foto
                      </span>
                      <div className={s.eventoCorpo}>
                        <div className={s.eventoLinha}>
                          <span className={s.eventoCodigo}>
                            {(rw.validation_type ?? '—').toUpperCase()}
                          </span>
                          <span className={s.aviso.atencao}>
                            <RotateCcw size={14} strokeWidth={2} aria-hidden="true" />
                            {rw.defect_type ?? 'defeito não informado'}
                            {rw.attempt_number ? ` · tentativa ${rw.attempt_number}` : ''}
                          </span>
                          <span className={s.eventoHora}>{hora(rw.started_at) ?? '—'}</span>
                        </div>
                        <span className={s.eventoDetalhe}>
                          {rw.defect_description ?? 'sem descrição'}
                          {rw.duration_seconds != null && ` · ${mmss(rw.duration_seconds)}`}
                          {rw.completed_at ? '' : ' · em aberto'}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <div className={s.rodapePainel}>
                A linha do tempo por PONTO (P1/P2/P4/P8) do desenho não existe: o único campo com
                noção de ponto é <span className={s.dado}>inspection_sessions.stage</span>, e o
                vínculo com a peça está quebrado no banco —{' '}
                <span className={s.dado}>piece_id</span> lá é texto, aqui é UUID. O que a peça de
                fato guarda são os retrabalhos acima.
              </div>
            </aside>
          )}
        </div>
      )}
    </>
  )
}

// ── D3 · Relatórios ─────────────────────────────────────────────────────────

function hojeISO(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function PainelRelatorios() {
  const { can } = useAuth()
  const podeExportar = can('reports:export')

  const [turno, setTurno] = useState('morning')
  const [data, setData] = useState(hojeISO)
  const [camera, setCamera] = useState('')

  const cameras = useRota<{ cameras: Array<{ id: string; name: string }> }>(R_CAMERAS)

  const rota = useMemo(() => {
    const q = new URLSearchParams({ shift: turno, shift_date: data })
    if (camera) q.set('camera_id', camera)
    return `${R_TURNO}?${q.toString()}`
  }, [turno, data, camera])

  const relatorio = useRota<RelatorioTurno>(rota)
  const rel = relatorio.dados

  return (
    <>
      <div className={s.filtros}>
        <div className={s.campo}>
          <label className={s.rotulo} htmlFor="q-turno">
            Turno
          </label>
          <select
            id="q-turno"
            className={s.seletor}
            value={turno}
            onChange={(e) => setTurno(e.target.value)}
          >
            {TURNOS.map(([v, r]) => (
              <option key={v} value={v}>
                {r}
              </option>
            ))}
          </select>
        </div>
        <div className={s.campo}>
          <label className={s.rotulo} htmlFor="q-data">
            Data
          </label>
          <input
            id="q-data"
            type="date"
            className={s.entradaData}
            value={data}
            onChange={(e) => setData(e.target.value)}
          />
        </div>
        <div className={s.campo}>
          <label className={s.rotulo} htmlFor="q-camera">
            Câmera
          </label>
          <select
            id="q-camera"
            className={s.seletor}
            value={camera}
            onChange={(e) => setCamera(e.target.value)}
          >
            <option value="">Todas as câmeras</option>
            {cameras.dados?.cameras.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>

        <span className={s.espacador} />

        {/*
          Os dois botões do desenho ficam no lugar, desabilitados, dizendo por
          quê. "Exportar WISER" não tem rota nenhuma: a exportação acontece
          sozinha no GateService quando a peça é aprovada, e num varredor Celery
          de reenvio. O front ANTIGO chama POST .../export-wiser e ele responde
          404 hoje. O CSV é a mesma história.
        */}
        <button
          type="button"
          className={s.botaoPrimario}
          disabled
          title="Sem rota: não existe endpoint de exportação WISER. A exportação é disparada pelo serviço quando a peça é aprovada e por um reenvio automático — não pela tela."
        >
          Exportar WISER
        </button>
        <button
          type="button"
          className={s.botaoSecundario}
          disabled
          title="Sem rota: GET /v1/quality/gate/pieces/export não existe no backend (o front antigo já chama e recebe 404)."
        >
          CSV
        </button>
      </div>

      {!podeExportar && (
        <span className={s.aviso.neutro}>
          <AlertTriangle size={15} strokeWidth={1.7} aria-hidden="true" />
          Seu perfil também não tem <span className={s.dado}>reports:export</span> — quando as rotas
          de exportação existirem, será preciso essa permissão.
        </span>
      )}

      {relatorio.carregando && <Carregando rotulo="CARREGANDO RELATÓRIO" />}

      {relatorio.erro && (
        <BlocoErro rota={R_TURNO} codigo={relatorio.erro} aoTentar={relatorio.recarregar} />
      )}

      {rel && !relatorio.carregando && !relatorio.erro && (
        <>
          <div className={s.gradeKpis}>
            <div className={s.kpi.neutro}>
              <span className={s.kpiRotulo}>Inspeções</span>
              <span className={s.kpiValor.neutro}>{inteiro(rel.total)}</span>
              <span className={s.kpiSub}>no turno e data escolhidos</span>
            </div>
            <div className={s.kpi.ok}>
              <span className={s.kpiRotulo}>Conformes</span>
              <span className={s.kpiValor.ok}>{inteiro(rel.total_ok)}</span>
              <span className={s.kpiSub}>resultado “ok”</span>
            </div>
            <div className={s.kpi.nc}>
              <span className={s.kpiRotulo}>Não conformes</span>
              <span className={s.kpiValor.nc}>{inteiro(rel.total_nok)}</span>
              <span className={s.kpiSub}>resultado “nok”</span>
            </div>
            <div className={s.kpi.nc}>
              <span className={s.kpiRotulo}>% não conforme</span>
              <span className={s.kpiValor.nc}>{umaCasa(rel.nok_rate * 100)}</span>
              <span className={s.kpiSub}>sobre as inspeções do turno</span>
            </div>
          </div>

          {rel.defect_pareto.length === 0 ? (
            <div className={s.centro}>
              <Inbox size={30} strokeWidth={1.5} aria-hidden="true" className={s.aviso.neutro} />
              <span className={s.centroTitulo}>Sem defeitos classificados neste turno</span>
              <span className={s.centroTexto}>
                {rel.total === 0
                  ? 'Nenhuma inspeção registrada neste turno e data.'
                  : 'Houve inspeções, mas nenhuma com classe de defeito preenchida.'}
              </span>
            </div>
          ) : (
            <div className={s.tabela} role="group" aria-label="Pareto de defeitos do turno">
              <div className={s.cabecalhoCelula}>Classe de defeito</div>
              <div className={s.cabecalhoCelula} style={{ textAlign: 'right' }}>
                Inspeções
              </div>
              <div className={s.cabecalhoCelula} style={{ textAlign: 'right' }}>
                % das NC
              </div>
              {rel.defect_pareto.map((linha) => (
                <div key={linha.defect_class} style={{ display: 'contents' }}>
                  <span className={s.celula.texto}>{linha.defect_class}</span>
                  <span className={s.celula.numero}>{inteiro(linha.count)}</span>
                  <span className={s.celula.numero}>{umaCasa(linha.pct * 100)}%</span>
                </div>
              ))}
            </div>
          )}

          <p className={s.nota}>
            O corte é por <span className={s.dado}>defect_class</span> — coluna livre de{' '}
            <span className={s.dado}>quality_inspections</span>, diferente do{' '}
            <span className={s.dado}>defect_category</span> usado no painel. As colunas PONTO /
            FOTOS / RETRABALHO MÉD. do desenho não têm agregação em rota nenhuma, e “corte por
            ponto” e “por classe” não existem como endpoint: só “por turno”, um turno e um dia por
            chamada.
          </p>
        </>
      )}
    </>
  )
}

// ── Tela ────────────────────────────────────────────────────────────────────

type Aba = 'd1' | 'd2' | 'd3'

const ABAS: Array<[Aba, string]> = [
  ['d1', 'Dashboard'],
  ['d2', 'Peças & OPs'],
  ['d3', 'Relatórios'],
]

export function GestaoQualidade() {
  const { hasModule } = useAuth()
  const [aba, setAba] = useState<Aba>('d1')
  const [periodo, setPeriodo] = useState<Periodo>('hoje')

  // Módulo desligado (nota do cético do flip): sem isto os painéis chamariam
  // as rotas de qualquer jeito e tomariam 403 cru — mesmo tratamento do KPI
  // "sem fonte" de Retrabalhos em Qualidade.tsx.
  if (!hasModule('quality')) {
    return (
      <div className={s.centro}>
        <Lock size={30} strokeWidth={1.5} aria-hidden="true" />
        <span className={s.centroTitulo}>Módulo não habilitado</span>
        <span className={s.centroTexto}>
          O módulo Qualidade (<code>quality</code>) não está habilitado nesta sessão. Peça
          ao administrador do seu tenant.
        </span>
      </div>
    )
  }

  return (
    <div className={s.raiz}>
      <div className={s.cabecalho}>
        <h1 className={s.titulo}>Gestão</h1>
        <div className={s.abas} role="tablist" aria-label="Seções da gestão de qualidade">
          {ABAS.map(([chave, rotulo]) => (
            <button
              key={chave}
              type="button"
              role="tab"
              id={`q-aba-${chave}`}
              aria-controls="q-painel"
              aria-selected={aba === chave}
              className={aba === chave ? s.aba.ativa : s.aba.inativa}
              onClick={() => setAba(chave)}
            >
              {rotulo}
            </button>
          ))}
        </div>
        <span className={s.espacador} />
        {/*
          O seletor de período só aparece em D1 porque só lá ele muda alguma
          coisa (`/inspections/summary` é a única rota de qualidade que aceita
          date_from/date_to). Em D2 e D3 o recorte é outro — status/OP e
          turno/data — e mostrar um período que o backend ignora seria dizer que
          a tela filtra o que ela não filtra.
        */}
        {aba === 'd1' && (
          <>
            <label className={s.rotulo} htmlFor="q-periodo">
              Período das inspeções
            </label>
            <select
              id="q-periodo"
              className={s.seletor}
              value={periodo}
              onChange={(e) => setPeriodo(e.target.value as Periodo)}
            >
              <option value="hoje">Hoje</option>
              <option value="sete">7 dias</option>
              <option value="trinta">30 dias</option>
            </select>
          </>
        )}
      </div>

      {/* Uma aba sem painel associado é aba quebrada para quem usa leitor de
          tela: o `tablist` anuncia 3 opções e nenhuma diz o que controla. */}
      <div id="q-painel" role="tabpanel" aria-labelledby={`q-aba-${aba}`} className={s.painelAba}>
        {aba === 'd1' && <PainelDashboard periodo={periodo} aoIrParaPecas={() => setAba('d2')} />}
        {aba === 'd2' && <PainelPecas />}
        {aba === 'd3' && <PainelRelatorios />}
      </div>
    </div>
  )
}
