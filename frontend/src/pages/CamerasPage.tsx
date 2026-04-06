/**
 * CamerasPage — CRUD de cameras e controle de stream.
 */
import { useState, useEffect, useCallback } from 'react'
import { api } from '../services/api'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import { StatusBadge } from '../components/shared/StatusBadge'
import type { Camera, ApiResponse } from '../types'

export function CamerasPage() {
  const [cameras, setCameras] = useState<Camera[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ name: '', host: '', port: '554', username: 'admin', password: '' })

  const loadCameras = useCallback(async () => {
    try {
      const res = await api.get<ApiResponse<Camera[]>>('/cameras')
      setCameras(res.data || [])
    } catch (err) {
      console.error('Failed to load cameras:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadCameras() }, [loadCameras])

  const createCamera = async () => {
    try {
      await api.post('/cameras', {
        name: form.name, host: form.host,
        port: parseInt(form.port), username: form.username,
        password: form.password,
      })
      setShowForm(false)
      setForm({ name: '', host: '', port: '554', username: 'admin', password: '' })
      await loadCameras()
    } catch (err: any) {
      alert(err.message || 'Erro ao criar camera')
    }
  }

  const toggleStream = async (cam: Camera) => {
    try {
      if (cam.stream_status === 'active') {
        await api.post(`/cameras/${cam.id}/stream/stop`)
      } else {
        await api.post(`/cameras/${cam.id}/stream/start`)
      }
      await loadCameras()
    } catch (err: any) {
      alert(err.message || 'Erro ao controlar stream')
    }
  }

  const inp: React.CSSProperties = {
    width: '100%', padding: '10px 12px', borderRadius: 8,
    border: '1px solid #334155', background: '#0f172a',
    color: '#e2e8f0', fontSize: 14, boxSizing: 'border-box',
  }

  if (loading) return <LoadingSpinner />

  return (
    <div style={{ padding: 32 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h2 style={{ color: '#e2e8f0', margin: 0 }}>Cameras</h2>
        <button onClick={() => setShowForm(!showForm)} style={{
          padding: '8px 20px', borderRadius: 8, border: 'none',
          background: '#2563eb', color: '#fff', fontSize: 14,
          fontWeight: 600, cursor: 'pointer',
        }}>
          {showForm ? 'Cancelar' : 'Nova Camera'}
        </button>
      </div>

      {showForm && (
        <div style={{
          padding: 20, background: '#1e293b', borderRadius: 12,
          border: '1px solid #334155', marginBottom: 20,
        }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <input style={inp} placeholder="Nome da camera" value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
            <input style={inp} placeholder="IP (ex: 192.168.1.100)" value={form.host}
              onChange={e => setForm(f => ({ ...f, host: e.target.value }))} />
            <input style={inp} placeholder="Porta" value={form.port}
              onChange={e => setForm(f => ({ ...f, port: e.target.value }))} />
            <input style={inp} placeholder="Usuario" value={form.username}
              onChange={e => setForm(f => ({ ...f, username: e.target.value }))} />
            <input style={{ ...inp, gridColumn: 'span 2' }} type="password"
              placeholder="Senha" value={form.password}
              onChange={e => setForm(f => ({ ...f, password: e.target.value }))} />
          </div>
          <button onClick={createCamera} style={{
            marginTop: 12, padding: '10px 24px', borderRadius: 8,
            border: 'none', background: '#22c55e', color: '#fff',
            fontWeight: 600, cursor: 'pointer',
          }}>
            Salvar Camera
          </button>
        </div>
      )}

      {cameras.length === 0 ? (
        <div style={{
          padding: 40, textAlign: 'center', color: '#64748b',
          background: '#1e293b', borderRadius: 12,
        }}>
          <p>Nenhuma camera cadastrada.</p>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 16 }}>
          {cameras.map(cam => (
            <div key={cam.id} style={{
              padding: 16, background: '#1e293b', borderRadius: 12,
              border: '1px solid #334155',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ color: '#e2e8f0', fontWeight: 600 }}>{cam.name}</span>
                <StatusBadge status={cam.stream_status || 'inactive'} />
              </div>
              <p style={{ color: '#64748b', fontSize: 13, margin: '8px 0' }}>
                {cam.host}:{cam.port} ({cam.manufacturer})
              </p>
              {cam.location && (
                <p style={{ color: '#475569', fontSize: 12, margin: '4px 0' }}>{cam.location}</p>
              )}
              <button onClick={() => toggleStream(cam)} style={{
                marginTop: 8, padding: '6px 16px', borderRadius: 6,
                border: 'none', fontSize: 13, fontWeight: 600, cursor: 'pointer',
                background: cam.stream_status === 'active' ? '#dc2626' : '#22c55e',
                color: '#fff',
              }}>
                {cam.stream_status === 'active' ? 'Parar' : 'Iniciar'}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
