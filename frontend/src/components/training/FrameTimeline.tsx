/**
 * FrameTimeline — carrossel estilo CapCut para navegação de frames.
 *
 * Layout:
 *   Topo (70%): preview grande do frame selecionado
 *   Baixo (30%): timeline horizontal scrollável com thumbnails densas
 *
 * Navegação: setas ← →, teclas de teclado, clique no thumb
 * Badges por frame: anotado ✓ / pré-anotado ◎ / vazio ○
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, X, Pencil, Wand2 } from 'lucide-react'
import * as s from './FrameTimeline.css'

export interface FrameInfo {
  id: string
  filename: string
  url?: string
  annotation_status?: 'annotated' | 'pre_annotated' | 'empty'
  frame_number?: number
}

interface FrameTimelineProps {
  frames: FrameInfo[]
  videoName: string
  apiBase: string
  onAnnotate: (frameId: string) => void
  onPreAnnotate?: (frameId: string) => void
  onClose: () => void
}

function FrameBadge({ status }: { status?: FrameInfo['annotation_status'] }) {
  if (status === 'annotated') return <span className={s.badgeAnnotated} title="Anotado">✓</span>
  if (status === 'pre_annotated') return <span className={s.badgePreAnnotated} title="Pré-anotado">◎</span>
  return <span className={s.badgeEmpty} title="Sem anotação">○</span>
}

export function FrameTimeline({ frames, videoName, apiBase, onAnnotate, onPreAnnotate, onClose }: FrameTimelineProps) {
  const [currentIndex, setCurrentIndex] = useState(0)
  const timelineRef = useRef<HTMLDivElement>(null)
  const thumbRefs = useRef<(HTMLButtonElement | null)[]>([])

  const current = frames[currentIndex]
  const total = frames.length

  const goTo = useCallback((index: number) => {
    const clamped = Math.max(0, Math.min(index, total - 1))
    setCurrentIndex(clamped)
    // Scroll thumb into view
    thumbRefs.current[clamped]?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' })
  }, [total])

  const goPrev = useCallback(() => goTo(currentIndex - 1), [currentIndex, goTo])
  const goNext = useCallback(() => goTo(currentIndex + 1), [currentIndex, goTo])

  // Keyboard navigation
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft') { e.preventDefault(); goPrev() }
      if (e.key === 'ArrowRight') { e.preventDefault(); goNext() }
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [goPrev, goNext, onClose])

  if (!current) return null

  const frameUrl = current.url ?? `${apiBase}/api/training/frames/${current.id}/image`

  return (
    <div className={s.overlay}>
      <div className={s.container}>
        {/* Header */}
        <div className={s.header}>
          <span className={s.videoName}>{videoName}</span>
          <span className={s.frameCount}>
            frame <strong>{currentIndex + 1}</strong> / {total}
          </span>
          <div className={s.headerActions}>
            {onPreAnnotate && (
              <button className={s.actionBtn} onClick={() => onPreAnnotate(current.id)} title="Pre-anotar com IA">
                <Wand2 size={14} /> Pre-anotar com IA
              </button>
            )}
            <button className={s.actionBtnPrimary} onClick={() => onAnnotate(current.id)} title="Abrir anotação">
              <Pencil size={14} /> Anotar
            </button>
            <button className={s.closeBtn} onClick={onClose} title="Fechar (Esc)">
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Preview */}
        <div className={s.preview}>
          <button
            className={`${s.navBtn} ${s.navBtnLeft}`}
            onClick={goPrev}
            disabled={currentIndex === 0}
            aria-label="Frame anterior"
          >
            <ChevronLeft size={20} />
          </button>

          <div className={s.previewImageWrap}>
            <img
              key={current.id}
              className={s.previewImage}
              src={frameUrl}
              alt={`Frame ${currentIndex + 1}`}
              draggable={false}
            />
            <div className={s.previewBadge}>
              <FrameBadge status={current.annotation_status} />
              <span className={s.previewBadgeLabel}>
                {current.annotation_status === 'annotated' ? 'Anotado'
                  : current.annotation_status === 'pre_annotated' ? 'Pré-anotado'
                  : 'Sem anotação'}
              </span>
            </div>
          </div>

          <button
            className={`${s.navBtn} ${s.navBtnRight}`}
            onClick={goNext}
            disabled={currentIndex === total - 1}
            aria-label="Próximo frame"
          >
            <ChevronRight size={20} />
          </button>
        </div>

        {/* Timeline strip */}
        <div className={s.timeline} ref={timelineRef}>
          {frames.map((frame, idx) => (
            <button
              key={frame.id}
              ref={el => { thumbRefs.current[idx] = el }}
              className={`${s.thumb} ${idx === currentIndex ? s.thumbActive : ''}`}
              onClick={() => goTo(idx)}
              title={`Frame ${idx + 1}${frame.annotation_status === 'annotated' ? ' ✓' : ''}`}
            >
              <img
                className={s.thumbImg}
                src={frame.url ?? `${apiBase}/api/training/frames/${frame.id}/image`}
                alt={`Frame ${idx + 1}`}
                loading="lazy"
                draggable={false}
              />
              <div className={s.thumbBadgeWrap}>
                <FrameBadge status={frame.annotation_status} />
              </div>
              {idx === currentIndex && <div className={s.thumbActiveBar} />}
            </button>
          ))}
        </div>

        {/* Keyboard hint */}
        <div className={s.hint}>
          <span>← → navegar</span>
          <span>·</span>
          <span>Esc fechar</span>
        </div>
      </div>
    </div>
  )
}
