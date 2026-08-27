/**
 * EPI Eventos — a lista de eventos do módulo EPI (rota nova `/epi/eventos`).
 *
 * Migração da `pages/AlertsHistoryPage.tsx` (rota antiga `/epi/alerts`) para o
 * front novo, contra o desenho `EPI Eventos.dc.html`. O de-para está em
 * `docs/migration/DELTA-PRE-MIGRACAO.md` §3.1.
 *
 * TRÊS EIXOS DISTINTOS, três colunas, três paletas — é o que o delta §2 manda
 * preservar e o que esta tela existe para não confundir:
 *
 *   EVENTO   = POLARIDADE — o que o evento É (classe do modelo, ADR-0065).
 *              Três estados: violação · conformidade · NÃO DEFINIDA. Verde e
 *              vermelho moram aqui e só aqui.
 *   VEREDITO = o que uma PESSOA julgou. Branco/âmbar/cinza, nunca verde nem
 *              vermelho — se "falso positivo" fosse vermelho, veredito e
 *              violação virariam a mesma cor na mesma linha.
 *   STATUS   = fluxo de trabalho (alguém deu ciência). Reconhecer é sempre um
 *              clique explícito, nunca hover.
 *
 * O QUE ESTA TELA NÃO FAZ, e por quê (para o design / backend):
 *
 * · **Miniatura da detecção.** O desenho tem uma coluna DETECÇÃO com o frame e
 *   a caixa. `GET /api/alerts` devolve `evidence_key`, mas NÃO devolve URL
 *   assinada — só o detalhe (`GET /api/alerts/<id>`) e `/snapshot` assinam, um
 *   alerta por requisição. Desenhar um retângulo cinza no lugar seria dado
 *   inventado; 20 requisições por página, um N+1 por rolagem. Falta
 *   `evidence_url` na listagem (ou uma rota em lote).
 * · **Faixa "eventos por hora".** A única fonte agregada é
 *   `GET /api/v1/events/timeline`, que ignora `kind` e `acknowledged` e soma
 *   `demo_events`: as barras discordariam da tabela logo abaixo sob o filtro
 *   padrão da própria tela. E a segunda série do desenho ("violação
 *   confirmada") não tem fonte nenhuma. Falta um agregado por hora que aceite
 *   os mesmos filtros da lista e separe confirmadas.
 * · **Status "descartado".** O desenho traz três estados numa coluna só;
 *   `alerts.acknowledged` é booleano. Descartar, na prática, é o veredito
 *   "falso positivo" — que é OUTRO eixo e tem coluna própria.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { NavLink, useSearchParams } from 'react-router-dom'
import {
  AlertTriangle, Check, CheckCircle, ChevronLeft, ChevronRight,
  Circle, Clock, Download, HelpCircle, Inbox, RefreshCw, ShieldCheck, XCircle,
  type LucideIcon,
} from 'lucide-react'

import { useAuth } from '../../hooks/useAuth'
import { useModuleClasses } from '../../hooks/useModuleClasses'
import { useToast } from '../../components/ui/Toast/useToast'
import { api, ApiError } from '../../services/api'
import { cameraService } from '../../services/cameraService'
import { classificarLatencia } from '../../components/shared/ProcedenciaBadge'
import { vereditoHumano, type Veredito } from '../../components/shared/VereditoHumano'
import {
  EXPLICACAO_POLARIDADE, ROTULO_POLARIDADE, type Polaridade,
} from '../../components/shared/PolaridadeClasse'
import { rangeForPeriod } from '../../utils/timeBuckets'
import type { Camera } from '../../types'
import { LogikosLoader } from '../shell/LogikosLoader'
import * as s from './Eventos.css'

const MODULO = 'epi'
const POR_PAGINA = 20

interface Violacao {
  class: string
  confidence?: number
}

interface Evento {
  id: string
  camera_id?: string
  camera_name?: string
  violations: Violacao[]
  acknowledged: boolean
  /** Quando o evento foi GRAVADO. */
  created_at: string
  /** Hora REAL da captura no edge — pode divergir de `created_at`. */
  timestamp?: string
  /** ADR-0065: 'compliance' = EPI em uso (telemetria); 'violation' = alertável. */
  event_kind?: 'violation' | 'compliance'
  /** Veredito bruto — a IA grava o MESMO 'approve'/'reject'; sozinho não prova gente. */
  verification_verdict?: string | null
  /** 'user:<id>' (gente) ou 'claude-haiku' (IA) — a prova de procedência do veredito. */
  verified_by?: string | null
  /** Justificativa que a pessoa deu ao julgar (`alerts.verification_reason`). */
  verification_reason?: string | null
}

interface Pagina {
  alerts: Evento[]
  total: number
  page: number
  per_page: number
  pages: number
}

type Periodo = 'hoje' | '7d' | '30d'

interface Filtros {
  periodo: Periodo
  /** Intervalo cru vindo de deep-link — vence o período até alguém trocá-lo. */
  intervalo: { from: string; to: string } | null
  cameraId: string
  classe: string
  /** '' = todos · 'false' = novo · 'true' = reconhecido (`?acknowledged=`). */
  status: string
  /** ADR-0065 — a tela abre em VIOLAÇÕES: EPI presente é telemetria, não alerta. */
  kind: string
  pagina: number
}

const ROTULO_VEREDITO: Record<Veredito, string> = {
  procedente: 'Procedente',
  'falso-positivo': 'Falso positivo',
  'nao-revisado': 'Não revisado',
}

const EXPLICACAO_VEREDITO: Record<Veredito, string> = {
  procedente: 'Uma pessoa revisou e considerou o evento correto.',
  'falso-positivo': 'Uma pessoa revisou e considerou a detecção incorreta.',
  'nao-revisado': 'Ninguém julgou este evento ainda. Não é o mesmo que "falso".',
}

const ICONE_POLARIDADE: Record<Polaridade, LucideIcon> = {
  violacao: AlertTriangle,
  conformidade: CheckCircle,
  indefinida: HelpCircle,
}

/** Ícones próprios: estado é cor + ÍCONE + palavra, e os dois eixos não se imitam. */
const ICONE_VEREDITO: Record<Veredito, LucideIcon> = {
  procedente: ShieldCheck,
  'falso-positivo': XCircle,
  'nao-revisado': Clock,
}

/** Intervalo do período. "Hoje" é o dia corrente de verdade, não 24h rolantes. */
function intervaloDoPeriodo(periodo: Periodo): { from: string; to: string } {
  if (periodo === 'hoje') {
    const inicio = new Date()
    inicio.setHours(0, 0, 0, 0)
    return { from: inicio.toISOString(), to: new Date().toISOString() }
  }
  const r = rangeForPeriod(periodo)
  return { from: r.from, to: r.to }
}

export function Eventos() {
  const { can } = useAuth()
  const toast = useToast()
  const [parametros] = useSearchParams()
  const { classes, classLabel } = useModuleClasses(MODULO)

  const [filtros, setFiltros] = useState<Filtros>(() => {
    const de = parametros.get('start_date')
    const ate = parametros.get('end_date')
    return {
      periodo: 'hoje',
      intervalo: de && ate ? { from: de, to: ate } : null,
      cameraId: parametros.get('camera_id') ?? '',
      classe: parametros.get('violation_type') ?? '',
      status: parametros.get('acknowledged') ?? '',
      kind: parametros.get('kind') ?? 'violation',
      pagina: 1,
    }
  })
  const [dados, setDados] = useState<Pagina | null>(null)
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)
  const [cameras, setCameras] = useState<Camera[]>([])
  const [selecionados, setSelecionados] = useState<string[]>([])
  const [ocupado, setOcupado] = useState<string | null>(null)
  const [exportando, setExportando] = useState(false)

  // Deep-link do sino: realça a linha e rola até ela, depois solta o realce.
  const [destaque, setDestaque] = useState<string | null>(() => parametros.get('highlight'))
  const refDestaque = useRef<HTMLTableRowElement | null>(null)

  const podeLer = can('alerts:read')
  const podeJulgar = can('alerts:feedback')
  const podeExportar = can('alerts:export')

  /** Querystring da listagem — a MESMA base do CSV, para o export sair no recorte da tela. */
  const consulta = useCallback(() => {
    const { from, to } = filtros.intervalo ?? intervaloDoPeriodo(filtros.periodo)
    const p = new URLSearchParams()
    if (filtros.cameraId) p.set('camera_id', filtros.cameraId)
    p.set('start_date', from)
    p.set('end_date', to)
    if (filtros.classe) p.set('violation_type', filtros.classe)
    if (filtros.status !== '') p.set('acknowledged', filtros.status)
    if (filtros.kind) p.set('kind', filtros.kind)
    return p
  }, [filtros])

  const carregar = useCallback(async () => {
    setCarregando(true)
    setErro(null)
    try {
      const p = consulta()
      // PAGINAÇÃO POR PÁGINA, como a tela antiga e como o backend calcula o
      // OFFSET (`(page-1)*per_page`, alerts/routes.py). Não trocar por cursor
      // nem por offset cru: a ordenação é `created_at DESC` e qualquer outro
      // mecanismo aqui reabre o buraco de linhas puladas entre páginas.
      p.set('page', String(filtros.pagina))
      p.set('per_page', String(POR_PAGINA))
      const res = await api.get<{ data?: Pagina }>(`/alerts?${p}`)
      const d = res?.data
      setDados({
        alerts: d?.alerts ?? [],
        total: d?.total ?? 0,
        page: d?.page ?? filtros.pagina,
        per_page: d?.per_page ?? POR_PAGINA,
        pages: d?.pages ?? 1,
      })
    } catch (e) {
      setDados(null)
      setErro(e instanceof ApiError ? `GET /api/alerts · HTTP ${e.status}` : 'GET /api/alerts · FALHA')
    } finally {
      setCarregando(false)
    }
  }, [consulta, filtros.pagina])

  useEffect(() => {
    if (podeLer) void carregar()
  }, [carregar, podeLer])

  // Nomes de câmera para o filtro do desenho ("CAM-04 Expedição"). Degrada em
  // silêncio: sem a lista, o filtro some — nunca vira campo de digitar UUID.
  useEffect(() => {
    if (!podeLer) return
    let vivo = true
    cameraService
      .list()
      .then((cs) => { if (vivo) setCameras(cs) })
      .catch(() => { if (vivo) setCameras([]) })
    return () => { vivo = false }
  }, [podeLer])

  useEffect(() => {
    if (!destaque || !dados) return
    refDestaque.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    const t = setTimeout(() => setDestaque(null), 4000)
    return () => clearTimeout(t)
  }, [dados, destaque])

  /**
   * POLARIDADE em três estados. `event_kind='compliance'` é afirmação POSITIVA
   * do backend (`is_violation IS FALSE`) e vale sozinha. Já `'violation'`
   * colapsa TRUE **e NULL** no mesmo balde — para exibir, isso mentiria
   * ("ninguém decidiu" apareceria como violação), então quem desempata é o
   * catálogo (`GET /api/modules/epi/classes`, campo `polaridade`).
   *
   * Sem catálogo carregado, ou classe fora dele, não há afirmação a fazer:
   * devolve `null` e a célula mostra só o nome da classe. Ausência de selo =
   * ausência de afirmação (mesma regra do badge de procedência).
   */
  const polaridadePorClasse = useMemo(() => {
    const m = new Map<string, Polaridade>()
    const lista: Array<{ class_name: string; polaridade?: Polaridade }> = classes
    for (const c of lista) if (c.polaridade) m.set(c.class_name, c.polaridade)
    return m
  }, [classes])

  const polaridadeDoEvento = useCallback(
    (ev: Evento): Polaridade | null => {
      if (ev.event_kind === 'compliance') return 'conformidade'
      const classe = ev.violations?.[0]?.class
      return (classe && polaridadePorClasse.get(classe)) || null
    },
    [polaridadePorClasse],
  )

  /** Todo filtro volta para a página 1 — paginar sobre outro recorte é linha pulada. */
  const trocarFiltro = (mudanca: Partial<Filtros>) =>
    setFiltros((f) => ({ ...f, ...mudanca, pagina: 1 }))

  const limparFiltros = () =>
    setFiltros({
      periodo: 'hoje', intervalo: null, cameraId: '', classe: '',
      status: '', kind: 'violation', pagina: 1,
    })

  /** Reconhecer: ato explícito. Não existe chave de permissão para "dar
   *  ciência" no registry (`core/permissions.py` só tem read/feedback/export),
   *  então o botão segue visível para quem lê — igual à tela antiga. Registrado
   *  para o backend. */
  const reconhecer = async (id: string) => {
    setOcupado(id)
    try {
      await api.post(`/alerts/${id}/acknowledge`)
      setSelecionados((sel) => sel.filter((i) => i !== id))
      await carregar()
    } catch {
      toast.error('Não foi possível reconhecer o evento')
    } finally {
      setOcupado(null)
    }
  }

  const reconhecerSelecionados = async () => {
    setOcupado('lote')
    const alvos = [...selecionados]
    const falhas = await Promise.all(
      alvos.map((id) => api.post(`/alerts/${id}/acknowledge`).then(() => 0).catch(() => 1)),
    )
    const erros = falhas.reduce<number>((a, b) => a + b, 0)
    if (erros) toast.error(`${erros} de ${alvos.length} não puderam ser reconhecidos`)
    setSelecionados([])
    setOcupado(null)
    await carregar()
  }

  /**
   * Veredito humano — reusa `POST /api/verification/<id>/review`, que carimba
   * `verified_by='user:<id>'` (a prova que a coluna VEREDITO lê). O MOTIVO
   * (`reason`) é campo da tela de detalhe, onde há espaço para escrever: aqui
   * o veredito é rápido e vai SEM motivo, exatamente como hoje — nunca com
   * motivo vazio, que gravaria "justificado" sobre uma justificativa que
   * ninguém deu. O motivo já registrado aparece abaixo do selo.
   */
  const julgar = async (id: string, verdict: 'approve' | 'reject') => {
    setOcupado(id)
    try {
      await api.post(`/verification/${id}/review`, { verdict })
      await carregar()
    } catch {
      toast.error('Não foi possível registrar o veredito')
    } finally {
      setOcupado(null)
    }
  }

  const exportar = async () => {
    setExportando(true)
    try {
      const blob = await api.downloadBlob(`/alerts/export?${consulta()}`)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'eventos.csv'
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      toast.error('Erro ao exportar')
    } finally {
      setExportando(false)
    }
  }

  const eventos = dados?.alerts ?? []
  const selecionaveis = eventos.filter((e) => !e.acknowledged).map((e) => e.id)

  if (!podeLer) {
    return (
      <div className={s.painelCentral}>
        <AlertTriangle size={36} strokeWidth={1.5} aria-hidden="true" />
        <span className={s.painelTitulo}>Sem permissão</span>
        <span className={s.painelTexto}>
          Ver eventos exige a permissão <code>alerts:read</code>. Peça a quem administra
          o seu acesso.
        </span>
      </div>
    )
  }

  return (
    <div className={s.pagina}>
      <div className={s.cabecalho}>
        <h1 className={s.titulo}>Eventos</h1>
        {dados && (
          <span className={s.meta}>
            {dados.total} NO PERÍODO
          </span>
        )}
        <span className={s.espacador} />

        <select
          className={s.filtro}
          aria-label="Período"
          value={filtros.intervalo ? '' : filtros.periodo}
          onChange={(e) => {
            // '' é só o rótulo do intervalo que veio no link; não é período.
            if (!e.target.value) return
            // Escolher um período descarta o intervalo cru do deep-link.
            trocarFiltro({ periodo: e.target.value as Periodo, intervalo: null })
          }}
        >
          {filtros.intervalo && <option value="">Período do link</option>}
          <option value="hoje">Hoje</option>
          <option value="7d">7 dias</option>
          <option value="30d">30 dias</option>
        </select>

        {cameras.length > 0 && (
          <select
            className={s.filtro}
            aria-label="Câmera"
            value={filtros.cameraId}
            onChange={(e) => trocarFiltro({ cameraId: e.target.value })}
          >
            <option value="">Todas as câmeras</option>
            {cameras.map((c) => (
              <option key={c.id} value={c.id}>
                {c.location ? `${c.name} · ${c.location}` : c.name}
              </option>
            ))}
          </select>
        )}

        {classes.length > 0 && (
          <select
            className={s.filtro}
            aria-label="Classe"
            value={filtros.classe}
            onChange={(e) => trocarFiltro({ classe: e.target.value })}
          >
            <option value="">Todas as classes</option>
            {classes.map((c) => (
              <option key={c.class_name} value={c.class_name}>
                {classLabel(c.class_name)}
              </option>
            ))}
          </select>
        )}

        <select
          className={s.filtro}
          aria-label="Status"
          value={filtros.status}
          onChange={(e) => trocarFiltro({ status: e.target.value })}
        >
          <option value="">Todos os status</option>
          <option value="false">Novo</option>
          <option value="true">Reconhecido</option>
        </select>

        {/* Fora do desenho, preservado da tela antiga (ADR-0065): sem isto a
            lista abriria misturando telemetria de EPI em uso com violação. */}
        <select
          className={s.filtro}
          aria-label="Tipo de evento"
          value={filtros.kind}
          onChange={(e) => trocarFiltro({ kind: e.target.value })}
        >
          <option value="violation">Violações</option>
          <option value="compliance">Conformidade (EPI em uso)</option>
          <option value="">Todos os tipos</option>
        </select>

        {podeExportar && (
          <button className={s.botao} onClick={() => void exportar()} disabled={exportando}>
            <Download size={15} strokeWidth={1.7} aria-hidden="true" />
            {exportando ? 'Exportando…' : 'Exportar CSV'}
          </button>
        )}
      </div>

      {selecionados.length > 0 && (
        <div className={s.barraSelecao}>
          <span className={s.contagemSelecao}>{selecionados.length} selecionados</span>
          <span className={s.espacador} />
          <button
            className={s.botaoPrimario}
            onClick={() => void reconhecerSelecionados()}
            disabled={ocupado === 'lote'}
          >
            Reconhecer selecionados
          </button>
          <button className={s.botao} onClick={() => setSelecionados([])}>
            Limpar
          </button>
        </div>
      )}

      {carregando ? (
        <LogikosLoader estado="waiting" variante="fullscreen" rotulo="CARREGANDO EVENTOS" />
      ) : erro ? (
        <div className={s.painelCentral} role="alert">
          <AlertTriangle size={36} strokeWidth={1.5} aria-hidden="true" />
          <span className={s.painelTitulo}>Não foi possível carregar</span>
          <span className={s.painelDetalhe}>{erro}</span>
          <button className={s.botaoPainel} onClick={() => void carregar()}>
            <RefreshCw size={16} strokeWidth={1.7} aria-hidden="true" />
            Tentar novamente
          </button>
        </div>
      ) : eventos.length === 0 ? (
        <div className={s.painelCentral}>
          <Inbox size={36} strokeWidth={1.5} aria-hidden="true" />
          <span className={s.painelTitulo}>Nenhum evento no período</span>
          <span className={s.painelTexto}>
            Nenhuma detecção com os filtros atuais. Bom sinal — ou filtro demais.
          </span>
          <button className={s.botaoPainel} onClick={limparFiltros}>
            Limpar filtros
          </button>
        </div>
      ) : (
        <>
          <div className={s.cartao}>
            <table className={s.tabela}>
              <thead>
                <tr>
                  <th scope="col" className={s.cabecalhoCelula}>
                    <input
                      type="checkbox"
                      className={s.caixaSelecao}
                      aria-label="Selecionar todos os eventos novos"
                      checked={
                        selecionaveis.length > 0 && selecionados.length === selecionaveis.length
                      }
                      onChange={(e) => setSelecionados(e.target.checked ? selecionaveis : [])}
                    />
                  </th>
                  <th scope="col" className={s.cabecalhoCelula}>Evento</th>
                  <th scope="col" className={s.cabecalhoCelula}>Câmera</th>
                  <th scope="col" className={s.cabecalhoCelula}>Hora</th>
                  <th scope="col" className={s.cabecalhoCelula}>Status</th>
                  <th scope="col" className={s.cabecalhoCelula}>Veredito humano</th>
                  <th scope="col" className={s.cabecalhoCelula} />
                </tr>
              </thead>
              <tbody>
                {eventos.map((ev) => {
                  const polaridade = polaridadeDoEvento(ev)
                  const IconePol = polaridade ? ICONE_POLARIDADE[polaridade] : null
                  const veredito = vereditoHumano(ev.verification_verdict, ev.verified_by)
                  const IconeVer = ICONE_VEREDITO[veredito]
                  const capturadoEm = ev.timestamp ?? ev.created_at
                  const retroativo =
                    classificarLatencia(ev.timestamp, ev.created_at) === 'retroativa'
                  const marcado = selecionados.includes(ev.id)
                  const realcada = ev.id === destaque
                  return (
                    <tr
                      key={ev.id}
                      ref={realcada ? refDestaque : undefined}
                      className={realcada ? s.linhaDestacada : undefined}
                    >
                      <td className={s.celula}>
                        {!ev.acknowledged && (
                          <input
                            type="checkbox"
                            className={s.caixaSelecao}
                            aria-label={`Selecionar evento de ${ev.camera_name ?? 'câmera'}`}
                            checked={marcado}
                            onChange={() =>
                              setSelecionados((sel) =>
                                marcado ? sel.filter((i) => i !== ev.id) : [...sel, ev.id],
                              )
                            }
                          />
                        )}
                      </td>

                      {/* POLARIDADE + classe. Cor + ícone + palavra, sempre. */}
                      <td className={s.celulaEvento}>
                        {polaridade && IconePol && (
                          <span
                            className={`${s.selo} ${s.corPolaridade[polaridade]}`}
                            title={EXPLICACAO_POLARIDADE[polaridade]}
                          >
                            <IconePol size={13} strokeWidth={1.7} aria-hidden="true" />
                            {ROTULO_POLARIDADE[polaridade]}
                          </span>
                        )}
                        <span className={s.nomeClasse}>
                          {ev.violations?.length
                            ? ev.violations.map((v) => classLabel(v.class)).join(', ')
                            : '—'}
                        </span>
                      </td>

                      <td className={s.celula}>{ev.camera_name || '—'}</td>

                      <td className={s.celulaMono}>
                        {new Date(capturadoEm).toLocaleString('pt-BR')}
                        {/* PROCEDÊNCIA: só a afirmação negativa. Sem badge =
                            sem afirmação — não existe carimbo de "ao vivo"
                            enquanto o shadow roda sobre frames já coletados. */}
                        {retroativo && (
                          <>
                            {' '}
                            <span
                              className={s.seloRetroativo}
                              title={`Capturado: ${ev.timestamp} · gravado: ${ev.created_at}`}
                            >
                              coleta retroativa
                            </span>
                          </>
                        )}
                      </td>

                      <td className={s.celula}>
                        <span
                          className={`${s.selo} ${
                            ev.acknowledged ? s.corStatus.reconhecido : s.corStatus.novo
                          }`}
                        >
                          {ev.acknowledged ? (
                            <Check size={13} strokeWidth={1.7} aria-hidden="true" />
                          ) : (
                            <Circle size={13} strokeWidth={1.7} aria-hidden="true" />
                          )}
                          {ev.acknowledged ? 'Reconhecido' : 'Novo'}
                        </span>
                      </td>

                      {/* VEREDITO — coluna e paleta próprias. O SELO aparece
                          sempre, inclusive em "Não revisado": ausência de
                          veredito é um estado, não um espaço em branco. */}
                      <td className={s.celula}>
                        <span
                          className={`${s.selo} ${s.corVeredito[veredito]}`}
                          title={EXPLICACAO_VEREDITO[veredito]}
                        >
                          <IconeVer size={13} strokeWidth={1.7} aria-hidden="true" />
                          {ROTULO_VEREDITO[veredito]}
                        </span>
                        {/* MOTIVO do veredito: o que separa "estava de máscara"
                            de "a caixa pegou a luva do outro". */}
                        {ev.verification_reason && (
                          <span className={s.motivo} title={ev.verification_reason}>
                            {ev.verification_reason}
                          </span>
                        )}
                        {veredito === 'nao-revisado' && podeJulgar && (
                          <span className={s.grupoBotoes}>
                            <button
                              className={s.botao}
                              disabled={ocupado === ev.id}
                              onClick={() => void julgar(ev.id, 'approve')}
                            >
                              Procedente
                            </button>
                            <button
                              className={s.botao}
                              disabled={ocupado === ev.id}
                              onClick={() => void julgar(ev.id, 'reject')}
                            >
                              Falso positivo
                            </button>
                          </span>
                        )}
                      </td>

                      <td className={s.celulaAcoes}>
                        {!ev.acknowledged && (
                          <button
                            className={s.botao}
                            disabled={ocupado === ev.id}
                            onClick={() => void reconhecer(ev.id)}
                          >
                            Reconhecer
                          </button>
                        )}
                        <NavLink className={s.botao} to={`/epi/eventos/${ev.id}`}>
                          Abrir →
                        </NavLink>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <div className={s.rodape}>
            <span>{dados?.total ?? 0} EVENTOS</span>
            <span className={s.espacador} />
            <button
              className={s.botao}
              aria-label="Página anterior"
              disabled={filtros.pagina <= 1}
              onClick={() => setFiltros((f) => ({ ...f, pagina: f.pagina - 1 }))}
            >
              <ChevronLeft size={16} strokeWidth={1.7} aria-hidden="true" />
            </button>
            <span className={s.overlineLegenda}>
              {dados?.page ?? 1} / {dados?.pages ?? 1}
            </span>
            <button
              className={s.botao}
              aria-label="Próxima página"
              disabled={!dados || filtros.pagina >= dados.pages}
              onClick={() => setFiltros((f) => ({ ...f, pagina: f.pagina + 1 }))}
            >
              <ChevronRight size={16} strokeWidth={1.7} aria-hidden="true" />
            </button>
          </div>

          <span className={s.nota}>
            Reconhecer é sempre um clique explícito — nunca hover. Do evento dá para agir
            em ≤2 cliques: Abrir → Confirmar / Criar ação.
          </span>
        </>
      )}
    </div>
  )
}
