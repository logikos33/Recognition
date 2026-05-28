interface BrandingPreviewProps {
  primary: string
  accent: string
  productName: string
  logoUrl?: string
}

const BG_BASE = '#0a0c10'
const BG_SURFACE = '#111318'
const BG_CARD = '#161a20'
const BORDER = '#1e2730'
const TEXT = '#f0f4f8'
const TEXT_MUTED = '#668096'

const miniScreen: React.CSSProperties = {
  background: BG_BASE,
  borderRadius: 8,
  border: `1px solid ${BORDER}`,
  overflow: 'hidden',
  fontSize: 9,
  color: TEXT,
  userSelect: 'none',
  position: 'relative',
}

const screenLabel: React.CSSProperties = {
  fontSize: 9,
  color: TEXT_MUTED,
  fontWeight: 600,
  marginBottom: 6,
  textTransform: 'uppercase' as const,
  letterSpacing: '0.06em',
}

function LoginPreview({ primary, productName, logoUrl }: Pick<BrandingPreviewProps, 'primary' | 'productName' | 'logoUrl'>) {
  return (
    <div>
      <div style={screenLabel}>Login</div>
      <div style={{ ...miniScreen, padding: '16px 14px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
        {logoUrl
          ? <img src={logoUrl} alt="logo" style={{ height: 20, objectFit: 'contain' }} />
          : <div style={{ width: 28, height: 28, borderRadius: 6, background: primary, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: 12, fontWeight: 700 }}>R</div>
        }
        <div style={{ fontWeight: 700, fontSize: 11, color: TEXT }}>{productName}</div>
        <div style={{ width: '100%', height: 20, background: BG_CARD, borderRadius: 4, border: `1px solid ${BORDER}` }} />
        <div style={{ width: '100%', height: 20, background: BG_CARD, borderRadius: 4, border: `1px solid ${BORDER}` }} />
        <div style={{ width: '100%', height: 22, background: primary, borderRadius: 4, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontWeight: 600 }}>
          Entrar
        </div>
      </div>
    </div>
  )
}

function DashboardPreview({ primary, accent, productName }: Omit<BrandingPreviewProps, 'logoUrl'>) {
  return (
    <div>
      <div style={screenLabel}>Dashboard</div>
      <div style={{ ...miniScreen, padding: 0 }}>
        {/* Top bar */}
        <div style={{ background: BG_SURFACE, borderBottom: `1px solid ${BORDER}`, padding: '5px 10px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: 9, fontWeight: 700, color: primary }}>{productName}</span>
          <div style={{ width: 14, height: 14, borderRadius: '50%', background: primary, opacity: 0.6 }} />
        </div>
        {/* Content */}
        <div style={{ padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: 6 }}>
          {/* KPI row */}
          <div style={{ display: 'flex', gap: 5 }}>
            {[primary, accent, '#10b981'].map((c, i) => (
              <div key={i} style={{ flex: 1, background: BG_CARD, borderRadius: 4, padding: '5px 6px', border: `1px solid ${BORDER}` }}>
                <div style={{ width: '60%', height: 4, background: TEXT_MUTED, borderRadius: 2, opacity: 0.4, marginBottom: 4 }} />
                <div style={{ fontSize: 12, fontWeight: 700, color: c }}>42</div>
              </div>
            ))}
          </div>
          {/* Chart placeholder */}
          <div style={{ background: BG_CARD, borderRadius: 4, border: `1px solid ${BORDER}`, padding: '6px 8px', height: 32, position: 'relative', overflow: 'hidden' }}>
            <div style={{ position: 'absolute', bottom: 6, left: 8, right: 8, display: 'flex', alignItems: 'flex-end', gap: 3 }}>
              {[60, 40, 75, 50, 90, 65, 80].map((h, i) => (
                <div key={i} style={{ flex: 1, height: `${h}%`, background: primary, borderRadius: '2px 2px 0 0', opacity: 0.7 }} />
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function AndonPreview({ primary, accent, productName }: Omit<BrandingPreviewProps, 'logoUrl'>) {
  return (
    <div>
      <div style={screenLabel}>Andon — TV Chão de Fábrica</div>
      <div style={{ ...miniScreen, padding: '10px', background: '#06080b' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <span style={{ fontWeight: 700, color: primary, fontSize: 10 }}>{productName}</span>
          <span style={{ color: '#22c55e', fontSize: 8, fontWeight: 600 }}>● AO VIVO</span>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 5 }}>
          {['CAM 01', 'CAM 02', 'CAM 03', 'CAM 04'].map((cam, i) => (
            <div key={cam} style={{ background: '#0a0c12', borderRadius: 4, border: `1px solid ${i === 2 ? accent : BORDER}`, overflow: 'hidden', aspectRatio: '16/9', display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative' }}>
              <span style={{ fontSize: 7, color: TEXT_MUTED }}>{cam}</span>
              {i === 2 && (
                <div style={{ position: 'absolute', top: 2, right: 2, width: 6, height: 6, borderRadius: '50%', background: accent }} />
              )}
            </div>
          ))}
        </div>
        <div style={{ marginTop: 6, display: 'flex', gap: 5 }}>
          <div style={{ flex: 1, background: BG_CARD, borderRadius: 3, padding: '4px 6px', border: `1px solid ${BORDER}` }}>
            <div style={{ fontSize: 8, color: TEXT_MUTED }}>Conformidade</div>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#10b981' }}>97%</div>
          </div>
          <div style={{ flex: 1, background: BG_CARD, borderRadius: 3, padding: '4px 6px', border: `1px solid rgba(239,68,68,0.3)` }}>
            <div style={{ fontSize: 8, color: TEXT_MUTED }}>Alertas</div>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#ef4444' }}>3</div>
          </div>
        </div>
      </div>
    </div>
  )
}

export function BrandingPreview({ primary, accent, productName, logoUrl }: BrandingPreviewProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ fontSize: 11, color: TEXT_MUTED, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
        Preview ao vivo
      </div>
      <LoginPreview primary={primary} productName={productName} logoUrl={logoUrl} />
      <DashboardPreview primary={primary} accent={accent} productName={productName} />
      <AndonPreview primary={primary} accent={accent} productName={productName} />
    </div>
  )
}
