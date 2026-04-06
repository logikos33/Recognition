/**
 * AnnotationPage — wrapper para AnnotationInterface.jsx.
 * NÃO modifica o componente congelado. Apenas gerencia seleção de vídeo.
 */
import { useState, useEffect } from 'react'
import { api } from '../services/api'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import { StatusBadge } from '../components/shared/StatusBadge'
import type { Video, ApiResponse } from '../types'

// @ts-ignore — JSX component congelado
import AnnotationInterface from '../components/AnnotationInterface'

export function AnnotationPage() {
  const [videos, setVideos] = useState<Video[]>([])
  const [selectedVideoId, setSelectedVideoId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadVideos()
  }, [])

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

  if (selectedVideoId) {
    return (
      <AnnotationInterface
        videoId={selectedVideoId}
        onBack={() => setSelectedVideoId(null)}
      />
    )
  }

  return (
    <div style={{ padding: 32 }}>
      <h2 style={{ color: '#e2e8f0', marginBottom: 20 }}>Anotacao de Frames</h2>

      {loading ? (
        <LoadingSpinner />
      ) : videos.length === 0 ? (
        <div style={{
          padding: 40, textAlign: 'center', color: '#64748b',
          background: '#1e293b', borderRadius: 12,
        }}>
          <p>Nenhum video disponivel para anotacao.</p>
          <p style={{ fontSize: 13 }}>Faca upload de um video primeiro.</p>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: 12 }}>
          {videos.filter(v => v.status === 'extracted').map(video => (
            <div
              key={video.id}
              onClick={() => setSelectedVideoId(video.id)}
              style={{
                padding: 16, background: '#1e293b', borderRadius: 12,
                border: '1px solid #334155', cursor: 'pointer',
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              }}
            >
              <div>
                <span style={{ color: '#e2e8f0', fontWeight: 600 }}>
                  {video.original_filename || video.filename}
                </span>
                <span style={{ color: '#64748b', fontSize: 13, marginLeft: 12 }}>
                  {video.frame_count} frames
                </span>
              </div>
              <StatusBadge status={video.status} />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
