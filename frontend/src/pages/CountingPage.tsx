import { useState, useEffect, useRef, useCallback } from 'react'
import { Hash, StopCircle, PlayCircle, RefreshCw } from 'lucide-react'
import { useToast } from '../components/ui/Toast/useToast'
import { api } from '../services/api'
import { Skeleton } from '../components/ui/Skeleton/Skeleton'

interface Camera { id: string; name: string; is_streaming: boolean }
interface CountSession { id: string; camera_id: string; status: string }
interface SessionStats { counts: Record<string, number>; total: number }

interface CamerasResponse { status: string; data: { cameras: Camera[] } }
interface SessionsResponse { status: string; data: { sessions: CountSession[] } }
interface StartSessionResponse { status: string; data: { session: CountSession } }
interface StopSessionResponse { status: string; data: { session: { total_counts: Record<string, number> } } }
interface StatsResponse { status: string; data: SessionStats }

const CLASS_LABELS: Record<string, string> = {
  helmet: 'Capacete',
  no_helmet: 'Sem capacete',
  vest: 'Colete',
  no_vest: 'Sem colete',
  gloves: 'Luvas',
  no_gloves: 'Sem luvas',
  glasses: 'Óculos',
  no_glasses: 'Sem óculos',
}

const isViolation = (cls: string) => cls.startsWith('no_')

export function CountingPage() {
  const toast = useToast()
  const [cameras, setCameras] = useState<Camera[]>([])
  const [selectedCameraId, setSelectedCameraId] = useState<string>('')
  const [activeSessions, setActiveSessions] = useState<CountSession[]>([])
  const [activeSession, setActiveSession] = useState<CountSession | null>(null)
  const [stats, setStats] = useState<SessionStats | null>(null)
  const [finalCounts, setFinalCounts] = useState<Record<string, number> | null>(null)
  const [loading, setLoading] = useState(true)
  const [starting, setStarting] = useState(false)
  const [stopping, setStopping] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const stopPolling = () => {
    if (pollRef.current !== null) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }

  const fetchStats = useCallback(async (sessionId: string) => {
    try {
      const res = await api.get<StatsResponse>(`/counting/sessions/${sessionId}/stats`)
      const data = res?.data ?? (res as unknown as SessionStats)
      setStats(data)
    } catch {
      // silently fail on poll errors
    }
  }, [])

  const startPolling = useCallback((sessionId: string) => {
    stopPolling()
    fetchStats(sessionId)
    pollRef.current = setInterval(() => fetchStats(sessionId), 3000)
  }, [fetchStats])

  const loadInitialData = useCallback(async () => {
    try {
      const [camRes, sessRes] = await Promise.all([
        api.get<CamerasResponse>('/cameras'),
        api.get<SessionsResponse>('/counting/sessions'),
      ])

      const camList: Camera[] = camRes?.data?.cameras ?? []
      const sessList: CountSession[] = sessRes?.data?.sessions ?? []

      setCameras(camList)
      setActiveSessions(sessList)

      if (camList.length > 0 && !selectedCameraId) {
        setSelectedCameraId(camList[0].id)
      }

      const running = sessList.find(s => s.status === 'active')
      if (running) {
        setActiveSession(running)
        startPolling(running.id)
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao carregar dados')
    } finally {
      setLoading(false)
    }
  }, [selectedCameraId, startPolling])

  useEffect(() => {
    loadInitialData()
    return () => stopPolling()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleStart = async () => {
    if (!selectedCameraId) {
      toast.error('Selecione uma câmera')
      return
    }
    setStarting(true)
    setFinalCounts(null)
    try {
      const res = await api.post<StartSessionResponse>('/counting/sessions', { camera_id: selectedCameraId })
      const session = res?.data?.session
      if (!session) throw new Error('Resposta inválida do servidor')
      setActiveSession(session)
      setActiveSessions(prev => [...prev, session])
      setStats(null)
      startPolling(session.id)
      toast.success('Contagem iniciada')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao iniciar contagem')
    } finally {
      setStarting(false)
    }
  }

  const handleStop = async () => {
    if (!activeSession) return
    setStopping(true)
    stopPolling()
    try {
      const res = await api.delete<StopSessionResponse>(`/counting/sessions/${activeSession.id}`)
      const totals = res?.data?.session?.total_counts ?? {}
      setFinalCounts(totals)
      setActiveSessions(prev => prev.filter(s => s.id !== activeSession.id))
      setActiveSession(null)
      setStats(null)
      toast.success('Contagem encerrada')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao encerrar contagem')
    } finally {
      setStopping(false)
    }
  }

  if (loading) return (
    <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Skeleton variant="title" width={200} />
      <Skeleton variant="rect" width="100%" height={44} />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px,1fr))', gap: 12 }}>
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: 6, padding: 12 }}>
            <Skeleton variant="text" width="60%" />
            <Skeleton variant="title" width="40%" />
          </div>
        ))}
      </div>
    </div>
  )

  const cameraName = (id: string) => cameras.find(c => c.id === id)?.name ?? id.slice(0, 8)

  return (
    <div style={{ padding: 24, maxWidth: 860, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Hash size={22} style={{ color: '#a78bfa' }} />
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: '#f1f5f9' }}>
            Contagem DeepSORT
          </h2>
          {activeSessions.length > 0 && (
            <span style={{
              background: '#7c3aed',
              color: '#fff',
              borderRadius: 999,
              padding: '2px 10px',
              fontSize: 12,
              fontWeight: 700,
            }}>
              {activeSessions.length} ativa{activeSessions.length !== 1 ? 's' : ''}
            </span>
          )}
        </div>
        <button
          onClick={loadInitialData}
          style={{
            background: 'transparent',
            border: '1px solid #334155',
            borderRadius: 6,
            color: '#94a3b8',
            padding: '6px 12px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 5,
            fontSize: 12,
          }}
        >
          <RefreshCw size={13} /> Atualizar
        </button>
      </div>

      <p style={{ color: '#64748b', fontSize: 13, marginBottom: 24, marginTop: 4 }}>
        Contagem por rastreamento DeepSORT. Selecione uma câmera e inicie a sessão.
      </p>

      {/* Controls */}
      <div style={{
        background: '#0f172a',
        border: '1px solid #1e293b',
        borderRadius: 10,
        padding: 20,
        marginBottom: 20,
        display: 'flex',
        gap: 12,
        alignItems: 'flex-end',
        flexWrap: 'wrap',
      }}>
        <div style={{ flex: 1, minWidth: 200 }}>
          <label style={{ display: 'block', fontSize: 12, color: '#64748b', marginBottom: 6 }}>
            Câmera
          </label>
          <select
            value={selectedCameraId}
            onChange={e => setSelectedCameraId(e.target.value)}
            disabled={!!activeSession}
            style={{
              width: '100%',
              background: '#1e293b',
              border: '1px solid #334155',
              borderRadius: 6,
              color: activeSession ? '#475569' : '#f1f5f9',
              padding: '8px 12px',
              fontSize: 14,
              cursor: activeSession ? 'not-allowed' : 'pointer',
              outline: 'none',
            }}
          >
            {cameras.length === 0 && (
              <option value="">Nenhuma câmera disponível</option>
            )}
            {cameras.map(cam => (
              <option key={cam.id} value={cam.id}>
                {cam.name}{cam.is_streaming ? ' (streaming)' : ''}
              </option>
            ))}
          </select>
        </div>

        {!activeSession ? (
          <button
            onClick={handleStart}
            disabled={starting || cameras.length === 0}
            style={{
              background: starting || cameras.length === 0 ? 'rgba(34,197,94,0.05)' : 'rgba(34,197,94,0.1)',
              border: '1px solid rgba(34,197,94,0.3)',
              borderRadius: 6,
              color: '#22c55e',
              padding: '8px 20px',
              cursor: starting || cameras.length === 0 ? 'not-allowed' : 'pointer',
              fontSize: 14,
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              opacity: starting || cameras.length === 0 ? 0.5 : 1,
              whiteSpace: 'nowrap',
            }}
          >
            <PlayCircle size={15} />
            {starting ? 'Iniciando...' : 'Iniciar Contagem'}
          </button>
        ) : (
          <button
            onClick={handleStop}
            disabled={stopping}
            style={{
              background: stopping ? 'rgba(239,68,68,0.05)' : 'rgba(239,68,68,0.1)',
              border: '1px solid rgba(239,68,68,0.3)',
              borderRadius: 6,
              color: '#ef4444',
              padding: '8px 20px',
              cursor: stopping ? 'not-allowed' : 'pointer',
              fontSize: 14,
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              opacity: stopping ? 0.5 : 1,
              whiteSpace: 'nowrap',
            }}
          >
            <StopCircle size={15} />
            {stopping ? 'Encerrando...' : 'Encerrar'}
          </button>
        )}
      </div>

      {/* Active session stats */}
      {activeSession && (
        <div style={{ marginBottom: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <div style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: '#22c55e',
              boxShadow: '0 0 6px #22c55e',
            }} />
            <span style={{ fontSize: 13, color: '#94a3b8' }}>
              Sessão ativa — câmera: <strong style={{ color: '#f1f5f9' }}>{cameraName(activeSession.camera_id)}</strong>
            </span>
            {stats && (
              <span style={{
                marginLeft: 'auto',
                fontSize: 12,
                color: '#64748b',
              }}>
                Total: <strong style={{ color: '#f1f5f9' }}>{stats.total}</strong>
              </span>
            )}
          </div>

          {stats && Object.keys(stats.counts).length > 0 ? (
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
              gap: 10,
            }}>
              {Object.entries(stats.counts).map(([cls, count]) => {
                const violation = isViolation(cls)
                const accent = violation ? '#ef4444' : '#22c55e'
                return (
                  <div
                    key={cls}
                    style={{
                      background: '#0f172a',
                      border: `1px solid ${violation ? 'rgba(239,68,68,0.25)' : 'rgba(34,197,94,0.25)'}`,
                      borderRadius: 8,
                      padding: '14px 16px',
                    }}
                  >
                    <div style={{ fontSize: 28, fontWeight: 700, color: accent, fontFamily: 'monospace', lineHeight: 1 }}>
                      {count}
                    </div>
                    <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 4 }}>
                      {CLASS_LABELS[cls] ?? cls}
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <div style={{
              textAlign: 'center',
              padding: '30px 20px',
              color: '#475569',
              border: '1px dashed #1e293b',
              borderRadius: 10,
              fontSize: 13,
            }}>
              Aguardando primeiras detecções...
            </div>
          )}
        </div>
      )}

      {/* Final counts modal/section */}
      {finalCounts && (
        <div style={{
          background: '#0f172a',
          border: '1px solid #334155',
          borderRadius: 10,
          padding: 20,
          marginBottom: 20,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
            <span style={{ fontSize: 15, fontWeight: 700, color: '#f1f5f9' }}>Totais da sessão encerrada</span>
            <button
              onClick={() => setFinalCounts(null)}
              style={{
                background: 'transparent',
                border: 'none',
                color: '#475569',
                cursor: 'pointer',
                fontSize: 18,
                lineHeight: 1,
                padding: 0,
              }}
              title="Fechar"
            >
              ×
            </button>
          </div>

          {Object.keys(finalCounts).length === 0 ? (
            <p style={{ margin: 0, fontSize: 13, color: '#64748b' }}>Nenhuma detecção registrada nesta sessão.</p>
          ) : (
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
              gap: 10,
            }}>
              {Object.entries(finalCounts).map(([cls, count]) => {
                const violation = isViolation(cls)
                const accent = violation ? '#ef4444' : '#22c55e'
                return (
                  <div
                    key={cls}
                    style={{
                      background: '#1e293b',
                      border: `1px solid ${violation ? 'rgba(239,68,68,0.2)' : 'rgba(34,197,94,0.2)'}`,
                      borderRadius: 8,
                      padding: '14px 16px',
                    }}
                  >
                    <div style={{ fontSize: 28, fontWeight: 700, color: accent, fontFamily: 'monospace', lineHeight: 1 }}>
                      {count}
                    </div>
                    <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 4 }}>
                      {CLASS_LABELS[cls] ?? cls}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* Other active sessions (not the one being controlled above) */}
      {activeSessions.filter(s => s.id !== activeSession?.id).length > 0 && (
        <div>
          <p style={{ fontSize: 12, color: '#64748b', marginBottom: 10 }}>Outras sessões ativas</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {activeSessions
              .filter(s => s.id !== activeSession?.id)
              .map(s => (
                <div
                  key={s.id}
                  style={{
                    background: '#0f172a',
                    border: '1px solid #1e293b',
                    borderRadius: 8,
                    padding: '12px 16px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                  }}
                >
                  <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#f59e0b', flexShrink: 0 }} />
                  <span style={{ fontSize: 13, color: '#94a3b8', flex: 1 }}>
                    Sessão <code style={{ color: '#f1f5f9', fontSize: 12 }}>{s.id.slice(0, 8)}</code>
                    {' — '}câmera: <strong style={{ color: '#f1f5f9' }}>{cameraName(s.camera_id)}</strong>
                  </span>
                  <span style={{
                    fontSize: 11,
                    color: '#475569',
                    background: '#1e293b',
                    borderRadius: 4,
                    padding: '2px 8px',
                  }}>
                    {s.status}
                  </span>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Empty state when nothing is running and no final counts */}
      {!activeSession && !finalCounts && activeSessions.length === 0 && (
        <div style={{
          textAlign: 'center',
          padding: '60px 20px',
          color: '#475569',
          border: '1px dashed #1e293b',
          borderRadius: 12,
        }}>
          <Hash size={40} style={{ opacity: 0.2, marginBottom: 12 }} />
          <p style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>Nenhuma contagem ativa</p>
          <p style={{ margin: '6px 0 0', fontSize: 13 }}>
            Selecione uma câmera e clique em "Iniciar Contagem".
          </p>
        </div>
      )}
    </div>
  )
}
