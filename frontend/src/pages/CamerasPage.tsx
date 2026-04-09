/**
 * CamerasPage — listagem e gerenciamento de câmeras IP.
 *
 * Usa CameraCard para cada câmera e CameraWizard para criar/editar.
 * Toasts substituem alert() do browser.
 */
import { useState, useCallback, useEffect } from 'react'
import toast from 'react-hot-toast'
import { api } from '../services/api'
import { CameraCard } from '../components/cameras/CameraCard'
import { CameraWizard } from '../components/cameras/CameraWizard'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import type { Camera } from '../types'

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
      const msg = err instanceof Error ? err.message : 'Erro ao carregar câmeras'
      toast.error(msg)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadCameras() }, [loadCameras])

  function handleEdit(camera: Camera) {
    setEditingCamera(camera)
    setWizardOpen(true)
  }

  function handleDelete(id: string) {
    setCameras(prev => prev.filter(c => c.id !== id))
  }

  function handleWizardClose() {
    setWizardOpen(false)
    setEditingCamera(undefined)
  }

  function handleWizardSuccess() {
    loadCameras()
  }

  function openCreate() {
    setEditingCamera(undefined)
    setWizardOpen(true)
  }

  const addBtn: React.CSSProperties = {
    padding: '8px 20px', borderRadius: 8, border: 'none',
    background: '#2563eb', color: '#fff', fontSize: 14,
    fontWeight: 600, cursor: 'pointer',
  }
  const refreshBtn: React.CSSProperties = {
    padding: '8px 12px', borderRadius: 8,
    border: '1px solid #334155', background: 'transparent',
    color: '#64748b', cursor: 'pointer', fontSize: 13,
  }

  if (loading) return <LoadingSpinner />

  return (
    <div style={{ padding: 32 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h2 style={{ color: '#e2e8f0', margin: 0 }}>Câmeras</h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 4 }}>
            <span style={{ fontSize: 13, color: '#64748b' }}>
              {cameras.length} câmera{cameras.length !== 1 ? 's' : ''} cadastrada{cameras.length !== 1 ? 's' : ''}
            </span>
            <span style={{
              fontSize: 11, padding: '2px 8px', borderRadius: 10, fontWeight: 600,
              background: gatewayStatus === 'online' ? '#22c55e20' : '#33415520',
              color: gatewayStatus === 'online' ? '#22c55e' : '#64748b',
            }}>
              Gateway: {gatewayStatus}
            </span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={loadCameras} style={refreshBtn} title="Atualizar lista">
            ⟳ Atualizar
          </button>
          <button onClick={openCreate} style={addBtn}>
            + Nova Câmera
          </button>
        </div>
      </div>

      {cameras.length === 0 ? (
        <div style={{
          padding: '60px 40px', textAlign: 'center',
          background: '#1e293b', borderRadius: 12, border: '1px solid #334155',
        }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>📷</div>
          <h3 style={{ color: '#e2e8f0', margin: '0 0 8px' }}>Nenhuma câmera cadastrada</h3>
          <p style={{ color: '#64748b', margin: '0 0 24px' }}>
            Adicione uma câmera para começar o monitoramento
          </p>
          <button onClick={openCreate} style={addBtn}>
            + Adicionar câmera
          </button>
        </div>
      ) : (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
          gap: 16,
        }}>
          {cameras.map(cam => (
            <CameraCard
              key={cam.id}
              camera={cam}
              onEdit={handleEdit}
              onDelete={handleDelete}
              onRefresh={loadCameras}
            />
          ))}
        </div>
      )}

      <CameraWizard
        isOpen={wizardOpen}
        onClose={handleWizardClose}
        onSuccess={handleWizardSuccess}
        camera={editingCamera}
      />
    </div>
  )
}
