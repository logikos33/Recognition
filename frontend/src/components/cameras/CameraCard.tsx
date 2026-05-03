/**
 * CameraCard — card de câmera com ações inline.
 *
 * Ações: testar conexão, iniciar/parar stream, editar (abre wizard), deletar (confirmação inline).
 */
import { useState } from 'react'
import toast from 'react-hot-toast'
import { Edit2, Trash2, Play, Square, RefreshCw } from 'lucide-react'
import type { Camera } from '../../types'
import { cameraService } from '../../services/cameraService'
import { Badge, statusToBadgeVariant } from '../ui/Badge/Badge'
import { Button } from '../ui/Button/Button'
import {
  card, cardHeader, cameraName, cameraLocation, cardInfo,
  rtspUrl, metaText, errorBanner,
  testBannerOk, testBannerError, testBannerLoading,
  actions, spacer, deleteConfirm, deleteConfirmText, deleteConfirmActions,
} from './CameraCard.css'

interface CameraCardProps {
  camera: Camera
  onEdit: (camera: Camera) => void
  onDelete: (id: string) => void
  onRefresh: () => void
}

type TestState = 'idle' | 'testing' | 'ok' | 'error'

function maskRtspUrl(camera: Camera): string {
  const host = camera.host || '...'
  const port = camera.port || 554
  const user = camera.username || ''
  if (user) return `rtsp://${user}:****@${host}:${port}/...`
  return `rtsp://${host}:${port}/...`
}

export function CameraCard({ camera, onEdit, onDelete, onRefresh }: CameraCardProps) {
  const [testState, setTestState] = useState<TestState>('idle')
  const [testMsg, setTestMsg] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)

  const status = camera.stream_status || 'inactive'

  async function handleTest() {
    setTestState('testing')
    setTestMsg('')
    try {
      const result = await cameraService.test(camera.id)
      if (result.success) {
        setTestState('ok')
        setTestMsg('Conexão OK')
      } else {
        setTestState('error')
        setTestMsg(result.error || 'Falha na conexão')
      }
    } catch {
      setTestState('error')
      setTestMsg('Erro ao testar')
    }
  }

  async function handleStart() {
    setStreaming(true)
    try {
      await cameraService.start(camera.id)
      toast.success('Stream iniciado')
      onRefresh()
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Erro ao iniciar stream')
    } finally {
      setStreaming(false)
    }
  }

  async function handleStop() {
    try {
      await cameraService.stop(camera.id)
      toast.success('Stream parado')
      onRefresh()
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Erro ao parar stream')
    }
  }

  async function handleDelete() {
    try {
      await cameraService.delete(camera.id)
      toast.success(`Câmera "${camera.name}" removida`)
      onDelete(camera.id)
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Erro ao remover câmera')
    }
    setConfirmDelete(false)
  }

  return (
    <div className={card}>
      {/* Header */}
      <div className={cardHeader}>
        <div>
          <div className={cameraName}>{camera.name}</div>
          {camera.location && <div className={cameraLocation}>{camera.location}</div>}
        </div>
        <Badge variant={statusToBadgeVariant(status)}>
          {status === 'active' ? 'Ativa' : status === 'starting' ? 'Iniciando' : status === 'error' ? 'Erro' : 'Inativa'}
        </Badge>
      </div>

      {/* Info */}
      <div className={cardInfo}>
        <div className={rtspUrl}>{maskRtspUrl(camera)}</div>
        <div className={metaText}>{camera.manufacturer || 'generic'} · porta {camera.port || 554}</div>
      </div>

      {/* Erro último stream */}
      {camera.last_error && status === 'error' && (
        <div className={errorBanner}>⚠ {camera.last_error}</div>
      )}

      {/* Resultado do último teste */}
      {testState === 'testing' && <div className={testBannerLoading}>⏳ Testando...</div>}
      {testState === 'ok' && <div className={testBannerOk}>✓ {testMsg}</div>}
      {testState === 'error' && <div className={testBannerError}>✗ {testMsg}</div>}

      {/* Ações */}
      <div className={actions}>
        <Button size="sm" variant="secondary" onClick={handleTest} disabled={testState === 'testing'}>
          <RefreshCw size={12} />
          {testState === 'testing' ? '...' : 'Testar'}
        </Button>

        {status === 'active' ? (
          <Button size="sm" variant="danger" onClick={handleStop}>
            <Square size={12} /> Parar
          </Button>
        ) : (
          <Button size="sm" variant="success" onClick={handleStart} disabled={streaming}>
            <Play size={12} /> {streaming ? '...' : 'Iniciar'}
          </Button>
        )}

        <div className={spacer} />

        <Button size="sm" variant="ghost" onClick={() => onEdit(camera)} title="Editar câmera">
          <Edit2 size={13} />
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setConfirmDelete(true)} title="Remover câmera">
          <Trash2 size={13} />
        </Button>
      </div>

      {/* Confirmação de delete */}
      {confirmDelete && (
        <div className={deleteConfirm}>
          <div className={deleteConfirmText}>
            Remover câmera <strong>"{camera.name}"</strong>? Esta ação não pode ser desfeita.
          </div>
          <div className={deleteConfirmActions}>
            <Button size="sm" variant="secondary" onClick={() => setConfirmDelete(false)}>Cancelar</Button>
            <Button size="sm" variant="danger" onClick={handleDelete}>Confirmar remoção</Button>
          </div>
        </div>
      )}
    </div>
  )
}

export default CameraCard
