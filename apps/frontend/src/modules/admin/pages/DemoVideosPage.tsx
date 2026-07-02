/**
 * DemoVideosPage — Gerenciamento de vídeos demo para modo demonstração.
 *
 * Acessível apenas para superadmin. Permite upload de MP4s que ficam em loop
 * no lugar do feed HLS real durante apresentações comerciais.
 * Clientes jamais veem esta página nem os vídeos demo.
 */
import { useState, useEffect, useRef } from 'react'
import { Navigate } from 'react-router-dom'
import { Trash2, Upload, Video } from 'lucide-react'
import { useAuth } from '../../../hooks/useAuth'
import { api } from '../../../services/api'
import { vars } from '../../../styles/theme.css'

interface DemoVideo {
  id: number
  module: string
  camera_id: number | null
  label: string | null
  r2_url: string
  file_size_bytes: number | null
  created_at: string
}

const MODULES = [
  { key: 'fueling',        label: 'Abastecimento' },
  { key: 'epi',            label: 'EPI' },
  { key: 'access_control', label: 'Controle de Acesso' },
] as const

type ModuleKey = typeof MODULES[number]['key']

function formatBytes(b: number | null): string {
  if (!b) return '—'
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(0)} KB`
  return `${(b / 1024 / 1024).toFixed(1)} MB`
}

export function DemoVideosPage() {
  const { isSuperAdmin } = useAuth()

  // Proteção extra no client: redireciona se não for superadmin
  if (!isSuperAdmin) return <Navigate to="/" replace />

  const [activeTab, setActiveTab] = useState<ModuleKey>('fueling')
  const [videos, setVideos] = useState<DemoVideo[]>([])
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [showUpload, setShowUpload] = useState(false)

  // Campos do formulário de upload
  const fileRef = useRef<HTMLInputElement>(null)
  const [uploadLabel, setUploadLabel] = useState('')

  const loadVideos = async (module: ModuleKey) => {
    setLoading(true)
    try {
      const res = await api.get<{ data: { videos: DemoVideo[] } }>(
        `/admin/demo-videos?module=${module}`
      )
      setVideos(res?.data?.videos ?? [])
    } catch {
      setVideos([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadVideos(activeTab)
  }, [activeTab])

  const handleDelete = async (id: number) => {
    if (!confirm('Remover este vídeo demo?')) return
    try {
      await api.delete(`/admin/demo-videos/${id}`)
      setVideos(v => v.filter(x => x.id !== id))
    } catch {
      alert('Erro ao remover vídeo.')
    }
  }

  const handleUpload = async () => {
    const file = fileRef.current?.files?.[0]
    if (!file) { setUploadError('Selecione um arquivo MP4.'); return }
    if (!file.type.includes('mp4')) { setUploadError('Apenas arquivos MP4 são aceitos.'); return }

    setUploading(true)
    setUploadError(null)
    const form = new FormData()
    form.append('video', file)
    form.append('module', activeTab)
    if (uploadLabel.trim()) form.append('label', uploadLabel.trim())

    try {
      await api.post('/admin/demo-videos/upload', form)
      setShowUpload(false)
      setUploadLabel('')
      if (fileRef.current) fileRef.current.value = ''
      await loadVideos(activeTab)
    } catch (e: unknown) {
      setUploadError(e instanceof Error ? e.message : 'Erro no upload.')
    } finally {
      setUploading(false)
    }
  }

  const tabStyle = (active: boolean): React.CSSProperties => ({
    padding: '8px 18px',
    borderRadius: 6,
    border: 'none',
    cursor: 'pointer',
    fontWeight: 600,
    fontSize: 13,
    background: active ? 'rgba(99,102,241,0.18)' : 'transparent',
    color: active ? '#a5b4fc' : vars.color.textMuted,
    transition: 'all 0.15s',
  })

  return (
    <div style={{ padding: 28, maxWidth: 900 }}>
      {/* Cabeçalho */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Video size={20} color="#a5b4fc" />
          <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: '#f1f5f9' }}>
            Vídeos Demo
          </h2>
          <span style={{
            background: 'rgba(99,102,241,0.15)',
            border: '1px solid rgba(99,102,241,0.3)',
            color: '#a5b4fc',
            borderRadius: 4,
            padding: '2px 8px',
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: '0.05em',
          }}>
            SUPERADMIN
          </span>
        </div>
        <button
          onClick={() => { setShowUpload(true); setUploadError(null) }}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            background: 'rgba(99,102,241,0.2)',
            border: '1px solid rgba(99,102,241,0.4)',
            borderRadius: 7,
            color: '#a5b4fc',
            padding: '7px 16px',
            fontSize: 13,
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          <Upload size={14} /> Upload de vídeo
        </button>
      </div>

      {/* Banner explicativo */}
      <div style={{
        background: 'rgba(99,102,241,0.08)',
        border: '1px solid rgba(99,102,241,0.2)',
        borderRadius: 8,
        padding: '10px 16px',
        marginBottom: 24,
        fontSize: 13,
        color: vars.color.textSecondary,
      }}>
        Vídeos MP4 aqui ficam em <strong style={{ color: '#a5b4fc' }}>loop</strong> no lugar do feed HLS durante demonstrações.
        Apenas visível para superadmin — clientes nunca veem esta página nem os vídeos.
      </div>

      {/* Tabs por módulo */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 20 }}>
        {MODULES.map(m => (
          <button
            key={m.key}
            style={tabStyle(activeTab === m.key)}
            onClick={() => setActiveTab(m.key)}
          >
            {m.label}
          </button>
        ))}
      </div>

      {/* Tabela de vídeos */}
      <div style={{ background: vars.color.bgBase, border: `1px solid ${vars.color.bgSurface}`, borderRadius: 10, overflow: 'hidden' }}>
        <div style={{ padding: '12px 20px', borderBottom: `1px solid ${vars.color.bgSurface}`, fontSize: 13, fontWeight: 600, color: vars.color.textMuted }}>
          Vídeos demo ativos — {MODULES.find(m => m.key === activeTab)?.label}
        </div>

        {loading ? (
          <div style={{ padding: 48, textAlign: 'center', color: vars.color.textMuted, fontSize: 13 }}>Carregando...</div>
        ) : videos.length === 0 ? (
          <div style={{ padding: 48, textAlign: 'center', color: vars.color.textMuted }}>
            <Video size={28} style={{ opacity: 0.25, marginBottom: 10 }} />
            <p style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>Nenhum vídeo demo cadastrado</p>
            <p style={{ margin: '6px 0 0', fontSize: 12 }}>
              Faça upload de um MP4 para usar neste módulo durante demonstrações.
            </p>
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${vars.color.bgSurface}` }}>
                {['Label', 'Câmera ID', 'Tamanho', 'Data de upload', ''].map(col => (
                  <th key={col} style={{
                    padding: '9px 20px', textAlign: 'left',
                    fontSize: 11, fontWeight: 600, color: vars.color.textMuted,
                    textTransform: 'uppercase', letterSpacing: '0.05em',
                  }}>
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {videos.map((v, idx) => (
                <tr key={v.id} style={{
                  borderBottom: idx < videos.length - 1 ? `1px solid ${vars.color.bgBase}` : 'none',
                  background: idx % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.015)',
                }}>
                  <td style={{ padding: '11px 20px', fontSize: 13, color: '#f1f5f9', fontWeight: 500 }}>
                    {v.label ?? <span style={{ color: vars.color.textMuted }}>sem label</span>}
                  </td>
                  <td style={{ padding: '11px 20px', fontSize: 12, color: vars.color.textMuted, fontFamily: 'monospace' }}>
                    {v.camera_id ?? '—'}
                  </td>
                  <td style={{ padding: '11px 20px', fontSize: 12, color: vars.color.textMuted }}>
                    {formatBytes(v.file_size_bytes)}
                  </td>
                  <td style={{ padding: '11px 20px', fontSize: 12, color: vars.color.textMuted }}>
                    {v.created_at ? new Date(v.created_at).toLocaleDateString('pt-BR') : '—'}
                  </td>
                  <td style={{ padding: '11px 20px', textAlign: 'right' }}>
                    <button
                      onClick={() => handleDelete(v.id)}
                      style={{
                        background: 'transparent',
                        border: '1px solid rgba(239,68,68,0.3)',
                        borderRadius: 5,
                        color: '#f87171',
                        padding: '4px 10px',
                        cursor: 'pointer',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 4,
                        fontSize: 12,
                      }}
                    >
                      <Trash2 size={12} /> Remover
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Modal de upload */}
      {showUpload && (
        <div style={{
          position: 'fixed', inset: 0,
          background: 'rgba(0,0,0,0.7)',
          backdropFilter: 'blur(4px)',
          zIndex: 100,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <div style={{
            background: vars.color.bgBase,
            border: `1px solid ${vars.color.bgSurface}`,
            borderRadius: 12,
            padding: 28,
            width: 420,
            maxWidth: '90vw',
          }}>
            <h3 style={{ margin: '0 0 20px', fontSize: 16, fontWeight: 700, color: '#f1f5f9' }}>
              Upload de vídeo demo
            </h3>

            <div style={{ marginBottom: 14 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: vars.color.textMuted, marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Módulo
              </label>
              <div style={{ padding: '8px 12px', background: vars.color.bgSurface, borderRadius: 6, fontSize: 13, color: '#a5b4fc', fontWeight: 600 }}>
                {MODULES.find(m => m.key === activeTab)?.label}
              </div>
            </div>

            <div style={{ marginBottom: 14 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: vars.color.textMuted, marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Arquivo MP4 *
              </label>
              <input
                ref={fileRef}
                type="file"
                accept="video/mp4"
                style={{ fontSize: 13, color: vars.color.textSecondary, width: '100%' }}
              />
            </div>

            <div style={{ marginBottom: 20 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: vars.color.textMuted, marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Label (opcional)
              </label>
              <input
                type="text"
                placeholder="ex: Pátio Baia 01"
                value={uploadLabel}
                onChange={e => setUploadLabel(e.target.value)}
                style={{
                  width: '100%', padding: '8px 12px',
                  background: vars.color.bgSurface, border: `1px solid ${vars.color.borderStrong}`,
                  borderRadius: 6, fontSize: 13, color: '#f1f5f9',
                  outline: 'none', boxSizing: 'border-box',
                }}
              />
            </div>

            {uploadError && (
              <p style={{ margin: '0 0 14px', fontSize: 13, color: '#f87171' }}>{uploadError}</p>
            )}

            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              <button
                onClick={() => { setShowUpload(false); setUploadError(null) }}
                disabled={uploading}
                style={{
                  padding: '8px 18px', borderRadius: 6,
                  background: 'transparent', border: `1px solid ${vars.color.borderStrong}`,
                  color: vars.color.textMuted, fontSize: 13, cursor: 'pointer',
                }}
              >
                Cancelar
              </button>
              <button
                onClick={handleUpload}
                disabled={uploading}
                style={{
                  padding: '8px 18px', borderRadius: 6,
                  background: 'rgba(99,102,241,0.25)',
                  border: '1px solid rgba(99,102,241,0.4)',
                  color: '#a5b4fc', fontSize: 13, fontWeight: 600,
                  cursor: uploading ? 'not-allowed' : 'pointer',
                  opacity: uploading ? 0.6 : 1,
                }}
              >
                {uploading ? 'Enviando...' : 'Fazer upload'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
