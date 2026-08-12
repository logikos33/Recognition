/**
 * useCameraSnapshot — miniatura de triagem (Bloco A, CameraTriagePage).
 *
 * Fluxo: POST /snapshot/refresh (o backend decide se é no-op — cache ainda
 * fresco — ou se despacha uma captura de verdade) seguido de polling de
 * GET /snapshot até "ready"/"failed" ou um teto de tentativas. Toda chamada
 * de rede passa pela `snapshotQueue` compartilhada (concorrência 1-2) —
 * nunca dispara as N miniaturas da tela de uma vez.
 *
 * Só ativa quando `active` é true (o caller decide isso via IntersectionObserver
 * — ver CameraSnapshotThumbnail) e só dispara UMA vez por ativação; chamar
 * `refresh()` força uma nova rodada (botão "atualizar imagem").
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { cameraService, type CameraSnapshotState, type CameraSnapshotStatus } from '../services/cameraService'
import { snapshotQueue } from '../utils/concurrencyQueue'

const POLL_INTERVAL_MS = 4000
const MAX_POLL_ATTEMPTS = 15 // ~1 min de tentativas (teto — nunca poll infinito)

export interface UseCameraSnapshotResult {
  status: CameraSnapshotStatus | 'idle'
  url: string | null
  capturedAt: string | null
  errorReason: string | null
  loading: boolean
  timedOut: boolean
  /** Força nova captura (respeita o cache fresco do servidor — pode virar no-op). */
  refresh: () => void
}

export function useCameraSnapshot(cameraId: string, active: boolean): UseCameraSnapshotResult {
  const [state, setState] = useState<CameraSnapshotState | null>(null)
  const [loading, setLoading] = useState(false)
  const [timedOut, setTimedOut] = useState(false)
  // Token de cancelamento: cada refresh()/unmount invalida o loop de poll
  // anterior sem precisar de AbortController por request (requests já
  // passam pela fila compartilhada — cancelar aqui só evita setState órfão).
  const pollToken = useRef(0)

  const poll = useCallback(async (token: number) => {
    for (let attempt = 0; attempt < MAX_POLL_ATTEMPTS; attempt++) {
      if (pollToken.current !== token) return
      try {
        const snap = await snapshotQueue.run(() => cameraService.getSnapshot(cameraId))
        if (pollToken.current !== token) return
        setState(snap)
        if (snap.status === 'ready' || snap.status === 'failed') {
          setLoading(false)
          return
        }
      } catch {
        if (pollToken.current !== token) return
        setLoading(false)
        setState({
          status: 'failed', url: null, captured_at: null,
          error_reason: 'Erro ao consultar o estado do snapshot',
        })
        return
      }
      await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS))
    }
    if (pollToken.current === token) {
      setLoading(false)
      setTimedOut(true)
    }
  }, [cameraId])

  const trigger = useCallback(() => {
    const token = ++pollToken.current
    setLoading(true)
    setTimedOut(false)
    snapshotQueue
      .run(() => cameraService.refreshSnapshot(cameraId))
      .catch(() => {
        // Falha no refresh não é fatal — o GET seguinte ainda pode achar um
        // cache pronto; o poll abaixo decide o desfecho.
      })
      .finally(() => {
        if (pollToken.current === token) void poll(token)
      })
  }, [cameraId, poll])

  useEffect(() => {
    if (!active) return
    trigger()
    return () => {
      pollToken.current += 1 // cancela qualquer poll em andamento (unmount/troca de câmera)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- trigger() muda de identidade a cada render por causa do cameraId; disparar só quando active/cameraId mudam é intencional (1x por ativação).
  }, [active, cameraId])

  return {
    status: state?.status ?? 'idle',
    url: state?.url ?? null,
    capturedAt: state?.captured_at ?? null,
    errorReason: state?.error_reason ?? null,
    loading,
    timedOut,
    refresh: trigger,
  }
}
