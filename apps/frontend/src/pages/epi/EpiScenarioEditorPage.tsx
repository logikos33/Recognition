/**
 * Página do editor visual de cenário para o módulo EPI.
 * Decisão (NEEDS CLARIFICATION resolvido): sem snapshot HLS disponível,
 * o canvas usa placeholder escuro em dev — editor não é bloqueado pelo stream.
 * Evita JWT em query param de URL (padrão de limitação documentado em CLAUDE.md).
 */
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { ScenarioEditor } from '../../components/scenario/ScenarioEditor'

export function EpiScenarioEditorPage() {
  const { cameraId } = useParams<{ cameraId: string }>()
  const navigate = useNavigate()

  if (!cameraId) {
    return <div style={{ padding: 32, color: '#888' }}>Câmera não encontrada</div>
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: '#0a0a0a' }}>
      {/* Breadcrumb */}
      <div
        style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '10px 16px',
          borderBottom: '1px solid #1e1e1e', background: '#0d0d0d',
        }}
      >
        <button
          onClick={() => navigate('/epi/cameras')}
          style={{
            display: 'flex', alignItems: 'center', gap: 4,
            background: 'transparent', border: 'none', color: '#888',
            cursor: 'pointer', fontSize: 13, padding: '2px 4px',
          }}
        >
          <ArrowLeft size={14} />
          Câmeras
        </button>
        <span style={{ color: '#444' }}>/</span>
        <span style={{ fontSize: 13, color: '#666' }}>Câmera {cameraId}</span>
        <span style={{ color: '#444' }}>/</span>
        <span style={{ fontSize: 13, color: '#e0e0e0' }}>Editor de Cenário</span>
      </div>

      <div style={{ flex: 1, overflow: 'hidden', padding: 16 }}>
        <ScenarioEditor cameraId={cameraId} defaultModuleId="ppe" />
      </div>
    </div>
  )
}
