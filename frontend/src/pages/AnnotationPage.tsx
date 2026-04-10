/**
 * AnnotationPage — wrapper para AnnotationInterface.jsx.
 * NÃO modifica o componente congelado. Apenas gerencia seleção de vídeo.
 */
import { useState, useEffect } from 'react'
import { api } from '../services/api'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import { Badge, statusToBadge } from '../components/ui/Badge/Badge'
import type { Video, ApiResponse } from '../types'
import * as s from './AnnotationPage.css'

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
              onClick={() => setSelectedVideoId(video.id)}
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
              <Badge status={statusToBadge(video.status)}>{video.status}</Badge>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
