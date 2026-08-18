/**
 * CameraCard — card de câmera com ações inline.
 *
 * Ações: testar conexão, iniciar/parar stream, editar (abre wizard), arquivar (confirmação inline).
 *
 * ⛔ Arquivar, nunca excluir: DELETE apaga em CASCATA frames, anotações e detecções —
 * acervo de treinamento. Arquivar é reversível e não perde nada (issue #428).
 */
import { useState } from 'react'
import { useToast } from '../ui/Toast/useToast'
import { Edit2, Archive, ArchiveRestore, Play, Square, RefreshCw } from 'lucide-react'
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
  onArchive: (id: string) => void
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

export function CameraCard({ camera, onEdit, onArchive, onRefresh }: CameraCardProps) {
  const toast = useToast()
  const [testState, setTestState] = useState<TestState>('idle')
  const [testMsg, setTestMsg] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [confirmArchive, setConfirmArchive] = useState(false)

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

  async function handleArchive() {
    try {
      await cameraService.archive(camera.id)
      toast.success(`Câmera "${camera.name}" arquivada`)
      onArchive(camera.id)
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Erro ao arquivar câmera')
    }
    setConfirmArchive(false)
  }

  async function handleRestore() {
    try {
      await cameraService.restore(camera.id)
      toast.success(`Câmera "${camera.name}" desarquivada`)
      onRefresh()
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Erro ao desarquivar câmera')
    }
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
        {camera.is_active === false ? (
          <Button size="sm" variant="ghost" onClick={handleRestore} title="Desarquivar câmera">
            <ArchiveRestore size={13} />
          </Button>
        ) : (
          <Button size="sm" variant="ghost" onClick={() => setConfirmArchive(true)} title="Arquivar câmera">
            <Archive size={13} />
          </Button>
        )}
      </div>

      {/* Confirmação de arquivamento */}
      {confirmArchive && (
        <div className={deleteConfirm}>
          <div className={deleteConfirmText}>
            Arquivar <strong>"{camera.name}"</strong>? Ela sai do reconhecimento e do export de
            dataset. Frames, anotações e detecções continuam no banco — dá para desarquivar.
          </div>
          <div className={deleteConfirmActions}>
            <Button size="sm" variant="secondary" onClick={() => setConfirmArchive(false)}>Cancelar</Button>
            <Button size="sm" variant="primary" onClick={handleArchive}>Arquivar</Button>
          </div>
        </div>
      )}
    </div>
  )
}

export default CameraCard
