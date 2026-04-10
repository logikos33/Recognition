/**
 * CameraGrid — DVR-style camera monitoring container.
 * Supports drag-drop reordering, layout presets, fullscreen, context menu.
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import {
  DndContext, closestCenter, DragEndEvent,
  PointerSensor, useSensor, useSensors,
} from '@dnd-kit/core'
import { SortableContext, rectSortingStrategy } from '@dnd-kit/sortable'
import { useCameraGridStore } from '../../stores/cameraGridStore'
import { useMonitoringSocket } from '../../hooks/useMonitoringSocket'
import { usePolling } from '../../hooks/usePolling'
import { api, getToken } from '../../services/api'
import type { Camera } from '../../types'
import { CameraCell } from './CameraCell'
import { CameraPlaceholder } from './CameraPlaceholder'
import { GridToolbar } from './GridToolbar'
import { GridPanel } from './GridPanel'
import {
  container, grid,
  contextMenu, contextMenuItem, contextMenuDanger,
  cameraSelectorOverlay, cameraSelectorDropdown,
  cameraSelectorItem, cameraSelectorTitle,
  hamburgerBtn,
} from './CameraGrid.css'
import { Maximize, Minimize, ArrowLeftRight, X, Menu } from 'lucide-react'

const WS_URL = import.meta.env.VITE_WS_URL || import.meta.env.VITE_API_URL || ''

interface ContextMenuState {
  x: number
  y: number
  position: number
}

export function CameraGrid() {
  const getActiveLayout = useCameraGridStore((s) => s.getActiveLayout)
  const cellAssignments = useCameraGridStore((s) => s.cellAssignments)
  const assignCamera = useCameraGridStore((s) => s.assignCamera)
  const swapCells = useCameraGridStore((s) => s.swapCells)
  const removeCamera = useCameraGridStore((s) => s.removeCamera)
  const expandedCell = useCameraGridStore((s) => s.expandedCell)
  const expandCell = useCameraGridStore((s) => s.expandCell)
  const showLabels = useCameraGridStore((s) => s.showLabels)

  const [cameras, setCameras] = useState<Camera[]>([])
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [ctxMenu, setCtxMenu] = useState<ContextMenuState | null>(null)
  const [selectorPos, setSelectorPos] = useState<number | null>(null)
  const [panelOpen, setPanelOpen] = useState(false)

  const containerRef = useRef<HTMLDivElement>(null)
  const token = getToken()
  const layout = getActiveLayout()

  // Fetch cameras with polling (60s refresh, visibility-aware)
  const fetchCameras = useCallback(async () => {
    const res = await api.get<any>('/cameras')
    const data = res as any
    const list = Array.isArray(data?.data) ? data.data : (data?.data?.cameras || data?.cameras || [])
    setCameras(list)
  }, [])

  usePolling(fetchCameras, 60000)

  // WebSocket for detections
  const { detections, alerts } = useMonitoringSocket({
    wsUrl: WS_URL,
    token: token || '',
    enabled: !!token,
  })


  // DnD sensors
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } })
  )

  const handleDragEnd = useCallback((event: DragEndEvent) => {
    const { active, over } = event
    if (!over || active.id === over.id) return
    const fromPos = active.data.current?.position
    const toPos = over.data.current?.position
    if (fromPos !== undefined && toPos !== undefined) {
      swapCells(fromPos, toPos)
    }
  }, [swapCells])

  // Fullscreen toggle
  const toggleFullscreen = useCallback(() => {
    if (!containerRef.current) return
    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen().then(() => setIsFullscreen(true)).catch(() => {})
    } else {
      document.exitFullscreen().then(() => setIsFullscreen(false)).catch(() => {})
    }
  }, [])

  useEffect(() => {
    const handler = () => setIsFullscreen(!!document.fullscreenElement)
    document.addEventListener('fullscreenchange', handler)
    return () => document.removeEventListener('fullscreenchange', handler)
  }, [])

  // Close context menu on any click
  useEffect(() => {
    if (!ctxMenu) return
    const close = () => setCtxMenu(null)
    window.addEventListener('click', close)
    return () => window.removeEventListener('click', close)
  }, [ctxMenu])

  // Escape closes panel or expanded cell
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (panelOpen) setPanelOpen(false)
        else if (expandedCell !== null) expandCell(null)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [expandedCell, expandCell, panelOpen])

  // Build grid style based on layout
  const isAsymmetric = layout.id === '1+5' || layout.id === '1+7'
  const gridStyle: React.CSSProperties = isAsymmetric
    ? {
        gridTemplateColumns: `repeat(${layout.columns}, 1fr)`,
        gridTemplateRows: `repeat(${layout.rows}, 1fr)`,
      }
    : {
        gridTemplateColumns: `repeat(${layout.columns}, 1fr)`,
        gridTemplateRows: `repeat(${layout.rows}, 1fr)`,
      }

  // Camera lookup
  const cameraMap = new Map(cameras.map((c) => [c.id, c]))

  // Render cells
  const cellCount = layout.cells.length
  const cellIds = Array.from({ length: cellCount }, (_, i) => `cell-${i}`)

  const renderCell = (cellIndex: number) => {
    const cellDef = layout.cells[cellIndex]
    const cameraId = cellAssignments[cellIndex] ?? null
    const camera = cameraId ? cameraMap.get(cameraId) ?? null : null
    const isExpanded = expandedCell === cellIndex

    // Cell style for asymmetric layouts
    const cellStyle: React.CSSProperties = {}
    if (isAsymmetric && cellDef.colspan) cellStyle.gridColumn = `span ${cellDef.colspan}`
    if (isAsymmetric && cellDef.rowspan) cellStyle.gridRow = `span ${cellDef.rowspan}`

    const cameraDetections = camera ? (detections[camera.id] || []) : []
    const hasViolation = camera ? alerts.some((a) => a.camera_id === camera.id) : false

    if (!camera) {
      return (
        <div key={cellIndex} style={cellStyle}>
          <CameraPlaceholder
            position={cellIndex}
            onClick={() => setSelectorPos(cellIndex)}
          />
        </div>
      )
    }

    return (
      <div key={cellIndex} style={cellStyle}>
        <CameraCell
          position={cellIndex}
          camera={camera}
          detections={cameraDetections}
          hasViolation={hasViolation}
          isExpanded={isExpanded}
          showLabels={showLabels}
          onDoubleClick={() => expandCell(isExpanded ? null : cellIndex)}
          onContextMenu={(e) => setCtxMenu({ x: e.clientX, y: e.clientY, position: cellIndex })}
        />
      </div>
    )
  }

  return (
    <div ref={containerRef} className={container}>
      {/* Hamburger button */}
      <button
        className={hamburgerBtn}
        onClick={() => setPanelOpen(true)}
        aria-label="Abrir painel de controle"
      >
        <Menu size={18} />
      </button>

      {/* Side panel */}
      {panelOpen && (
        <GridPanel
          cameras={cameras}
          onClose={() => setPanelOpen(false)}
          onCamerasChanged={() => fetchCameras()}
        />
      )}

      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext items={cellIds} strategy={rectSortingStrategy}>
          <div className={grid} style={gridStyle}>
            {Array.from({ length: cellCount }, (_, i) => renderCell(i))}
          </div>
        </SortableContext>
      </DndContext>

      <GridToolbar
        isFullscreen={isFullscreen}
        onToggleFullscreen={toggleFullscreen}
      />

      {/* Context Menu */}
      {ctxMenu && (
        <div className={contextMenu} style={{ left: ctxMenu.x, top: ctxMenu.y }}>
          {expandedCell === ctxMenu.position ? (
            <button className={contextMenuItem} onClick={() => { expandCell(null); setCtxMenu(null) }}>
              <Minimize size={14} /> Restaurar
            </button>
          ) : (
            <button className={contextMenuItem} onClick={() => { expandCell(ctxMenu.position); setCtxMenu(null) }}>
              <Maximize size={14} /> Expandir
            </button>
          )}
          <button className={contextMenuItem} onClick={() => { setSelectorPos(ctxMenu.position); setCtxMenu(null) }}>
            <ArrowLeftRight size={14} /> Trocar câmera
          </button>
          <button className={contextMenuDanger} onClick={() => { removeCamera(ctxMenu.position); setCtxMenu(null) }}>
            <X size={14} /> Remover do grid
          </button>
        </div>
      )}

      {/* Camera Selector */}
      {selectorPos !== null && (
        <>
          <div className={cameraSelectorOverlay} onClick={() => setSelectorPos(null)} />
          <div className={cameraSelectorDropdown}>
            <div className={cameraSelectorTitle}>Selecionar câmera</div>
            {cameras.length === 0 ? (
              <div style={{ padding: '8px 10px', fontSize: 12, color: '#64748b' }}>
                Nenhuma câmera cadastrada
              </div>
            ) : (
              cameras.map((cam) => (
                <button
                  key={cam.id}
                  className={cameraSelectorItem}
                  onClick={() => {
                    assignCamera(selectorPos, cam.id)
                    setSelectorPos(null)
                  }}
                >
                  {cam.name}
                  {cam.location && <span style={{ marginLeft: 'auto', fontSize: 10, opacity: 0.5 }}>{cam.location}</span>}
                </button>
              ))
            )}
          </div>
        </>
      )}
    </div>
  )
}
