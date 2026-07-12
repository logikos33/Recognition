/**
 * Player de vídeo de clip NOK com renovação automática de URL presigned.
 *
 * Segurança: controlsList="nodownload" + onContextMenu preventDefault
 * A URL é gerenciada pelo hook useClipPlayer (renovação 2min antes de expirar).
 */
import { useRef } from 'react'
import { videoWrapper, videoElement } from './quality.css'
import { useClipPlayer } from '../hooks/useClipPlayer'
import { vars } from '../../../styles/theme.css'

interface ClipPlayerProps {
  inspectionId: string
  clipStatus: string
}

export function ClipPlayer({ inspectionId, clipStatus }: ClipPlayerProps) {
  const { url, loading, error } = useClipPlayer(
    clipStatus === 'available' ? inspectionId : null
  )
  const videoRef = useRef<HTMLVideoElement>(null)

  if (clipStatus === 'pending') {
    return (
      <div className={videoWrapper} style={{ padding: '24px', textAlign: 'center', color: vars.color.textMuted, fontSize: '13px' }}>
        Gerando clipe… isso pode levar alguns instantes.
      </div>
    )
  }

  if (clipStatus === 'unavailable' || clipStatus === 'expired') {
    return (
      <div className={videoWrapper} style={{ padding: '24px', textAlign: 'center', color: vars.color.textMuted, fontSize: '13px' }}>
        Clipe não disponível para esta inspeção.
      </div>
    )
  }

  if (loading) {
    return (
      <div className={videoWrapper} style={{ padding: '24px', textAlign: 'center', color: vars.color.textMuted, fontSize: '13px' }}>
        Carregando player…
      </div>
    )
  }

  if (error || !url) {
    return (
      <div className={videoWrapper} style={{ padding: '24px', textAlign: 'center', color: vars.color.danger, fontSize: '13px' }}>
        {error ?? 'Erro ao carregar clipe'}
      </div>
    )
  }

  return (
    <div className={videoWrapper}>
      {/* controlsList="nodownload" impede download nativo; onContextMenu bloqueia menu de contexto */}
      <video
        ref={videoRef}
        className={videoElement}
        src={url}
        controls
        controlsList="nodownload"
        onContextMenu={(e) => e.preventDefault()}
        playsInline
      />
    </div>
  )
}
