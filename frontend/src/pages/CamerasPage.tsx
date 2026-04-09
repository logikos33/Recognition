/**
 * CamerasPage — listagem e gerenciamento de câmeras IP.
 */
import { useState, useCallback, useEffect } from 'react'
import toast from 'react-hot-toast'
import { RefreshCw, Plus } from 'lucide-react'
import { api } from '../services/api'
import { CameraCard } from '../components/cameras/CameraCard'
import { CameraWizard } from '../components/cameras/CameraWizard'
import { Badge, statusToBadge } from '../components/ui/Badge/Badge'
import { Button } from '../components/ui/Button/Button'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import type { Camera } from '../types'
import {
  page, pageHeader, pageTitle, pageMeta, pageCount,
  headerActions, emptyState, emptyTitle, emptyText, grid,
} from './CamerasPage.css'

export function CamerasPage() {
  const [cameras, setCameras] = useState<Camera[]>([])
  const [loading, setLoading] = useState(true)
  const [wizardOpen, setWizardOpen] = useState(false)
  const [editingCamera, setEditingCamera] = useState<Camera | undefined>()
  const [gatewayStatus, setGatewayStatus] = useState('offline')

  const loadCameras = useCallback(async () => {
    try {
      const res = await api.get<unknown>('/cameras')
      const data = res as { cameras?: Camera[]; gateway_status?: { status: string } }
      if (Array.isArray(res)) {
        setCameras(res as Camera[])
      } else {
        setCameras(data.cameras || [])
        setGatewayStatus(data.gateway_status?.status || 'offline')
      }
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Erro ao carregar câmeras')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadCameras() }, [loadCameras])

  function openCreate() { setEditingCamera(undefined); setWizardOpen(true) }
  function handleEdit(camera: Camera) { setEditingCamera(camera); setWizardOpen(true) }
  function handleDelete(id: string) { setCameras(prev => prev.filter(c => c.id !== id)) }
  function handleWizardClose() { setWizardOpen(false); setEditingCamera(undefined) }

  if (loading) return <LoadingSpinner />

  return (
    <div className={page}>
      <div className={pageHeader}>
        <div>
          <h2 className={pageTitle}>Câmeras</h2>
          <div className={pageMeta}>
            <span className={pageCount}>
              {cameras.length} câmera{cameras.length !== 1 ? 's' : ''}
            </span>
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
            <Plus size={15} /> Nova Câmera
          </Button>
        </div>
      </div>

      {cameras.length === 0 ? (
        <div className={emptyState}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>📷</div>
          <h3 className={emptyTitle}>Nenhuma câmera cadastrada</h3>
          <p className={emptyText}>Adicione uma câmera para começar o monitoramento</p>
          <Button variant="primary" onClick={openCreate}>
            <Plus size={15} /> Adicionar câmera
          </Button>
        </div>
      ) : (
        <div className={grid}>
          {cameras.map(cam => (
            <CameraCard key={cam.id} camera={cam}
              onEdit={handleEdit} onDelete={handleDelete} onRefresh={loadCameras} />
          ))}
        </div>
      )}

      <CameraWizard isOpen={wizardOpen} onClose={handleWizardClose}
        onSuccess={loadCameras} camera={editingCamera} />
    </div>
  )
}
