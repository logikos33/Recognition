/**
 * BrandingPreview — prova visual do White-Label (WS1).
 * Renderiza mini-telas (login, dashboard, panel+modal, andon) usando as cores
 * EM EDIÇÃO — incluindo containers/superfícies — antes de salvar.
 */
import { vars } from '../../../styles/theme.css'
import { RECOGNITION_DEFAULT_SURFACES } from '../../../theme/tenant-theme/defaults'
import type { TenantSurfaceOverrides } from '../../../theme/tenant-theme/types'

interface BrandingPreviewProps {
  primary: string
  accent: string
  productName: string
  logoUrl?: string
  surfaces?: TenantSurfaceOverrides
}

type ResolvedSurfaces = Required<TenantSurfaceOverrides>

function resolveSurfaces(s?: TenantSurfaceOverrides): ResolvedSurfaces {
  return {
    bgBase: s?.bgBase ?? RECOGNITION_DEFAULT_SURFACES.bgBase,
    bgSurface: s?.bgSurface ?? RECOGNITION_DEFAULT_SURFACES.bgSurface,
    bgElevated: s?.bgElevated ?? RECOGNITION_DEFAULT_SURFACES.bgElevated,
    bgCard: s?.bgCard ?? RECOGNITION_DEFAULT_SURFACES.bgCard,
    textPrimary: s?.textPrimary ?? RECOGNITION_DEFAULT_SURFACES.textPrimary,
    textSecondary: s?.textSecondary ?? RECOGNITION_DEFAULT_SURFACES.textSecondary,
    border: s?.border ?? RECOGNITION_DEFAULT_SURFACES.border,
  }
}

function miniScreen(s: ResolvedSurfaces): React.CSSProperties {
  return {
    background: s.bgBase,
    borderRadius: 8,
    border: `1px solid ${s.border}`,
    overflow: 'hidden',
    fontSize: 9,
    color: s.textPrimary,
    userSelect: 'none',
    position: 'relative',
  }
}

const screenLabel: React.CSSProperties = {
  fontSize: 9,
  color: vars.color.textMuted,
  fontWeight: 600,
  marginBottom: 6,
  textTransform: 'uppercase' as const,
  letterSpacing: '0.06em',
}

function LoginPreview({ primary, productName, logoUrl, s }: { primary: string; productName: string; logoUrl?: string; s: ResolvedSurfaces }) {
  return (
    <div>
      <div style={screenLabel}>Login</div>
      <div style={{ ...miniScreen(s), padding: '16px 14px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
        {logoUrl
          ? <img src={logoUrl} alt="logo" style={{ height: 20, objectFit: 'contain' }} />
          : <div style={{ width: 28, height: 28, borderRadius: 6, background: primary, display: 'flex', alignItems: 'center', justifyContent: 'center', color: vars.color.textOnPrimary, fontSize: 12, fontWeight: 700 }}>R</div>
        }
        <div style={{ fontWeight: 700, fontSize: 11, color: s.textPrimary }}>{productName}</div>
        <div style={{ width: '100%', height: 20, background: s.bgCard, borderRadius: 4, border: `1px solid ${s.border}` }} />
        <div style={{ width: '100%', height: 20, background: s.bgCard, borderRadius: 4, border: `1px solid ${s.border}` }} />
        <div style={{ width: '100%', height: 22, background: primary, borderRadius: 4, display: 'flex', alignItems: 'center', justifyContent: 'center', color: vars.color.textOnPrimary, fontWeight: 600 }}>
          Entrar
        </div>
      </div>
    </div>
  )
}

function PanelModalPreview({ primary, s }: { primary: string; s: ResolvedSurfaces }) {
  return (
    <div>
      <div style={screenLabel}>Painel + Modal</div>
      <div style={{ ...miniScreen(s), padding: 8, minHeight: 110 }}>
        {/* Panel */}
        <div style={{ background: s.bgSurface, border: `1px solid ${s.border}`, borderRadius: 5 }}>
          <div style={{ padding: '5px 8px', borderBottom: `1px solid ${s.border}`, fontWeight: 700, fontSize: 9, color: s.textPrimary }}>
            Painel de seção
          </div>
          <div style={{ padding: 8, display: 'flex', gap: 5 }}>
            <div style={{ flex: 1, height: 24, background: s.bgCard, borderRadius: 3, border: `1px solid ${s.border}` }} />
            <div style={{ flex: 1, height: 24, background: s.bgCard, borderRadius: 3, border: `1px solid ${s.border}` }} />
          </div>
        </div>
        {/* Modal simulado sobre o painel */}
        <div style={{
          background: 'rgba(0,0,0,0.55)', // allow: mock de overlay no preview
          position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <div style={{ width: '70%', background: s.bgElevated, border: `1px solid ${s.border}`, borderRadius: 5, overflow: 'hidden' }}>
            <div style={{ padding: '5px 8px', borderBottom: `1px solid ${s.border}`, fontWeight: 700, fontSize: 9, color: s.textPrimary }}>
              Modal (elevado)
            </div>
            <div style={{ padding: 8, color: s.textSecondary, fontSize: 8 }}>
              Fundo em bgElevated, borda e textos do tenant.
            </div>
            <div style={{ padding: '5px 8px', display: 'flex', justifyContent: 'flex-end', gap: 4, background: s.bgSurface }}>
              <div style={{ padding: '3px 8px', borderRadius: 3, border: `1px solid ${s.border}`, color: s.textSecondary, fontSize: 8 }}>Cancelar</div>
              <div style={{ padding: '3px 8px', borderRadius: 3, background: primary, color: vars.color.textOnPrimary, fontSize: 8, fontWeight: 600 }}>Confirmar</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function DashboardPreview({ primary, accent, productName, s }: { primary: string; accent: string; productName: string; s: ResolvedSurfaces }) {
  return (
    <div>
      <div style={screenLabel}>Dashboard</div>
      <div style={{ ...miniScreen(s), padding: 0 }}>
        <div style={{ background: s.bgSurface, borderBottom: `1px solid ${s.border}`, padding: '5px 10px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: 9, fontWeight: 700, color: primary }}>{productName}</span>
          <div style={{ width: 14, height: 14, borderRadius: '50%', background: primary, opacity: 0.6 }} />
        </div>
        <div style={{ padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ display: 'flex', gap: 5 }}>
            {[primary, accent, vars.color.success].map((c, i) => (
              <div key={i} style={{ flex: 1, background: s.bgCard, borderRadius: 4, padding: '5px 6px', border: `1px solid ${s.border}` }}>
                <div style={{ width: '60%', height: 4, background: s.textSecondary, borderRadius: 2, opacity: 0.4, marginBottom: 4 }} />
                <div style={{ fontSize: 12, fontWeight: 700, color: c }}>42</div>
              </div>
            ))}
          </div>
          <div style={{ background: s.bgCard, borderRadius: 4, border: `1px solid ${s.border}`, padding: '6px 8px', height: 32, position: 'relative', overflow: 'hidden' }}>
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

export function BrandingPreview({ primary, accent, productName, logoUrl, surfaces }: BrandingPreviewProps) {
  const s = resolveSurfaces(surfaces)
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ fontSize: 11, color: vars.color.textMuted, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
        Preview ao vivo
      </div>
      <LoginPreview primary={primary} productName={productName} logoUrl={logoUrl} s={s} />
      <PanelModalPreview primary={primary} s={s} />
      <DashboardPreview primary={primary} accent={accent} productName={productName} s={s} />
    </div>
  )
}
