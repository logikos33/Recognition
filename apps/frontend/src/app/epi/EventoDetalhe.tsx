/**
 * EPI Evento Detalhe — `/epi/eventos/:id` (front novo).
 *
 * Migração de `pages/epi/AlertDetailPage.tsx` (`/epi/alerts/:alertId`) para o
 * desenho `EPI Evento Detalhe.dc.html`. É a tela que LEVA AO ACONTECIDO: frame
 * inteiro da evidência, caixa no lugar exato, hora REAL da captura, classe e
 * confiança — e o veredito humano com o MOTIVO.
 *
 * ─────────────────────────────────────────────────────────────────────────
 * O QUE NÃO PODE SE PERDER (docs/migration/DELTA-PRE-MIGRACAO.md §2)
 *
 * · **Badge de procedência** (item 2, ADR-0066 — "a caixa diz quem a
 *   desenhou"): reusa `classificarLatencia()` de
 *   `components/shared/ProcedenciaBadge.tsx` — a REGRA (limiar de 5 min,
 *   normalização de RFC 822 vs. ISO naive, relógio adiantado → "desconhecida")
 *   é a mesma função, importada, não recopiada. Só a PINTURA é nova, porque o
 *   `Badge` antigo usa `styles/theme.css` e nesta tela cor vem de `lk`. Se o
 *   limiar mudar lá, muda aqui junto — que é o ponto.
 *   Segue afirmando SÓ o negativo: sem badge = sem afirmação (`alerts.timestamp`
 *   ainda nasce com DEFAULT NOW(), carimbar "AO VIVO" trocaria uma mentira por
 *   outra).
 *
 * · **Motivo do veredito** (item 5): campo `reason` no
 *   `POST /verification/:id/review`. É ele que desambigua o `reject` — "a
 *   pessoa estava de máscara", "a caixa pegou a pessoa errada" e "não dava
 *   para ver" pedem correções OPOSTAS. Sem ele o falso positivo não ensina
 *   nada além de "erramos". Mesmo `aria-label`, mesmo `maxLength`, mesma
 *   ida ao backend.
 *
 * · **Lupa da evidência** (item 3): `proximoEstado()` de
 *   `pages/epi/lupaEvidencia.ts` — módulo PURO e testado, reusado inteiro.
 *   ⚠️ Ele mora em `pages/epi/` mas NÃO é do front antigo: marcar como INFRA
 *   no `MANIFESTO-FRONT-ANTIGO.md`, senão some junto com a página velha.
 *
 * ─────────────────────────────────────────────────────────────────────────
 * ADR-0065 / 0066 / 0067 — o que esta tela NÃO afirma
 *
 * O desenho carimba "VIOLAÇÃO CONFIRMADA" no chip. Esta tela carimba
 * "CONFIRMADO", sem a palavra violação, porque `GET /api/alerts/:id` **não
 * devolve a polaridade**: a lista deriva `event_kind` ('violation' |
 * 'compliance') no SQL, o detalhe tem projeção explícita e não a carrega.
 * Afirmar violação sem esse campo é exatamente o que a ADR-0067 proíbe —
 * violação nasce de julgamento POSITIVO de ausência, nunca do silêncio.
 *
 * Pelo mesmo motivo a tela não diz QUEM julgou: a projeção do detalhe omite
 * `verified_by` de propósito, e sem o prefixo `user:` não dá para separar o
 * veredito humano do que a task Celery de pré-análise grava com
 * `verified_by='claude-haiku'` (ver `components/shared/VereditoHumano.tsx`).
 * O chip diz o que está REGISTRADO, e o `title` diz que a autoria não vem
 * neste endpoint. Os dois gaps estão no bloco PARA O BACKEND, no fim.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { AlertTriangle, ArrowLeft, Check, Clock, Maximize2, Minus, Plus, SearchX, X } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import { classificarLatencia } from '../../components/shared/ProcedenciaBadge'
import { useAuth } from '../../hooks/useAuth'
import {
  ESCALA_MAX, ESCALA_MIN, LUPA_INICIAL, distanciaEntre, proximoEstado,
  type EventoLupa, type Palco,
} from '../../pages/epi/lupaEvidencia'
import { ApiError, api } from '../../services/api'
import { labelForClass } from '../../utils/labels'
import { LogikosLoader } from '../shell/LogikosLoader'
import * as s from './EventoDetalhe.css'

/** Rota da lista no front novo (de-para do DELTA: `/epi/alerts` → `/epi/eventos`). */
const ROTA_EVENTOS = '/epi/eventos'

type Bbox = [number, number, number, number]

/** Única unidade de bbox que esta tela sabe projetar (contrato de `domain/detectors/base.py`). */
export const BBOX_PIXELS = 'pixels_xywh_frame_original'

interface Violacao {
  class: string
  confidence: number
  bbox?: Bbox
  bbox_unidade?: string
}

/** Projeção de `GET /api/alerts/:id` — só o que a rota realmente devolve. */
export interface Evento {
  id: string
  camera_id: string | null
  camera_name?: string | null
  violations: Violacao[]
  acknowledged: boolean
  captured_at: string | null
  created_at?: string | null
  evidence_url: string | null
  verification_verdict?: string | null
  verified_at?: string | null
}

type Fase = 'carregando' | 'carregado' | 'vazio' | 'erro'
type Veredito = 'approve' | 'reject'

/**
 * bbox = [x, y, w, h] em PIXELS do frame ORIGINAL (canto superior-esquerdo,
 * NÃO centro) → caixa em % sobre a imagem renderizada. O alerta não carrega as
 * dimensões do frame; elas saem de `naturalWidth`/`naturalHeight` da <img>.
 *
 * Exportada porque é a única lógica não-trivial de posicionamento da tela.
 * (Mesma matemática de `AlertDetailPage.boxStyle`; copiada de propósito para o
 * front novo não importar um módulo do front antigo, que tem de poder sair.)
 */
export function caixaEmPorcento([x, y, w, h]: Bbox, natW: number, natH: number) {
  // toFixed(4) só apara o ruído binário; 4 casas em % é sub-pixel em qualquer frame.
  const pct = (n: number, total: number) => `${+((n / total) * 100).toFixed(4)}%`
  return { left: pct(x, natW), top: pct(y, natH), width: pct(w, natW), height: pct(h, natH) }
}

/** Estado do veredito REGISTRADO. Cor + ícone + palavra — nunca só cor. */
const VEREDITO_CHIP = {
  approve: { variante: 'confirmado', palavra: 'CONFIRMADO', Icone: AlertTriangle },
  reject: { variante: 'descartado', palavra: 'DESCARTADO', Icone: X },
  nenhum: { variante: 'aguarda', palavra: 'AGUARDA VEREDITO', Icone: Clock },
} as const

function chipDoVeredito(verdict?: string | null) {
  if (verdict === 'approve') return VEREDITO_CHIP.approve
  if (verdict === 'reject') return VEREDITO_CHIP.reject
  return VEREDITO_CHIP.nenhum
}

const dataHora = (iso?: string | null) =>
  iso ? new Date(iso).toLocaleString('pt-BR') : '—'

export function EventoDetalhe() {
  const { id } = useParams<{ id: string }>()
  const { can } = useAuth()

  const [evento, setEvento] = useState<Evento | null>(null)
  const [fase, setFase] = useState<Fase>('carregando')
  const [tentativa, setTentativa] = useState(0)
  /** Dimensões do frame ORIGINAL: só existem depois que a <img> carrega. */
  const [natural, setNatural] = useState<{ w: number; h: number } | null>(null)

  /** Motivo do veredito — opcional, mas é ele que desambigua o `reject`. */
  const [motivo, setMotivo] = useState('')
  const [salvando, setSalvando] = useState(false)
  const [erroAcao, setErroAcao] = useState<string | null>(null)

  useEffect(() => {
    let vivo = true
    setFase('carregando')
    setErroAcao(null)
    // Frame novo = dimensões novas. Sem isto a caixa do próximo evento cairia
    // projetada nas dimensões do frame anterior até a <img> carregar.
    setNatural(null)
    api.get<{ data?: { alert: Evento } }>(`/alerts/${id}`)
      .then((res) => {
        if (!vivo) return
        const a = res.data?.alert ?? null
        setEvento(a)
        setFase(a ? 'carregado' : 'vazio')
      })
      .catch((e: unknown) => {
        if (!vivo) return
        setEvento(null)
        // 404 é "não existe OU é de outro tenant" (C-01) — os dois são o mesmo
        // estado vazio para quem olha. Qualquer outro status é falha de carga.
        setFase(e instanceof ApiError && e.status === 404 ? 'vazio' : 'erro')
      })
    return () => { vivo = false }
  }, [id, tentativa])

  // ── lupa ──────────────────────────────────────────────────────────────────
  // A evidência é uma caixa de orelha num frame 1920x1080: sem ampliar, o dono
  // não julga. Zoom/pan vivem numa ÚNICA camada transformada que envolve a
  // <img> E as caixas — por isso a caixa escala junto, ancorada nos mesmos
  // pixels. Tirar as caixas de dentro dessa camada dessincroniza em silêncio.
  const palcoRef = useRef<HTMLDivElement>(null)
  const [lupa, setLupa] = useState(LUPA_INICIAL)
  // O listener de wheel é registrado uma vez (precisa ser não-passivo); o ref
  // dá a ele o estado atual sem re-registrar.
  const lupaRef = useRef(lupa)
  lupaRef.current = lupa
  const ponteiros = useRef(new Map<number, { x: number; y: number }>())
  const distPinca = useRef(0)

  // Evento novo = enquadramento novo.
  useEffect(() => { setLupa(LUPA_INICIAL) }, [id])

  const medir = useCallback((): { rect: DOMRect; palco: Palco } | null => {
    const el = palcoRef.current
    if (!el) return null
    const rect = el.getBoundingClientRect()
    return { rect, palco: { largura: rect.width, altura: rect.height } }
  }, [])

  const despachar = useCallback((ev: EventoLupa, palco: Palco) => {
    setLupa((prev) => proximoEstado(prev, ev, palco))
  }, [])

  /** Âncora relativa ao CENTRO do palco — `transformOrigin: center` assume isso. */
  const ancorar = (rect: DOMRect, clientX: number, clientY: number) => ({
    ancoraX: clientX - (rect.left + rect.width / 2),
    ancoraY: clientY - (rect.top + rect.height / 2),
  })

  const evidencia = evento?.evidence_url ?? null
  useEffect(() => {
    const el = palcoRef.current
    if (!el) return
    const onWheel = (ev: WheelEvent) => {
      // Já no piso e afastando: NÃO sequestra a roda — a página rola normal.
      if (lupaRef.current.escala === ESCALA_MIN && ev.deltaY > 0) return
      ev.preventDefault()   // exige passive:false; o onWheel do React é passivo.
      const m = medir()
      if (!m) return
      despachar(
        { tipo: 'zoom', fator: ev.deltaY < 0 ? 1.15 : 1 / 1.15, ...ancorar(m.rect, ev.clientX, ev.clientY) },
        m.palco,
      )
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [despachar, medir, evidencia])

  const aoDescerPonteiro = (e: React.PointerEvent<HTMLDivElement>) => {
    ponteiros.current.set(e.pointerId, { x: e.clientX, y: e.clientY })
    if (ponteiros.current.size === 2) distPinca.current = distanciaEntre([...ponteiros.current.values()])
    e.currentTarget.setPointerCapture(e.pointerId)
  }

  const aoMoverPonteiro = (e: React.PointerEvent<HTMLDivElement>) => {
    const anterior = ponteiros.current.get(e.pointerId)
    if (!anterior) return
    ponteiros.current.set(e.pointerId, { x: e.clientX, y: e.clientY })
    const m = medir()
    if (!m) return
    const pontos = [...ponteiros.current.values()]
    if (pontos.length >= 2) {
      // Pinça: fator = variação da distância, âncora no ponto médio.
      const nova = distanciaEntre(pontos)
      if (distPinca.current > 0 && nova > 0) {
        const meio = { x: (pontos[0].x + pontos[1].x) / 2, y: (pontos[0].y + pontos[1].y) / 2 }
        despachar({ tipo: 'zoom', fator: nova / distPinca.current, ...ancorar(m.rect, meio.x, meio.y) }, m.palco)
      }
      distPinca.current = nova
      return
    }
    // Em escala 1 o limite de pan é 0: arrastar já é inócuo, sem guarda extra.
    despachar({ tipo: 'arrastar', dx: e.clientX - anterior.x, dy: e.clientY - anterior.y }, m.palco)
  }

  const aoSoltarPonteiro = (e: React.PointerEvent<HTMLDivElement>) => {
    ponteiros.current.delete(e.pointerId)
    distPinca.current = 0
  }

  const aoDuploClique = (e: React.MouseEvent<HTMLDivElement>) => {
    const m = medir()
    if (!m) return
    if (lupaRef.current.escala >= ESCALA_MAX) { despachar({ tipo: 'reset' }, m.palco); return }
    despachar({ tipo: 'zoom', fator: 2, ...ancorar(m.rect, e.clientX, e.clientY) }, m.palco)
  }

  /** Teclado: zoom só na roda é inutilizável sem mouse. Não é enfeite. */
  const PASSO_TECLA = 40
  const aoTeclar = (e: React.KeyboardEvent<HTMLDivElement>) => {
    const m = medir()
    if (!m) return
    const noCentro = { ancoraX: 0, ancoraY: 0 }
    const setas: Record<string, [number, number]> = {
      ArrowLeft: [PASSO_TECLA, 0], ArrowRight: [-PASSO_TECLA, 0],
      ArrowUp: [0, PASSO_TECLA], ArrowDown: [0, -PASSO_TECLA],
    }
    if (e.key === '+' || e.key === '=') despachar({ tipo: 'zoom', fator: 1.5, ...noCentro }, m.palco)
    else if (e.key === '-' || e.key === '_') despachar({ tipo: 'zoom', fator: 1 / 1.5, ...noCentro }, m.palco)
    else if (e.key === '0') despachar({ tipo: 'reset' }, m.palco)
    else if (setas[e.key]) { const [dx, dy] = setas[e.key]; despachar({ tipo: 'arrastar', dx, dy }, m.palco) }
    else return
    e.preventDefault()
  }

  const zoomBotao = (fator: number) => {
    const m = medir()
    if (m) despachar({ tipo: 'zoom', fator, ancoraX: 0, ancoraY: 0 }, m.palco)
  }

  // ── veredito ──────────────────────────────────────────────────────────────

  /**
   * `POST /verification/:id/review`. NÃO toca `/acknowledge`: reconhecer é
   * ciência do operador, veredito é verdade sobre a detecção. `reason` vai
   * junto sempre que houver — a rota e o service sempre aceitaram.
   */
  const darVeredito = async (verdict: Veredito) => {
    setSalvando(true)
    setErroAcao(null)
    try {
      await api.post(`/verification/${id}/review`, {
        verdict,
        ...(motivo.trim() ? { reason: motivo.trim() } : {}),
      })
      setMotivo('')
      await api.get<{ data?: { alert: Evento } }>(`/alerts/${id}`)
        .then((res) => setEvento(res.data?.alert ?? null))
        .catch(() => { /* a tela segue mostrando o estado anterior */ })
    } catch {
      setErroAcao('Não foi possível registrar o veredito.')
    } finally {
      setSalvando(false)
    }
  }

  // ── estados de tela inteira ───────────────────────────────────────────────

  if (fase === 'carregando') {
    return <LogikosLoader estado="waiting" variante="fullscreen" rotulo="CARREGANDO EVENTO" tamanho={96} />
  }

  // ERRO antes de VAZIO, e a ordem importa: em `erro` o evento também é null,
  // e a ordem invertida mostraria "não encontrado" para uma falha de rede —
  // um 500 vira "esse evento não existe", que é mentira e mata o retry.
  if (fase === 'erro') {
    return (
      <div className={s.estadoCentral}>
        <AlertTriangle className={s.estadoIcone.falha} strokeWidth={1.5} aria-hidden />
        <span className={s.estadoTitulo}>Falha ao carregar o evento</span>
        <span className={s.estadoMono}>GET /api/alerts/{id}</span>
        <button type="button" className={s.botaoPrimario} onClick={() => setTentativa((t) => t + 1)}>
          Tentar novamente
        </button>
      </div>
    )
  }

  if (fase === 'vazio' || !evento) {
    return (
      <div className={s.estadoCentral}>
        <SearchX className={s.estadoIcone.neutro} strokeWidth={1.5} aria-hidden />
        <span className={s.estadoTitulo}>Evento não encontrado</span>
        <p className={s.estadoTexto}>
          O evento pode ter sido removido pela política de retenção (90 dias).
        </p>
        <Link to={ROTA_EVENTOS} className={s.botaoPrimario}>Voltar aos eventos</Link>
      </div>
    )
  }

  // ── carregado ─────────────────────────────────────────────────────────────

  const chip = chipDoVeredito(evento.verification_verdict)
  const classes = evento.violations ?? []
  const primeira = classes[0]
  // Só desenha o que sabemos projetar. Unidade ausente/estranha = origem
  // desconhecida: melhor nenhuma caixa que caixa mentirosa.
  const desenhaveis = classes.filter((v) => v.bbox && v.bbox_unidade === BBOX_PIXELS)
  const unidadeDesconhecida = classes.filter((v) => v.bbox && v.bbox_unidade !== BBOX_PIXELS)
  const retroativa = classificarLatencia(evento.captured_at, evento.created_at) === 'retroativa'
  const podeJulgar = can('verification:write')

  return (
    <div className={s.pagina}>
      <div className={s.cabecalho}>
        <Link to={ROTA_EVENTOS} className={s.voltar}>
          <ArrowLeft size={14} aria-hidden /> Eventos
        </Link>
        <h1 className={s.titulo}>
          Evento <span className={s.tituloId} title={evento.id}>#{evento.id.slice(0, 8)}</span>
        </h1>
        <span
          className={s.chip[chip.variante]}
          title="Veredito registrado sobre a detecção. Este endpoint não devolve quem julgou nem a polaridade do evento."
        >
          <chip.Icone className={s.chipIcone} aria-hidden /> {chip.palavra}
        </span>
      </div>

      <div className={s.corpo}>
        <div className={s.colunaEvidencia}>
          <div
            ref={palcoRef}
            className={s.palco}
            tabIndex={0}
            role="group"
            aria-label="Frame da evidência. Roda do mouse ou + e − para ampliar, setas para deslocar, 0 para voltar ao enquadramento inteiro."
            onPointerDown={aoDescerPonteiro}
            onPointerMove={aoMoverPonteiro}
            onPointerUp={aoSoltarPonteiro}
            onPointerCancel={aoSoltarPonteiro}
            onDoubleClick={aoDuploClique}
            onKeyDown={aoTeclar}
            style={{ cursor: lupa.escala > ESCALA_MIN ? 'grab' : 'zoom-in' }}
          >
            <span className={s.selo.esquerda}>
              {(evento.camera_name ?? evento.camera_id?.slice(0, 8) ?? '—').toUpperCase()}
            </span>
            <span className={s.selo.direita}>{dataHora(evento.captured_at)}</span>

            {evidencia ? (
              <div
                className={s.camada}
                style={{ transform: `translate(${lupa.x}px, ${lupa.y}px) scale(${lupa.escala})` }}
              >
                <div className={s.quadro}>
                  <img
                    className={s.imagem}
                    src={evidencia}
                    alt="Frame da evidência"
                    draggable={false}   // o drag nativo da imagem atropela o pan
                    onLoad={(e) => {
                      const img = e.currentTarget
                      if (img.naturalWidth > 0 && img.naturalHeight > 0) {
                        setNatural({ w: img.naturalWidth, h: img.naturalHeight })
                      }
                    }}
                  />
                  {natural && desenhaveis.map((v, i) => (
                    <div
                      key={i}
                      data-testid="caixa-violacao"
                      className={s.caixa}
                      style={{
                        ...caixaEmPorcento(v.bbox as Bbox, natural.w, natural.h),
                        // contra-escala: a 8× uma borda de 2,5px come a evidência
                        borderWidth: `${2.5 / lupa.escala}px`,
                        borderRadius: `${4 / lupa.escala}px`,
                      }}
                    >
                      <span
                        className={s.caixaRotulo}
                        style={{ transform: `scale(${1 / lupa.escala})` }}
                      >
                        {labelForClass(v.class)} · {(v.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className={s.semImagem}>
                <SearchX className={s.estadoIcone.neutro} strokeWidth={1.5} aria-hidden />
                Sem imagem de evidência para este evento
              </div>
            )}
          </div>

          <div className={s.barraLupa}>
            <button type="button" className={s.botaoLupa} aria-label="Ampliar"
                    onClick={() => zoomBotao(1.5)} disabled={lupa.escala >= ESCALA_MAX}>
              <Plus size={15} aria-hidden />
            </button>
            <button type="button" className={s.botaoLupa} aria-label="Reduzir"
                    onClick={() => zoomBotao(1 / 1.5)} disabled={lupa.escala <= ESCALA_MIN}>
              <Minus size={15} aria-hidden />
            </button>
            <button type="button" className={s.botaoLupa} disabled={lupa.escala === ESCALA_MIN}
                    onClick={() => { const m = medir(); if (m) despachar({ tipo: 'reset' }, m.palco) }}>
              <Maximize2 size={14} aria-hidden /> Frame inteiro
            </button>
            <span className={s.dicaLupa}>
              {lupa.escala.toFixed(1).replace('.', ',')}× · roda amplia · arrastar desloca
            </span>
          </div>

          {evidencia && classes.length > 0 && classes.every((v) => !v.bbox) && (
            <p className={s.aviso}>Evento sem coordenadas gravadas — frame exibido sem marcação.</p>
          )}
          {evidencia && unidadeDesconhecida.length > 0 && (
            <p className={s.aviso}>
              Coordenadas de origem desconhecida — caixa não desenhada para{' '}
              {unidadeDesconhecida.length === 1 ? '1 detecção' : `${unidadeDesconhecida.length} detecções`}.
            </p>
          )}
        </div>

        <aside className={s.painel}>
          {primeira && (
            <span className={s.classeChip}>
              <AlertTriangle className={s.classeIcone} aria-hidden />
              {labelForClass(primeira.class).toUpperCase()}
            </span>
          )}

          <div className={s.grade}>
            <span className={s.rotulo}>Câmera</span>
            <span>{evento.camera_name ?? evento.camera_id ?? '—'}</span>

            <span className={s.rotulo}>Captura</span>
            <span className={s.valorMono}>
              {dataHora(evento.captured_at)}{' '}
              {/* Badge de procedência (ADR-0066). Só a afirmação NEGATIVA: sem
                  badge = sem afirmação. A tela do ACONTECIDO é justamente onde
                  a distância entre captura e gravação precisa aparecer. */}
              {retroativa && (
                <span
                  className={s.procedencia}
                  title={`Capturado: ${evento.captured_at} · gravado: ${evento.created_at}`}
                >
                  <Clock className={s.procedenciaIcone} aria-hidden /> coleta retroativa
                </span>
              )}
            </span>

            <span className={s.rotulo}>Reconhecimento</span>
            <span>{evento.acknowledged ? 'Reconhecido' : 'Pendente'}</span>

            <span className={s.rotulo}>Veredito em</span>
            <span className={s.valorMono}>{dataHora(evento.verified_at)}</span>
          </div>

          <div className={s.bloco}>
            <span className={s.overline}>Detecções</span>
            {classes.length === 0 ? (
              <span className={s.rotulo}>Nenhuma detecção gravada neste evento.</span>
            ) : (
              <ul className={s.listaDeteccoes}>
                {classes.map((v, i) => (
                  <li key={i} className={s.deteccao}>
                    <span>{labelForClass(v.class)}</span>
                    <span className={s.confianca}>{(v.confidence * 100).toFixed(0)}%</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className={s.vereditoBloco}>
            <span className={s.overline}>Veredito</span>
            <p className={s.ajuda}>
              O veredito é sobre a DETECÇÃO: ela é procedente ou o modelo errou.
              Não confundir com <strong>Reconhecer</strong>, que só registra que
              alguém viu o evento.
            </p>

            {podeJulgar ? (
              <>
                <input
                  type="text"
                  className={s.campoMotivo}
                  value={motivo}
                  onChange={(e) => setMotivo(e.target.value)}
                  placeholder="Por quê? (opcional — ex.: a caixa pegou a luva do outro)"
                  aria-label="Motivo do veredito"
                  maxLength={280}
                />
                <p className={s.ajuda}>
                  O motivo é o que separa “a pessoa estava de máscara” de “a caixa
                  pegou a pessoa errada”. As duas coisas pedem correções opostas.
                </p>
                <div className={s.botoesVeredito}>
                  <button type="button" className={s.botaoVeredito.confirmar}
                          onClick={() => darVeredito('approve')} disabled={salvando}
                          title="A detecção está correta (procedente)">
                    <Check className={s.iconeVeredito} aria-hidden /> Confirmar
                  </button>
                  <button type="button" className={s.botaoVeredito.descartar}
                          onClick={() => darVeredito('reject')} disabled={salvando}
                          title="A detecção está errada (falso positivo)">
                    <X className={s.iconeVeredito} aria-hidden /> Descartar
                  </button>
                </div>
              </>
            ) : (
              <p className={s.aviso}>
                Você não tem permissão para julgar detecções (verification:write).
              </p>
            )}

            {erroAcao && <p role="alert" className={s.erro}>{erroAcao}</p>}
          </div>
        </aside>
      </div>
    </div>
  )
}

export default EventoDetalhe

/* ───────────────────────────────────────────────────────────────────────────
 * PARA O DESIGN — o desenho pede, o produto ainda não tem
 *
 * 1. **Player do evento** (▶ / 1× / faixa 24h clicável com scrubbing). Não há
 *    clipe: `alerts.evidence_key` é UM JPEG. Os clipes de 20-30s da ADR-0033
 *    não estão ligados ao alerta por endpoint nenhum. Botões de play sobre um
 *    still seriam controles falsos — omitidos.
 * 2. **Faixa "ÚLTIMAS 24H" com legenda OK / EVENTO / VIOLAÇÃO.**
 *    `GET /api/v1/events/timeline` devolve `{bucket, count}` — CONTAGEM, não
 *    severidade, e sem polaridade. Pintar contagem com a legenda do desenho
 *    trocaria o significado da faixa. Precisa de severidade por bucket.
 * 3. **← CAM-03 / CAM-05 →** (câmera vizinha). Não existe noção de vizinhança
 *    (nem ordem física, nem grupo/doca) em `ip_cameras`.
 * 4. **EVIDÊNCIAS · FRAMES T−2S / T / T+2S.** A API entrega um frame só.
 * 5. **Compartilhar** (expiração 1h/24h/7d, ver / ver+baixar). Nenhum endpoint
 *    de share link para evento no contrato do handoff — só o admin tem.
 * 6. **Criar ação corretiva** (sugestões, responsável, prazo). O módulo de
 *    ações (`EPI Ações`) não tem UMA rota mapeada no `contrato-dados.js`.
 * 7. **Zona** ("Zona de capacete obrigatório") e **Pessoas** ("2 na cena · 1 em
 *    violação"): o detalhe do alerta não devolve zona nem contagem de pessoas.
 * 8. **Largura**: o desenho desta tela usa 1360px; o token do shell é 1280.
 *    Usei o token. Se 1360 for regra desta tela, vira token.
 *
 * PARA O BACKEND — dois campos que a tela precisa e a projeção do detalhe omite
 *
 * A. `event_kind` ('violation' | 'compliance'). A LISTA deriva no SQL
 *    (`alert_repository.list_with_filters`), o DETALHE não. Sem ele o chip não
 *    pode dizer "VIOLAÇÃO CONFIRMADA" como o desenho quer — e ADR-0067 proíbe
 *    inferir. Um campo na projeção de `get_alert` resolve.
 * B. `verified_by` (ou um booleano `veredito_humano`). Sem o prefixo `user:`
 *    não dá para separar veredito de gente do que a task Celery grava com
 *    `verified_by='claude-haiku'`. Com ele, esta tela reusa
 *    `vereditoHumano()` e passa a dizer quem julgou.
 *
 * Migrado do front antigo e NÃO trazido (segue de pé em `/epi/alerts/:alertId`):
 * correção de caixa (`PATCH /alerts/:id/violations` + entrada por teclado das
 * coordenadas + "Caixa corrigida por…"). Não há desenho para ela nesta tela —
 * pedido de tela ao design, não invenção aqui.
 * ─────────────────────────────────────────────────────────────────────────── */
