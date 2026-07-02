/**
 * AdminIntegrationsPage — Integrações self-service (superadmin only).
 *
 * Formulário extraído para IntegrationsPanel (WS6) — reutilizado na aba
 * "Armazenamento & Integrações" do AdminTenantDetailPage com tenantId.
 * Aqui, SEM tenantId → tenant do JWT (comportamento original preservado).
 */
import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../../hooks/useAuth'
import { IntegrationsPanel } from '../components/IntegrationsPanel'
import { vars } from '../../../styles/theme.css'

export function AdminIntegrationsPage() {
  const { isSuperAdmin } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    if (!isSuperAdmin) {
      navigate('/admin', { replace: true })
    }
  }, [isSuperAdmin]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!isSuperAdmin) return null

  return (
    <div style={styles.root}>
      <h1 style={styles.title}>Integrações</h1>
      <p style={styles.subtitle}>
        Credenciais armazenadas cifradas (Fernet). O plaintext nunca é exibido.
      </p>
      <IntegrationsPanel />
    </div>
  )
}

const styles = {
  root: {
    padding: '24px 32px',
    maxWidth: 900,
  } satisfies React.CSSProperties,
  title: {
    fontSize: 24,
    fontWeight: 700,
    marginBottom: 6,
  } satisfies React.CSSProperties,
  subtitle: {
    color: vars.color.textSecondary,
    fontSize: 14,
    marginBottom: 28,
  } satisfies React.CSSProperties,
}
