/**
 * CamerasPage — split-view: camera list (left) + detail/preview panel (right).
 */
import { useState, useCallback, useEffect } from 'react'
import toast from 'react-hot-toast'
import { RefreshCw, Plus, Camera, Plug, Info, Play, Square } from 'lucide-react'
import { api } from '../services/api'
import { cameraService } from '../services/cameraService'
import { CameraWizard } from '../components/cameras/CameraWizard'
import { CameraPlayer } from '../components/monitoring/CameraPlayer'
import { Badge, statusToBadge } from '../components/ui/Badge/Badge'
import { Button } from '../components/ui/Button/Button'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import type { Camera as CameraType } from '../types'
import {
  page, pageHeader, pageTitle, pageMeta, pageCount,
  headerActions, splitView, cameraList, cameraListItem,
  cameraListItemActive, listDot, listName, listLocation,
  detailPanel, detailEmpty, previewWrap, detailFields,
  fieldGroup, fieldLabel, fieldValue, detailActions,
  logList, logItem, sectionTitle, rtspTip,
  emptyState, emptyTitle, emptyText,
} from './CamerasPage.css'

const FRIENDLY_ERRORS: Record<string, string> = {
  'not_found': 'Camera nao esta transmitindo. Verifique se esta ligada.',
  'connection_refused': 'Nao foi possivel conectar. Verifique IP e porta.',
  'timeout': 'Camera nao respondeu a tempo. Verifique a rede.',
  'auth_error': 'Credenciais incorretas.',
  'dns_error': 'Endereco IP invalido ou nao encontrado.',
}

function translateTestError(msg: string): string {
  const lower = msg.toLowerCase()
  if (lower.includes('refused') || lower.includes('connect')) return FRIENDLY_ERRORS.connection_refused
  if (lower.includes('timeout') || lower.includes('timed out')) return FRIENDLY_ERRORS.timeout
  if (lower.includes('auth') || lower.includes('401') || lower.includes('credential')) return FRIENDLY_ERRORS.auth_error
  if (lower.includes('dns') || lower.includes('resolve') || lower.includes('host')) return FRIENDLY_ERRORS.dns_error
  return msg
}

interface LogEntry {
  ts: string
  type: 'ok' | 'error' | 'info'
  text: string
}

export function CamerasPage() {
  const [cameras, setCameras] = useState<CameraType[]>([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<CameraType | null>(null)
  const [wizardOpen, setWizardOpen] = useState(false)
  const [editingCamera, setEditingCamera] = useState<CameraType | undefined>()
  const [gatewayStatus, setGatewayStatus] = useState('offline')
  const [testLogs, setTestLogs] = useState<LogEntry[]>([])
  const [testing, setTesting] = useState(false)
  const [showTip, setShowTip] = useState(false)

  const loadCameras = useCallback(async () => {
    try {
      const res = await api.get<any>('/cameras')
      const inner = res?.data || res
      const list = Array.isArray(inner) ? inner : (inner?.cameras || [])
      setCameras(list)
      setGatewayStatus(inner?.gateway_status?.status || 'offline')
      if (selected) {
        const updated = list.find((c: CameraType) => c.id === selected.id)
        if (updated) setSelected(updated)
      }
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Erro ao carregar cameras')
    } finally {
      setLoading(false)
    }
  }, [selected])

  useEffect(() => { loadCameras() }, [loadCameras])

  function openCreate() { setEditingCamera(undefined); setWizardOpen(true) }
  function handleEdit() { if (selected) { setEditingCamera(selected); setWizardOpen(true) } }
  function handleWizardClose() { setWizardOpen(false); setEditingCamera(undefined) }

  async function handleDelete() {
    if (!selected) return
    try {
      await cameraService.delete(selected.id)
      toast.success(`Camera "${selected.name}" removida`)
      setSelected(null)
      loadCameras()
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Erro ao remover')
    }
  }

  async function handleStartStream() {
    if (!selected) return
    try {
      await cameraService.start(selected.id)
      toast.success('Stream iniciado')
      loadCameras()
    } catch { toast.error('Erro ao iniciar stream') }
  }

  async function handleStopStream() {
    if (!selected) return
    try {
      await cameraService.stop(selected.id)
      toast.success('Stream parado')
      loadCameras()
    } catch { toast.error('Erro ao parar stream') }
  }

  async function handleTest() {
    if (!selected) return
    setTesting(true)
    const ts = new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    setTestLogs(prev => [...prev, { ts, type: 'info', text: 'Testando conexao...' }])
    try {
      const result = await cameraService.test(selected.id)
      const ts2 = new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
      if (result.success) {
        setTestLogs(prev => [...prev, { ts: ts2, type: 'ok', text: 'Conexao estabelecida' }])
      } else {
        setTestLogs(prev => [...prev, { ts: ts2, type: 'error', text: translateTestError(result.error || 'Falha') }])
      }
    } catch {
      const ts2 = new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
      setTestLogs(prev => [...prev, { ts: ts2, type: 'error', text: 'Erro ao testar conexao' }])
    } finally {
      setTesting(false)
    }
  }

  function maskRtsp(cam: CameraType): string {
    const host = cam.host || '...'
    const port = cam.port || 554
    const user = cam.username || ''
    if (user) return `rtsp://${user}:****@${host}:${port}/...`
    return `rtsp://${host}:${port}/...`
  }

  if (loading) return <LoadingSpinner />

  const apiBase = import.meta.env.VITE_API_URL || ''

  return (
    <div className={page}>
      <div className={pageHeader}>
        <div>
          <h2 className={pageTitle}>Cameras</h2>
          <div className={pageMeta}>
            <span className={pageCount}>{cameras.length} camera{cameras.length !== 1 ? 's' : ''}</span>
            <Badge status={statusToBadge(gatewayStatus === 'online' ? 'online' : 'offline')}>
              Gateway: {gatewayStatus}
            </Badge>
          </div>
        </div>
        <div className={headerActions}>
          <Button variant="ghost" size="sm" onClick={loadCameras} title="Atualizar">
            <RefreshCw size={14} /> Atualizar
          </Button>
          <Button variant="primary" onClick={openCreate}>
            <Plus size={15} /> Nova Camera
          </Button>
        </div>
      </div>

      {cameras.length === 0 ? (
        <div className={emptyState}>
          <Camera size={48} style={{ opacity: 0.3, marginBottom: 16 }} />
          <h3 className={emptyTitle}>Nenhuma camera cadastrada</h3>
          <p className={emptyText}>Adicione uma camera para comecar o monitoramento</p>
          <Button variant="primary" onClick={openCreate}>
            <Plus size={15} /> Adicionar camera
          </Button>
        </div>
      ) : (
        <div className={splitView}>
          {/* Camera list */}
          <div className={cameraList}>
            {cameras.map(cam => {
              const isActive = selected?.id === cam.id
              const status = cam.stream_status || 'inactive'
              const isOnline = status === 'active' || status === 'online'
              return (
                <div
                  key={cam.id}
                  className={isActive ? cameraListItemActive : cameraListItem}
                  onClick={() => { setSelected(cam); setTestLogs([]) }}
                >
                  <span
                    className={listDot}
                    style={{ background: isOnline ? '#22c55e' : '#64748b' }}
                  />
                  <span className={listName}>{cam.name}</span>
                  {cam.location && <span className={listLocation}>{cam.location}</span>}
                </div>
              )
            })}
          </div>

          {/* Detail panel */}
          {!selected ? (
            <div className={detailEmpty}>
              <Camera size={40} style={{ opacity: 0.2 }} />
              <span>Selecione uma camera para ver detalhes</span>
            </div>
          ) : (
            <div className={detailPanel}>
              {/* Preview */}
              <div className={previewWrap}>
                <CameraPlayer
                  cameraId={selected.id}
                  hlsUrl={`${apiBase}/api/cameras/${selected.id}/stream/stream.m3u8`}
                  width={640}
                  height={360}
                />
              </div>

              {/* Fields */}
              <div className={detailFields}>
                <div className={fieldGroup}>
                  <span className={fieldLabel}>Nome</span>
                  <span className={fieldValue}>{selected.name}</span>
                </div>
                <div className={fieldGroup}>
                  <span className={fieldLabel}>Local</span>
                  <span className={fieldValue}>{selected.location || '—'}</span>
                </div>
                <div className={fieldGroup}>
                  <span className={fieldLabel}>RTSP URL</span>
                  <span className={fieldValue}>{maskRtsp(selected)}</span>
                </div>
                <div className={fieldGroup}>
                  <span className={fieldLabel}>Fabricante</span>
                  <span className={fieldValue}>{selected.manufacturer || 'generic'}</span>
                </div>
                <div className={fieldGroup}>
                  <span className={fieldLabel}>Porta</span>
                  <span className={fieldValue}>{selected.port || 554}</span>
                </div>
                <div className={fieldGroup}>
                  <span className={fieldLabel}>Status</span>
                  <span className={fieldValue}>{selected.stream_status || 'inactive'}</span>
                </div>
              </div>

              {/* RTSP tip */}
              <div>
                <button
                  onClick={() => setShowTip(v => !v)}
                  style={{ background: 'none', border: 'none', color: 'rgba(139,92,246,0.7)', cursor: 'pointer', fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}
                >
                  <Info size={13} /> Dica: URLs RTSP por fabricante
                </button>
                {showTip && (
                  <div className={rtspTip}>
                    Hikvision: rtsp://user:pass@IP:554/Streaming/Channels/101<br />
                    Dahua/Intelbras: rtsp://user:pass@IP:554/cam/realmonitor?channel=1<br />
                    Generico ONVIF: rtsp://IP:554/stream1
                  </div>
                )}
              </div>

              {/* Actions */}
              <div className={detailActions}>
                {selected.stream_status !== 'active' && selected.stream_status !== 'online' ? (
                  <Button size="sm" variant="primary" onClick={handleStartStream}>
                    <Play size={13} /> Iniciar Stream
                  </Button>
                ) : (
                  <Button size="sm" variant="ghost" onClick={handleStopStream}>
                    <Square size={13} /> Parar Stream
                  </Button>
                )}
                <Button size="sm" variant="secondary" onClick={handleTest} disabled={testing}>
                  <Plug size={13} /> {testing ? 'Testando...' : 'Testar Conexao'}
                </Button>
                <Button size="sm" variant="secondary" onClick={handleEdit}>
                  Editar
                </Button>
                <Button size="sm" variant="danger" onClick={handleDelete}>
                  Excluir
                </Button>
              </div>

              {/* Logs */}
              {testLogs.length > 0 && (
                <div>
                  <h4 className={sectionTitle}>Logs</h4>
                  <div className={logList}>
                    {testLogs.slice(-8).map((log, i) => (
                      <div key={i} className={logItem}>
                        <span style={{ opacity: 0.5, marginRight: 8 }}>{log.ts}</span>
                        <span style={{ marginRight: 6 }}>
                          {log.type === 'ok' ? '✓' : log.type === 'error' ? '✗' : 'ℹ'}
                        </span>
                        {log.text}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      <CameraWizard isOpen={wizardOpen} onClose={handleWizardClose}
        onSuccess={loadCameras} camera={editingCamera} />
    </div>
  )
}
