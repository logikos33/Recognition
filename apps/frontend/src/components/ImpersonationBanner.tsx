/**
 * Banner global de impersonation "ver como" (WS6).
 *
 * Renderizado em App.tsx FORA das rotas — visível em TODAS as telas enquanto
 * o superadmin estiver vendo a plataforma como outro usuário. Saída em 1
 * clique. Também exibe o toast de "visualização encerrada" quando o token
 * expira (flag gravada pelo branch 401 de services/api.ts).
 */
import { useEffect, useState } from 'react'
import { Eye } from 'lucide-react'
import { Banner } from './ui/Banner/Banner'
import { Button } from './ui/Button/Button'
import { useToast } from './ui/Toast/useToast'
import { IMPERSONATION_EXPIRED_FLAG } from '../services/api'
import {
  getImpersonationMeta,
  isImpersonating,
  stopImpersonation,
} from '../services/impersonation'

export function ImpersonationBanner() {
  const toast = useToast()
  const [leaving, setLeaving] = useState(false)
  const meta = getImpersonationMeta()
  const active = isImpersonating() && meta !== null

  useEffect(() => {
    if (sessionStorage.getItem(IMPERSONATION_EXPIRED_FLAG)) {
      sessionStorage.removeItem(IMPERSONATION_EXPIRED_FLAG)
      toast.info(
        'Visualização encerrada',
        'O token de visualização expirou — sua sessão de superadmin foi restaurada.',
      )
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (!active) return null

  const handleStop = async () => {
    setLeaving(true)
    try {
      await stopImpersonation()
    } catch {
      toast.error('Erro ao sair da visualização', 'Tente novamente.')
      setLeaving(false)
    }
  }

  const displayName = meta.target_name || meta.target_email

  return (
    <Banner variant="warning" icon={<Eye size={16} aria-hidden="true" />}>
      <span
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          minWidth: 0,
        }}
      >
        <span
          style={{
            flex: '1 1 auto',
            minWidth: 0,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
          title={`${displayName} (${meta.target_email})`}
        >
          Você está vendo como <strong>{displayName}</strong> ({meta.target_email})
        </span>
        <span style={{ flexShrink: 0 }}>
          <Button size="sm" variant="secondary" loading={leaving} onClick={handleStop}>
            Sair da visualização
          </Button>
        </span>
      </span>
    </Banner>
  )
}
