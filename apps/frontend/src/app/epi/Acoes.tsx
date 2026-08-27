/**
 * EPI · Ações — a etapa AGIR da jornada (DETECTAR → TRIAR → AGIR → PROVAR).
 *
 * ⚠️ LEIA ANTES DE ESTENDER — o desenho pede mais do que o backend tem.
 *
 * `EPI Ações.dc.html` desenha um controle de AÇÕES CORRETIVAS: título livre,
 * responsável, prazo, "Nova ação", "Minhas ações", "Vencidas". Esse domínio
 * NÃO EXISTE em lugar nenhum do produto — não há tabela, não há endpoint, não
 * há ADR, e o `contrato-dados.js` do próprio handoff (421 entradas, 421/421
 * batendo com a API real) não tem UMA linha para esta tela. O estado de erro
 * do desenho cita `GET /api/epi/acoes`, que não existe no `url_map`.
 *
 * O ÚNICO registro de ação que o backend guarda hoje contra um evento é o
 * RECONHECIMENTO: `alerts.acknowledged` + `POST /api/alerts/<id>/acknowledge`.
 * É esse ledger que esta tela mostra, com a forma do desenho:
 *
 *   coluna "aguardando"  ← GET /api/alerts?acknowledged=false
 *   coluna "reconhecidas"← GET /api/alerts?acknowledged=true
 *   botão do cartão      ← POST /api/alerts/<id>/acknowledge
 *   faixa de taxa        ← os dois `total` do envelope, mesma janela de 30 dias
 *
 * O que o desenho pede e o backend NÃO serve não é renderizado com dado
 * inventado — simplesmente não existe aqui, e a nota no topo diz isso na cara
 * do usuário. Campos ausentes: título livre, responsável, prazo, "Nova ação",
 * filtros "Minhas"/"Vencidas", contagem de vencidas.
 *
 * `kind=violation` (ADR-0065): evento de CONFORMIDADE é telemetria de EPI em
 * uso — não é coisa sobre a qual se age. Uma tela de AGIR que listasse
 * conformidade estaria pedindo ação sobre quem está certo.
 */
import { useCallback, useEffect, useState } from 'react'
import { Check, Clock, ClipboardCheck, LayoutGrid, List, TriangleAlert } from 'lucide-react'

import { useAuth } from '../../hooks/useAuth'
import { api } from '../../services/api'
import { labelForClass } from '../../utils/labels'
import { LogikosLoader } from '../shell/LogikosLoader'
import * as s from './Acoes.css'

/** Ícones do handoff: stroke 1.7, ponta reta. */
const ICONE = { strokeWidth: 1.7, strokeLinecap: 'square' } as const

/** Janela única da tela — a mesma das duas listas e da taxa. */
const DIAS = 30
const POR_PAGINA = 50

/** Rota do front ATUAL — a fila de eventos nova ainda não está registrada. */
const EVENTOS_HOJE = '/epi/alerts'

interface Violacao { class: string }

interface Evento {
  id: string
  camera_id: string
  camera_name?: string
  violations?: Violacao[]
  acknowledged: boolean
  created_at: string
}

interface Envelope {
  data?: { alerts: Evento[]; total: number }
}

type Vista = 'kanban' | 'lista'
type Fase = 'carregando' | 'pronto' | 'erro'

/** "Sem capacete, Sem colete" — as classes do próprio evento, nada inventado. */
function descrever(e: Evento): string {
  const classes = (e.violations ?? []).map((v) => labelForClass(v.class)).filter(Boolean)
  return classes.length ? classes.join(', ') : 'Evento sem classe registrada'
}

/** "CAM-04 · 08/08 14:32" em mono — id curto só quando não há nome. */
function referencia(e: Evento): string {
  return e.camera_name || e.camera_id.slice(0, 8)
}

function horario(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? '—'
    : d.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function desde(dias: number): string {
  return new Date(Date.now() - dias * 86_400_000).toISOString()
}

export function Acoes() {
  const { can } = useAuth()
  const podeReconhecer = can('alerts:feedback')

  const [vista, setVista] = useState<Vista>('kanban')
  const [fase, setFase] = useState<Fase>('carregando')
  const [erro, setErro] = useState('')
  const [abertas, setAbertas] = useState<Evento[]>([])
  const [feitas, setFeitas] = useState<Evento[]>([])
  const [totalAbertas, setTotalAbertas] = useState(0)
  const [totalFeitas, setTotalFeitas] = useState(0)
  const [reconhecendo, setReconhecendo] = useState<string | null>(null)

  const carregar = useCallback(async () => {
    setFase('carregando')
    const base = `kind=violation&start_date=${encodeURIComponent(desde(DIAS))}&per_page=${POR_PAGINA}`
    try {
      const [aberto, feito] = await Promise.all([
        api.get<Envelope>(`/alerts?${base}&acknowledged=false`),
        api.get<Envelope>(`/alerts?${base}&acknowledged=true`),
      ])
      setAbertas(aberto.data?.alerts ?? [])
      setFeitas(feito.data?.alerts ?? [])
      setTotalAbertas(aberto.data?.total ?? 0)
      setTotalFeitas(feito.data?.total ?? 0)
      setFase('pronto')
    } catch (e) {
      setErro(e instanceof Error ? e.message : 'falha desconhecida')
      setFase('erro')
    }
  }, [])

  useEffect(() => { void carregar() }, [carregar])

  const reconhecer = async (id: string) => {
    setReconhecendo(id)
    try {
      await api.post(`/alerts/${id}/acknowledge`)
      await carregar()
    } catch (e) {
      setErro(e instanceof Error ? e.message : 'falha desconhecida')
      setFase('erro')
    } finally {
      setReconhecendo(null)
    }
  }

  if (fase === 'carregando') {
    return <LogikosLoader estado="waiting" variante="fullscreen" rotulo="CARREGANDO AÇÕES" />
  }

  if (fase === 'erro') {
    return (
      <div className={s.centro}>
        <TriangleAlert size={36} {...ICONE} aria-hidden />
        <span className={s.centroTitulo}>Não foi possível carregar</span>
        <span className={s.centroMono}>GET /api/alerts · {erro.toUpperCase()}</span>
        <button type="button" className={s.botaoPrimario} onClick={() => void carregar()}>
          Tentar novamente
        </button>
      </div>
    )
  }

  const total = totalAbertas + totalFeitas

  if (total === 0) {
    return (
      <div className={s.centro}>
        <ClipboardCheck size={36} {...ICONE} aria-hidden />
        <span className={s.centroTitulo}>Nenhuma ação aberta</span>
        <span className={s.centroTexto}>
          Ações nascem de eventos. Nos últimos {DIAS} dias não houve evento de violação
          para reconhecer nesta operação.
        </span>
        <a className={s.botaoPrimario} href={EVENTOS_HOJE}>Ir para eventos</a>
      </div>
    )
  }

  const taxa = Math.round((totalFeitas / total) * 100)

  const cartao = (e: Evento, concluida: boolean) => (
    <div key={e.id} className={concluida ? s.cartao.concluida : s.cartao.aberta}>
      <span className={s.cartaoTitulo}>{descrever(e)}</span>
      <span className={s.origem}>EVENTO {e.id.slice(0, 8)} · {referencia(e)}</span>
      <div className={s.cartaoRodape}>
        <span className={concluida ? s.estado.reconhecida : s.estado.aguardando}>
          {concluida ? <Check size={13} {...ICONE} aria-hidden /> : <Clock size={13} {...ICONE} aria-hidden />}
          {concluida ? 'Reconhecida' : 'Aguardando'}
        </span>
        <span className={s.quando}>
          <Clock size={12} {...ICONE} aria-hidden />
          {horario(e.created_at)}
        </span>
      </div>
      {!concluida && podeReconhecer && (
        <button
          type="button"
          className={s.botaoCartao}
          disabled={reconhecendo === e.id}
          onClick={() => void reconhecer(e.id)}
        >
          {reconhecendo === e.id ? 'Reconhecendo…' : 'Marcar reconhecida'}
        </button>
      )}
    </div>
  )

  const todos = [...abertas, ...feitas]

  return (
    <div className={s.pagina}>
      <div className={s.cabecalho}>
        <h1 className={s.titulo}>Ações corretivas</h1>
        <div className={s.empurra} />
        <div className={s.segmentado} role="group" aria-label="Vista">
          <button
            type="button"
            className={vista === 'kanban' ? s.segmento.ativo : s.segmento.inativo}
            aria-pressed={vista === 'kanban'}
            onClick={() => setVista('kanban')}
          >
            <LayoutGrid size={13} {...ICONE} aria-hidden /> Kanban
          </button>
          <button
            type="button"
            className={vista === 'lista' ? s.segmento.ativo : s.segmento.inativo}
            aria-pressed={vista === 'lista'}
            onClick={() => setVista('lista')}
          >
            <List size={13} {...ICONE} aria-hidden /> Lista
          </button>
        </div>
      </div>

      <p className={s.nota}>
        Esta tela mostra o reconhecimento de eventos — o único registro de ação que o
        sistema guarda hoje. Ação corretiva com título, responsável e prazo ainda não
        existe no backend, e por isso não aparece aqui.
      </p>

      <div className={s.faixaTaxa}>
        <span className={s.taxaNumero}>{taxa}%</span>
        <span className={s.taxaRotulo}>taxa de reconhecimento · {DIAS} dias</span>
        <div className={s.taxaTrilho}>
          <div className={s.taxaBarra} style={{ width: `${taxa}%` }} />
        </div>
        <span className={s.taxaContagem}>{totalFeitas}/{total} RECONHECIDAS</span>
      </div>

      {vista === 'kanban' ? (
        <div className={s.kanban}>
          <div className={s.coluna}>
            <div className={s.colunaTopo}>
              <span className={s.overline}>Aguardando</span>
              <span className={s.contador}>{totalAbertas}</span>
            </div>
            {abertas.map((e) => cartao(e, false))}
          </div>
          <div className={s.coluna}>
            <div className={s.colunaTopo}>
              <span className={s.overline}>Reconhecidas</span>
              <span className={s.contador}>{totalFeitas}</span>
            </div>
            {feitas.map((e) => cartao(e, true))}
          </div>
        </div>
      ) : (
        <div className={s.tabela} role="table">
          <div className={s.th}>EVENTO</div>
          <div className={s.th}>ORIGEM</div>
          <div className={s.th}>QUANDO</div>
          <div className={s.th}>ESTADO</div>
          {todos.map((e) => (
            <div key={e.id} style={{ display: 'contents' }}>
              <span className={s.td}>{descrever(e)}</span>
              <span className={s.tdMono}>{e.id.slice(0, 8)} · {referencia(e)}</span>
              <span className={s.tdMono}>{horario(e.created_at)}</span>
              <span className={s.td}>
                <span className={e.acknowledged ? s.estado.reconhecida : s.estado.aguardando}>
                  {e.acknowledged
                    ? <Check size={13} {...ICONE} aria-hidden />
                    : <Clock size={13} {...ICONE} aria-hidden />}
                  {e.acknowledged ? 'Reconhecida' : 'Aguardando'}
                </span>
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
