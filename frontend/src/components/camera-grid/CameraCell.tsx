/**
 * CameraCell — individual cell in the DVR grid.
 * Renders HLS player + detection overlay for assigned camera.
 */
import { useState, useEffect, useCallback } from 'react'
import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { CameraPlayer } from '../monitoring/CameraPlayer'
import { DetectionOverlay } from '../monitoring/DetectionOverlay'
import type { Detection } from '../monitoring/DetectionOverlay'
import type { Camera } from '../../types'
import {
  cellBase, cellExpanded, cellAlert, cellDragOver, cellDragging,
  cellHeader, cellName, liveBadge, liveDot, alertBadge, alertDot,
  cellFooter, cellLocation, cellTime, playerWrap,
} from './CameraGrid.css'

interface CameraCellProps {
  position: number
  camera: Camera | null
  detections?: Detection[]
  hasViolation?: boolean
  isExpanded?: boolean
  showLabels?: boolean
  colspan?: number
  rowspan?: number
  onDoubleClick?: () => void
  onContextMenu?: (e: React.MouseEvent) => void
}

export function CameraCell({
  position,
  camera,
  detections = [],
  hasViolation = false,
  isExpanded = false,
  showLabels = true,
  colspan,
  rowspan,
  onDoubleClick,
  onContextMenu,
}: CameraCellProps) {
  const [time, setTime] = useState('')

  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
    isOver,
  } = useSortable({ id: `cell-${position}`, data: { position } })

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    ...(colspan && { gridColumn: `span ${colspan}` }),
    ...(rowspan && { gridRow: `span ${rowspan}` }),
  }

  // Update clock every second
  useEffect(() => {
    const update = () => setTime(new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }))
    update()
    const id = setInterval(update, 60000)
    return () => clearInterval(id)
  }, [])

  const handleContextMenu = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    onContextMenu?.(e)
  }, [onContextMenu])

  if (!camera) return null

  const apiBase = import.meta.env.VITE_API_URL || ''
  const hlsUrl = `${apiBase}/api/cameras/${camera.id}/stream/stream.m3u8`

  const classes = [
    cellBase,
    isExpanded && cellExpanded,
    hasViolation && cellAlert,
    isOver && cellDragOver,
    isDragging && cellDragging,
  ].filter(Boolean).join(' ')

  return (
    <div
      ref={setNodeRef}
      className={classes}
      style={style}
      onDoubleClick={onDoubleClick}
      onContextMenu={handleContextMenu}
      {...attributes}
      {...listeners}
    >
      {/* Header overlay */}
      {showLabels && (
        <div className={cellHeader}>
          <span className={cellName}>
            {camera.name}
          </span>
          {hasViolation ? (
            <span className={alertBadge}>
              <span className={alertDot} /> ALERT
            </span>
          ) : (
            <span className={liveBadge}>
              <span className={liveDot} /> LIVE
            </span>
          )}
        </div>
      )}

      {/* HLS Player + Detection Overlay */}
      <div className={playerWrap}>
        <CameraPlayer
          cameraId={camera.id}
          hlsUrl={hlsUrl}
          width={640}
          height={360}
        />
        <DetectionOverlay
          detections={detections}
          videoWidth={640}
          videoHeight={360}
          displayWidth={640}
          displayHeight={360}
        />
      </div>

      {/* Footer overlay */}
      {showLabels && (
        <div className={cellFooter}>
          <span className={cellLocation}>{camera.location || 'Sem local'}</span>
          <span className={cellTime}>{time}</span>
        </div>
      )}
    </div>
  )
}
