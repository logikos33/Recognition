import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, FlaskConical, RotateCcw } from 'lucide-react'
import { resolveTheme } from '../../../theme/tenant-theme/resolver'
import { ColorPicker } from '../components/ColorPicker'
import { BrandingPreview } from '../components/BrandingPreview'

const DEFAULTS = { primary: '#06b6d4', accent: '#ea580c', productName: 'Recognition' }

const PRESETS = [
  { label: 'Recognition', primary: '#06b6d4', accent: '#ea580c' },
  { label: 'Verde Industrial', primary: '#16a34a', accent: '#f59e0b' },
  { label: 'Azul Corporativo', primary: '#2563eb', accent: '#f59e0b' },
  { label: 'Roxo Tech', primary: '#7c3aed', accent: '#f97316' },
  { label: 'Vermelho Crítico', primary: '#dc2626', accent: '#06b6d4' },
  { label: 'Teal Segurança', primary: '#0d9488', accent: '#fb923c' },
]

export function AdminBrandingSandboxPage() {
  const navigate = useNavigate()
  const [primary, setPrimary] = useState(DEFAULTS.primary)
  const [accent, setAccent] = useState(DEFAULTS.accent)
  const [productName, setProductName] = useState(DEFAULTS.productName)
  const [applied, setApplied] = useState(false)

  function applyToPage() {
    const { cssVars } = resolveTheme({ brand: { productName }, colors: { primary, accent } })
    const style = document.getElementById('recognition-tenant-theme')
    if (style) {
      const vars = Object.entries(cssVars).map(([k, v]) => `${k}: ${v};`).join(' ')
      style.textContent = `:root { ${vars} }`
    }
    setApplied(true)
  }

  function clearFromPage() {
    const style = document.getElementById('recognition-tenant-theme')
    if (style) style.textContent = ''
    setApplied(false)
  }

  function applyPreset(p: typeof PRESETS[0]) {
    setPrimary(p.primary)
    setAccent(p.accent)
  }

  function reset() {
    setPrimary(DEFAULTS.primary)
    setAccent(DEFAULTS.accent)
    setProductName(DEFAULTS.productName)
    clearFromPage()
  }

  return (
    <div style={{ padding: 32, maxWidth: 1100 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 6 }}>
        <button
          onClick={() => navigate('/admin/branding/tenants')}
          style={{ background: 'transparent', border: 'none', color: '#668096', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4, fontSize: 13, padding: 0 }}
        >
          <ArrowLeft size={14} /> Tenants
        </button>
        <span style={{ color: '#334155' }}>/</span>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: '#f0f4f8', display: 'flex', alignItems: 'center', gap: 8 }}>
          <FlaskConical size={18} style={{ color: '#a78bfa' }} /> Sandbox
        </h2>
        {applied && (
          <span style={{ background: 'rgba(167,139,250,0.12)', color: '#a78bfa', fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 4 }}>
            Aplicado na página
          </span>
        )}
      </div>
      <p style={{ color: '#668096', fontSize: 13, margin: '0 0 24px' }}>
        Experimente combinações de cores livremente. Nada é salvo — use para testar paletas antes de aplicar a um tenant.
      </p>

      {/* Presets */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 28 }}>
        {PRESETS.map(p => (
          <button
            key={p.label}
            onClick={() => applyPreset(p)}
            style={{
              display: 'flex', alignItems: 'center', gap: 7,
              background: '#111318', border: `1px solid ${primary === p.primary ? '#2a3545' : '#1e2730'}`,
              borderRadius: 6, padding: '5px 12px', cursor: 'pointer', fontSize: 12, color: '#8ba3bc',
            }}
          >
            <div style={{ display: 'flex', gap: 3 }}>
              <div style={{ width: 10, height: 10, borderRadius: '50%', background: p.primary }} />
              <div style={{ width: 10, height: 10, borderRadius: '50%', background: p.accent }} />
            </div>
            {p.label}
          </button>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 32, alignItems: 'start' }}>
        {/* Controls */}
        <div style={{ background: '#111318', border: '1px solid #1e2730', borderRadius: 10, padding: 24 }}>
          <h3 style={{ margin: '0 0 20px', fontSize: 15, fontWeight: 600, color: '#f0f4f8' }}>Cores</h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            {/* Product name */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <label style={{ fontSize: 12, color: '#8ba3bc', fontWeight: 500 }}>Nome do produto</label>
              <input
                type="text"
                value={productName}
                onChange={e => setProductName(e.target.value)}
                style={{ background: '#0a0c10', border: '1px solid #1e2730', borderRadius: 6, color: '#f0f4f8', fontSize: 14, padding: '8px 12px' }}
              />
            </div>

            <ColorPicker label="Cor primária" value={primary} onChange={setPrimary} />
            <ColorPicker label="Cor de acento" value={accent} onChange={setAccent} />
          </div>

          {/* Actions */}
          <div style={{ marginTop: 28, display: 'flex', gap: 10 }}>
            {applied ? (
              <button
                onClick={clearFromPage}
                style={{ background: 'rgba(167,139,250,0.1)', border: '1px solid rgba(167,139,250,0.3)', borderRadius: 6, color: '#a78bfa', padding: '8px 18px', cursor: 'pointer', fontSize: 13, fontWeight: 600 }}
              >
                Remover da página
              </button>
            ) : (
              <button
                onClick={applyToPage}
                style={{ background: '#7c3aed', border: 'none', borderRadius: 6, color: '#fff', padding: '8px 18px', cursor: 'pointer', fontSize: 13, fontWeight: 600 }}
              >
                Aplicar na página
              </button>
            )}
            <button
              onClick={reset}
              style={{ background: 'transparent', border: '1px solid #1e2730', borderRadius: 6, color: '#668096', padding: '8px 16px', cursor: 'pointer', fontSize: 13, display: 'flex', alignItems: 'center', gap: 6 }}
            >
              <RotateCcw size={13} /> Resetar
            </button>
          </div>
        </div>

        {/* Preview */}
        <div style={{ background: '#111318', border: '1px solid #1e2730', borderRadius: 10, padding: 20, position: 'sticky', top: 20 }}>
          <BrandingPreview primary={primary} accent={accent} productName={productName} />
        </div>
      </div>
    </div>
  )
}
