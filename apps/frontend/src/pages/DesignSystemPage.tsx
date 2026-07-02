/**
 * DesignSystemPage — catálogo interno de tokens, primitivos e padrões.
 * Rota: /design-system (apenas superadmin em dev).
 */
import { useState } from 'react'
import { vars } from '../styles/theme.css'
import { Button } from '../components/ui/Button/Button'
import { Badge } from '../components/ui/Badge/Badge'
import { Input, Field } from '../components/ui/Input/Input'
import { Skeleton } from '../components/ui/Skeleton/Skeleton'
import { useToast } from '../components/ui/Toast/useToast'
import { Panel } from '../components/ui/Panel/Panel'
import { PageHeader } from '../components/ui/PageHeader/PageHeader'
import { Modal } from '../components/ui/Modal/Modal'
import { AppDrawer } from '../components/ui/AppDrawer/AppDrawer'

// ── Section wrapper ───────────────────────────────────────────────────────────

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section style={{ marginBottom: 48 }}>
      <h2 style={{
        fontSize: 13, fontWeight: 700, color: vars.color.textMuted,
        textTransform: 'uppercase', letterSpacing: '0.1em',
        borderBottom: `1px solid ${vars.color.borderSubtle}`,
        paddingBottom: 10, marginBottom: 20,
      }}>{title}</h2>
      {children}
    </section>
  )
}

function TokenRow({ name, value, swatch }: { name: string; value: string; swatch?: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '7px 0', borderBottom: `1px solid ${vars.color.borderSubtle}` }}>
      {swatch !== undefined && (
        <div style={{ width: 24, height: 24, borderRadius: 4, background: swatch, border: `1px solid ${vars.color.borderDefault}`, flexShrink: 0 }} />
      )}
      <code style={{ fontSize: 12, color: vars.color.primary, minWidth: 180, fontFamily: 'monospace' }}>{name}</code>
      <code style={{ fontSize: 11, color: vars.color.textSecondary, flex: 1, fontFamily: 'monospace' }}>{value}</code>
    </div>
  )
}

// ── Color tokens ──────────────────────────────────────────────────────────────

const COLOR_TOKENS = [
  { name: 'bgBase', value: '#0a0c10' },
  { name: 'bgSurface', value: '#111318' },
  { name: 'bgElevated', value: '#1e2330' },
  { name: 'bgCard', value: '#161a20' },
  { name: 'bgHover', value: '#1a1f27' },
  { name: 'textPrimary', value: '#f0f4f8' },
  { name: 'textSecondary', value: '#8ba3bc' },
  { name: 'textMuted', value: '#668096' },
  { name: 'primary', value: '#06b6d4' },
  { name: 'primaryLight', value: '#22d3ee' },
  { name: 'primaryDark', value: '#0891b2' },
  { name: 'primaryAlpha', value: 'rgba(6,182,212,0.1)' },
  { name: 'accent', value: '#ea580c' },
  { name: 'accentLight', value: '#f97316' },
  { name: 'success', value: '#10b981' },
  { name: 'warning', value: '#f59e0b' },
  { name: 'danger', value: '#ef4444' },
  { name: 'borderSubtle', value: '#161c24' },
  { name: 'borderDefault', value: '#1e2730' },
  { name: 'borderStrong', value: '#2a3545' },
]

// ── Typography ────────────────────────────────────────────────────────────────

function TypographySection() {
  const sizes = [
    { label: 'Display', style: { fontSize: 32, fontWeight: 700, letterSpacing: '-0.02em' } },
    { label: 'H1', style: { fontSize: 24, fontWeight: 700 } },
    { label: 'H2', style: { fontSize: 20, fontWeight: 700 } },
    { label: 'H3', style: { fontSize: 16, fontWeight: 600 } },
    { label: 'Body', style: { fontSize: 14, fontWeight: 400 } },
    { label: 'Small', style: { fontSize: 12, fontWeight: 400 } },
    { label: 'Caption', style: { fontSize: 11, fontWeight: 400 } },
    { label: 'Label', style: { fontSize: 10, fontWeight: 600, textTransform: 'uppercase' as const, letterSpacing: '0.08em' } },
  ]
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {sizes.map(s => (
        <div key={s.label} style={{ display: 'flex', alignItems: 'baseline', gap: 24, padding: '8px 0', borderBottom: `1px solid ${vars.color.borderSubtle}` }}>
          <code style={{ fontSize: 11, color: vars.color.textMuted, minWidth: 80, fontFamily: 'monospace' }}>{s.label}</code>
          <span style={{ ...s.style, color: vars.color.textPrimary }}>{s.label} — Recognition platform typography</span>
        </div>
      ))}
    </div>
  )
}

// ── Spacing ───────────────────────────────────────────────────────────────────

const SPACING = [
  { token: 'xs', value: '4px' },
  { token: 'sm', value: '8px' },
  { token: 'md', value: '16px' },
  { token: 'lg', value: '24px' },
  { token: 'xl', value: '32px' },
  { token: 'xxl', value: '48px' },
]

function SpacingSection() {
  return (
    <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
      {SPACING.map(s => (
        <div key={s.token} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
          <div style={{ background: vars.color.primary, opacity: 0.7, height: 20, width: s.value, minWidth: 4 }} />
          <code style={{ fontSize: 10, color: vars.color.textMuted, fontFamily: 'monospace' }}>{s.token}</code>
          <span style={{ fontSize: 10, color: vars.color.textSecondary }}>{s.value}</span>
        </div>
      ))}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function DesignSystemPage() {
  const toast = useToast()
  const [inputVal, setInputVal] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)

  return (
    <div style={{ padding: '32px 40px', maxWidth: 900, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: 40 }}>
        <h1 style={{ fontSize: 28, fontWeight: 800, color: vars.color.textPrimary, margin: 0 }}>
          Design System
        </h1>
        <p style={{ color: vars.color.textMuted, fontSize: 14, margin: '8px 0 0' }}>
          Recognition · Logikos — Tokens, primitivos e padrões de composição.
        </p>
      </div>

      {/* Color tokens */}
      <Section title="Color Tokens">
        {COLOR_TOKENS.map(t => (
          <TokenRow key={t.name} name={`vars.color.${t.name}`} value={t.value} swatch={t.value} />
        ))}
      </Section>

      {/* Typography */}
      <Section title="Typography">
        <TypographySection />
      </Section>

      {/* Spacing */}
      <Section title="Spacing">
        <SpacingSection />
      </Section>

      {/* Containers canônicos (WS1) */}
      <Section title="Containers — Panel / PageHeader / Modal / AppDrawer">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <div style={{ border: `1px dashed ${vars.color.borderDefault}`, borderRadius: 8, padding: 16 }}>
            <PageHeader
              title="Título da página"
              subtitle="Subtítulo em textSecondary — substitui H1 hardcoded"
              actions={<Button variant="primary" size="sm">Ação</Button>}
            />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16 }}>
            <Panel variant="surface" title="Panel surface" subtitle="vars.color.bgSurface">
              <span style={{ fontSize: 13, color: vars.color.textSecondary }}>Seção de página padrão.</span>
            </Panel>
            <Panel variant="card" title="Panel card" subtitle="vars.color.bgCard">
              <span style={{ fontSize: 13, color: vars.color.textSecondary }}>Bloco de conteúdo.</span>
            </Panel>
            <Panel variant="elevated" title="Panel elevated" subtitle="vars.color.bgElevated" actions={<Badge variant="primary">ações</Badge>}>
              <span style={{ fontSize: 13, color: vars.color.textSecondary }}>Destaque / composição rica.</span>
            </Panel>
          </div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <Button variant="secondary" onClick={() => setModalOpen(true)}>Abrir Modal</Button>
            <Button variant="secondary" onClick={() => setDrawerOpen(true)}>Abrir AppDrawer</Button>
          </div>
          <Modal
            open={modalOpen}
            onClose={() => setModalOpen(false)}
            title="Modal canônico"
            footer={
              <>
                <Button variant="ghost" onClick={() => setModalOpen(false)}>Cancelar</Button>
                <Button variant="primary" onClick={() => setModalOpen(false)}>Confirmar</Button>
              </>
            }
          >
            <p style={{ fontSize: 13, color: vars.color.textSecondary, margin: 0 }}>
              Único contêiner sobreposto permitido (com AppDrawer). Abre sobre o
              contexto com animação (vars.animation) e overlay tokenizado
              (vars.color.overlay) — VMS §7.
            </p>
          </Modal>
          <AppDrawer isOpen={drawerOpen} onClose={() => setDrawerOpen(false)} title="AppDrawer canônico" size="sm">
            <div style={{ padding: 20, fontSize: 13, color: vars.color.textSecondary }}>
              Gaveta lateral padrão — abre sobre o contexto sem desmontar o que
              roda atrás; fecha com Esc, overlay ou X.
            </div>
          </AppDrawer>
        </div>
      </Section>

      {/* Buttons */}
      <Section title="Button">
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center', marginBottom: 16 }}>
          <Button variant="primary">Primary</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="danger">Danger</Button>
          <Button variant="primary" disabled>Disabled</Button>
        </div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <Button variant="primary" size="sm">Small</Button>
          <Button variant="primary" size="md">Medium</Button>
          <Button variant="primary" size="lg">Large</Button>
        </div>
      </Section>

      {/* Badges */}
      <Section title="Badge">
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <Badge variant="success">success</Badge>
          <Badge variant="warning">warning</Badge>
          <Badge variant="danger">danger</Badge>
          <Badge variant="primary">primary</Badge>
          <Badge variant="neutral">neutral</Badge>
          <Badge variant="accent">accent</Badge>
        </div>
      </Section>

      {/* Inputs */}
      <Section title="Input">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, maxWidth: 360 }}>
          <Input placeholder="Sem label" value={inputVal} onChange={e => setInputVal(e.target.value)} />
          <Field label="Com label">
            <Input placeholder="Digite aqui..." value="" onChange={() => {}} />
          </Field>
          <Field label="Com erro" error="Este campo é obrigatório">
            <Input placeholder="Campo inválido" error="Este campo é obrigatório" value="" onChange={() => {}} />
          </Field>
          <Field label="Desabilitado">
            <Input placeholder="Não editável" value="valor fixo" onChange={() => {}} disabled />
          </Field>
        </div>
      </Section>

      {/* Skeleton */}
      <Section title="Skeleton">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxWidth: 400 }}>
          <Skeleton variant="title" width={200} />
          <Skeleton variant="text" width="80%" />
          <Skeleton variant="text" width="60%" />
          <Skeleton variant="rect" width={120} height={32} />
          <div style={{ display: 'flex', gap: 8 }}>
            <Skeleton variant="rect" width={80} height={80} />
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flex: 1 }}>
              <Skeleton variant="text" width="90%" />
              <Skeleton variant="text" width="70%" />
              <Skeleton variant="text" width="50%" />
            </div>
          </div>
        </div>
      </Section>

      {/* Toast */}
      <Section title="Toast">
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <Button variant="secondary" size="sm" onClick={() => toast.success('Operação concluída com sucesso')}>Success</Button>
          <Button variant="secondary" size="sm" onClick={() => toast.error('Erro ao processar solicitação')}>Error</Button>
          <Button variant="secondary" size="sm" onClick={() => toast.warning('Atenção: limite próximo do limite')}>Warning</Button>
          <Button variant="secondary" size="sm" onClick={() => toast.info('Informação importante disponível')}>Info</Button>
        </div>
      </Section>

      {/* Shadow */}
      <Section title="Shadow">
        <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
          {[
            { label: 'sm', shadow: vars.shadow.sm },
            { label: 'md', shadow: vars.shadow.md },
            { label: 'lg', shadow: vars.shadow.lg },
            { label: 'glow', shadow: vars.shadow.glow },
            { label: 'glowCyan', shadow: vars.shadow.glowCyan },
          ].map(s => (
            <div key={s.label} style={{ width: 100, height: 80, background: vars.color.bgCard, borderRadius: vars.radius.md, boxShadow: s.shadow, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <code style={{ fontSize: 11, color: vars.color.textMuted, fontFamily: 'monospace' }}>{s.label}</code>
            </div>
          ))}
        </div>
      </Section>

      {/* Border radius */}
      <Section title="Border Radius">
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'center' }}>
          {[
            { label: 'sm', value: vars.radius.sm },
            { label: 'md', value: vars.radius.md },
            { label: 'lg', value: vars.radius.lg },
            { label: 'xl', value: vars.radius.xl },
            { label: 'full', value: vars.radius.full },
          ].map(r => (
            <div key={r.label} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
              <div style={{ width: 48, height: 48, background: vars.color.primary, opacity: 0.7, borderRadius: r.value }} />
              <code style={{ fontSize: 10, color: vars.color.textMuted, fontFamily: 'monospace' }}>{r.label}</code>
            </div>
          ))}
        </div>
      </Section>
    </div>
  )
}
