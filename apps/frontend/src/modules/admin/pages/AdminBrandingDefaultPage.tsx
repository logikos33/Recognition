import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Lock } from 'lucide-react'
import { vars } from '../../../styles/theme.css'

const TOKENS = [
  { group: 'Fundo', items: [
    { name: 'bgBase', value: '#0a0c10', desc: 'Fundo principal da aplicação' },
    { name: 'bgSurface', value: '#111318', desc: 'Superfícies elevadas (cards, sidebar)' },
    { name: 'bgElevated', value: '#1e2330', desc: 'Modais, dropdowns' },
    { name: 'bgCard', value: '#161a20', desc: 'Cards secundários' },
  ]},
  { group: 'Texto', items: [
    { name: 'textPrimary', value: '#f0f4f8', desc: 'Texto principal' },
    { name: 'textSecondary', value: '#8ba3bc', desc: 'Texto de suporte' },
    { name: 'textMuted', value: '#668096', desc: 'Labels, metadados (WCAG AA: 4.76:1)' },
  ]},
  { group: 'Cor Primária (ciano)', items: [
    { name: 'primary', value: '#06b6d4', desc: 'Ações principais, links, foco' },
    { name: 'primaryLight', value: '#22d3ee', desc: 'Hover de botões primários' },
    { name: 'primaryDark', value: '#0891b2', desc: 'Estado active' },
    { name: 'primaryAlpha', value: 'rgba(6,182,212,0.1)', desc: 'Fundos de foco, seleção' },
  ]},
  { group: 'Acento (laranja-segurança)', items: [
    { name: 'accent', value: '#ea580c', desc: 'Alertas visuais, destaques' },
    { name: 'accentLight', value: '#f97316', desc: 'Hover de acento' },
    { name: 'accentDark', value: '#c2410c', desc: 'Estado active' },
  ]},
  { group: 'Semânticas', items: [
    { name: 'success', value: '#10b981', desc: 'Conformidade, OK' },
    { name: 'warning', value: '#f59e0b', desc: 'Atenção, limiar' },
    { name: 'danger', value: '#ef4444', desc: 'Violação, erro crítico' },
  ]},
  { group: 'Bordas', items: [
    { name: 'borderSubtle', value: '#161c24', desc: 'Separadores de baixo contraste' },
    { name: 'borderDefault', value: '#1e2730', desc: 'Bordas padrão de cards' },
    { name: 'borderStrong', value: '#2a3545', desc: 'Bordas em foco/hover' },
  ]},
]

function Swatch({ color }: { color: string }) {
  const isRgba = color.startsWith('rgba')
  return (
    <div style={{
      width: 28, height: 28, borderRadius: 5, flexShrink: 0,
      background: color, border: '1px solid rgba(255,255,255,0.08)',
      ...(isRgba ? { backgroundImage: `linear-gradient(45deg, ${vars.color.borderDefault} 25%, transparent 25%)`, backgroundSize: '6px 6px' } : {}),
    }} />
  )
}

export function AdminBrandingDefaultPage() {
  const navigate = useNavigate()

  return (
    <div style={{ padding: 32, maxWidth: 820 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 6 }}>
        <button
          onClick={() => navigate('/admin/branding/tenants')}
          style={{ background: 'transparent', border: 'none', color: '#668096', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4, fontSize: 13, padding: 0 }}
        >
          <ArrowLeft size={14} /> Tenants
        </button>
        <span style={{ color: vars.color.borderStrong }}>/</span>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: '#f0f4f8' }}>Tema Padrão Recognition</h2>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4, background: '#161a20', color: '#668096', fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 4 }}>
          <Lock size={10} /> Somente leitura
        </span>
      </div>
      <p style={{ color: '#668096', fontSize: 13, margin: '0 0 28px' }}>
        Tokens de design base da plataforma Recognition. Tenants herdam esses valores e podem sobrescrever primary, accent e nome.
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        {TOKENS.map(group => (
          <div key={group.group} style={{ background: '#111318', border: '1px solid #1e2730', borderRadius: 10, overflow: 'hidden' }}>
            <div style={{ padding: '10px 18px', borderBottom: '1px solid #1e2730', background: '#0d1117' }}>
              <span style={{ fontSize: 11, fontWeight: 600, color: '#668096', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{group.group}</span>
            </div>
            <div style={{ padding: '8px 0' }}>
              {group.items.map(item => (
                <div key={item.name} style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '8px 18px' }}>
                  <Swatch color={item.value} />
                  <code style={{ fontSize: 12, color: '#06b6d4', minWidth: 140, fontFamily: 'monospace' }}>{item.name}</code>
                  <code style={{ fontSize: 11, color: '#8ba3bc', minWidth: 200, fontFamily: 'monospace' }}>{item.value}</code>
                  <span style={{ fontSize: 12, color: '#668096' }}>{item.desc}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
