/**
 * EPI Dashboard — `/epi/dashboard` (F3 da migração).
 *
 * Desenho: `EPI Dashboard.dc.html`. Layout, medidas e copy são do handoff.
 *
 * ⛔ ZERO DADO INVENTADO — e neste dashboard isso custa caro, porque o desenho
 * pede coisas que o backend HOJE não tem. Cada uma aparece como vazio
 * honesto, nunca como número plausível:
 *
 *  1. **Delta e curva de 7 dias do score.** `/api/modules/epi/stats` devolve o
 *     score do momento e nada de histórico. "+5 vs ontem (82)" e a sparkline
 *     exigiriam uma série de score por dia que não existe em endpoint nenhum.
 *     → o rodapé do cartão diz SEM HISTÓRICO em vez de desenhar uma linha.
 *
 *  2. **Ações (abertas / recentes).** A tela "EPI Ações" tem ZERO endpoints no
 *     contrato de migração (`contrato-dados.js`, 407 entradas) e não existe
 *     `actions:*` no registry de permissões — o mesmo achado que
 *     `navPorPerfil.ts` já registrou. → cartão e painel ficam de pé, marcados
 *     como indisponíveis. Inventar "6 abertas · 2 vencidas" seria prometer um
 *     plano de ação que o produto não guarda em lugar nenhum.
 *
 *  3. **Seletor de site.** Nenhum dos endpoints desta tela aceita escopo de
 *     site (`/modules/epi/stats` é do tenant; `/v1/events/*` filtra por câmera).
 *     → o seletor não entra. Um filtro que não filtra é pior que filtro nenhum:
 *     o operador acha que está olhando a doca e está olhando a fábrica toda.
 *
 *  4. **Conectividade por câmera ("online").** `public.cameras.last_seen`
 *     existe na tabela mas nunca recebe UPDATE em lugar nenhum do código —
 *     o sistema não sabe se uma câmera está transmitindo, só sabe se ela
 *     está cadastrada como ativa (não arquivada). O cartão dizia "Câmeras
 *     online" e derivava "N fora do ar" de `total − ativas`, mas `total`
 *     incluía câmeras ARQUIVADAS (29 = 19 ativas + 10 arquivadas na RVB) —
 *     dois erros empilhados fabricando uma métrica de disponibilidade que
 *     não existe. → cartão agora diz "Câmeras ativas", um número só, com a
 *     legenda admitindo a falta de telemetria. PEDIDO-AO-BACKEND: heartbeat
 *     real por câmera (writer de `last_seen`) para um "online" que signifique
 *     algo.
 *
 * O seletor de TURNO entra porque é real: recorta `from`/`to` dos dois painéis
 * de evento. Os KPIs do topo NÃO são recortáveis por turno (o backend fixa
 * "hoje" e "últimas 24 h"), e o cartão diz isso na legenda em vez de deixar o
 * leitor supor que o filtro alcançou tudo.
 */
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import {
  DndContext,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core'
import { SortableContext, rectSortingStrategy, useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { useQuery } from '@tanstack/react-query'
import {
  ArrowDown,
  ArrowUp,
  BarChart3,
  CheckCircle2,
  GripVertical,
  LayoutGrid,
  ShieldAlert,
  SlidersHorizontal,
  AlertTriangle,
} from 'lucide-react'
import { Link } from 'react-router-dom'

import { useAuth } from '../../hooks/useAuth'
import { moduleService, type ModuleStats } from '../../services/moduleService'
import { eventsService } from '../../services/eventsService'
import { violationLabel } from '../../components/dashboard/widgets/violationLabels'
import { fillBuckets, formatBucketLabel } from '../../utils/timeBuckets'
import { LogikosLoader } from '../shell/LogikosLoader'
import { lk } from '../tokens/lk.css'
import * as s from './Dashboard.css'
import { rotaNova } from '../RotasNovas'

/**
 * `ModuleStats` (serviço compartilhado com o front antigo) só declara as 4
 * chaves originais; `module_service.get_stats` devolve também os KPIs de BI.
 * Declarado aqui, opcional, para não mexer num arquivo que outras telas usam.
 */
type EstatisticasEpi = ModuleStats & { compliance_rate?: number | null }

// ── Turno ───────────────────────────────────────────────────────────────────

type IdTurno = 'primeiro' | 'segundo' | 'dia'

/**
 * ⚠️ Janelas fixas: o backend não expõe os turnos do cliente em lugar nenhum.
 * As horas vão no rótulo de propósito — ninguém precisa adivinhar o que
 * "1º turno" recorta, e no dia em que a janela real do RVB for outra o texto
 * está errado na cara do operador, não escondido no código.
 */
const TURNOS: Array<{ id: IdTurno; rotulo: string; inicio: number; fim: number }> = [
  { id: 'primeiro', rotulo: '1º turno · 06h–14h', inicio: 6, fim: 14 },
  { id: 'segundo', rotulo: '2º turno · 14h–22h', inicio: 14, fim: 22 },
  { id: 'dia', rotulo: 'Dia inteiro · 00h–24h', inicio: 0, fim: 24 },
]

function janelaDoTurno(turno: IdTurno, agora = new Date()) {
  const t = TURNOS.find((x) => x.id === turno) ?? TURNOS[2]
  const inicio = new Date(agora)
  inicio.setHours(t.inicio, 0, 0, 0)
  const fim = new Date(agora)
  // setHours(24) rola para a meia-noite seguinte — é o fim exclusivo do dia.
  fim.setHours(t.fim, 0, 0, 0)
  return { de: inicio.toISOString(), ate: fim.toISOString(), faixa: t }
}

// ── Preferência de widgets (ordem + visibilidade) ───────────────────────────

type IdWidget = 'eventos-hora' | 'violacoes-classe' | 'acoes-recentes' | 'cameras-eventos'

const WIDGETS: Array<{ id: IdWidget; rotulo: string }> = [
  { id: 'eventos-hora', rotulo: 'Eventos por hora' },
  { id: 'violacoes-classe', rotulo: 'Violações por classe' },
  { id: 'acoes-recentes', rotulo: 'Ações recentes' },
  { id: 'cameras-eventos', rotulo: 'Câmeras com mais eventos' },
]

/**
 * Janela fixa de 30 dias para o ranking — não segue o seletor de TURNO (o
 * ranking lê o acumulado do mês, não o recorte do turno escolhido).
 * `_MAX_SUMMARY_DAYS` em `services/api/app/api/v1/events/routes.py` é 92:
 * 30 cabe com folga, sem precisar reduzir a janela nem o rótulo.
 */
const JANELA_RANKING_DIAS = 30
const ROTULO_JANELA_RANKING = `ÚLTIMOS ${JANELA_RANKING_DIAS} DIAS`

const PADRAO: IdWidget[] = WIDGETS.map((w) => w.id)
const CHAVE_PREF = 'lk-epi-dashboard-widgets'

interface Preferencia {
  ordem: IdWidget[]
  ocultos: IdWidget[]
}

/**
 * Tolerante de propósito: storage corrompido, id que já não existe e widget
 * novo que ainda não estava salvo não podem quebrar a tela nem sumir. O que
 * está salvo manda na ordem; o que é novo entra no fim.
 */
function lerPreferencia(): Preferencia {
  const conhecido = (id: unknown): id is IdWidget => PADRAO.includes(id as IdWidget)
  try {
    const cru = JSON.parse(localStorage.getItem(CHAVE_PREF) ?? 'null') as Partial<Preferencia> | null
    const salvos = (cru?.ordem ?? []).filter(conhecido)
    return {
      ordem: [...salvos, ...PADRAO.filter((id) => !salvos.includes(id))],
      ocultos: (cru?.ocultos ?? []).filter(conhecido),
    }
  } catch {
    return { ordem: PADRAO, ocultos: [] }
  }
}

function gravarPreferencia(pref: Preferencia) {
  try {
    localStorage.setItem(CHAVE_PREF, JSON.stringify(pref))
  } catch {
    // Modo privado / cota cheia: a preferência é conveniência, não dado.
  }
}

// ── Peças visuais ───────────────────────────────────────────────────────────

type Severidade = 'ok' | 'atencao' | 'nc' | 'neutro'

const COR: Record<Severidade, string> = {
  ok: lk.estado.ok,
  atencao: lk.estado.atencao,
  nc: lk.estado.nc,
  neutro: lk.cor.cinzaNevoa,
}

/** Estado = cor + ícone + palavra. Os três juntos, sempre — nunca só a cor. */
function Estado({ nivel, palavra }: { nivel: Severidade; palavra: string }) {
  const Icone = nivel === 'ok' ? CheckCircle2 : AlertTriangle
  return (
    <span className={s.estadoLinha} style={{ color: COR[nivel] }}>
      <Icone size={12} strokeWidth={2} aria-hidden="true" />
      {palavra}
    </span>
  )
}

function numero(n: number) {
  return n.toLocaleString('pt-BR')
}

function horaCurta(ms: number) {
  return new Date(ms).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
}

/**
 * Monta o link para `/epi/eventos` na querystring que aquela tela já lê
 * (`start_date`/`end_date`/`camera_id`/`violation_type` — ver `Eventos.tsx`).
 * Não inventa parâmetro novo: só usa o que o destino já suporta.
 */
function linkParaEventos(params: {
  start_date?: string
  end_date?: string
  camera_id?: string
  violation_type?: string
}) {
  const q = new URLSearchParams()
  for (const [chave, valor] of Object.entries(params)) if (valor) q.set(chave, valor)
  const query = q.toString()
  return rotaNova(`/epi/eventos${query ? `?${query}` : ''}`)
}

interface PainelProps {
  id: IdWidget
  titulo: string
  nota?: string
  acao?: ReactNode
  children: ReactNode
}

/** Painel arrastável — a alça é a única área que inicia o arrasto. */
function Painel({ id, titulo, nota, acao, children }: PainelProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id })
  return (
    <section
      ref={setNodeRef}
      className={isDragging ? `${s.painel} ${s.arrastando}` : s.painel}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      aria-label={titulo}
    >
      <div className={s.painelCabecalho}>
        <button
          type="button"
          className={s.alca}
          aria-label={`Mover ${titulo}`}
          {...attributes}
          {...listeners}
        >
          <GripVertical size={14} strokeWidth={2} aria-hidden="true" />
        </button>
        <span className={s.painelTitulo}>{titulo}</span>
        {nota && <span className={s.painelNota}>{nota}</span>}
        {acao}
      </div>
      {children}
    </section>
  )
}

/**
 * Vazio/erro de painel: nunca derruba a tela, sempre diz o que houve. `cta`
 * é o caminho de saída de um vazio de JANELA (turno sem evento) — sem ele o
 * operador fica preso olhando um painel em branco sem saber que 30 dias atrás
 * tem dado.
 */
function VazioPainel({
  texto,
  aoRetentar,
  cta,
}: {
  texto: string
  aoRetentar?: () => void
  cta?: { texto: string; to: string }
}) {
  return (
    <div className={s.painelVazio}>
      <span>{texto}</span>
      {aoRetentar && (
        <button type="button" className={s.botaoRetentar} onClick={aoRetentar}>
          Tentar novamente
        </button>
      )}
      {cta && (
        <Link to={cta.to} className={s.botaoRetentar}>
          {cta.texto}
        </Link>
      )}
    </div>
  )
}

// ── Tela ────────────────────────────────────────────────────────────────────

export function Dashboard() {
  const { can } = useAuth()
  const [turno, setTurno] = useState<IdTurno>('dia')
  const [dicaAberta, setDicaAberta] = useState(false)
  const [personalizar, setPersonalizar] = useState(false)
  const [pref, setPref] = useState<Preferencia>(lerPreferencia)
  const refPersonalizar = useRef<HTMLDivElement>(null)

  // Clique fora fecha. Sem isto o popover só some clicando de volta no botão —
  // e quem abriu por engano fica com ele plantado sobre o primeiro cartão.
  useEffect(() => {
    if (!personalizar) return
    const fora = (e: PointerEvent) => {
      if (!refPersonalizar.current?.contains(e.target as Node)) setPersonalizar(false)
    }
    document.addEventListener('pointerdown', fora)
    return () => document.removeEventListener('pointerdown', fora)
  }, [personalizar])

  const janela = useMemo(() => janelaDoTurno(turno), [turno])

  const estatisticas = useQuery({
    queryKey: ['epi', 'stats'],
    queryFn: () => moduleService.getStats('epi') as Promise<EstatisticasEpi>,
    staleTime: 30_000,
    refetchInterval: 60_000,
  })

  const linhaDoTempo = useQuery({
    queryKey: ['epi', 'timeline', janela.de, janela.ate],
    queryFn: () =>
      eventsService.getTimeline({
        from: janela.de,
        to: janela.ate,
        bucket: 'hour',
        moduleCode: 'epi',
      }),
    staleTime: 30_000,
    refetchInterval: 60_000,
  })

  const resumo = useQuery({
    queryKey: ['epi', 'summary', janela.de, janela.ate],
    queryFn: () => eventsService.getSummary({ from: janela.de, to: janela.ate, moduleCode: 'epi' }),
    staleTime: 30_000,
    refetchInterval: 60_000,
  })

  const janela30d = useMemo(() => {
    const agora = new Date()
    const inicio = new Date(agora)
    inicio.setDate(inicio.getDate() - JANELA_RANKING_DIAS)
    return { de: inicio.toISOString(), ate: agora.toISOString() }
  }, [])

  // Mesma definição de "hoje" que `Eventos.tsx` usa (00h local até agora) —
  // é a janela que o backend fixa para `alerts_today`, não a do turno.
  const janelaHoje = useMemo(() => {
    const agora = new Date()
    const inicio = new Date(agora)
    inicio.setHours(0, 0, 0, 0)
    return { de: inicio.toISOString(), ate: agora.toISOString() }
  }, [])

  const rankingCameras = useQuery({
    queryKey: ['epi', 'summary-cameras', janela30d.de, janela30d.ate],
    queryFn: () => eventsService.getSummary({ from: janela30d.de, to: janela30d.ate, moduleCode: 'epi' }),
    staleTime: 30_000,
    refetchInterval: 60_000,
  })

  const atualizar = useCallback(() => {
    void estatisticas.refetch()
    void linhaDoTempo.refetch()
    void resumo.refetch()
    void rankingCameras.refetch()
  }, [estatisticas, linhaDoTempo, resumo, rankingCameras])

  const alterarPref = useCallback((proxima: Preferencia) => {
    setPref(proxima)
    gravarPreferencia(proxima)
  }, [])

  const sensores = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }))

  const visiveis = useMemo(
    () => pref.ordem.filter((id) => !pref.ocultos.includes(id)),
    [pref],
  )

  const aoSoltar = useCallback(
    (evento: DragEndEvent) => {
      const { active, over } = evento
      if (!over || active.id === over.id) return
      const de = pref.ordem.indexOf(active.id as IdWidget)
      const para = pref.ordem.indexOf(over.id as IdWidget)
      if (de < 0 || para < 0) return
      const ordem = [...pref.ordem]
      const [movido] = ordem.splice(de, 1)
      ordem.splice(para, 0, movido)
      alterarPref({ ...pref, ordem })
    },
    [pref, alterarPref],
  )

  // ── Estados de tela inteira ───────────────────────────────────────────────

  if (estatisticas.isPending) {
    return (
      <LogikosLoader
        estado="waiting"
        variante="fullscreen"
        rotulo="CARREGANDO DASHBOARD"
        tamanho={96}
      />
    )
  }

  if (estatisticas.isError) {
    return (
      <div className={s.telaCentral}>
        <AlertTriangle size={36} strokeWidth={1.5} color={lk.estado.nc} aria-hidden="true" />
        <span className={s.telaTitulo}>Não foi possível carregar</span>
        <span className={s.telaDetalhe}>GET /API/MODULES/EPI/STATS</span>
        <button type="button" className={s.botaoPrimario} onClick={atualizar}>
          Tentar novamente
        </button>
      </div>
    )
  }

  const dados = estatisticas.data
  const camerasTotal = dados.cameras_total ?? 0
  const camerasAtivas = dados.cameras_active ?? 0
  const eventosHoje = dados.alerts_today ?? 0
  const eventosSemana = dados.alerts_week ?? 0

  // Vazio de verdade = não há de onde vir dado nenhum. Zero evento com câmera
  // rodando NÃO é vazio: é o resultado que o cliente quer ver, e esconder isso
  // atrás de "sem dados" apagaria justamente o dia bom.
  if (camerasTotal === 0 && eventosHoje === 0) {
    return (
      <div className={s.telaCentral}>
        <LayoutGrid size={36} strokeWidth={1.5} color={lk.cor.cinzaNevoa} aria-hidden="true" />
        <span className={s.telaTitulo}>Sem dados para este módulo</span>
        <span className={s.telaTexto}>
          Nenhuma câmera está atribuída ao EPI ainda. O score aparece após as primeiras detecções.
        </span>
        {can('cameras:read') && (
          <Link to={rotaNova('/epi/cameras')} className={s.botaoPrimario}>
            Ver câmeras
          </Link>
        )}
      </div>
    )
  }

  // ── Derivações (todas a partir de dado real) ──────────────────────────────

  const score = dados.compliance_rate
  const nivelScore: Severidade =
    score == null ? 'atencao' : score >= 90 ? 'ok' : score >= 70 ? 'atencao' : 'nc'
  const palavraScore = score == null ? 'Indisponível' : score >= 90 ? 'Conforme' : score >= 70 ? 'Atenção' : 'Crítico'

  const media7d = eventosSemana / 7
  const deltaEventos = media7d > 0 ? Math.round(((eventosHoje - media7d) / media7d) * 100) : null


  const pontos = fillBuckets(janela.de, janela.ate, 'hour', linhaDoTempo.data?.timeline ?? []).map(
    (p) => ({ ...p, rotulo: formatBucketLabel(p.bucket, 'hour') }),
  )
  const picoEventos = pontos.reduce<(typeof pontos)[number] | null>(
    (maior, p) => (maior === null || p.count > maior.count ? p : maior),
    null,
  )
  const maxHora = picoEventos?.count ?? 0
  const totalHoras = pontos.reduce((soma, p) => soma + p.count, 0)

  const porClasse = [...(resumo.data?.by_class ?? [])].sort((a, b) => b.count - a.count)
  const maxClasse = porClasse[0]?.count ?? 0
  const totalClasses = porClasse.reduce((soma, c) => soma + c.count, 0)

  // Backend já devolve top-10 ordenado por count DESC (top_cameras_by_alerts).
  const porCamera = rankingCameras.data?.by_camera ?? []
  const maxCamera = porCamera[0]?.count ?? 0
  const totalEventosCameras = porCamera.reduce((soma, c) => soma + c.count, 0)
  const concentracaoTop3 =
    totalEventosCameras > 0
      ? Math.round(
          (porCamera.slice(0, 3).reduce((soma, c) => soma + c.count, 0) / totalEventosCameras) * 100,
        )
      : 0

  const faixaTurno = `HOJE · ${String(janela.faixa.inicio).padStart(2, '0')}H–${String(
    janela.faixa.fim,
  ).padStart(2, '0')}H`

  const painelPorId: Record<IdWidget, ReactNode> = {
    'eventos-hora': (
      <Painel key="eventos-hora" id="eventos-hora" titulo="Eventos por hora" nota={faixaTurno}>
        {linhaDoTempo.isError ? (
          <VazioPainel
            texto="Não foi possível carregar a linha do tempo."
            aoRetentar={() => void linhaDoTempo.refetch()}
          />
        ) : linhaDoTempo.isPending ? (
          <VazioPainel texto="Carregando…" />
        ) : totalHoras === 0 ? (
          <VazioPainel
            texto="Sem eventos no período."
            cta={{
              texto: 'Ver últimos 30 dias →',
              to: linkParaEventos({ start_date: janela30d.de, end_date: janela30d.ate }),
            }}
          />
        ) : (
          <>
            <div className={s.barras} role="group" aria-label={`Eventos por hora, ${faixaTurno}`}>
              {pontos.map((p) => {
                const nivel: Severidade =
                  p.count === 0
                    ? 'neutro'
                    : p.count === maxHora
                      ? 'nc'
                      : p.count >= maxHora * 0.6
                        ? 'atencao'
                        : 'neutro'
                const fimHora = new Date(new Date(p.bucket).getTime() + 3_600_000).toISOString()
                return (
                  <Link
                    key={p.bucket}
                    to={linkParaEventos({ start_date: p.bucket, end_date: fimHora })}
                    className={`${s.colunaBarra} ${s.linkLimpo}`}
                    title={`${p.rotulo} · ${numero(p.count)} evento(s)`}
                    aria-label={`${p.rotulo} · ${numero(p.count)} evento(s) · ver eventos`}
                  >
                    <div
                      className={s.barra}
                      style={{
                        height: maxHora > 0 ? `${Math.round((p.count / maxHora) * 100)}%` : '0%',
                        background: p.count === 0 ? lk.cor.borda : COR[nivel],
                      }}
                    />
                    <span className={s.barraRotulo}>{p.rotulo}</span>
                  </Link>
                )
              })}
            </div>
            <span className={s.legenda}>
              Pico às {picoEventos?.rotulo} · {numero(maxHora)} evento(s) · {numero(totalHoras)} no
              período.
            </span>
          </>
        )}
      </Painel>
    ),

    'violacoes-classe': (
      <Painel key="violacoes-classe" id="violacoes-classe" titulo="Violações por classe">
        {resumo.isError ? (
          <VazioPainel
            texto="Não foi possível carregar as classes."
            aoRetentar={() => void resumo.refetch()}
          />
        ) : resumo.isPending ? (
          <VazioPainel texto="Carregando…" />
        ) : totalClasses === 0 ? (
          <VazioPainel
            texto="Sem violações no período."
            cta={{
              texto: 'Ver últimos 30 dias →',
              to: linkParaEventos({ start_date: janela30d.de, end_date: janela30d.ate }),
            }}
          />
        ) : (
          <>
            {porClasse.slice(0, 6).map((c) => (
              <Link
                key={c.class}
                to={linkParaEventos({
                  start_date: janela.de,
                  end_date: janela.ate,
                  violation_type: c.class,
                })}
                className={`${s.classeLinha} ${s.linkLimpo}`}
                aria-label={`${violationLabel(c.class)} · ${numero(c.count)} evento(s) · ver eventos`}
              >
                <ShieldAlert
                  size={16}
                  strokeWidth={1.7}
                  color={lk.cor.cinzaNevoa}
                  aria-hidden="true"
                />
                <span className={s.classeNome}>{violationLabel(c.class)}</span>
                <div className={s.classeTrilho}>
                  <div
                    className={s.classePreenchimento}
                    style={{ width: `${Math.round((c.count / maxClasse) * 100)}%` }}
                  />
                </div>
                <span className={s.classeValor}>{numero(c.count)}</span>
              </Link>
            ))}
            <span className={s.legenda}>
              {violationLabel(porClasse[0].class)} concentra{' '}
              {Math.round((porClasse[0].count / totalClasses) * 100)}% das violações.
            </span>
          </>
        )}
      </Painel>
    ),

    'acoes-recentes': (
      <Painel
        key="acoes-recentes"
        id="acoes-recentes"
        titulo="Ações recentes"
        acao={
          can('alerts:read') ? (
            <Link to={rotaNova('/epi/acoes')} className={s.atalhoInline}>
              todas →
            </Link>
          ) : undefined
        }
      >
        {/* Sem endpoint no backend (ver cabeçalho). Vazio honesto, não exemplo. */}
        <div className={s.itemAcao}>
          <span className={s.itemAcaoTitulo}>Ações ainda não são registradas</span>
          <div className={s.itemAcaoMeta}>
            <span>SEM FONTE DE DADOS</span>
          </div>
        </div>
        <span className={s.legenda}>
          Quando o plano de ação existir no sistema, as ações do período aparecem aqui.
        </span>
      </Painel>
    ),

    'cameras-eventos': (
      <Painel
        key="cameras-eventos"
        id="cameras-eventos"
        titulo="Câmeras com mais eventos"
        nota={ROTULO_JANELA_RANKING}
      >
        {rankingCameras.isError ? (
          <VazioPainel
            texto="Não foi possível carregar o ranking de câmeras."
            aoRetentar={() => void rankingCameras.refetch()}
          />
        ) : rankingCameras.isPending ? (
          <VazioPainel texto="Carregando…" />
        ) : totalEventosCameras === 0 ? (
          <div className={s.rankingVazio}>
            <BarChart3 size={30} strokeWidth={1.5} color={lk.cor.cinzaNevoa} aria-hidden="true" />
            <span className={s.rankingVazioTitulo}>Sem eventos no período</span>
            <span className={s.rankingVazioTexto}>
              Nenhuma câmera registrou evento. O ranking aparece assim que houver o primeiro.
            </span>
          </div>
        ) : (
          <>
            <div className={s.rankingLista}>
              {porCamera.map((c, i) => {
                // Regra do ciano: só as 3 primeiras posições em destaque (barra e nome).
                const destaque = i < 3 ? 'top' : 'resto'
                const nome = c.camera_name ?? 'Sem nome'
                const conteudo = (
                  <>
                    <span className={s.rankingPos}>{String(i + 1).padStart(2, '0')}</span>
                    <span className={`${s.rankingNome} ${s.rankingDestaque[destaque]}`} title={nome}>
                      {nome}
                    </span>
                    <div className={s.rankingTrilho}>
                      <div
                        className={s.rankingPreenchimento[destaque]}
                        style={{ width: maxCamera > 0 ? `${Math.round((c.count / maxCamera) * 100)}%` : '0%' }}
                      />
                    </div>
                    <span className={`${s.rankingValor} ${s.rankingDestaque[destaque]}`}>
                      {numero(c.count)}
                    </span>
                  </>
                )
                // Sem camera_id (evento sem câmera atribuída) não tem para onde
                // filtrar — 'camera_id=' vazio mostraria TODAS, o oposto do que
                // a linha representa. Linha fica de pé, só não clicável.
                return c.camera_id ? (
                  <Link
                    key={c.camera_id}
                    to={linkParaEventos({
                      start_date: janela30d.de,
                      end_date: janela30d.ate,
                      camera_id: c.camera_id,
                    })}
                    className={`${s.rankingLinha} ${s.linkLimpo}`}
                    aria-label={`${nome} · ${numero(c.count)} evento(s) · ver eventos`}
                  >
                    {conteudo}
                  </Link>
                ) : (
                  <div key={`${nome}-${i}`} className={s.rankingLinha}>
                    {conteudo}
                  </div>
                )
              })}
            </div>
            <div className={s.rankingDivisor} />
            <div className={s.rankingRodape}>
              <span className={s.legenda}>
                As três primeiras concentram{' '}
                <strong className={s.rankingEnfase}>{concentracaoTop3}%</strong> dos eventos do
                período.
              </span>
              {can('alerts:read') && (
                <Link to={rotaNova('/epi/eventos')} className={s.atalhoInline}>
                  ver eventos →
                </Link>
              )}
            </div>
          </>
        )}
      </Painel>
    ),
  }

  return (
    <div className={s.raiz}>
      <div className={s.cabecalho}>
        <h1 className={s.titulo}>Dashboard</h1>
        <span className={s.espacador} />

        <select
          className={s.seletor}
          aria-label="Turno"
          value={turno}
          onChange={(e) => setTurno(e.target.value as IdTurno)}
        >
          {TURNOS.map((t) => (
            <option key={t.id} value={t.id}>
              {t.rotulo}
            </option>
          ))}
        </select>

        <div
          className={s.envoltorioPopover}
          ref={refPersonalizar}
          onKeyDown={(e) => e.key === 'Escape' && setPersonalizar(false)}
        >
          <button
            type="button"
            className={s.botaoFantasma}
            aria-expanded={personalizar}
            onClick={() => setPersonalizar((v) => !v)}
          >
            <SlidersHorizontal size={14} strokeWidth={1.7} aria-hidden="true" />
            Personalizar widgets
          </button>
          {personalizar && (
            <div className={s.popover} role="group" aria-label="Personalizar widgets">
              <span className={s.overline}>Widgets visíveis</span>
              {WIDGETS.map((w) => (
                <label key={w.id} className={s.popoverLinha}>
                  <input
                    type="checkbox"
                    className={s.popoverCheck}
                    checked={!pref.ocultos.includes(w.id)}
                    onChange={() =>
                      alterarPref({
                        ...pref,
                        ocultos: pref.ocultos.includes(w.id)
                          ? pref.ocultos.filter((id) => id !== w.id)
                          : [...pref.ocultos, w.id],
                      })
                    }
                  />
                  <span>{w.rotulo}</span>
                </label>
              ))}
              <button
                type="button"
                className={s.botaoRetentar}
                onClick={() => alterarPref({ ordem: PADRAO, ocultos: [] })}
              >
                Restaurar padrão
              </button>
            </div>
          )}
        </div>
      </div>

      <div className={s.gridKpi}>
        {/* Score de conformidade */}
        <section className={s.cartaoScore} aria-label="Score de conformidade">
          <div className={s.linhaOverline}>
            <span className={s.overline}>Score de conformidade</span>
            <button
              type="button"
              className={s.botaoAjuda}
              aria-label="Como o score é calculado"
              aria-expanded={dicaAberta}
              onClick={() => setDicaAberta((v) => !v)}
              onMouseEnter={() => setDicaAberta(true)}
              onMouseLeave={() => setDicaAberta(false)}
            >
              i
            </button>
          </div>
          {dicaAberta && (
            <div className={s.dica} role="note">
              Como é calculado: 100 × (1 − horas-câmera com violação ÷ (câmeras ativas × 24)) nas
              últimas 24 h. Sem câmera ativa o score não é calculado — aparece como indisponível,
              nunca como 100.
            </div>
          )}
          <div className={s.scoreLinha}>
            <span className={s.scoreNumero}>{score == null ? '—' : Math.round(score)}</span>
            <div className={s.scoreLado}>
              <Estado nivel={nivelScore} palavra={palavraScore} />
              <span className={s.legenda}>
                {score == null
                  ? 'sem câmera ativa para calcular'
                  : 'últimas 24 h · todas as câmeras do módulo'}
              </span>
            </div>
          </div>
          <div className={s.rodapeMono}>
            {/*
              "SEM HISTÓRICO" sozinho contradizia o cartão ao lado, que mostra
              "% vs média 7d" a 40px daqui: um diz que não há histórico, o outro
              calcula em cima de uma média de 7 dias. São coisas diferentes — não
              existe SÉRIE DO SCORE em endpoint nenhum, enquanto a contagem de
              eventos da semana existe (`alerts_week`) — mas quem lê a tela não
              tem como saber disso. O rótulo passa a dizer de que histórico fala.
            */}
            <span>SCORE SEM SÉRIE · 7 DIAS</span>
            <span>ATUALIZADO {horaCurta(estatisticas.dataUpdatedAt)}</span>
          </div>
        </section>

        {/* Eventos hoje */}
        <section className={`${s.cartaoKpi} ${s.acento.neutro}`} aria-label="Eventos hoje">
          <span className={s.overline}>Eventos hoje</span>
          <Link
            to={linkParaEventos({ start_date: janelaHoje.de, end_date: janelaHoje.ate })}
            className={`${s.kpiValor} ${s.linkLimpo}`}
            aria-label={`Eventos hoje: ${numero(eventosHoje)} · ver eventos`}
          >
            {numero(eventosHoje)}
          </Link>
          <span className={s.legenda}>
            {deltaEventos === null ? (
              'sem média de 7 dias ainda'
            ) : (
              <>
                {deltaEventos >= 0 ? (
                  <ArrowUp size={12} strokeWidth={2} aria-hidden="true" />
                ) : (
                  <ArrowDown size={12} strokeWidth={2} aria-hidden="true" />
                )}{' '}
                {deltaEventos >= 0 ? '+' : '−'}
                {Math.abs(deltaEventos)}% vs média 7d
              </>
            )}
          </span>
          {can('alerts:read') && (
            <Link to={rotaNova('/epi/eventos')} className={s.atalho}>
              triar eventos →
            </Link>
          )}
        </section>

        {/* Ações abertas — sem endpoint no backend (ver cabeçalho) */}
        <section className={`${s.cartaoKpi} ${s.acento.neutro}`} aria-label="Ações abertas">
          <span className={s.overline}>Ações abertas</span>
          <span className={s.kpiValor}>—</span>
          <Estado nivel="atencao" palavra="Indisponível" />
          <span className={s.legenda}>ações ainda não são registradas no sistema</span>
        </section>

        {/* Câmeras ativas — não existe telemetria de conectividade por câmera
            (ver cabeçalho, item 4): "online" prometeria um dado que o
            sistema não mede. O que existe é status de cadastro. */}
        <section
          className={`${s.cartaoKpi} ${camerasAtivas > 0 ? s.acento.ok : s.acento.atencao}`}
          aria-label="Câmeras ativas"
        >
          <span className={s.overline}>Câmeras ativas</span>
          <span className={s.kpiValor}>{numero(camerasAtivas)}</span>
          <Estado
            nivel={camerasAtivas > 0 ? 'ok' : 'atencao'}
            palavra={camerasAtivas > 0 ? 'Cadastradas e ativas' : 'Nenhuma câmera ativa'}
          />
          <span className={s.legenda}>sem telemetria de conectividade por câmera ainda</span>
          {can('cameras:read') && (
            <Link to={rotaNova('/epi/cameras')} className={s.atalho}>
              ver câmeras →
            </Link>
          )}
        </section>
      </div>

      <DndContext sensors={sensores} collisionDetection={closestCenter} onDragEnd={aoSoltar}>
        <SortableContext items={visiveis} strategy={rectSortingStrategy}>
          <div className={s.gridPaineis}>{visiveis.map((id) => painelPorId[id])}</div>
        </SortableContext>
      </DndContext>
    </div>
  )
}

export default Dashboard
