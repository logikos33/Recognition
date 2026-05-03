import { useState, useEffect, useCallback } from 'react'
import { api } from '../services/api'
import { useToast } from '../components/ui/Toast/useToast'

interface ModuleClass {
  id: string
  module_code: string
  class_id: number
  class_name: string
  display_name: string
  dino_prompt: string | null
  is_active: boolean
  color: string | null
}

interface Detection {
  bbox: [number, number, number, number]
  label: string
  confidence: number
}

export default function ModuleClassesPage() {
  const toast = useToast()
  const [classes, setClasses] = useState<ModuleClass[]>([])
  const [loading, setLoading] = useState(true)
  const [toggling, setToggling] = useState<string | null>(null)
  const [testFrameId, setTestFrameId] = useState('')
  const [detecting, setDetecting] = useState(false)
  const [detections, setDetections] = useState<Detection[] | null>(null)

  const loadClasses = useCallback(async () => {
    try {
      const res = await api.get<{ status: string; data: { classes: ModuleClass[] } }>('/modules/epi/classes')
      setClasses(res.data?.classes ?? [])
    } catch {
      toast.error('Erro ao carregar classes')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadClasses() }, [loadClasses])

  const handleToggle = async (cls: ModuleClass) => {
    setToggling(cls.id)
    try {
      await api.patch(`/modules/epi/classes/${cls.id}`, { is_active: !cls.is_active })
      setClasses(prev => prev.map(c => c.id === cls.id ? { ...c, is_active: !c.is_active } : c))
      toast.success(cls.is_active ? `${cls.display_name} desativada` : `${cls.display_name} ativada`)
    } catch {
      toast.error('Erro ao alterar classe')
    } finally {
      setToggling(null)
    }
  }

  const handleDetect = async () => {
    if (!testFrameId.trim()) {
      toast.error('Informe o ID de um frame')
      return
    }
    setDetecting(true)
    setDetections(null)
    try {
      const res = await api.post<{ status: string; data: { detections: Detection[] } }>(
        '/modules/epi/classes/detect',
        { frame_id: testFrameId.trim() }
      )
      const dets = res.data?.detections ?? []
      setDetections(dets)
      if (dets.length === 0) {
        toast.warning('Nenhuma detecção encontrada. Tente outro frame ou ajuste o prompt.')
      } else {
        toast.success(`${dets.length} detecção(ões) encontrada(s)`)
      }
    } catch {
      toast.error('Erro ao testar detecção')
    } finally {
      setDetecting(false)
    }
  }

  if (loading) return <div style={{ padding: 32 }}>Carregando classes...</div>

  const active = classes.filter(c => c.is_active)
  const inactive = classes.filter(c => !c.is_active)

  return (
    <div style={{ padding: '24px 32px', maxWidth: 800 }}>
      <h2 style={{ marginBottom: 8 }}>Classes do Módulo EPI</h2>
      <p style={{ color: '#6b7280', marginBottom: 24 }}>
        Ative ou desative as classes que o modelo deve detectar.
        Classes inativas não entram no treinamento nem na inferência.
      </p>

      {/* Active classes */}
      <section style={{ marginBottom: 32 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, color: '#374151', marginBottom: 12 }}>
          Ativas ({active.length})
        </h3>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {active.map(cls => (
            <button
              key={cls.id}
              onClick={() => handleToggle(cls)}
              disabled={toggling === cls.id}
              style={{
                padding: '6px 14px',
                borderRadius: 20,
                border: `2px solid ${cls.color ?? '#3b82f6'}`,
                background: cls.color ? `${cls.color}22` : '#eff6ff',
                color: cls.color ?? '#1d4ed8',
                fontWeight: 500,
                cursor: 'pointer',
                opacity: toggling === cls.id ? 0.5 : 1,
              }}
              title="Clique para desativar"
            >
              {cls.display_name} ✓
            </button>
          ))}
          {active.length === 0 && (
            <p style={{ color: '#9ca3af', fontSize: 14 }}>Nenhuma classe ativa.</p>
          )}
        </div>
      </section>

      {/* Inactive classes */}
      {inactive.length > 0 && (
        <section style={{ marginBottom: 32 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, color: '#9ca3af', marginBottom: 12 }}>
            Inativas ({inactive.length})
          </h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {inactive.map(cls => (
              <button
                key={cls.id}
                onClick={() => handleToggle(cls)}
                disabled={toggling === cls.id}
                style={{
                  padding: '6px 14px',
                  borderRadius: 20,
                  border: '2px solid #d1d5db',
                  background: '#f9fafb',
                  color: '#9ca3af',
                  fontWeight: 500,
                  cursor: 'pointer',
                  opacity: toggling === cls.id ? 0.5 : 1,
                }}
                title="Clique para ativar"
              >
                {cls.display_name}
              </button>
            ))}
          </div>
        </section>
      )}

      {/* Test DINO detection */}
      <section style={{ borderTop: '1px solid #e5e7eb', paddingTop: 24 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, color: '#374151', marginBottom: 12 }}>
          Testar Detecção DINO
        </h3>
        <p style={{ color: '#6b7280', fontSize: 13, marginBottom: 12 }}>
          Informe o ID de um frame existente para testar a detecção automática com os prompts configurados.
        </p>
        <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
          <input
            type="text"
            placeholder="ID do frame (UUID)"
            value={testFrameId}
            onChange={e => setTestFrameId(e.target.value)}
            style={{
              flex: 1, padding: '8px 12px', borderRadius: 6,
              border: '1px solid #d1d5db', fontSize: 14,
            }}
          />
          <button
            onClick={handleDetect}
            disabled={detecting}
            style={{
              padding: '8px 16px', borderRadius: 6, border: 'none',
              background: '#3b82f6', color: '#fff', fontWeight: 500,
              cursor: detecting ? 'not-allowed' : 'pointer',
              opacity: detecting ? 0.7 : 1,
            }}
          >
            {detecting ? 'Detectando...' : 'Testar DINO'}
          </button>
        </div>
        {detections !== null && (
          <div style={{
            padding: 12, borderRadius: 6, background: '#f0fdf4',
            border: '1px solid #bbf7d0', fontSize: 13,
          }}>
            {detections.length === 0
              ? 'Nenhuma detecção. Tente outro frame.'
              : `${detections.length} detecção(ões): ` +
                detections.map(d => `${d.label} (${(d.confidence * 100).toFixed(0)}%)`).join(', ')
            }
          </div>
        )}
      </section>
    </div>
  )
}
