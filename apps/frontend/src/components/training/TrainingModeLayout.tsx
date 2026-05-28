/**
 * TrainingModeLayout — orquestrador da aba Treinamento/Operações.
 *
 * Gerencia:
 *   - Modo View vs Edit (useState<'view'|'edit'>)
 *   - Lista de operações (useOperations)
 *   - Status em tempo real (useOperationLiveStatus)
 *   - Tipos disponíveis (useOperationTypes)
 *   - Modais de criação, edição e exclusão
 *
 * Todos os módulos consomem este componente via props.
 */
import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { useOperations, useOperationTypes } from '../../hooks/useOperations'
import { useOperationLiveStatus } from '../../hooks/useOperationLiveStatus'
import { useMonitoringSocket } from '../../hooks/useMonitoringSocket'
import { getToken } from '../../services/api'
import { LiveVideoWithOperations } from './canvas/LiveVideoWithOperations'
import { RegisteredToolsPanel } from './panels/RegisteredToolsPanel'
import { OperationCatalogPanel } from './panels/OperationCatalogPanel'
import { OperationCreateModal } from './modals/OperationCreateModal'
import { OperationEditModal } from './modals/OperationEditModal'
import { DeleteConfirmModal } from './modals/DeleteConfirmModal'
import { ViewMode } from './modes/ViewMode'
import { EditMode } from './modes/EditMode'
import type { Operation, OperationWithStatus } from '../../types/operations'

const WS_URL = import.meta.env.VITE_API_URL ?? ''

interface TrainingModeLayoutProps {
  moduleId: string
  cameraId: string | number
  hlsUrl: string
  feedType?: 'hls' | 'demo_video'
  feedUrl?: string
  title?: string
  children?: ReactNode
}

export function TrainingModeLayout({
  moduleId,
  cameraId,
  hlsUrl,
  feedType = 'hls',
  feedUrl,
  title = 'Operações',
  children,
}: TrainingModeLayoutProps) {
  const token = getToken()
  const [mode, setMode] = useState<'view' | 'edit'>('view')

  // Data hooks
  const {
    operations,
    loading: opsLoading,
    createOperation,
    updateOperation,
    deleteOperation,
    refetch,
  } = useOperations({ cameraId, moduleId, enabled: true })

  const { types, loading: typesLoading } = useOperationTypes({ moduleId, enabled: mode === 'edit' })

  // Live detections for video overlay
  const { detections, subscribeCamera, unsubscribeCamera } = useMonitoringSocket({
    wsUrl: WS_URL,
    token: token ?? '',
    enabled: !!token,
  })

  // Live status updates for operations
  const { liveStatuses } = useOperationLiveStatus({
    wsUrl: WS_URL,
    token: token ?? '',
    operationIds: operations.map(op => op.id),
    enabled: !!token && operations.length > 0,
  })

  // Subscribe to camera on mount
  useEffect(() => {
    if (!token || !cameraId) return
    subscribeCamera(String(cameraId))
    return () => unsubscribeCamera(String(cameraId))
  }, [cameraId, token, subscribeCamera, unsubscribeCamera])

  // Modal state
  const [createOpen, setCreateOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<Operation | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Operation | null>(null)

  // Merge live status into operations
  const operationsWithStatus: OperationWithStatus[] = operations.map(op => {
    const live = liveStatuses[op.id]
    return live
      ? { ...op, live_status: live.status, live_last_value: live.last_value, live_timestamp: live.timestamp }
      : op
  })

  const cameraDetections = detections[String(cameraId)] ?? []

  const handleEnterEditMode = useCallback(() => {
    setMode('edit')
    setCreateOpen(true)
  }, [])

  const handleCancelEdit = useCallback(() => {
    setMode('view')
    setCreateOpen(false)
  }, [])

  const handleSaveEdit = useCallback(() => {
    setMode('view')
    refetch()
  }, [refetch])

  const handleUpdate = useCallback(
    async (data: { name: string; config: Record<string, unknown> }) => {
      if (!editTarget) return
      await updateOperation(editTarget.id, data)
      setEditTarget(null)
    },
    [editTarget, updateOperation]
  )

  const handleDeleteConfirm = useCallback(
    async (confirmName?: string) => {
      if (!deleteTarget) return
      await deleteOperation(deleteTarget.id, confirmName)
      setDeleteTarget(null)
    },
    [deleteTarget, deleteOperation]
  )

  const handleSelectTypeFromCatalog = useCallback(() => {
    setCreateOpen(true)
  }, [])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#0a0a0a' }}>
      {/* Header: view or edit mode */}
      {mode === 'view' ? (
        <ViewMode title={title}>{children}</ViewMode>
      ) : (
        <EditMode onCancel={handleCancelEdit} onSave={handleSaveEdit} />
      )}

      {/* Main content: sidebar + video area */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* Sidebar */}
        <aside
          style={{
            width: 240,
            flexShrink: 0,
            borderRight: '1px solid #1e1e1e',
            overflowY: 'auto',
            background: '#0d0d0d',
          }}
        >
          {mode === 'edit' ? (
            <OperationCatalogPanel
              types={types}
              onSelectType={handleSelectTypeFromCatalog}
              loading={typesLoading}
            />
          ) : (
            <RegisteredToolsPanel
              operations={operationsWithStatus}
              onEdit={op => setEditTarget(op)}
              onDelete={op => setDeleteTarget(op)}
              loading={opsLoading}
            />
          )}
        </aside>

        {/* Video + tools area */}
        <main style={{ flex: 1, padding: 20, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 20 }}>
          <LiveVideoWithOperations
            cameraId={String(cameraId)}
            hlsUrl={hlsUrl}
            feedType={feedType}
            feedUrl={feedUrl}
            detections={cameraDetections}
            operations={operations}
            isEditMode={mode === 'edit'}
            onEnterEditMode={handleEnterEditMode}
            width={640}
            height={360}
          />

          {/* Tabela resumo de ferramentas (modo view) */}
          {mode === 'view' && operationsWithStatus.length > 0 && (
            <div style={{ background: '#0d0d0d', border: '1px solid #1e1e1e', borderRadius: 8, overflow: 'hidden' }}>
              <div style={{ padding: '10px 16px', borderBottom: '1px solid #1e1e1e' }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: '#888', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  Ferramentas cadastradas
                </span>
              </div>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr style={{ color: '#555', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    <th style={{ padding: '8px 16px', textAlign: 'left', fontWeight: 500 }}>ID</th>
                    <th style={{ padding: '8px 16px', textAlign: 'left', fontWeight: 500 }}>Tipo</th>
                    <th style={{ padding: '8px 16px', textAlign: 'left', fontWeight: 500 }}>Nome</th>
                    <th style={{ padding: '8px 16px', textAlign: 'left', fontWeight: 500 }}>Status</th>
                    <th style={{ padding: '8px 16px', textAlign: 'left', fontWeight: 500 }}>Último valor</th>
                  </tr>
                </thead>
                <tbody>
                  {operationsWithStatus.map((op, idx) => (
                    <tr key={op.id} style={{ borderTop: '1px solid #141414' }}>
                      <td style={{ padding: '8px 16px', color: '#555', fontFamily: 'monospace' }}>
                        {String(idx + 1).padStart(2, '0')}
                      </td>
                      <td style={{ padding: '8px 16px', color: '#888', fontFamily: 'monospace', fontSize: 11 }}>
                        {op.type_id}
                      </td>
                      <td style={{ padding: '8px 16px', color: '#e0e0e0' }}>{op.name}</td>
                      <td style={{ padding: '8px 16px' }}>
                        <span style={{
                          display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11,
                          color: op.live_status === 'active' || op.status === 'active' ? '#22c55e'
                            : op.live_status === 'error' || op.status === 'error' ? '#ef4444'
                            : '#f59e0b',
                        }}>
                          <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'currentColor', display: 'inline-block' }} />
                          {op.live_status ?? op.status}
                        </span>
                      </td>
                      <td style={{ padding: '8px 16px', color: '#666', fontFamily: 'monospace', fontSize: 12 }}>
                        {op.live_last_value !== undefined
                          ? String(op.live_last_value).slice(0, 30)
                          : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </main>
      </div>

      {/* Modals */}
      <OperationCreateModal
        open={createOpen}
        onClose={() => { setCreateOpen(false); if (mode === 'edit') setMode('view') }}
        onCreated={createOperation}
        availableTypes={types}
        moduleId={moduleId}
      />

      <OperationEditModal
        open={editTarget !== null}
        onClose={() => setEditTarget(null)}
        onUpdated={handleUpdate}
        operation={editTarget}
      />

      <DeleteConfirmModal
        open={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleDeleteConfirm}
        operationName={deleteTarget?.name ?? ''}
        resultCount={0}
      />
    </div>
  )
}
