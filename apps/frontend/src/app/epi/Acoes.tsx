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
 *
 * DECISÃO (rodada de correção UX, contrato A1): isto também deixa de fora a
 * classe INDECIDIDA ('observacao' — is_violation NULL, ou fora do catálogo),
 * e a fila continua com `kind=violation` mesmo assim. Registrado, não
 * esquecido: o backend não tem um `kind` "tudo que não é conformidade" (só
 * os quatro valores testados em test_alert_event_kind.py), e trocar para ''
 * (todos) reabriria esta fila de AÇÃO com conformidade dentro — o mesmo
 * ruído que este filtro existe para excluir. O indecidido tem tela própria
 * para achar (`/epi/eventos`, filtro "Não definida") — não desaparece do
 * produto, só não entra nesta fila de ação enquanto o backend não tiver um
 * recorte que junte violação+observação sem trazer conformidade junto.
 */
import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Check, ChevronDown, ChevronRight, Clock, ClipboardCheck, ImageOff, LayoutGrid, List,
  TriangleAlert, X,
} from 'lucide-react'

import { vereditoHumano } from '../../components/shared/VereditoHumano'
import { useAuth } from '../../hooks/useAuth'
import { api } from '../../services/api'
import { labelForClass } from '../../utils/labels'
import { agruparPorRajada, type Rajada } from '../../utils/rajadas'
import { rotaNova } from '../RotasNovas'
import { LogikosLoader } from '../shell/LogikosLoader'
import * as s from './Acoes.css'

/** Ícones do handoff: stroke 1.7, ponta reta. */
const ICONE = { strokeWidth: 1.7, strokeLinecap: 'square' } as const

/** Janela única da tela — a mesma das duas listas e da taxa. */
const DIAS = 30
const POR_PAGINA = 50

/**
 * A fila de eventos NOVA, que existe desde a primeira leva
 * (`RotasNovas.tsx`, `path="epi/eventos"`). O comentário anterior dizia que
 * ela "ainda não está registrada" e mandava para `/epi/alerts` — era falso, e
 * o efeito era despejar no front ANTIGO quem clicasse em "Ir para eventos"
 * a partir do estado vazio desta tela.
 */
const ROTA_EVENTOS = rotaNova('/epi/eventos')

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
  data?: { alerts: Evento[]; total: number; total_situacoes?: number }
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
  // ux2/dedup: rajadas (câmera+classe em <60s) do MESMO filtro, não linhas —
  // `null` até o primeiro sync OK (backend/mock antigo sem a chave cai para
  // o total de linhas nos usos abaixo, nunca 500 nem NaN na tela).
  const [situacoesAbertas, setSituacoesAbertas] = useState<number | null>(null)
  const [situacoesFeitas, setSituacoesFeitas] = useState<number | null>(null)
  // QUEBRA 3 (rodada de correção): NÃO é `situacoesAbertas + situacoesFeitas`
  // — uma rajada parcialmente reconhecida (parte ack=false, parte ack=true)
  // conta 1 sessão em CADA recorte isolado e infla a soma. Este é o
  // `total_situacoes` de um TERCEIRO pedido sem filtro `acknowledged` — a
  // MESMA rajada, vista sobre a união dos dois estados, conta 1 vez só.
  const [situacoesTotal, setSituacoesTotal] = useState<number | null>(null)
  const [reconhecendo, setReconhecendo] = useState<string | null>(null)
  const [julgando, setJulgando] = useState<string | null>(null)
  // Cartões/linhas de rajada expandidos (id do representante) — nunca
  // esconde: expandir revela as N repetições da mesma cena.
  const [expandidos, setExpandidos] = useState<Set<string>>(new Set())
  const alternarExpandido = (id: string) =>
    setExpandidos((atual) => {
      const novo = new Set(atual)
      if (novo.has(id)) novo.delete(id)
      else novo.add(id)
      return novo
    })

  const carregar = useCallback(async () => {
    setFase('carregando')
    const baseFiltro = `kind=violation&start_date=${encodeURIComponent(desde(DIAS))}`
    try {
      // QUEBRA 3: o terceiro pedido (sem `acknowledged`, `per_page=1` — só
      // o envelope importa, não os itens) devolve `total_situacoes` sobre a
      // UNIÃO dos dois estados. Fonte do denominador — nunca a soma dos
      // outros dois recortes (dupla-conta rajada parcialmente reconhecida).
      const [aberto, feito, todos] = await Promise.all([
        api.get<Envelope>(`/alerts?${baseFiltro}&per_page=${POR_PAGINA}&acknowledged=false`),
        api.get<Envelope>(`/alerts?${baseFiltro}&per_page=${POR_PAGINA}&acknowledged=true`),
        api.get<Envelope>(`/alerts?${baseFiltro}&per_page=1`),
      ])
      setAbertas(aberto.data?.alerts ?? [])
      setFeitas(feito.data?.alerts ?? [])
      setTotalAbertas(aberto.data?.total ?? 0)
      setTotalFeitas(feito.data?.total ?? 0)
      setSituacoesAbertas(aberto.data?.total_situacoes ?? null)
      setSituacoesFeitas(feito.data?.total_situacoes ?? null)
      setSituacoesTotal(todos.data?.total_situacoes ?? null)
      setFase('pronto')
    } catch (e) {
      setErro(e instanceof Error ? e.message : 'falha desconhecida')
      setFase('erro')
    }
  }, [])

  useEffect(() => { void carregar() }, [carregar])

  // ux2/dedup: agrupa CADA coluna por câmera+classe+60s — mesma janela do
  // backend. Colunas separadas de propósito (aguardando/reconhecida É o
  // eixo do kanban): uma rajada parcialmente reconhecida aparece como um
  // representante em cada coluna, nunca mistura os dois estados num cartão só.
  const gruposAbertas = useMemo(
    () => agruparPorRajada(abertas, {
      cameraId: (e: Evento) => e.camera_id,
      classe: (e: Evento) => e.violations?.[0]?.class ?? '',
      criadoEm: (e: Evento) => e.created_at,
    }),
    [abertas],
  )
  const gruposFeitas = useMemo(
    () => agruparPorRajada(feitas, {
      cameraId: (e: Evento) => e.camera_id,
      classe: (e: Evento) => e.violations?.[0]?.class ?? '',
      criadoEm: (e: Evento) => e.created_at,
    }),
    [feitas],
  )

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
        {/* `<Link>`, não `<a href>`: âncora recarrega a aplicação inteira
            (perde o Shell, o token em memória e o contexto de tenant) para ir
            a uma rota que o próprio Router já serve. */}
        <Link className={s.botaoPrimario} to={ROTA_EVENTOS}>Ir para eventos</Link>
      </div>
    )
  }

  // ux2/dedup: "1/66 reconhecidas" media repetição, não trabalho — a taxa e
  // os contadores de coluna usam SITUAÇÕES (`total_situacoes`), com
  // fallback pro total de linhas quando o backend/mock ainda não manda a
  // chave nova (nunca NaN, nunca 500).
  const situAbertasN = situacoesAbertas ?? totalAbertas
  const situFeitasN = situacoesFeitas ?? totalFeitas
  // QUEBRA 3: NÃO `situAbertasN + situFeitasN` — cada termo vem de um
  // recorte isolado (ack=false / ack=true) regrupado à parte, e uma rajada
  // que atravessa os dois estados conta 1 sessão em CADA um, inflando a
  // soma. `situacoesTotal` é o `total_situacoes` da UNIÃO (3º pedido, sem
  // filtro `acknowledged`) — a mesma rajada, vista inteira, conta 1 vez.
  const situTotal = situacoesTotal ?? (totalAbertas + totalFeitas)
  const taxa = situTotal === 0 ? 0 : Math.round((situFeitasN / situTotal) * 100)

  const cartao = (grupo: Rajada<Evento>, concluida: boolean) => {
    const e = grupo.representante
    // Veredito é eixo independente de reconhecimento — não some quando o
    // filtro de coluna é `acknowledged`, então checa nos dois grupos.
    const veredito = vereditoHumano(e.verification_verdict, e.verified_by)
    const abrirEvento = () => abrir(e.id)
    const expandido = expandidos.has(e.id)
    const repeticoes = grupo.repeticoes.filter((r) => r.id !== e.id)
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

        {/* Rajada (ux2/dedup) — cartão repetia a mesma cena; nunca esconde,
         *  só recolhe. Expandir revela as N repetições, cada uma com a
         *  própria ação de reconhecer. */}
        {repeticoes.length > 0 && (
          <button
            type="button"
            className={s.rajadaToggle}
            onClick={(ev) => { ev.stopPropagation(); alternarExpandido(e.id) }}
          >
            {expandido
              ? <ChevronDown size={11} {...ICONE} aria-hidden />
              : <ChevronRight size={11} {...ICONE} aria-hidden />}
            +{repeticoes.length} repetiç{repeticoes.length === 1 ? 'ão' : 'ões'} da mesma cena
          </button>
        )}
        {expandido && repeticoes.length > 0 && (
          <div className={s.rajadaLista} onClick={(ev) => ev.stopPropagation()}>
            {repeticoes.map((r) => (
              <div key={r.id} className={s.rajadaItem}>
                <span><Clock size={11} {...ICONE} aria-hidden /> {horario(r.created_at)}</span>
                {r.acknowledged ? (
                  <span className={s.estado.reconhecida}>
                    <Check size={12} {...ICONE} aria-hidden /> Reconhecida
                  </span>
                ) : podeReconhecer ? (
                  <button
                    type="button"
                    className={s.botaoCartao}
                    disabled={reconhecendo === r.id}
                    onClick={() => void reconhecer(r.id)}
                  >
                    {reconhecendo === r.id ? 'Reconhecendo…' : 'Reconhecer'}
                  </button>
                ) : (
                  <span className={s.estado.aguardando}>
                    <Clock size={12} {...ICONE} aria-hidden /> Aguardando
                  </span>
                )}
              </div>
            ))}
          </div>
        )}

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

  const linhasLista = [
    ...gruposAbertas.map((grupo) => ({ grupo, concluida: false })),
    ...gruposFeitas.map((grupo) => ({ grupo, concluida: true })),
  ]

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
        <span className={s.taxaContagem}>
          {/* ux2/dedup: SITUAÇÕES, não linhas — "1/66 reconhecidas" media
              repetição, não trabalho. Mostra o raw só quando diverge. */}
          {situTotal !== total
            ? `${situFeitasN}/${situTotal} SITUAÇÕES RECONHECIDAS · ${totalFeitas}/${total} eventos`
            : `${totalFeitas}/${total} RECONHECIDAS`}
        </span>
      </div>

      {vista === 'kanban' ? (
        <div className={s.kanban}>
          <div className={s.coluna}>
            <div className={s.colunaTopo}>
              <span className={s.overline}>Aguardando</span>
              <span className={s.contador}>{situAbertasN}</span>
            </div>
            {gruposAbertas.map((g) => cartao(g, false))}
          </div>
          <div className={s.coluna}>
            <div className={s.colunaTopo}>
              <span className={s.overline}>Reconhecidas</span>
              <span className={s.contador}>{situFeitasN}</span>
            </div>
            {gruposFeitas.map((g) => cartao(g, true))}
          </div>
        </div>
      ) : (
        <div className={s.tabela} role="table">
          <div className={s.th}>EVENTO</div>
          <div className={s.th}>ORIGEM</div>
          <div className={s.th}>QUANDO</div>
          <div className={s.th}>ESTADO</div>
          {linhasLista.map(({ grupo }) => {
            const e = grupo.representante
            const expandido = expandidos.has(e.id)
            const repeticoes = grupo.repeticoes.filter((r) => r.id !== e.id)
            return (
              <Fragment key={e.id}>
                <div style={{ display: 'contents' }}>
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
                    {repeticoes.length > 0 && (
                      <button
                        type="button"
                        className={s.rajadaToggle}
                        onClick={() => alternarExpandido(e.id)}
                      >
                        {expandido
                          ? <ChevronDown size={11} {...ICONE} aria-hidden />
                          : <ChevronRight size={11} {...ICONE} aria-hidden />}
                        +{repeticoes.length}
                      </button>
                    )}
                  </span>
                </div>
                {expandido && repeticoes.map((r) => (
                  <div key={r.id} style={{ display: 'contents' }}>
                    <span className={s.tdRepeticao}>{descrever(r)}</span>
                    <span className={s.tdRepeticao}>{r.id.slice(0, 8)} · {referencia(r)}</span>
                    <span className={s.tdRepeticao}>{horario(r.created_at)}</span>
                    <span className={s.tdRepeticao}>
                      <span className={r.acknowledged ? s.estado.reconhecida : s.estado.aguardando}>
                        {r.acknowledged
                          ? <Check size={13} {...ICONE} aria-hidden />
                          : <Clock size={13} {...ICONE} aria-hidden />}
                        {r.acknowledged ? 'Reconhecida' : 'Aguardando'}
                      </span>
                    </span>
                  </div>
                ))}
              </Fragment>
            )
          })}
        </div>
      )}
    </div>
  )
}
