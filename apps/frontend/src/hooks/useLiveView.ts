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

type CacheEntry = { url: string; fetchedAt: number }

const cache = new Map<string, CacheEntry>()
const inFlight = new Map<string, Promise<string>>()

function isFresh(entry: CacheEntry): boolean {
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
      cache.set(cameraId, { url, fetchedAt: Date.now() })
      return url
    })
    .finally(() => {
      inFlight.delete(cameraId)
    })

  inFlight.set(cameraId, promise)
  return promise
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

  const load = useCallback(
    (force: boolean) => {
      if (!cameraId || !enabled) return
      setLoading(true)
      setError(null)
      resolveUrl(cameraId, force)
        .then((url) => {
          if (!aliveRef.current) return
          setHlsUrl(url)
        })
        .catch((err: unknown) => {
          if (!aliveRef.current) return
          setError(err instanceof Error ? err.message : 'Falha ao iniciar o stream')
        })
        .finally(() => {
          if (aliveRef.current) setLoading(false)
        })
    },
    [cameraId, enabled],
  )

  useEffect(() => {
    aliveRef.current = true
    load(false)
    return () => {
      aliveRef.current = false
    }
  }, [load])

  // Renovação proativa: mantém o token válido em sessão longa.
  useEffect(() => {
    if (!cameraId || !enabled) return
    const timer = setInterval(
      () => load(true),
      ASSUMED_TOKEN_TTL_MS - RENEW_MARGIN_MS,
    )
    return () => clearInterval(timer)
  }, [cameraId, enabled, load])

  const refresh = useCallback(() => load(true), [load])

  return { hlsUrl, loading, error, refresh }
}

/** Só para testes: zera cache/in-flight entre casos. */
export function __resetLiveViewCache(): void {
  cache.clear()
  inFlight.clear()
}
