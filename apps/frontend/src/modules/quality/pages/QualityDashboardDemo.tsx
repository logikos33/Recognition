/**
 * QualityDashboard — modo demonstração.
 * Dados mockados: 3 câmeras com feed de inspeções ao vivo simulado e pareto do turno.
 */
import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { vars } from '../../../styles/theme.css'

interface MockCamera {
  id: string
  name: string
  sub: string
  nokRate: number
  cepAlerts: number
  total: number
  ok: number
  nok: number
}

interface FeedEvent {
  id: string
  result: 'ok' | 'nok'
  defect: string | null
  confidence: number
  time: string
  fresh: boolean
}

const MOCK_CAMERAS: MockCamera[] = [
  { id: 'cam-a', name: 'Linha A', sub: 'Frontal',   nokRate: 0.034, cepAlerts: 0, total: 1247, ok: 1204, nok:  43 },
  { id: 'cam-b', name: 'Linha B', sub: 'Lateral',   nokRate: 0.087, cepAlerts: 3, total:  892, ok:  814, nok:  78 },
  { id: 'cam-c', name: 'Linha C', sub: 'Embalagem', nokRate: 0.012, cepAlerts: 0, total: 2103, ok: 2078, nok:  25 },
]

const DEFECTS = ['Arranhão', 'Mancha', 'Deformação', 'Cor incorreta', 'Trinca']

const PARETO = [
  { label: 'Arranhão',   pct: 47, count: 68 },
  { label: 'Mancha',     pct: 31, count: 45 },
  { label: 'Deformação', pct: 14, count: 20 },
  { label: 'Outros',     pct:  8, count: 12 },
]

function makeEvent(fresh: boolean): FeedEvent {
  const isNok = Math.random() < 0.28
  return {
    id: Math.random().toString(36).slice(2),
    result: isNok ? 'nok' : 'ok',
    defect: isNok ? (DEFECTS[Math.floor(Math.random() * DEFECTS.length)] ?? null) : null,
    confidence: 0.82 + Math.random() * 0.17,
    time: new Date().toLocaleTimeString('pt-BR'),
    fresh,
  }
}

function makeInitialFeed(): FeedEvent[] {
  return Array.from({ length: 10 }, () => makeEvent(false))
}

interface QualityDashboardDemoProps {
  onSwitchPro: () => void
}

export function QualityDashboardDemo({ onSwitchPro }: QualityDashboardDemoProps) {
  const navigate = useNavigate()
  const [selectedId, setSelectedId] = useState('cam-a')
  const [feed, setFeed] = useState<FeedEvent[]>(makeInitialFeed)
  const [dotOn, setDotOn] = useState(true)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    intervalRef.current = setInterval(() => {
      const ev = makeEvent(true)
      setFeed(prev => [ev, ...prev.slice(0, 19)])
      setTimeout(() => {
        setFeed(prev => prev.map(e => (e.id === ev.id ? { ...e, fresh: false } : e)))
      }, 500)
    }, 2500)
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [])

  useEffect(() => {
    const t = setInterval(() => setDotOn(v => !v), 900)
    return () => clearInterval(t)
  }, [])

  const cam = MOCK_CAMERAS.find(c => c.id === selectedId) ?? MOCK_CAMERAS[0]!
  const nokColor = (cam.nokRate > 0.05) ? vars.color.danger : '#FFB74D'
  const cepColor = (cam.cepAlerts > 0) ? vars.color.danger : vars.color.success

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: '600px', background: '#080808', color: vars.color.textSecondary }}>

      {/* Top bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px', padding: '11px 20px', borderBottom: `1px solid ${vars.color.borderDefault}`, background: vars.color.bgBase, flexShrink: 0 }}>
        <span style={{ fontSize: '14px', fontWeight: 700, color: vars.color.textPrimary, letterSpacing: '0.3px' }}>
          Qualidade Industrial
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
          <span style={{ width: '7px', height: '7px', borderRadius: '50%', display: 'inline-block', background: dotOn ? vars.color.success : '#1d4a30', transition: 'background 0.5s' }} />
          <span style={{ fontSize: '10px', fontWeight: 700, color: vars.color.success, letterSpacing: '0.8px' }}>AO VIVO</span>
        </span>
        <span style={{ fontSize: '10px', fontWeight: 700, padding: '2px 8px', borderRadius: '3px', background: '#1a1200', color: '#FFB74D', letterSpacing: '0.5px' }}>
          TURNO: MANHÃ
        </span>
        <span style={{ fontSize: '10px', fontWeight: 700, padding: '2px 8px', borderRadius: '3px', background: vars.color.bgSurface, color: vars.color.textMuted, letterSpacing: '0.5px' }}>
          {MOCK_CAMERAS.length} CÂMERAS
        </span>
        <span style={{ marginLeft: 'auto', fontSize: '10px', color: vars.color.textPrimary, letterSpacing: '0.5px', marginRight: '8px' }}>MODO DEMONSTRAÇÃO</span>
        <button
          onClick={onSwitchPro}
          style={{
            fontSize: '10px', fontWeight: 700, padding: '3px 10px', borderRadius: '4px',
            background: 'rgba(79,195,247,0.12)', border: '1px solid rgba(79,195,247,0.3)',
            color: '#4FC3F7', cursor: 'pointer', letterSpacing: '0.5px',
          }}
        >
          MODO PRO →
        </button>
      </div>

      {/* Body */}
      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>

        {/* Sidebar */}
        <div style={{ width: '200px', flexShrink: 0, borderRight: `1px solid ${vars.color.borderDefault}`, background: vars.color.bgBase, display: 'flex', flexDirection: 'column', paddingTop: '14px' }}>
          <div style={{ fontSize: '10px', color: vars.color.textPrimary, fontWeight: 700, letterSpacing: '1px', padding: '0 14px', marginBottom: '8px' }}>CÂMERAS ATIVAS</div>

          {MOCK_CAMERAS.map(c => (
            <div
              key={c.id}
              onClick={() => setSelectedId(c.id)}
              style={{
                padding: '11px 14px', cursor: 'pointer',
                borderLeft: c.id === selectedId ? '3px solid #4FC3F7' : '3px solid transparent',
                background: c.id === selectedId ? '#0d1929' : 'transparent',
                transition: 'background 0.15s',
                marginBottom: '2px',
              }}
            >
              <div style={{ fontSize: '12px', fontWeight: 600, color: c.id === selectedId ? vars.color.textOnPrimary : vars.color.textSecondary }}>{c.name}</div>
              <div style={{ fontSize: '11px', color: vars.color.textMuted, marginTop: '1px' }}>{c.sub}</div>
              <div style={{ fontSize: '11px', marginTop: '5px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span
                  onClick={e => { e.stopPropagation(); navigate(`/quality/inspections?camera_id=${c.id}&result=nok`) }}
                  title="Ver defeitos desta câmera →"
                  style={{ color: c.nokRate > 0.05 ? vars.color.danger : vars.color.textMuted, cursor: 'pointer', textDecoration: 'underline dotted', textUnderlineOffset: '2px' }}
                >
                  NOK {(c.nokRate * 100).toFixed(1)}%
                </span>
                {c.cepAlerts > 0 && (
                  <span
                    onClick={e => { e.stopPropagation(); navigate(`/quality/inspections?camera_id=${c.id}&result=nok&feedback_status=pending`) }}
                    title="Ver alertas pendentes →"
                    style={{ color: vars.color.danger, fontSize: '10px', cursor: 'pointer' }}
                  >
                    ⚠ {c.cepAlerts}
                  </span>
                )}
              </div>
            </div>
          ))}

          <div style={{ flex: 1 }} />

          <button
            onClick={() => navigate(`/quality/inspections?camera_id=${selectedId}`)}
            title="Ver todas as inspeções desta câmera"
            style={{ margin: '12px', padding: '8px 12px', background: 'none', border: `1px solid ${vars.color.borderDefault}`, borderRadius: '4px', color: '#4FC3F7', fontSize: '11px', cursor: 'pointer', textAlign: 'left' }}
          >
            ↗ Ver inspeções
          </button>
        </div>

        {/* Main panel */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '16px', gap: '14px', minWidth: 0 }}>

          {/* KPI row */}
          <div style={{ display: 'flex', gap: '12px', flexShrink: 0 }}>
            {[
              { label: 'TOTAL INSPECIONADO', value: cam.total.toLocaleString('pt-BR'), accent: '#4FC3F7', to: `/quality/inspections?camera_id=${cam.id}`, tip: 'Ver todas as inspeções desta câmera →' },
              { label: 'TAXA OK',             value: `${((cam.ok / cam.total) * 100).toFixed(1)}%`, accent: vars.color.success, to: `/quality/inspections?camera_id=${cam.id}&result=ok`, tip: 'Ver inspeções aprovadas →' },
              { label: 'TAXA NOK',            value: `${(cam.nokRate * 100).toFixed(1)}%`, accent: nokColor, to: `/quality/inspections?camera_id=${cam.id}&result=nok`, tip: 'Ver defeitos detectados →' },
              { label: 'STATUS CEP',          value: cam.cepAlerts > 0 ? `${cam.cepAlerts} ALERTAS` : 'CONTROLE', accent: cepColor, to: `/quality/inspections?camera_id=${cam.id}&result=nok${cam.cepAlerts > 0 ? '&feedback_status=pending' : ''}`, tip: cam.cepAlerts > 0 ? 'Ver alertas de CEP pendentes de revisão →' : 'Ver inspeções desta câmera →' },
            ].map(kpi => (
              <div
                key={kpi.label}
                onClick={() => navigate(kpi.to)}
                title={kpi.tip}
                style={{ flex: 1, background: vars.color.bgSurface, borderRadius: '6px', padding: '14px 16px', border: `1px solid ${vars.color.borderDefault}`, borderTopColor: kpi.accent, borderTopWidth: '2px', borderTopStyle: 'solid', cursor: 'pointer' }}
              >
                <div style={{ fontSize: '22px', fontWeight: 700, color: kpi.accent, fontVariantNumeric: 'tabular-nums' }}>{kpi.value}</div>
                <div style={{ fontSize: '10px', color: vars.color.textMuted, marginTop: '5px', letterSpacing: '0.5px' }}>{kpi.label}</div>
                <div style={{ fontSize: '9px', color: vars.color.textPrimary, marginTop: '4px', letterSpacing: '0.3px' }}>clique para filtrar ↗</div>
              </div>
            ))}
          </div>

          {/* Feed + Pareto */}
          <div style={{ display: 'flex', gap: '14px', flex: 1, minHeight: 0 }}>

            {/* Feed de inspeções */}
            <div style={{ flex: 1, background: vars.color.bgBase, borderRadius: '6px', border: `1px solid ${vars.color.borderDefault}`, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>
              <div style={{ padding: '10px 14px', fontSize: '10px', fontWeight: 700, color: vars.color.textMuted, borderBottom: `1px solid ${vars.color.borderDefault}`, letterSpacing: '0.8px', flexShrink: 0 }}>
                FEED DE INSPEÇÕES — {cam.name.toUpperCase()} / {cam.sub.toUpperCase()}
              </div>
              <div style={{ overflow: 'auto', flex: 1 }}>
                {feed.map(ev => (
                  <div
                    key={ev.id}
                    onClick={ev.result === 'nok' ? () => navigate(`/quality/inspections?camera_id=${cam.id}&result=nok`) : undefined}
                    title={ev.result === 'nok' ? 'Ver defeitos desta câmera →' : undefined}
                    style={{
                      display: 'flex', alignItems: 'center', gap: '10px',
                      padding: '8px 14px', borderBottom: `1px solid ${vars.color.borderDefault}`,
                      opacity: ev.fresh ? 0 : 1,
                      transform: ev.fresh ? 'translateY(-4px)' : 'none',
                      transition: 'opacity 0.4s, transform 0.4s',
                      background: ev.fresh ? (ev.result === 'nok' ? '#180808' : '#081408') : 'transparent',
                      cursor: ev.result === 'nok' ? 'pointer' : 'default',
                    }}
                  >
                    <span style={{
                      fontSize: '9px', fontWeight: 700, padding: '2px 6px', borderRadius: '2px', minWidth: '28px', textAlign: 'center',
                      background: ev.result === 'nok' ? '#3d0f0f' : '#0f3d1f',
                      color: ev.result === 'nok' ? vars.color.danger : vars.color.success,
                    }}>
                      {ev.result.toUpperCase()}
                    </span>
                    <span style={{ fontSize: '12px', color: vars.color.textSecondary, flex: 1 }}>
                      {ev.defect ?? '—'}
                    </span>
                    <span style={{ fontSize: '11px', color: vars.color.textMuted, fontVariantNumeric: 'tabular-nums' }}>
                      {(ev.confidence * 100).toFixed(0)}%
                    </span>
                    <span style={{ fontSize: '10px', color: '#3a3a3a', minWidth: '60px', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                      {ev.time}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Pareto */}
            <div style={{ width: '230px', flexShrink: 0, background: vars.color.bgBase, borderRadius: '6px', border: `1px solid ${vars.color.borderDefault}`, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
              <div style={{ padding: '10px 14px', fontSize: '10px', fontWeight: 700, color: vars.color.textMuted, borderBottom: `1px solid ${vars.color.borderDefault}`, letterSpacing: '0.8px', flexShrink: 0 }}>
                PARETO — TURNO ATUAL
              </div>
              <div style={{ padding: '14px', display: 'flex', flexDirection: 'column', gap: '14px', overflow: 'auto', flex: 1 }}>
                {PARETO.map(p => (
                  <div
                    key={p.label}
                    onClick={() => navigate(`/quality/inspections?camera_id=${cam.id}&result=nok`)}
                    title={`Ver inspeções NOK — ${p.label} →`}
                    style={{ cursor: 'pointer' }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
                      <span style={{ fontSize: '12px', color: vars.color.textSecondary }}>{p.label}</span>
                      <span style={{ fontSize: '11px', color: vars.color.textMuted }}>{p.pct}% · {p.count}</span>
                    </div>
                    <div style={{ height: '6px', background: vars.color.bgCard, borderRadius: '3px', overflow: 'hidden' }}>
                      <div style={{
                        height: '100%',
                        width: `${p.pct}%`,
                        borderRadius: '3px',
                        background: p.pct > 40 ? vars.color.danger : p.pct > 25 ? '#FFB74D' : '#4FC3F7',
                        transition: 'width 0.8s ease',
                      }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>

          </div>
        </div>
      </div>
    </div>
  )
}
