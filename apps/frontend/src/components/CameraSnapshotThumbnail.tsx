/**
 * CameraSnapshotThumbnail — miniatura de triagem (Bloco A, CameraTriagePage).
 *
 * Carrega SOB DEMANDA: só ativa (POST /refresh + poll de GET /snapshot)
 * quando o elemento entra na viewport (IntersectionObserver) — nunca
 * dispara as N câmeras da tela de uma vez. A concorrência real das
 * chamadas de rede é limitada pela `snapshotQueue` (useCameraSnapshot).
 *
 * Nunca ativa a câmera nem toca no channel_map/HLS — é só leitura do
 * snapshot cacheado no servidor (R2 + Redis), substituindo o preview ao
 * vivo temporário que existia antes para câmeras draft.
 */
import { useEffect, useRef, useState } from 'react'
import { useCameraSnapshot } from '../hooks/useCameraSnapshot'
import * as s from './CameraSnapshotThumbnail.css'

interface CameraSnapshotThumbnailProps {
  cameraId: string
}

function formatAge(capturedAt: string): string {
  const ms = Date.now() - new Date(capturedAt).getTime()
  const minutes = Math.max(0, Math.round(ms / 60000))
  if (minutes < 1) return 'capturada agora'
  if (minutes === 1) return 'capturada há 1 min'
  return `capturada há ${minutes} min`
}

export function CameraSnapshotThumbnail({ cameraId }: CameraSnapshotThumbnailProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [inView, setInView] = useState(false)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    if (typeof IntersectionObserver === 'undefined') {
      // Ambiente sem IntersectionObserver (ex.: jsdom em teste) — carrega
      // direto em vez de nunca carregar.
      setInView(true)
      return
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          setInView(true)
          observer.disconnect() // só precisa disparar a ativação uma vez
        }
      },
      { rootMargin: '200px' },
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  const snap = useCameraSnapshot(cameraId, inView)

  return (
    <div ref={containerRef} className={s.wrapper} data-testid={`snapshot-thumb-${cameraId}`}>
      <div className={s.imageButton}>{renderThumbnailContent(snap)}</div>
      <button
        type="button"
        className={s.refreshBtn}
        onClick={() => snap.refresh()}
        disabled={snap.loading}
        aria-label="Atualizar imagem"
        title="Atualizar imagem"
      >
        {snap.loading ? '…' : '↻'}
      </button>
    </div>
  )
}

function renderThumbnailContent(snap: ReturnType<typeof useCameraSnapshot>) {
  // 'pending'/'failed' podem trazer a URL da captura ANTERIOR (o servidor
  // preserva o último r2_key enquanto uma captura nova está em andamento ou
  // acabou de falhar) — mostra a miniatura velha com um selo, em vez de
  // apagar a imagem só porque a tentativa mais recente não terminou bem.
  if (snap.url) {
    const badge =
      snap.status === 'pending'
        ? 'atualizando…'
        : snap.status === 'failed'
          ? snap.errorReason || 'falha ao atualizar'
          : snap.capturedAt
            ? formatAge(snap.capturedAt)
            : null
    return (
      <>
        <img src={snap.url} alt="" className={s.image} />
        {badge && (
          <span className={snap.status === 'failed' ? s.failedBadge : s.capturedBadge}>
            {badge}
          </span>
        )}
      </>
    )
  }
  if (snap.status === 'failed') {
    return <span className={s.failedText}>{snap.errorReason || 'Falha ao capturar imagem'}</span>
  }
  if (snap.timedOut) {
    return <span className={s.failedText}>Tempo esgotado ao capturar</span>
  }
  if (snap.loading || snap.status === 'pending') {
    return <span className={s.statusText}>Capturando…</span>
  }
  return <span className={s.statusText}>—</span>
}

/**
 * CameraSnapshotViewer — versão ampliada, usada no painel/modal aberto pelo
 * "Ver imagem" de uma câmera draft. Sempre ativa (o caller só monta isto
 * quando o painel está aberto).
 */
export function CameraSnapshotViewer({ cameraId }: { cameraId: string }) {
  const snap = useCameraSnapshot(cameraId, true)

  // 'pending'/'failed' podem trazer a URL da captura anterior — mostra a
  // imagem que já existe em vez de um placeholder vazio enquanto atualiza
  // ou depois de uma falha (a mensagem de status some junto).
  if (snap.url) {
    return (
      <div className={s.enlargedWrap}>
        <img src={snap.url} alt="" className={s.enlargedImage} />
        <div className={s.enlargedMeta}>
          {snap.status === 'pending' && 'Atualizando…'}
          {snap.status === 'failed' && (snap.errorReason || 'Falha ao atualizar')}
          {snap.status === 'ready' && snap.capturedAt && formatAge(snap.capturedAt)}
          {' · '}
          <button type="button" onClick={() => snap.refresh()} disabled={snap.loading}>
            {snap.loading ? 'Atualizando…' : 'Atualizar imagem'}
          </button>
        </div>
      </div>
    )
  }

  let message = 'Capturando imagem…'
  if (snap.status === 'failed') message = snap.errorReason || 'Falha ao capturar imagem'
  else if (snap.timedOut) message = 'Tempo esgotado ao capturar imagem'
  else if (snap.status === 'none' && !snap.loading) message = 'Nenhuma imagem capturada ainda'

  return (
    <div className={s.enlargedWrap}>
      <div className={s.enlargedPlaceholder}>{message}</div>
      <button type="button" onClick={() => snap.refresh()} disabled={snap.loading}>
        {snap.loading ? 'Atualizando…' : 'Tentar novamente'}
      </button>
    </div>
  )
}
