/**
 * useLiveView — fonte única da URL de live view.
 *
 * POR QUE ESTE HOOK EXISTE
 * `serve_hls` é público por design (hls.js não envia header de auth), então o
 * token de playback no path é o ÚNICO portão de tenant. Com
 * `HLS_REQUIRE_PLAYBACK_TOKEN` ligado (default desde o mutirão), a URL legada
 * montada no front — `${API}/api/cameras/${id}/stream/stream.m3u8` — recebe
 * **404**, e o player fica preto sem erro visível no backend.
 *
 * A URL TEM que vir de `POST /stream/start`, que valida o tenant do JWT e
 * assina o token. O token viaja no PATH (`/stream/s/<token>/stream.m3u8`) de
 * propósito: os `.ts` da playlist são relativos e herdam o token sozinhos.
 * Passar `?token=` em query NÃO funciona — `serve_hls` lê do path.
 *
 * IDEMPOTÊNCIA
 * Havia registro de o front chamar `/stream/start` 5× em 13s: cada re-render
 * de tela com várias câmeras disparava um POST por câmera. Duas travas aqui:
 *   1. `inFlight` — chamadas concorrentes para a mesma câmera compartilham a
 *      mesma Promise (dedupe entre componentes irmãos do mesmo grid);
 *   2. `cache` — a URL é reaproveitada enquanto o token não estiver perto de
 *      expirar, então re-render não gera request.
 *
 * RENOVAÇÃO
 * O token dura 1h (`HLS_PLAYBACK_TOKEN_TTL`). O hook renova sozinho um pouco
 * antes de expirar; e o player pode chamar `refresh()` quando levar 404 no
 * meio da sessão (token expirado é indistinguível de stream ausente — os dois
 * respondem 404 por C-01).
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { cameraService } from '../services/cameraService'

const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? ''

// TTL do token no backend é 3600s. Renovar com folga generosa: um live view
// aberto por horas não pode piscar, e o custo de um POST a mais é irrelevante
// perto de uma tela preta.
const RENEW_MARGIN_MS = 5 * 60 * 1000
const ASSUMED_TOKEN_TTL_MS = 60 * 60 * 1000
// Retry curto quando a renovação proativa falha com o token ainda vivo — uma
// falha transitória (deploy da API, rede) não pode deixar o token morrer:
// antes, a próxima tentativa só vinha no intervalo cheio (55min), o token
// vencia aos 60min e a grade inteira congelava no mesmo segundo (04/08).
const RENEW_RETRY_MS = 30_000

type CacheEntry = { url: string; fetchedAt: number; expMs: number | null }

const cache = new Map<string, CacheEntry>()
const inFlight = new Map<string, Promise<string>>()

/**
 * Extrai o epoch de expiração (ms) do token de playback embutido na URL
 * (`/stream/s/<exp>.<sig>/…` — o exp é público por construção, só a
 * assinatura é segredo). null para URL legada sem token.
 */
export function playbackTokenExpMs(url: string): number | null {
  const m = /\/stream\/s\/(\d+)\./.exec(url)
  return m ? Number(m[1]) * 1000 : null
}

function isFresh(entry: CacheEntry): boolean {
  // Fonte da verdade: o exp REAL do token na URL. Fallback (URL legada sem
  // token): idade do fetch contra o TTL espelhado do backend.
  if (entry.expMs !== null) return Date.now() < entry.expMs - RENEW_MARGIN_MS
  return Date.now() - entry.fetchedAt < ASSUMED_TOKEN_TTL_MS - RENEW_MARGIN_MS
}

/** Resolve a URL absoluta, deduplicando chamadas concorrentes por câmera. */
function resolveUrl(cameraId: string, force: boolean): Promise<string> {
  if (!force) {
    const cached = cache.get(cameraId)
    if (cached && isFresh(cached)) return Promise.resolve(cached.url)
    const pending = inFlight.get(cameraId)
    if (pending) return pending
  }

  const promise = cameraService
    .start(cameraId)
    .then((res) => {
      const raw = res?.hls_url
      if (!raw) throw new Error('Backend não devolveu hls_url')
      const url = raw.startsWith('http') ? raw : `${API_BASE}${raw}`
      cache.set(cameraId, { url, fetchedAt: Date.now(), expMs: playbackTokenExpMs(url) })
      return url
    })
    .finally(() => {
      inFlight.delete(cameraId)
    })

  inFlight.set(cameraId, promise)
  return promise
}

/**
 * Força um novo `/stream/start` e devolve a URL fresca — para uso FORA do ciclo
 * de vida do hook (ex.: `CameraPlayer` recuperando de erro fatal de rede do
 * hls.js, sem depender do componente que originalmente chamou `useLiveView`
 * re-renderizar com uma `hlsUrl` nova).
 *
 * Mesma semântica de `refresh()`: como é uma chamada "forçada", ela NÃO
 * reaproveita cache nem uma chamada já em voo (mesmo comportamento do
 * `resolveUrl(cameraId, force=true)` interno) — sempre bate no backend. Ok
 * para o caso de uso (recuperação de erro é raro), mas não chame em loop.
 */
export function refreshLiveViewUrl(cameraId: string): Promise<string> {
  return resolveUrl(cameraId, true)
}

export interface UseLiveViewResult {
  /** URL absoluta e tokenizada; `null` enquanto não resolveu. */
  hlsUrl: string | null
  loading: boolean
  error: string | null
  /** Força novo /stream/start — usar quando o player levar 404 (token expirado). */
  refresh: () => void
}

export function useLiveView(
  cameraId: string | undefined,
  enabled: boolean = true,
): UseLiveViewResult {
  const [hlsUrl, setHlsUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // Evita setState depois do unmount (grid de câmeras monta/desmonta bastante).
  const aliveRef = useRef(true)

  // Devolve `true` em sucesso — o ciclo de renovação proativa usa o sinal
  // para decidir entre reagendar o próximo ciclo ou entrar em retry curto.
  const load = useCallback(
    (force: boolean): Promise<boolean> => {
      if (!cameraId || !enabled) return Promise.resolve(false)
      setLoading(true)
      setError(null)
      return resolveUrl(cameraId, force)
        .then((url) => {
          if (aliveRef.current) setHlsUrl(url)
          return true
        })
        .catch((err: unknown) => {
          if (aliveRef.current) {
            setError(err instanceof Error ? err.message : 'Falha ao iniciar o stream')
          }
          return false
        })
        .finally(() => {
          if (aliveRef.current) setLoading(false)
        })
    },
    [cameraId, enabled],
  )

  useEffect(() => {
    aliveRef.current = true
    void load(false)
    return () => {
      aliveRef.current = false
    }
  }, [load])

  // Renovação proativa: mantém o token válido em sessão longa. Pausa enquanto a
  // aba está oculta (Page Visibility API) — task-teardown-abas: uma aba em
  // segundo plano não tem espectador nenhum (CameraPlayer já destruiu a
  // instância hls.js nesse momento — ver CameraPlayer.tsx), então bater
  // /stream/start aqui só re-arma a chave `epi:stream:{id}:active` no servidor
  // e, em modo local, pode até religar um FFmpeg que o watchdog já havia
  // corretamente encerrado por inatividade — sem ninguém de fato olhando.
  // ANCORADO NO EXP REAL do token (cache.expMs), não em intervalo fixo. O
  // setInterval de 55min tinha três modos de morte que congelaram a grade em
  // 04/08: (1) falha transitória da renovação (deploy da API) só tentava de
  // novo 55min depois — token morto aos 60; (2) voltar de aba oculta
  // reiniciava o intervalo INTEIRO; (3) o efeito re-executa em qualquer
  // toggle de [cameraId, enabled] (scroll/drawer mudando effectiveVisible) e
  // também zerava o relógio sem re-mintar. Agora: setTimeout calculado a
  // partir do exp do token vigente (+1s além da borda da margem, p/ não girar
  // em falso), retry curto em falha enquanto o token viver, e catch-up
  // imediato ao voltar visível se a renovação estiver atrasada. O ciclo usa
  // force=false de propósito: cache/inFlight deduplicam com o
  // reacquireAfterHidden do CameraPlayer (mesma câmera, mesmo instante — um
  // POST só); na borda de renovação o cache já não está fresco, então o
  // force=false ainda bate no backend.
  useEffect(() => {
    if (!cameraId || !enabled) return

    let timer: ReturnType<typeof setTimeout> | undefined
    let stopped = false

    const nextRenewalDelay = (): number => {
      const entry = cache.get(cameraId)
      if (entry && entry.expMs !== null) {
        // Teto no TTL nominal: um exp anômalo muito distante não pode virar
        // setTimeout gigante (delay > 2^31-1 ms estoura o int32 do timer e
        // dispara em 1ms — loop). Re-agendar no teto e reavaliar é barato.
        const untilMargin = Math.max(0, entry.expMs - RENEW_MARGIN_MS - Date.now()) + 1000
        return Math.min(untilMargin, ASSUMED_TOKEN_TTL_MS)
      }
      return ASSUMED_TOKEN_TTL_MS - RENEW_MARGIN_MS
    }

    const chain = (delay: number) => {
      if (stopped) return
      timer = setTimeout(() => {
        timer = undefined
        void load(false).then((ok) => {
          if (stopped) return
          if (ok) {
            // Piso de RENEW_RETRY_MS no reagendamento pós-sucesso: se o
            // backend mintar um token que o relógio DESTE cliente já considera
            // vencido (skew extremo), o ciclo degrada para 1 tentativa/30s em
            // vez de girar a cada segundo.
            chain(Math.max(RENEW_RETRY_MS, nextRenewalDelay()))
            return
          }
          // Falha com token ainda vivo → retry curto. Token já vencido →
          // desiste: o CameraPlayer recupera via 410 (refreshLiveViewUrl), e
          // duas correntes de retry martelariam o mesmo endpoint.
          const entry = cache.get(cameraId)
          const alive = !entry || entry.expMs === null || Date.now() < entry.expMs
          if (alive) chain(RENEW_RETRY_MS)
        })
      }, delay)
    }

    const unschedule = () => {
      if (timer) {
        clearTimeout(timer)
        timer = undefined
      }
    }
    const schedule = () => {
      if (timer) return
      chain(nextRenewalDelay())
    }

    if (!document.hidden) schedule()

    const handleVisibilityChange = () => {
      if (document.hidden) {
        unschedule()
      } else {
        schedule()
      }
    }
    document.addEventListener('visibilitychange', handleVisibilityChange)

    return () => {
      stopped = true
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      unschedule()
    }
  }, [cameraId, enabled, load])

  const refresh = useCallback(() => load(true), [load])

  return { hlsUrl, loading, error, refresh }
}

/** Só para testes: zera cache/in-flight entre casos. */
export function __resetLiveViewCache(): void {
  cache.clear()
  inFlight.clear()
}
