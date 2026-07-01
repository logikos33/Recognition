/**
 * MonitoringPage — VMS ao vivo (deliverable h).
 *
 * Grid de câmeras filtrável por módulo.
 * Toggle de overlay de reconhecimento (bounding boxes).
 * Clicar numa câmera abre AppDrawer com feed ao vivo, logs e info.
 * Fechar drawer volta ao grid sem recarregar.
 *
 * Performance:
 *   - IntersectionObserver: só monta CameraPlayer das câmeras visíveis
 *   - Debounce 200ms nos updates de overlay via WS
 *   - Throttle 500ms nos logs ao vivo
 */
import {
  useState,
  useCallback,
  useEffect,
  useRef,
  useMemo,
  type RefObject,
} from 'react'
import { Eye, EyeOff } from 'lucide-react'
import { useAuth } from '../hooks/useAuth'
import {
  useMonitoringSocket,
  type Detection,
} from '../hooks/useMonitoringSocket'
import { api, getToken } from '../services/api'
import type { Camera } from '../types'
import { CameraPlayer } from '../components/monitoring/CameraPlayer'
import { DetectionOverlay } from '../components/monitoring/DetectionOverlay'
import { AppDrawer } from '../components/ui/AppDrawer/AppDrawer'
import {
  page,
  toolbar,
  moduleTabList,
  moduleTab,
  moduleTabActive,
  spacer,
  statusBadge,
  statusDotOnline,
  statusDotOffline,
  overlayToggle,
  overlayToggleActive,
  gridContainer,
  cameraGrid,
  cameraCard,
  cameraCardAlert,
  cardAspect,
  cardInner,
  cardPlaceholder,
  cardHeader,
  cardName,
  cardAlertLabel,
  cardFooter,
  cardLocation,
  cardModuleBadge,
  drawerFeed,
  drawerTabList,
  drawerTab,
  drawerTabActive,
  drawerScrollBody,
  drawerInfoGrid,
  drawerInfoItem,
  drawerInfoLabel,
  drawerInfoValue,
  logsList,
  logEntry,
  logEntryAlert,
  logTimestamp,
  logDetectionRow,
  emptyState,
} from './MonitoringPage.css'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const WS_URL = import.meta.env.VITE_WS_URL || import.meta.env.VITE_API_URL || ''
const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? ''

const MODULE_LABELS: Record<string, string> = {
  epi: 'EPI',
  fueling: 'Combustível',
  quality: 'Qualidade',
  parking: 'Estacionamento',
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface CameraWithModule extends Camera {
  module_code?: string
}

interface LogEntry {
  id: string
  timestamp: string
  detections: Detection[]
  hasViolation: boolean
}

// ---------------------------------------------------------------------------
// Hook: useIntersection — lazy rendering via IntersectionObserver
// ---------------------------------------------------------------------------
function useIntersection(
  ref: RefObject<HTMLDivElement | null>,
  rootMargin = '150px',
): boolean {
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const obs = new IntersectionObserver(
      (entries) => {
        const entry = entries[0]
        if (entry) setVisible(entry.isIntersecting)
      },
      { rootMargin, threshold: 0 },
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [ref, rootMargin])
  return visible
}

// ---------------------------------------------------------------------------
// VmsCameraCard — single camera tile with lazy HLS loading
// ---------------------------------------------------------------------------
interface VmsCameraCardProps {
  camera: CameraWithModule
  detections: Detection[]
  hasViolation: boolean
  onOpen: () => void
}

function VmsCameraCard({
  camera,
  detections,
  hasViolation,
  onOpen,
}: VmsCameraCardProps) {
  const cardRef = useRef<HTMLDivElement>(null)
  const isVisible = useIntersection(cardRef)
  const hlsUrl = `${API_BASE}/api/cameras/${camera.id}/stream/stream.m3u8`

  return (
    <div
      ref={cardRef}
      className={hasViolation ? cameraCardAlert : cameraCard}
      onClick={onOpen}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onOpen()
        }
      }}
      aria-label={`Abrir câmera ${camera.name}`}
    >
      <div className={cardAspect}>
        <div className={cardInner}>
          {isVisible ? (
            <>
              <CameraPlayer
                cameraId={camera.id}
                hlsUrl={hlsUrl}
                width={640}
                height={360}
              />
              {detections.length > 0 && (
                <DetectionOverlay
                  detections={detections}
                  videoWidth={640}
                  videoHeight={360}
                  displayWidth={640}
                  displayHeight={360}
                />
              )}
            </>
          ) : (
            <div className={cardPlaceholder}>carregando...</div>
          )}

          {/* Header overlay — pointerEvents none, safe per regras absolutas */}
          <div className={cardHeader}>
            <span className={cardName}>{camera.name}</span>
            {hasViolation && <span className={cardAlertLabel}>Alerta</span>}
          </div>

          {/* Footer overlay */}
          <div className={cardFooter}>
            <span className={cardLocation}>{camera.location ?? 'Sem local'}</span>
            {camera.module_code != null && (
              <span className={cardModuleBadge}>
                {MODULE_LABELS[camera.module_code] ?? camera.module_code}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// CameraDrawerContent — detail view inside AppDrawer
// ---------------------------------------------------------------------------
type DrawerTab = 'feed' | 'logs' | 'info'

interface CameraDrawerContentProps {
  camera: CameraWithModule
  detections: Detection[]
  logs: LogEntry[]
}

function CameraDrawerContent({
  camera,
  detections,
  logs,
}: CameraDrawerContentProps) {
  const [activeTab, setActiveTab] = useState<DrawerTab>('feed')
  const hlsUrl = `${API_BASE}/api/cameras/${camera.id}/stream/stream.m3u8`
  const hasFps = detections.length > 0

  return (
    <>
      {/* Feed — always mounted, hidden when not active tab */}
      <div
        className={drawerFeed}
        style={{ display: activeTab === 'feed' ? 'block' : 'none' }}
      >
        <CameraPlayer
          cameraId={camera.id}
          hlsUrl={hlsUrl}
          width={640}
          height={360}
        />
        {detections.length > 0 && (
          <DetectionOverlay
            detections={detections}
            videoWidth={640}
            videoHeight={360}
            displayWidth={640}
            displayHeight={360}
          />
        )}
      </div>

      {/* Tab bar */}
      <div className={drawerTabList}>
        <button
          className={activeTab === 'feed' ? drawerTabActive : drawerTab}
          onClick={() => setActiveTab('feed')}
        >
          Feed
        </button>
        <button
          className={activeTab === 'logs' ? drawerTabActive : drawerTab}
          onClick={() => setActiveTab('logs')}
        >
          Logs ao vivo
        </button>
        <button
          className={activeTab === 'info' ? drawerTabActive : drawerTab}
          onClick={() => setActiveTab('info')}
        >
          Info
        </button>
      </div>

      {/* Tab content */}
      <div className={drawerScrollBody}>
        {activeTab === 'logs' && (
          <div className={logsList}>
            {logs.length === 0 ? (
              <div className={emptyState}>Aguardando detecções...</div>
            ) : (
              logs.map((entry) => (
                <div
                  key={entry.id}
                  className={entry.hasViolation ? logEntryAlert : logEntry}
                >
                  <span className={logTimestamp}>
                    {new Date(entry.timestamp).toLocaleTimeString('pt-BR')}
                  </span>
                  {entry.detections.map((d, i) => (
                    <span key={i} className={logDetectionRow}>
                      {d.class} — {(d.confidence * 100).toFixed(0)}%
                    </span>
                  ))}
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'info' && (
          <div className={drawerInfoGrid}>
            <div className={drawerInfoItem}>
              <span className={drawerInfoLabel}>Nome</span>
              <span className={drawerInfoValue}>{camera.name}</span>
            </div>
            <div className={drawerInfoItem}>
              <span className={drawerInfoLabel}>Módulo</span>
              <span className={drawerInfoValue}>
                {camera.module_code != null
                  ? (MODULE_LABELS[camera.module_code] ?? camera.module_code)
                  : '—'}
              </span>
            </div>
            <div className={drawerInfoItem}>
              <span className={drawerInfoLabel}>Localização</span>
              <span className={drawerInfoValue}>{camera.location ?? '—'}</span>
            </div>
            <div className={drawerInfoItem}>
              <span className={drawerInfoLabel}>Status</span>
              <span
                className={drawerInfoValue}
                style={{ color: camera.is_active ? '#22c55e' : '#ef4444' }} // allow: semantic status color
              >
                {camera.is_active ? 'Ativa' : 'Inativa'}
              </span>
            </div>
            <div className={drawerInfoItem}>
              <span className={drawerInfoLabel}>Fabricante</span>
              <span className={drawerInfoValue}>{camera.manufacturer}</span>
            </div>
            <div className={drawerInfoItem}>
              <span className={drawerInfoLabel}>FPS atual</span>
              <span className={drawerInfoValue}>
                {hasFps ? '~5 FPS' : 'N/A'}
              </span>
            </div>
          </div>
        )}
      </div>
    </>
  )
}

// ---------------------------------------------------------------------------
// MonitoringPage
// ---------------------------------------------------------------------------
export function MonitoringPage() {
  const { user } = useAuth()
  const token = getToken()

  // Module filter
  const userModules = useMemo<string[]>(() => user?.modules ?? [], [user])
  const [activeModule, setActiveModule] = useState<string>('all')

  // Cameras
  const [cameras, setCameras] = useState<CameraWithModule[]>([])
  const [loading, setLoading] = useState(true)

  // Overlay toggle
  const [showOverlay, setShowOverlay] = useState(true)

  // Debounced overlay detections (200ms) — avoid re-render on every WS tick
  const [debouncedDetections, setDebouncedDetections] = useState<
    Record<string, Detection[]>
  >({})
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | undefined>(
    undefined,
  )

  // Drawer state
  const [selectedCamera, setSelectedCamera] =
    useState<CameraWithModule | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)

  // Live logs buffer + throttled display (500ms)
  const logBufferRef = useRef<LogEntry[]>([])
  const [displayLogs, setDisplayLogs] = useState<LogEntry[]>([])
  const throttleTimerRef = useRef<ReturnType<typeof setTimeout> | undefined>(
    undefined,
  )

  // WebSocket
  const { connected, detections, alerts, subscribeCamera } =
    useMonitoringSocket({
      wsUrl: WS_URL,
      token: token ?? '',
      enabled: !!token,
    })

  // ---------------------------------------------------------------------------
  // Fetch cameras
  // ---------------------------------------------------------------------------
  const fetchCameras = useCallback(async () => {
    setLoading(true)
    try {
      const path =
        activeModule !== 'all'
          ? `/cameras?module=${activeModule}`
          : '/cameras'
      const res = await api.get<{ data: CameraWithModule[] | { cameras: CameraWithModule[] } }>(path)
      const raw = res.data
      let list: CameraWithModule[]
      if (Array.isArray(raw)) {
        list = raw
      } else if (Array.isArray((raw as { cameras?: CameraWithModule[] }).cameras)) {
        list = (raw as { cameras: CameraWithModule[] }).cameras
      } else {
        list = []
      }
      setCameras(list)
    } catch {
      setCameras([])
    } finally {
      setLoading(false)
    }
  }, [activeModule])

  useEffect(() => {
    void fetchCameras()
  }, [fetchCameras])

  // Subscribe all cameras for WS after they load
  useEffect(() => {
    if (!connected) return
    cameras.forEach((c) => subscribeCamera(c.id))
  }, [cameras, connected, subscribeCamera])

  // Cleanup timers on unmount
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current != null)
        clearTimeout(debounceTimerRef.current)
      if (throttleTimerRef.current != null)
        clearTimeout(throttleTimerRef.current)
    }
  }, [])

  // ---------------------------------------------------------------------------
  // Debounce overlay updates (200ms)
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (debounceTimerRef.current != null)
      clearTimeout(debounceTimerRef.current)
    debounceTimerRef.current = setTimeout(() => {
      setDebouncedDetections(detections)
    }, 200)
    return () => {
      if (debounceTimerRef.current != null)
        clearTimeout(debounceTimerRef.current)
    }
  }, [detections])

  // ---------------------------------------------------------------------------
  // Accumulate live logs for selected camera (throttle 500ms)
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (selectedCamera == null) return
    const cameraDetections = detections[selectedCamera.id]
    if (cameraDetections == null || cameraDetections.length === 0) return

    const hasViolation = cameraDetections.some((d) => d.is_violation === true)
    const entry: LogEntry = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
      timestamp: new Date().toISOString(),
      detections: cameraDetections,
      hasViolation,
    }
    logBufferRef.current = [entry, ...logBufferRef.current].slice(0, 50)

    if (throttleTimerRef.current == null) {
      throttleTimerRef.current = setTimeout(() => {
        setDisplayLogs([...logBufferRef.current])
        throttleTimerRef.current = undefined
      }, 500)
    }
  }, [detections, selectedCamera])

  // Clear logs when selected camera changes
  useEffect(() => {
    logBufferRef.current = []
    setDisplayLogs([])
    if (throttleTimerRef.current != null) {
      clearTimeout(throttleTimerRef.current)
      throttleTimerRef.current = undefined
    }
  }, [selectedCamera?.id])

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------
  const handleOpenCamera = useCallback((camera: CameraWithModule) => {
    setSelectedCamera(camera)
    setDrawerOpen(true)
  }, [])

  const handleCloseDrawer = useCallback(() => {
    setDrawerOpen(false)
  }, [])

  // ---------------------------------------------------------------------------
  // Derived data
  // ---------------------------------------------------------------------------
  // Client-side module filter (secondary check — trusts API first)
  const filteredCameras = useMemo<CameraWithModule[]>(() => {
    if (activeModule === 'all') return cameras
    const hasModuleInfo = cameras.some((c) => c.module_code != null)
    if (!hasModuleInfo) return cameras
    return cameras.filter(
      (c) => c.module_code == null || c.module_code === activeModule,
    )
  }, [cameras, activeModule])

  const violatingCameraIds = useMemo<Set<string>>(() => {
    const ids = new Set<string>()
    alerts.forEach((a) => ids.add(a.camera_id))
    return ids
  }, [alerts])

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <div className={page}>
      {/* Toolbar */}
      <div className={toolbar}>
        <div className={moduleTabList}>
          <button
            className={activeModule === 'all' ? moduleTabActive : moduleTab}
            onClick={() => setActiveModule('all')}
          >
            Todos
          </button>
          {userModules.map((mod) => (
            <button
              key={mod}
              className={activeModule === mod ? moduleTabActive : moduleTab}
              onClick={() => setActiveModule(mod)}
            >
              {MODULE_LABELS[mod] ?? mod}
            </button>
          ))}
        </div>

        <div className={spacer} />

        {/* Connection status */}
        <div className={statusBadge}>
          <span className={connected ? statusDotOnline : statusDotOffline} />
          {connected ? 'Ao vivo' : 'Desconectado'}
        </div>

        {/* Overlay toggle */}
        <button
          className={showOverlay ? overlayToggleActive : overlayToggle}
          onClick={() => setShowOverlay((v) => !v)}
          aria-pressed={showOverlay}
        >
          {showOverlay ? <Eye size={13} /> : <EyeOff size={13} />}
          Overlay
        </button>
      </div>

      {/* Camera grid */}
      <div className={gridContainer}>
        {loading ? (
          <div className={emptyState}>Carregando câmeras...</div>
        ) : filteredCameras.length === 0 ? (
          <div className={emptyState}>Nenhuma câmera encontrada</div>
        ) : (
          <div className={cameraGrid}>
            {filteredCameras.map((camera) => (
              <VmsCameraCard
                key={camera.id}
                camera={camera}
                detections={
                  showOverlay
                    ? (debouncedDetections[camera.id] ?? [])
                    : []
                }
                hasViolation={violatingCameraIds.has(camera.id)}
                onOpen={() => handleOpenCamera(camera)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Camera detail drawer — kept mounted during close animation */}
      {selectedCamera != null && (
        <AppDrawer
          isOpen={drawerOpen}
          onClose={handleCloseDrawer}
          title={selectedCamera.name}
          size="lg"
        >
          <CameraDrawerContent
            camera={selectedCamera}
            detections={debouncedDetections[selectedCamera.id] ?? []}
            logs={displayLogs}
          />
        </AppDrawer>
      )}
    </div>
  )
}
