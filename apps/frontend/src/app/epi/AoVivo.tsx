/**
 * EPI Ao Vivo — `/epi/live` (de-para: `/epi/monitoring` do front atual).
 *
 * Desenho: `EPI Ao Vivo.dc.html`. Presets 2×2/3×3/4×3 + colunas 2–6 + modo
 * DESTAQUE (1 grande + trilho), overlay de detecção com toggle, gaveta da
 * câmera. Em ≥5 colunas o estado vira só o ícone e os rótulos de bbox somem.
 *
 * ─────────────────────────────────────────────────────────────────────────
 * O QUE ESTA TELA HERDA E NÃO PODE REGREDIR (história cara)
 * ─────────────────────────────────────────────────────────────────────────
 *
 * 1. **A URL do HLS NUNCA é montada aqui.** Desde os PRs 255/256, `m3u8`
 *    sem token de playback responde 404 — o MESMO 404 de stream inexistente
 *    (C-01: não vaze existência). A URL vem de `POST /stream/start` via
 *    `useLiveView`, com o token no PATH (`/stream/s/<token>/stream.m3u8`),
 *    porque os `.ts` da playlist são relativos e herdam o token sozinhos.
 *
 * 2. **Nada de player novo.** `CameraPlayer` carrega o watchdog de stall, o
 *    backoff, a recuperação por URL nova no 404/410 e o teardown de aba
 *    oculta. `useLiveView` carrega a renovação ancorada no `exp` REAL do
 *    token — a cadeia que causou o congelamento cíclico de 04/08 e foi
 *    fechada nos PRs 306-308. Reescrever qualquer um dos dois é reabrir
 *    aquele bug.
 *
 * 3. **Sessão única de playback por câmera.** Ladrilho e gaveta cada um monta
 *    seu `useLiveView` + `CameraPlayer`. Com os dois vivos para a MESMA
 *    câmera, cada um minta um token próprio e dois tokens baixam o mesmo
 *    `.ts` (visto em produção). `suprimido` desliga o player do ladrilho
 *    enquanto a gaveta da mesma câmera está aberta.
 *
 * 4. **Só monta player de câmera visível** (IntersectionObserver). Um video
 *    wall de 28 câmeras montando 28 players fora da viewport derruba o
 *    bucket de vídeo do rate-limit.
 *
 * ─────────────────────────────────────────────────────────────────────────
 * DADO REAL, OU VAZIO HONESTO — o que esta tela NÃO inventa
 * ─────────────────────────────────────────────────────────────────────────
 *
 * · **Estado da câmera.** `cameras.stream_status` NÃO EXISTE mais no backend
 *   (só sobrou no type do front) e `cameras.last_seen` não é escrito por
 *   ninguém. O único sinal honesto de "o vídeo está chegando" é o próprio
 *   caminho de playback: arquivada → OFFLINE; `/stream/start` falhou →
 *   OFFLINE; URL ainda não resolveu → CONECTANDO; URL na mão → ONLINE.
 *   O desenho diz "INSTÁVEL" no estado do meio — trocado por "CONECTANDO",
 *   que é o que o sinal disponível de fato afirma.
 *
 * · **Contagem do cabeçalho.** "N CÂMERAS · M ATIVAS" (de `is_active`), não
 *   "M ONLINE": online é por ladrilho e só existe depois do playback.
 *
 * · **Preset ≠ paginação.** No protótipo o preset 2×2 corta a lista em 4 e
 *   não há como ver a 5ª câmera. Aqui o preset define COLUNAS e a grade
 *   mostra todas — 28 câmeras não podem sumir por causa de um preset.
 */
import { useCallback, useEffect, useMemo, useRef, useState, type RefObject } from 'react'
import { Link } from 'react-router-dom'
import { Maximize2, Plus, Video, X } from 'lucide-react'

import { api, getToken } from '../../services/api'
import { useAuth } from '../../hooks/useAuth'
import { useLiveView } from '../../hooks/useLiveView'
import { useMonitoringSocket, type Detection } from '../../hooks/useMonitoringSocket'
import { CameraPlayer } from '../../components/monitoring/CameraPlayer'
import type { Camera } from '../../types'
import { LogikosLoader } from '../shell/LogikosLoader'
import * as s from './AoVivo.css'
import { rotaNova } from '../RotasNovas'

const WS_URL = (import.meta.env.VITE_WS_URL as string | undefined)
  || (import.meta.env.VITE_API_URL as string | undefined)
  || ''

/**
 * Dimensão do frame que as bbox do WebSocket usam como referência. É a MESMA
 * suposição que `DetectionOverlay` do front atual carrega desde sempre (seus
 * callers passam 640×360 fixo) — o payload de `detection` não traz as
 * dimensões do frame. Convertido para % aqui, então o ladrilho pode ter
 * qualquer tamanho sem recalcular nada.
 */
const FRAME = { largura: 640, altura: 360 }

/** Acima disto o ladrilho fica pequeno: estado vira ícone, rótulo de bbox some. */
const COLUNAS_COMPACTAS = 5

type EstadoCamera = 'online' | 'conectando' | 'offline'

const TARJA: Record<EstadoCamera, { icone: string; palavra: string }> = {
  online: { icone: '●', palavra: 'ONLINE' },
  conectando: { icone: '▲', palavra: 'CONECTANDO' },
  offline: { icone: '✕', palavra: 'OFFLINE' },
}

type Preset = '2x2' | '3x3' | '4x3' | 'destaque' | 'custom'

const COLUNAS_DO_PRESET: Partial<Record<Preset, number>> = { '2x2': 2, '3x3': 3, '4x3': 4 }

const PRESETS: Array<[Preset, string]> = [
  ['2x2', '2×2'],
  ['3x3', '3×3'],
  ['4x3', '4×3'],
  ['destaque', 'DESTAQUE'],
]

interface AlertaRecente {
  id: string
  class_name?: string | null
  violations?: Array<{ class?: string }> | null
  created_at?: string | null
  captured_at?: string | null
}

// ---------------------------------------------------------------------------
// useNaTela — só monta player do que está na viewport (ver ponto 4 do topo).
// ---------------------------------------------------------------------------
function useNaTela(ref: RefObject<HTMLElement | null>): boolean {
  // jsdom não tem IntersectionObserver: sem observer, tudo é visível — senão a
  // tela nasceria vazia em teste por um detalhe de ambiente.
  const [visivel, setVisivel] = useState(typeof IntersectionObserver === 'undefined')
  useEffect(() => {
    const el = ref.current
    if (!el || typeof IntersectionObserver === 'undefined') return
    const obs = new IntersectionObserver(
      (entradas) => {
        const e = entradas[0]
        if (e) setVisivel(e.isIntersecting)
      },
      { rootMargin: '150px', threshold: 0 },
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [ref])
  return visivel
}

// ---------------------------------------------------------------------------
// Overlay de detecção — ⛔ pointerEvents none, ZERO onClick (CLAUDE.md).
// ---------------------------------------------------------------------------
function CamadaCaixas({ deteccoes, comRotulo }: { deteccoes: Detection[]; comRotulo: boolean }) {
  return (
    // pointerEvents também inline: é regra de segurança de interação, não
    // enfeite — tem de valer mesmo se alguém trocar a folha de estilo.
    <div className={s.camadaCaixas} style={{ pointerEvents: 'none' }} data-testid="camada-caixas">
      {deteccoes.map((d, i) => {
        const [x, y, w, h] = d.bbox
        const tom = d.is_violation === true ? 'nc' : 'ok'
        return (
          <div
            key={`${d.class}-${i}`}
            className={s.caixa[tom]}
            data-testid="caixa-deteccao"
            style={{
              left: `${(x / FRAME.largura) * 100}%`,
              top: `${(y / FRAME.altura) * 100}%`,
              width: `${(w / FRAME.largura) * 100}%`,
              height: `${(h / FRAME.altura) * 100}%`,
            }}
          >
            {comRotulo && (
              <span className={s.rotuloCaixa[tom]}>
                {d.class} {Math.round(d.confidence * 100)}%
              </span>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Ladrilho — uma câmera. Dono do seu próprio ciclo de playback.
// ---------------------------------------------------------------------------
interface LadrilhoProps {
  camera: Camera
  deteccoes: Detection[]
  compacto: boolean
  selecionado: boolean
  /** Gaveta desta MESMA câmera aberta — não manter dois players (ponto 3). */
  suprimido: boolean
  grande?: boolean
  onSelecionar: () => void
  onDestacar?: () => void
}

function Ladrilho({
  camera,
  deteccoes,
  compacto,
  selecionado,
  suprimido,
  grande = false,
  onSelecionar,
  onDestacar,
}: LadrilhoProps) {
  const ref = useRef<HTMLDivElement>(null)
  const naTela = useNaTela(ref)
  const ativo = naTela && !suprimido && camera.is_active
  const { hlsUrl, error } = useLiveView(camera.id, ativo)

  const estado: EstadoCamera = !camera.is_active || error != null
    ? 'offline'
    : hlsUrl != null
      ? 'online'
      : 'conectando'

  const tarja = TARJA[estado]
  const descricao = `${tarja.icone} ${tarja.palavra}`

  return (
    <div
      ref={ref}
      className={grande ? s.foco : s.ladrilho[selecionado ? 'selecionado' : 'normal']}
      role="button"
      tabIndex={0}
      aria-label={`Abrir ${camera.name}`}
      onClick={onSelecionar}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onSelecionar()
        }
      }}
    >
      {ativo && hlsUrl != null && (
        <div className={s.moldura}>
          <CameraPlayer cameraId={camera.id} hlsUrl={hlsUrl} />
        </div>
      )}

      {/* Reconectando é só quando de fato há o que reconectar. Câmera
          arquivada não está "tentando" nada — dizer que está seria mentir com
          animação. */}
      {estado === 'offline' && camera.is_active && (
        <LogikosLoader
          variante={compacto ? 'spinner' : 'tile'}
          estado="retry"
          rotulo={`RECONECTANDO · ${camera.name}`}
          tamanho={grande ? 52 : 44}
        />
      )}
      {estado === 'offline' && !camera.is_active && (
        <span className={s.centradoDetalhe}>Câmera arquivada</span>
      )}

      <span className={s.tarjaNome}>{camera.name}</span>
      <span className={s.tarjaEstado[estado]} title={descricao}>
        {compacto ? tarja.icone : descricao}
      </span>

      {deteccoes.length > 0 && <CamadaCaixas deteccoes={deteccoes} comRotulo={!compacto} />}

      {onDestacar != null && (
        <button
          type="button"
          className={s.botaoDestacar}
          title="Destacar esta câmera"
          aria-label={`Destacar ${camera.name}`}
          onClick={(e) => {
            e.stopPropagation()
            onDestacar()
          }}
        >
          <Maximize2 size={14} strokeWidth={1.8} />
        </button>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Gaveta da câmera
// ---------------------------------------------------------------------------
function Gaveta({
  camera,
  deteccoes,
  onFechar,
  onDestacar,
}: {
  camera: Camera
  deteccoes: Detection[]
  onFechar: () => void
  onDestacar: () => void
}) {
  const { hlsUrl } = useLiveView(camera.id, camera.is_active)
  const [eventos, setEventos] = useState<AlertaRecente[] | null>(null)

  useEffect(() => {
    let vivo = true
    setEventos(null)
    api
      .get<{ data?: { alerts?: AlertaRecente[] } }>(
        `/alerts?camera_id=${encodeURIComponent(camera.id)}&per_page=5`,
      )
      .then((res) => {
        if (vivo) setEventos(res.data?.alerts ?? [])
      })
      .catch(() => {
        if (vivo) setEventos([])
      })
    return () => {
      vivo = false
    }
  }, [camera.id])

  const estado: EstadoCamera = !camera.is_active ? 'offline' : hlsUrl != null ? 'online' : 'conectando'

  return (
    <aside className={s.gaveta} aria-label={`Detalhes de ${camera.name}`}>
      <div className={s.gavetaTopo}>
        <span className={s.gavetaNome}>{camera.name}</span>
        <span className={s.tarjaEstado[estado]} style={{ position: 'static' }}>
          {TARJA[estado].icone} {TARJA[estado].palavra}
        </span>
        <button type="button" className={s.gavetaFechar} onClick={onFechar} aria-label="Fechar painel">
          <X size={13} strokeWidth={1.8} />
        </button>
      </div>

      <div className={s.gavetaVideo}>
        {hlsUrl != null && (
          <div className={s.moldura}>
            <CameraPlayer cameraId={camera.id} hlsUrl={hlsUrl} />
          </div>
        )}
        {deteccoes.length > 0 && <CamadaCaixas deteccoes={deteccoes} comRotulo />}
      </div>

      {/* Só o que o backend de fato devolve nesta rota. Resolução e origem do
          feed (o "1080P · HLS · EDGE" do desenho) não vêm de GET /cameras. */}
      <div className={s.gavetaDados}>
        <span>{camera.fps_target != null ? `${camera.fps_target} FPS` : 'FPS —'}</span>
        <span>HLS</span>
        <span>{camera.location ?? 'SEM LOCAL'}</span>
      </div>

      <button type="button" className={s.acaoSecundaria} onClick={onDestacar}>
        <Maximize2 size={14} strokeWidth={1.8} />
        Destacar no grid
      </button>

      <div className={s.blocoLista}>
        <span className={s.overline}>Eventos recentes</span>
        {eventos == null ? (
          <LogikosLoader variante="spinner" estado="waiting" />
        ) : eventos.length === 0 ? (
          <span className={s.centradoDetalhe}>Nenhum evento nesta câmera</span>
        ) : (
          eventos.map((ev) => (
            <Link key={ev.id} to={rotaNova(`/epi/eventos/${ev.id}`)} className={s.itemEvento}>
              <span className={s.pontoEvento} />
              <span className={s.eventoTitulo}>
                {ev.class_name ?? ev.violations?.map((v) => v.class).filter(Boolean).join(', ') ?? 'Evento'}
              </span>
              <span className={s.eventoHora}>{horaDe(ev.captured_at ?? ev.created_at)}</span>
            </Link>
          ))
        )}
      </div>

      <Link to={rotaNova('/epi/cameras')} className={s.acaoSecundaria}>
        Ir para gestão da câmera
      </Link>
    </aside>
  )
}

function horaDe(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? '—'
    : d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
}

// ---------------------------------------------------------------------------
// AoVivo
// ---------------------------------------------------------------------------
export function AoVivo() {
  const { can } = useAuth()
  const podeVer = can('cameras:read')

  const [cameras, setCameras] = useState<Camera[] | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [carregando, setCarregando] = useState(true)

  const [preset, setPreset] = useState<Preset>('2x2')
  const [colunas, setColunas] = useState(4)
  const [overlay, setOverlay] = useState(true)
  const [selecionada, setSelecionada] = useState<string | null>(null)
  const [focada, setFocada] = useState<string | null>(null)

  const carregar = useCallback(async () => {
    setCarregando(true)
    setErro(null)
    try {
      const res = await api.get<{ data?: { cameras?: Camera[] } | Camera[] }>('/cameras')
      const bruto = res.data
      const lista = Array.isArray(bruto)
        ? bruto
        : Array.isArray(bruto?.cameras)
          ? bruto.cameras
          : []
      setCameras(lista)
    } catch (e) {
      setCameras(null)
      setErro(e instanceof Error ? e.message : 'Conexão recusada')
    } finally {
      setCarregando(false)
    }
  }, [])

  useEffect(() => {
    if (podeVer) void carregar()
    else setCarregando(false)
  }, [carregar, podeVer])

  // WebSocket de detecções — JWT vai no handshake (`auth`), nunca na query.
  const token = getToken()
  const { detections, subscribeCamera, connected } = useMonitoringSocket({
    wsUrl: WS_URL,
    token: token ?? '',
    enabled: !!token && podeVer,
  })

  useEffect(() => {
    if (!connected || cameras == null) return
    cameras.forEach((c) => subscribeCamera(c.id))
  }, [cameras, connected, subscribeCamera])

  const colunasEfetivas = COLUNAS_DO_PRESET[preset] ?? colunas
  const compacto = colunasEfetivas >= COLUNAS_COMPACTAS
  const emDestaque = preset === 'destaque'

  const camDe = useCallback(
    (id: string | null) => (id == null ? null : (cameras?.find((c) => c.id === id) ?? null)),
    [cameras],
  )
  const cameraSelecionada = camDe(selecionada)
  const cameraFocada = camDe(focada) ?? cameras?.[0] ?? null

  const deteccoesDe = useCallback(
    (id: string): Detection[] => (overlay ? (detections[id] ?? []) : []),
    [detections, overlay],
  )

  const ativas = useMemo(() => cameras?.filter((c) => c.is_active).length ?? 0, [cameras])

  const destacar = useCallback((id: string) => {
    setPreset('destaque')
    setFocada(id)
    setSelecionada(null)
  }, [])

  if (!podeVer) {
    return (
      <div className={s.centrado}>
        <Video size={36} strokeWidth={1.5} aria-hidden />
        <span className={s.centradoTitulo}>Sem permissão para ver câmeras</span>
        <span className={s.centradoTexto}>
          Peça a um administrador a permissão <code>cameras:read</code> para acompanhar o ao vivo.
        </span>
      </div>
    )
  }

  if (carregando) {
    return <LogikosLoader variante="fullscreen" estado="waiting" rotulo="CONECTANDO ÀS CÂMERAS" />
  }

  if (erro != null) {
    return (
      <div className={s.centrado}>
        <span className={s.centradoTitulo}>Falha ao conectar ao gateway de vídeo</span>
        <span className={s.centradoDetalhe}>GET /cameras · {erro.toUpperCase()}</span>
        <button type="button" className={s.acaoPrimaria} onClick={() => void carregar()}>
          Tentar novamente
        </button>
      </div>
    )
  }

  if (cameras == null || cameras.length === 0) {
    return (
      <div className={s.centrado}>
        <Video size={36} strokeWidth={1.5} aria-hidden />
        <span className={s.centradoTitulo}>Nenhuma câmera neste site</span>
        <span className={s.centradoTexto}>
          Cadastre a primeira câmera para começar o monitoramento ao vivo.
        </span>
        <Link to={rotaNova('/epi/cameras')} className={s.acaoPrimaria}>
          Adicionar câmera
        </Link>
      </div>
    )
  }

  return (
    <div className={s.pagina}>
      <div className={s.barra}>
        <h1 className={s.titulo}>Ao Vivo</h1>
        <span className={s.resumo}>
          {cameras.length} CÂMERAS · {ativas} ATIVAS
        </span>
        <span className={s.espacador} />

        <div className={s.grupoPresets} role="group" aria-label="Layout da grade">
          {PRESETS.map(([chave, rotulo]) => (
            <button
              key={chave}
              type="button"
              className={s.preset[preset === chave ? 'ativo' : 'inativo']}
              aria-pressed={preset === chave}
              onClick={() => setPreset(chave)}
            >
              {rotulo}
            </button>
          ))}
        </div>

        <div className={s.colunas[preset === 'custom' ? 'ativo' : 'inativo']}>
          <span className={s.rotuloColunas}>COLUNAS</span>
          <button
            type="button"
            className={s.passo}
            aria-label="Menos colunas"
            disabled={colunas <= 2}
            onClick={() => {
              setPreset('custom')
              setColunas((c) => Math.max(2, c - 1))
            }}
          >
            −
          </button>
          <span
            className={s.valorColunas[preset === 'custom' ? 'ativo' : 'inativo']}
            data-testid="colunas-valor"
          >
            {colunasEfetivas}
          </span>
          <button
            type="button"
            className={s.passo}
            aria-label="Mais colunas"
            disabled={colunas >= 6}
            onClick={() => {
              setPreset('custom')
              setColunas((c) => Math.min(6, c + 1))
            }}
          >
            +
          </button>
        </div>

        <button
          type="button"
          className={s.alternador[overlay ? 'ligado' : 'desligado']}
          aria-pressed={overlay}
          onClick={() => setOverlay((v) => !v)}
        >
          <span className={s.trilho[overlay ? 'ligado' : 'desligado']} aria-hidden>
            <span className={s.botaoTrilho[overlay ? 'ligado' : 'desligado']} />
          </span>
          Overlay de detecção
        </button>
      </div>

      <div className={s.area}>
        <div className={s.coluna}>
          {emDestaque && cameraFocada != null ? (
            <div className={s.destaque}>
              <div className={s.focoColuna}>
                <Ladrilho
                  key={cameraFocada.id}
                  camera={cameraFocada}
                  deteccoes={deteccoesDe(cameraFocada.id)}
                  compacto={false}
                  selecionado={false}
                  suprimido={selecionada === cameraFocada.id}
                  grande
                  onSelecionar={() => setSelecionada(cameraFocada.id)}
                />
              </div>
              <div className={s.trilhoLateral}>
                {cameras
                  .filter((c) => c.id !== cameraFocada.id)
                  .map((c) => (
                    <Ladrilho
                      key={c.id}
                      camera={c}
                      deteccoes={deteccoesDe(c.id)}
                      compacto
                      selecionado={selecionada === c.id}
                      suprimido={selecionada === c.id}
                      onSelecionar={() => setFocada(c.id)}
                    />
                  ))}
              </div>
            </div>
          ) : (
            <div
              className={s.grade}
              data-testid="grade"
              style={{ gridTemplateColumns: `repeat(${colunasEfetivas}, 1fr)` }}
            >
              {cameras.map((c) => (
                <Ladrilho
                  key={c.id}
                  camera={c}
                  deteccoes={deteccoesDe(c.id)}
                  compacto={compacto}
                  selecionado={selecionada === c.id}
                  suprimido={selecionada === c.id}
                  onSelecionar={() => setSelecionada(c.id)}
                  onDestacar={() => destacar(c.id)}
                />
              ))}
              <Link to={rotaNova('/epi/cameras')} className={s.ladrilhoVago}>
                <Plus size={22} strokeWidth={1.7} aria-hidden />
                Adicionar câmera
              </Link>
            </div>
          )}
        </div>

        {cameraSelecionada != null && (
          <Gaveta
            camera={cameraSelecionada}
            deteccoes={deteccoesDe(cameraSelecionada.id)}
            onFechar={() => setSelecionada(null)}
            onDestacar={() => destacar(cameraSelecionada.id)}
          />
        )}
      </div>
    </div>
  )
}
