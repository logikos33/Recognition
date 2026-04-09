/**
 * CameraCard — card de câmera com ações inline.
 *
 * Ações: testar conexão, iniciar/parar stream, editar (abre wizard), deletar (confirmação inline).
 */
import { useState } from 'react'
import toast from 'react-hot-toast'
import type { Camera } from '../../types'
import { cameraService } from '../../services/cameraService'

interface CameraCardProps {
  camera: Camera
  onEdit: (camera: Camera) => void
  onDelete: (id: string) => void
  onRefresh: () => void
}

type TestState = 'idle' | 'testing' | 'ok' | 'error'

const STATUS_LABEL: Record<string, { label: string; color: string }> = {
  active: { label: 'Ativa', color: '#22c55e' },
  starting: { label: 'Iniciando', color: '#f59e0b' },
  error: { label: 'Erro', color: '#ef4444' },
  inactive: { label: 'Inativa', color: '#64748b' },
}

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
  const statusInfo = STATUS_LABEL[status] || STATUS_LABEL.inactive

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
      const msg = err instanceof Error ? err.message : 'Erro ao iniciar stream'
      toast.error(msg)
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
      const msg = err instanceof Error ? err.message : 'Erro ao parar stream'
      toast.error(msg)
    }
  }

  async function handleDelete() {
    try {
      await cameraService.delete(camera.id)
      toast.success(`Câmera "${camera.name}" removida`)
      onDelete(camera.id)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Erro ao remover câmera'
      toast.error(msg)
    }
    setConfirmDelete(false)
  }

  const card: React.CSSProperties = {
    background: '#1e293b',
    borderRadius: 12,
    border: '1px solid #334155',
    overflow: 'hidden',
  }

  const btn = (bg: string, fg = '#fff'): React.CSSProperties => ({
    padding: '5px 12px',
    borderRadius: 6,
    border: 'none',
    background: bg,
    color: fg,
    fontSize: 12,
    fontWeight: 600,
    cursor: 'pointer',
  })

  const iconBtn: React.CSSProperties = {
    padding: '6px 8px',
    borderRadius: 6,
    border: '1px solid #475569',
    background: 'transparent',
    color: '#94a3b8',
    cursor: 'pointer',
    fontSize: 13,
    lineHeight: 1,
  }

  return (
    <div style={card}>
      {/* Header */}
      <div style={{ padding: '14px 16px 8px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ color: '#e2e8f0', fontWeight: 600, fontSize: 15 }}>{camera.name}</div>
          {camera.location && (
            <div style={{ color: '#64748b', fontSize: 12, marginTop: 2 }}>{camera.location}</div>
          )}
        </div>
        <span style={{
          padding: '3px 8px',
          borderRadius: 20,
          fontSize: 11,
          fontWeight: 700,
          background: statusInfo.color + '22',
          color: statusInfo.color,
        }}>
          {statusInfo.label}
        </span>
      </div>

      {/* Info */}
      <div style={{ padding: '0 16px 8px' }}>
        <div style={{ color: '#475569', fontSize: 11, fontFamily: 'monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {maskRtspUrl(camera)}
        </div>
        <div style={{ color: '#475569', fontSize: 11, marginTop: 2 }}>
          {camera.manufacturer || 'generic'} · porta {camera.port || 554}
        </div>
      </div>

      {/* Erro último stream */}
      {camera.last_error && status === 'error' && (
        <div style={{ margin: '0 16px 8px', padding: '6px 10px', background: '#ef444420', borderRadius: 6, color: '#fca5a5', fontSize: 11 }}>
          ⚠ {camera.last_error}
        </div>
      )}

      {/* Resultado do último teste */}
      {testState !== 'idle' && (
        <div style={{ margin: '0 16px 8px', padding: '6px 10px', borderRadius: 6, fontSize: 11, background: testState === 'ok' ? '#22c55e20' : testState === 'error' ? '#ef444420' : '#334155', color: testState === 'ok' ? '#86efac' : testState === 'error' ? '#fca5a5' : '#94a3b8' }}>
          {testState === 'testing' && '⏳ Testando...'}
          {testState === 'ok' && `✓ ${testMsg}`}
          {testState === 'error' && `✗ ${testMsg}`}
        </div>
      )}

      {/* Ações */}
      <div style={{ padding: '8px 16px 14px', borderTop: '1px solid #334155', display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <button
          onClick={handleTest}
          disabled={testState === 'testing'}
          style={btn('#334155', '#94a3b8')}
        >
          {testState === 'testing' ? '...' : '⟳ Testar'}
        </button>

        {status === 'active' ? (
          <button onClick={handleStop} style={btn('#dc2626')}>
            ■ Parar
          </button>
        ) : (
          <button onClick={handleStart} disabled={streaming} style={btn('#16a34a')}>
            {streaming ? '...' : '▶ Iniciar'}
          </button>
        )}

        <div style={{ flex: 1 }} />

        <button onClick={() => onEdit(camera)} style={iconBtn} title="Editar câmera">
          ✎
        </button>
        <button
          onClick={() => setConfirmDelete(true)}
          style={{ ...iconBtn, color: '#f87171' }}
          title="Remover câmera"
        >
          ✕
        </button>
      </div>

      {/* Confirmação de delete */}
      {confirmDelete && (
        <div style={{ padding: '12px 16px', borderTop: '1px solid #334155', background: '#ef444415' }}>
          <div style={{ color: '#fca5a5', fontSize: 12, marginBottom: 10 }}>
            Remover câmera <strong>"{camera.name}"</strong>? Esta ação não pode ser desfeita.
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={() => setConfirmDelete(false)} style={btn('#334155', '#94a3b8')}>
              Cancelar
            </button>
            <button onClick={handleDelete} style={btn('#dc2626')}>
              Confirmar remoção
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default CameraCard
