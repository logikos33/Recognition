/**
 * Banner global de contexto de tenant assumido.
 *
 * Renderizado em App.tsx FORA das rotas — visível em TODAS as telas enquanto
 * o superadmin estiver navegando "dentro" de um tenant específico. Saída em
 * 1 clique. Também exibe o toast de "contexto encerrado" quando o token
 * expira (flag gravada pelo branch 401 de services/api.ts).
 *
 * Deliberadamente MAIS chamativo que o ImpersonationBanner (variant
 * "danger" em vez de "warning") — item explícito do desenho: não pode ser
 * sutil, é acesso a dado pessoal de cliente sob impersonation.
 */
import { useEffect, useState } from 'react'
import { Building2 } from 'lucide-react'
import { Banner } from './ui/Banner/Banner'
import { Button } from './ui/Button/Button'
import { useToast } from './ui/Toast/useToast'
import { TENANT_CONTEXT_EXPIRED_FLAG } from '../services/api'
import {
  exitTenantContext,
  getTenantContextMeta,
  isInTenantContext,
} from '../services/tenantContext'

export function TenantContextBanner() {
  const toast = useToast()
  const [leaving, setLeaving] = useState(false)
  const meta = getTenantContextMeta()
  const active = isInTenantContext() && meta !== null

  useEffect(() => {
    if (sessionStorage.getItem(TENANT_CONTEXT_EXPIRED_FLAG)) {
      sessionStorage.removeItem(TENANT_CONTEXT_EXPIRED_FLAG)
      toast.info(
        'Contexto encerrado',
        'O token de contexto assumido expirou — sua sessão de superadmin foi restaurada.',
      )
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (!active) return null

  const handleExit = () => {
    setLeaving(true)
    exitTenantContext()
  }

  return (
    <div style={{ position: 'sticky', top: 0, zIndex: 2001 }}>
      <Banner variant="danger" icon={<Building2 size={16} aria-hidden="true" />}>
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 12,
            flexWrap: 'wrap',
          }}
        >
          <span>
            Você está vendo como <strong>{meta.tenant_name}</strong> ({meta.tenant_slug})
          </span>
          <Button size="sm" variant="secondary" loading={leaving} onClick={handleExit}>
            Sair do contexto
          </Button>
        </span>
      </Banner>
    </div>
  )
}
