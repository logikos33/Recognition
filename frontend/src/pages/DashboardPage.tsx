/**
 * DashboardPage — overview do sistema.
 */
import { useState, useEffect } from 'react'
import { api } from '../services/api'
import type { Camera, TrainingJob, Video, ApiResponse } from '../types'

export function DashboardPage() {
  const [stats, setStats] = useState({
    cameras: 0, activeCameras: 0,
    videos: 0, jobs: 0, runningJobs: 0,
  })

  useEffect(() => {
    loadStats()
  }, [])

  const loadStats = async () => {
    try {
      const [camsRes, videosRes, jobsRes] = await Promise.all([
        api.get<ApiResponse<Camera[]>>('/cameras').catch(() => ({ data: [] })),
        api.get<ApiResponse<Video[]>>('/training/videos').catch(() => ({ data: [] })),
        api.get<ApiResponse<TrainingJob[]>>('/training/jobs').catch(() => ({ data: [] })),
      ])
      const cams = (camsRes as any).data || []
      const vids = (videosRes as any).data || []
      const jbs = (jobsRes as any).data || []
      setStats({
        cameras: cams.length,
        activeCameras: cams.filter((c: Camera) => c.stream_status === 'active').length,
        videos: vids.length,
        jobs: jbs.length,
        runningJobs: jbs.filter((j: TrainingJob) => j.status === 'running').length,
      })
    } catch {}
  }

  const cards = [
    { label: 'Cameras', value: stats.cameras, sub: `${stats.activeCameras} ativas`, color: '#2563eb' },
    { label: 'Videos', value: stats.videos, sub: 'enviados', color: '#8b5cf6' },
    { label: 'Treinamentos', value: stats.jobs, sub: `${stats.runningJobs} em execucao`, color: '#22c55e' },
  ]

  return (
    <div style={{ padding: 32 }}>
      <h2 style={{ color: '#e2e8f0', marginBottom: 24 }}>Dashboard</h2>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 16 }}>
        {cards.map(card => (
          <div key={card.label} style={{
            padding: 24, background: '#1e293b', borderRadius: 12,
            border: '1px solid #334155',
          }}>
            <div style={{ color: '#94a3b8', fontSize: 13, marginBottom: 8 }}>{card.label}</div>
            <div style={{ fontSize: 36, fontWeight: 800, color: card.color }}>{card.value}</div>
            <div style={{ color: '#64748b', fontSize: 13, marginTop: 4 }}>{card.sub}</div>
          </div>
        ))}
      </div>

      <div style={{
        marginTop: 32, padding: 24, background: '#1e293b',
        borderRadius: 12, border: '1px solid #334155',
      }}>
        <h3 style={{ color: '#e2e8f0', marginBottom: 12 }}>Status do Sistema</h3>
        <div style={{ display: 'grid', gap: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', color: '#94a3b8', fontSize: 14 }}>
            <span>API</span>
            <span style={{ color: '#22c55e', fontWeight: 600 }}>Online</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', color: '#94a3b8', fontSize: 14 }}>
            <span>Arquitetura</span>
            <span style={{ color: '#64748b' }}>Microservicos V2</span>
          </div>
        </div>
      </div>
    </div>
  )
}
