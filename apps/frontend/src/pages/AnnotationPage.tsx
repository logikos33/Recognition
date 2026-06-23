/**
 * AnnotationPage — selecao de video e validacao de frames.
 * AI_NOTE: AnnotationInterface.jsx e CONGELADO — nunca modificar.
 * A logica de validacao fica neste wrapper, nao no componente congelado.
 * US-025: adiciona painel de validacao de frames anotados por video.
 */
import { useState, useEffect } from 'react'
import { api, getToken } from '../services/api'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import { Badge, statusToBadgeVariant } from '../components/ui/Badge/Badge'
import type { Video, ApiResponse } from '../types'
import * as s from './AnnotationPage.css'

// @ts-ignore — JSX component congelado
import AnnotationInterface from '../components/AnnotationInterface'

interface AnnotatedFrame {
  id: string
  frame_number: number
  filename: string
  is_annotated: boolean
  validated_at: string | null
  url: string | null
}

interface ValidationStats {
  annotated: number
  validated: number
  total: number
}

export function AnnotationPage() {
  const [videos, setVideos] = useState<Video[]>([])
  const [selectedVideoId, setSelectedVideoId] = useState<string | null>(null)
  // AI_NOTE: showAnnotation separates video-detail view from annotation full-screen mode
  const [showAnnotation, setShowAnnotation] = useState(false)
  const [loading, setLoading] = useState(true)

  // Validation panel state
  const [annotatedFrames, setAnnotatedFrames] = useState<AnnotatedFrame[]>([])
  const [stats, setStats] = useState<ValidationStats | null>(null)
  const [validatingId, setValidatingId] = useState<string | null>(null)
  const [framesLoading, setFramesLoading] = useState(false)

  useEffect(() => {
    loadVideos()
  }, [])

  // AI_NOTE: reload frames/stats each time detail panel is shown (not during annotation mode)
  useEffect(() => {
    if (selectedVideoId && !showAnnotation) {
      loadFramesAndStats(selectedVideoId)
    }
  }, [selectedVideoId, showAnnotation])

  const loadVideos = async () => {
    try {
      const res = await api.get<ApiResponse<Video[]>>('/training/videos')
      setVideos(res.data || [])
    } catch (err) {
      console.error('Failed to load videos:', err)
    } finally {
      setLoading(false)
    }
  }

  const loadFramesAndStats = async (videoId: string) => {
    setFramesLoading(true)
    try {
      const token = getToken()
      const authHeader = token ? `Bearer ${token}` : ''
      const [framesRes, statsRes] = await Promise.all([
        fetch(`/api/training/videos/${videoId}/frames`, {
          headers: { Authorization: authHeader },
        }).then(r => r.json()),
        fetch(`/api/training/videos/${videoId}/validation-stats`, {
          headers: { Authorization: authHeader },
        }).then(r => r.json()),
      ])

      const frames: AnnotatedFrame[] = framesRes.frames || []
      setAnnotatedFrames(frames.filter(f => f.is_annotated))
      setStats(statsRes.stats || null)
    } catch (err) {
      console.error('Failed to load frames/stats:', err)
    } finally {
      setFramesLoading(false)
    }
  }

  const handleValidate = async (frameId: string) => {
    setValidatingId(frameId)
    try {
      const token = getToken()
      const res = await fetch(`/api/training/frames/${frameId}/validate`, {
        method: 'POST',
        headers: { Authorization: token ? `Bearer ${token}` : '' },
      })
      const data = await res.json()
      if (data.success) {
        setAnnotatedFrames(prev =>
          prev.map(f => f.id === frameId ? { ...f, validated_at: data.validated_at } : f)
        )
        setStats(prev => prev ? { ...prev, validated: prev.validated + 1 } : prev)
      }
    } catch (err) {
      console.error('Failed to validate frame:', err)
    } finally {
      setValidatingId(null)
    }
  }

  // --- Render: full-screen annotation mode ---
  if (showAnnotation && selectedVideoId) {
    return (
      <AnnotationInterface
        videoId={selectedVideoId}
        onBack={() => setShowAnnotation(false)}
      />
    )
  }

  // --- Render: video detail + validation panel ---
  if (selectedVideoId) {
    const video = videos.find(v => v.id === selectedVideoId)
    return (
      <div className={s.page}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '20px' }}>
          <button
            onClick={() => { setSelectedVideoId(null); setAnnotatedFrames([]); setStats(null) }}
            style={{
              background: 'none', border: '1px solid rgba(255,255,255,0.2)',
              color: 'rgba(255,255,255,0.7)', padding: '6px 12px',
              borderRadius: '6px', cursor: 'pointer', fontSize: '13px',
            }}
          >
            &larr; Voltar
          </button>
          <h2 className={s.pageTitle} style={{ margin: 0 }}>
            {video?.original_filename || video?.filename || 'Video'}
          </h2>
          <button
            onClick={() => setShowAnnotation(true)}
            style={{
              background: '#3b82f6', border: 'none',
              color: '#fff', padding: '8px 18px',
              borderRadius: '6px', cursor: 'pointer', fontSize: '14px',
              fontWeight: 600, marginLeft: 'auto',
            }}
          >
            Anotar Frames
          </button>
        </div>

        {/* Validation counters */}
        {stats && (
          <div style={{
            display: 'flex', gap: '16px', marginBottom: '20px',
            padding: '12px 16px', background: 'rgba(255,255,255,0.04)',
            borderRadius: '8px', border: '1px solid rgba(255,255,255,0.08)',
          }}>
            <span style={{ color: 'rgba(255,255,255,0.6)', fontSize: '13px' }}>
              Total: <strong style={{ color: '#fff' }}>{stats.total}</strong>
            </span>
            <span style={{ color: 'rgba(255,255,255,0.6)', fontSize: '13px' }}>
              Anotados: <strong style={{ color: '#22c55e' }}>{stats.annotated}</strong>
            </span>
            <span style={{ color: 'rgba(255,255,255,0.6)', fontSize: '13px' }}>
              Validados: <strong style={{ color: '#3b82f6' }}>{stats.validated}</strong>
              {stats.validated < 20 && (
                <span style={{ color: '#f59e0b', marginLeft: '6px', fontSize: '12px' }}>
                  (minimo 20 para treinar)
                </span>
              )}
            </span>
          </div>
        )}

        {/* Annotated frames list */}
        <h3 style={{ color: 'rgba(255,255,255,0.8)', fontSize: '14px', marginBottom: '12px', fontWeight: 500 }}>
          Frames para Validacao
        </h3>

        {framesLoading ? (
          <LoadingSpinner />
        ) : annotatedFrames.length === 0 ? (
          <div className={s.emptyState}>
            <p className={s.emptyText}>Nenhum frame anotado ainda.</p>
            <p className={s.emptyTextSub}>Clique em &quot;Anotar Frames&quot; para comecar.</p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {annotatedFrames.map(frame => (
              <div
                key={frame.id}
                style={{
                  display: 'flex', alignItems: 'center', gap: '12px',
                  padding: '10px 14px',
                  background: 'rgba(255,255,255,0.04)',
                  border: `1px solid ${frame.validated_at ? 'rgba(59,130,246,0.4)' : 'rgba(255,255,255,0.08)'}`,
                  borderRadius: '8px',
                }}
              >
                {frame.url && (
                  <img
                    src={frame.url}
                    alt={`Frame ${frame.frame_number}`}
                    style={{ width: '72px', height: '45px', objectFit: 'cover', borderRadius: '4px', flexShrink: 0 }}
                  />
                )}
                <span style={{ color: 'rgba(255,255,255,0.7)', fontSize: '13px', flex: 1 }}>
                  Frame #{frame.frame_number}
                </span>
                {frame.validated_at ? (
                  <span style={{
                    color: '#3b82f6', fontSize: '12px', fontWeight: 600,
                    padding: '4px 10px', background: 'rgba(59,130,246,0.12)',
                    borderRadius: '4px',
                  }}>
                    Validado
                  </span>
                ) : (
                  <button
                    disabled={validatingId === frame.id}
                    onClick={() => handleValidate(frame.id)}
                    style={{
                      background: validatingId === frame.id ? 'rgba(255,255,255,0.1)' : 'rgba(34,197,94,0.15)',
                      border: '1px solid rgba(34,197,94,0.4)',
                      color: '#22c55e', padding: '5px 14px',
                      borderRadius: '5px', cursor: validatingId === frame.id ? 'not-allowed' : 'pointer',
                      fontSize: '12px', fontWeight: 600,
                    }}
                  >
                    {validatingId === frame.id ? 'Salvando...' : 'Validar'}
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }

  // --- Render: video list ---
  return (
    <div className={s.page}>
      <h2 className={s.pageTitle}>Anotacao de Frames</h2>

      {loading ? (
        <LoadingSpinner />
      ) : videos.length === 0 ? (
        <div className={s.emptyState}>
          <p className={s.emptyText}>Nenhum video disponivel para anotacao.</p>
          <p className={s.emptyTextSub}>Faca upload de um video primeiro.</p>
        </div>
      ) : (
        <div className={s.grid}>
          {videos.filter(v => v.status === 'extracted').map(video => (
            <div
              key={video.id}
              onClick={() => { setSelectedVideoId(video.id); setShowAnnotation(false) }}
              className={s.videoCard}
            >
              <div>
                <span className={s.videoName}>
                  {video.original_filename || video.filename}
                </span>
                <span className={s.videoFrameCount}>
                  {video.frame_count} frames
                </span>
              </div>
              <Badge variant={statusToBadgeVariant(video.status)}>{video.status}</Badge>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
