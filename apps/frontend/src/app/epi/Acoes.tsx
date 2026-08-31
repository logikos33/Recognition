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
 * O backend guarda DUAS coisas reais contra um evento, e este cartão mostra
 * as duas — cada uma na sua própria ação, seu próprio botão, sua própria cor:
 *
 *   RECONHECIMENTO ← `alerts.acknowledged` + POST /api/alerts/<id>/acknowledge
 *     "alguém viu o evento". Rótulo/cor verde·âmbar (era o único par de
 *     estados desta tela até esta rodada — segue sendo o mesmo).
 *   VEREDITO        ← `alerts.verification_verdict` + POST /api/verification/<id>/review
 *     "a detecção é procedente ou o modelo errou". Rótulo/cor cinza (mesma
 *     regra de `EventoDetalhe.tsx`/`VereditoHumano.tsx`: veredito NUNCA usa a
 *     paleta de reconhecimento nem a de polaridade — são três eixos, três
 *     paletas. Confirmar/Descartar reaproveitam o mesmo endpoint e o mesmo
 *     `verdict` que a tela de evidência, só sem o campo `reason` — este é um
 *     atalho da lista, quem quer motivar o veredito abre o cartão).
 *
 * Abrir o cartão (clique em qualquer área fora dos botões) só NAVEGA para
 * `/epi/eventos/<id>` — nunca chama `/acknowledge` nem `/review` sozinho.
 *
 * A EVIDÊNCIA da miniatura é a MESMA fonte que `EventoDetalhe.tsx` usa
 * (`evidence_key` → URL assinada), só pelo endpoint leve
 * `GET /alerts/<id>/snapshot` (o mesmo que `Verificacao.tsx` já usa para o
 * mesmo propósito) em vez do alerta inteiro — a lista de `/alerts` não devolve
 * `evidence_url` (só o detalhe assina), e com até 100 cartões na tela pedir a
 * evidência de todos ao montar seria o N+1 que `Eventos.tsx` documenta como o
 * motivo de não ter miniatura na lista de eventos. Por isso cada miniatura só
 * pede a própria URL quando entra na viewport — mesmo padrão de
 * `CameraSnapshotThumbnail.tsx` (IntersectionObserver; ausente em jsdom nos
 * testes, que então carregam direto).
 *
 * TRATATIVA (título/responsável/prazo) continua sem backend. Em vez de sumir
 * em silêncio, o cartão desenha o controle que o desenho pede — desabilitado,
 * com selo — mesmo padrão de dependência de `Cenario.tsx`
 * (`botaoDependente` + `seloAguarda`): controle visível, zero ação falsa.
 *
 * `kind=violation` (ADR-0065): evento de CONFORMIDADE é telemetria de EPI em
 * uso — não é coisa sobre a qual se age. Uma tela de AGIR que listasse
 * conformidade estaria pedindo ação sobre quem está certo.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Check, Clock, ClipboardCheck, ImageOff, LayoutGrid, List, TriangleAlert, X,
} from 'lucide-react'

import { vereditoHumano } from '../../components/shared/VereditoHumano'
import { useAuth } from '../../hooks/useAuth'
import { api } from '../../services/api'
import { labelForClass } from '../../utils/labels'
import { rotaNova } from '../RotasNovas'
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
  /** Presença (não o valor) decide se vale a pena pedir a miniatura. */
  evidence_key?: string | null
  /** `list_with_filters` devolve a linha crua (`SELECT a.*`) — os dois campos
   *  do veredito já vêm de graça, sem chamada extra. */
  verification_verdict?: string | null
  verified_by?: string | null
}

/** `POST /verification/<id>/review` — mesmo verbo do backend, sem `reason`
 *  (a lista é atalho; motivar o veredito é coisa do cartão inteiro, em
 *  `EventoDetalhe.tsx`). */
type VeredictoAcao = 'approve' | 'reject'

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

/**
 * Miniatura da evidência — mesma fonte que `EventoDetalhe.tsx` usa
 * (`evidence_key` → URL assinada), pelo endpoint leve de UM alerta
 * (`GET /alerts/<id>/snapshot`, já usado por `Verificacao.tsx` para o mesmo
 * fim). Só pede quando o cartão entra na viewport — com dezenas de cartões na
 * tela, pedir todas ao montar seria o N+1 que `Eventos.tsx` documenta como o
 * motivo de a lista de eventos não ter miniatura.
 */
function EvidenciaCartao({ id, temEvidencia }: { id: string; temEvidencia: boolean }) {
  const ref = useRef<HTMLDivElement>(null)
  const [emVista, setEmVista] = useState(false)
  const [url, setUrl] = useState<string | null>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (typeof IntersectionObserver === 'undefined') {
      // jsdom (teste) não implementa — carrega direto em vez de nunca carregar.
      setEmVista(true)
      return
    }
    const obs = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) { setEmVista(true); obs.disconnect() }
      },
      { rootMargin: '200px' },
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  useEffect(() => {
    if (!emVista || !temEvidencia) return
    let vivo = true
    api.get<{ data?: { snapshot_url?: string } }>(`/alerts/${id}/snapshot`)
      .then((r) => { if (vivo) setUrl(r?.data?.snapshot_url ?? null) })
      .catch(() => { if (vivo) setUrl(null) })
    return () => { vivo = false }
  }, [emVista, temEvidencia, id])

  return (
    <div ref={ref} className={s.miniatura}>
      {url ? (
        <img src={url} alt="Frame da evidência" className={s.miniaturaImagem} />
      ) : (
        <span className={s.miniaturaVazia}>
          <ImageOff size={14} {...ICONE} aria-hidden />
          {temEvidencia ? 'sem prévia' : 'sem evidência'}
        </span>
      )}
    </div>
  )
}

export function Acoes() {
  const { can } = useAuth()
  const navegar = useNavigate()
  const podeReconhecer = can('alerts:feedback')
  const podeJulgar = can('verification:write')

  const [vista, setVista] = useState<Vista>('kanban')
  const [fase, setFase] = useState<Fase>('carregando')
  const [erro, setErro] = useState('')
  const [abertas, setAbertas] = useState<Evento[]>([])
  const [feitas, setFeitas] = useState<Evento[]>([])
  const [totalAbertas, setTotalAbertas] = useState(0)
  const [totalFeitas, setTotalFeitas] = useState(0)
  const [reconhecendo, setReconhecendo] = useState<string | null>(null)
  const [julgando, setJulgando] = useState<string | null>(null)

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

  /** Mesmo endpoint/verbo de `EventoDetalhe.tsx` (`darVeredito`), sem `reason`
   *  — atalho da lista. NÃO toca `acknowledged`: veredito é verdade sobre a
   *  detecção, reconhecer é ciência do operador — eixos independentes. */
  const julgar = async (id: string, verdict: VeredictoAcao) => {
    setJulgando(id)
    try {
      await api.post(`/verification/${id}/review`, { verdict })
      await carregar()
    } catch (e) {
      setErro(e instanceof Error ? e.message : 'falha desconhecida')
      setFase('erro')
    } finally {
      setJulgando(null)
    }
  }

  /** Só NAVEGA. Nunca chama `/acknowledge` — abrir não é reconhecer. */
  const abrir = (id: string) => navegar(rotaNova(`/epi/eventos/${id}`))

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

  const cartao = (e: Evento, concluida: boolean) => {
    // Veredito é eixo independente de reconhecimento — não some quando o
    // filtro de coluna é `acknowledged`, então checa nos dois grupos.
    const veredito = vereditoHumano(e.verification_verdict, e.verified_by)
    const abrirEvento = () => abrir(e.id)
    return (
      <div
        key={e.id}
        className={concluida ? s.cartao.concluida : s.cartao.aberta}
        role="button"
        tabIndex={0}
        aria-label={`Abrir evento ${e.id.slice(0, 8)}`}
        onClick={abrirEvento}
        onKeyDown={(ev) => {
          if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); abrirEvento() }
        }}
      >
        <EvidenciaCartao id={e.id} temEvidencia={Boolean(e.evidence_key)} />
        <span className={s.cartaoTitulo}>{descrever(e)}</span>
        <span className={s.origem}>EVENTO {e.id.slice(0, 8)} · {referencia(e)}</span>
        <div className={s.cartaoRodape}>
          <span className={concluida ? s.estado.reconhecida : s.estado.aguardando}>
            {concluida ? <Check size={13} {...ICONE} aria-hidden /> : <Clock size={13} {...ICONE} aria-hidden />}
            {concluida ? 'Reconhecida' : 'Aguardando'}
          </span>
          {veredito !== 'nao-revisado' && (
            <span className={s.veredito}>
              {veredito === 'procedente' ? <Check size={13} {...ICONE} aria-hidden /> : <X size={13} {...ICONE} aria-hidden />}
              {veredito === 'procedente' ? 'Procedente' : 'Falso positivo'}
            </span>
          )}
          <span className={s.quando}>
            <Clock size={12} {...ICONE} aria-hidden />
            {horario(e.created_at)}
          </span>
        </div>

        {/* Tratativa (título/responsável/prazo) do desenho: sem tabela, sem
         *  endpoint (ver cabeçalho do arquivo). Controle desenhado e
         *  desabilitado, com selo — nunca some em silêncio, nunca finge dado. */}
        <div className={s.acoesCartao} onClick={(ev) => ev.stopPropagation()}>
          <button
            type="button"
            className={s.botaoTratativa}
            disabled
            title="Tratativa (título, responsável e prazo): não existe tabela nem endpoint para isso no backend ainda."
          >
            <ClipboardCheck size={13} {...ICONE} aria-hidden /> Tratativa
          </button>
          <span className={s.seloAguarda}>AGUARDA BACKEND</span>

          {podeJulgar && (
            <>
              <button
                type="button"
                className={s.botaoVeredito.confirmar}
                disabled={julgando === e.id}
                onClick={() => void julgar(e.id, 'approve')}
                title="A detecção está correta (procedente)"
              >
                <Check size={13} {...ICONE} aria-hidden /> Confirmar
              </button>
              <button
                type="button"
                className={s.botaoVeredito.descartar}
                disabled={julgando === e.id}
                onClick={() => void julgar(e.id, 'reject')}
                title="A detecção está errada (falso positivo)"
              >
                <X size={13} {...ICONE} aria-hidden /> Descartar
              </button>
            </>
          )}

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
      </div>
    )
  }

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
        Esta tela mostra o reconhecimento de eventos e o veredito humano sobre a
        detecção — os dois registros de ação que o sistema guarda hoje. Ação
        corretiva com título, responsável e prazo ainda não existe no backend, e
        por isso não aparece aqui — o selo “Tratativa” em cada cartão avisa disso.
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
