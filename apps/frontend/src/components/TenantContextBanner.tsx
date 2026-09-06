/**
 * Banner global de contexto de tenant assumido.
 *
 * Renderizado em App.tsx FORA das rotas — visível em TODAS as telas enquanto
 * o superadmin estiver navegando "dentro" de um tenant específico. Saída em
 * 1 clique.
 *
 * Também cobre a EXPIRAÇÃO (TTL 30min, core/tenant_context.py): quando o
 * branch 401 de services/api.ts restaura o superadmin automaticamente, este
 * componente troca pro estado "contexto expirou" — não é só um toast que
 * passa despercebido, é um banner persistente com "Reassumir" (mesmo
 * tenant_id, novo /assume) até o usuário dispensar ou reassumir. Nunca
 * derruba pro login enquanto houver esse caminho — só o token restaurado
 * (o do superadmin) expirando de novo é que cai no logout normal.
 *
 * Deliberadamente MAIS chamativo que o ImpersonationBanner (variant
 * "danger" em vez de "warning") — item explícito do desenho: não pode ser
 * sutil, é acesso a dado pessoal de cliente sob impersonation.
 *
 * D-48 (opção C): também dono do agendamento de renovação proativa do
 * contexto — é o único ponto montado globalmente (App.tsx) durante toda a
 * sessão autenticada, então liga/desliga scheduleTenantContextRenewal
 * conforme `active` muda (assumiu → agenda; saiu/expirou → cancela).
 */
import { useEffect, useState } from 'react'
import { Building2 } from 'lucide-react'
import { Banner } from './ui/Banner/Banner'
import { Button } from './ui/Button/Button'
import { useToast } from './ui/Toast/useToast'
import { TENANT_CONTEXT_EXPIRED_FLAG, TENANT_CONTEXT_EXPIRED_META_KEY } from '../services/api'
import {
  assumeTenantContext,
  cancelTenantContextRenewal,
  exitTenantContext,
  getTenantContextMeta,
  isInTenantContext,
  scheduleTenantContextRenewal,
  type TenantContextMeta,
} from '../services/tenantContext'

export function TenantContextBanner() {
  const toast = useToast()
  const [leaving, setLeaving] = useState(false)
  const [reassuming, setReassuming] = useState(false)
  const [expiredMeta, setExpiredMeta] = useState<TenantContextMeta | null>(null)
  const meta = getTenantContextMeta()
  const active = isInTenantContext() && meta !== null

  useEffect(() => {
    // Nunca agenda renovação fora de um contexto ativo — scheduleTenantContextRenewal
    // já checa isInTenantContext() internamente, mas o cancel no `else` evita
    // deixar um timer órfão de uma sessão anterior enquanto `active` for false.
    if (active) {
      scheduleTenantContextRenewal()
    } else {
      cancelTenantContextRenewal()
    }
    return () => cancelTenantContextRenewal()
  }, [active])

  useEffect(() => {
    if (!sessionStorage.getItem(TENANT_CONTEXT_EXPIRED_FLAG)) return
    sessionStorage.removeItem(TENANT_CONTEXT_EXPIRED_FLAG)
    const rawMeta = sessionStorage.getItem(TENANT_CONTEXT_EXPIRED_META_KEY)
    sessionStorage.removeItem(TENANT_CONTEXT_EXPIRED_META_KEY)
    let parsed: TenantContextMeta | null = null
    try {
      parsed = rawMeta ? (JSON.parse(rawMeta) as TenantContextMeta) : null
    } catch {
      parsed = null
    }
    setExpiredMeta(parsed)
    toast.info(
      'Contexto encerrado',
      parsed
        ? `O contexto de ${parsed.tenant_name} expirou — sua sessão de superadmin foi restaurada.`
        : 'O token de contexto assumido expirou — sua sessão de superadmin foi restaurada.',
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleReassume = async () => {
    if (!expiredMeta) return
    setReassuming(true)
    try {
      // Destino explícito = a tela corrente. Este banner aparece em QUALQUER
      // tela (GlobalBanners, fora das rotas); reassumir o contexto não é razão
      // para tirar a pessoa de onde ela está. (#760: sem 2º argumento ia para
      // o default `'/'`, que logado entregava o front ANTIGO.)
      await assumeTenantContext(
        expiredMeta.tenant_id,
        window.location.pathname + window.location.search,
      ) // recarrega em caso de sucesso
    } catch (err) {
      setReassuming(false)
      toast.error('Erro ao reassumir contexto', err instanceof Error ? err.message : undefined)
    }
  }

  if (!active && !expiredMeta) return null

  const handleExit = () => {
    setLeaving(true)
    exitTenantContext()
  }

  // Contexto expirou (401 restaurou o superadmin) e ainda não foi dispensado
  // nem reassumido — não é o mesmo banner de "contexto ativo" abaixo.
  if (!active && expiredMeta) {
    return (
      <Banner
        variant="warning"
        icon={<Building2 size={16} aria-hidden="true" />}
        onDismiss={() => setExpiredMeta(null)}
      >
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
            title={expiredMeta.tenant_name}
          >
            O contexto de <strong>{expiredMeta.tenant_name}</strong> expirou.
          </span>
          <span style={{ flexShrink: 0 }}>
            <Button size="sm" variant="secondary" loading={reassuming} onClick={() => void handleReassume()}>
              Reassumir
            </Button>
          </span>
        </span>
      </Banner>
    )
  }

  if (!meta) return null

  return (
    <Banner variant="danger" icon={<Building2 size={16} aria-hidden="true" />}>
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
          title={`${meta.tenant_name} (${meta.tenant_slug})`}
        >
          Você está vendo como <strong>{meta.tenant_name}</strong> ({meta.tenant_slug})
        </span>
        <span style={{ flexShrink: 0 }}>
          <Button size="sm" variant="secondary" loading={leaving} onClick={handleExit}>
            Sair do contexto
          </Button>
        </span>
      </span>
    </Banner>
  )
}
