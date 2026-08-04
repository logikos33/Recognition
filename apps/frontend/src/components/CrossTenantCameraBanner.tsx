/**
 * Banner "assumir contexto" — grade de monitoramento.
 *
 * GET /cameras/{id}/stream/info aplica C-01 (câmera precisa ser do tenant do
 * token): câmera de outro tenant vira 404, indistinguível de câmera offline
 * pro usuário. Quando o CameraCell confirma (via /v1/admin/inventory) que
 * uma câmera 404 é de outro tenant — cenário do superadmin DEV navegando com
 * o próprio token — este banner aparece com um atalho de 1 clique pra
 * "assumir contexto" daquele tenant, em vez de deixar o grid parecendo
 * quebrado. Some sozinho assim que o superadmin entra em contexto (reload
 * troca de tela) ou não sobra nenhuma câmera cross-tenant reportada.
 *
 * D-48 (opção B): quando TODAS as câmeras cross-tenant da grade são de UM
 * único tenant, useAutoAssumeTenantContext assume aquele contexto sozinho —
 * este banner vira o fallback visível (2+ tenants, ou o auto-assume ainda
 * não disparou/falhou dentro da janela de debounce).
 *
 * Ver services/crossTenantCameras.ts (store) e services/tenantContext.ts
 * (assumeTenantContext, mesmo mecanismo do TenantContextBanner).
 */
import { useState } from 'react'
import { Building2 } from 'lucide-react'
import { Banner } from './ui/Banner/Banner'
import { Button } from './ui/Button/Button'
import { useToast } from './ui/Toast/useToast'
import { useAuth } from '../hooks/useAuth'
import { useAutoAssumeTenantContext } from '../hooks/useAutoAssumeTenantContext'
import { assumeTenantContext, isInTenantContext } from '../services/tenantContext'
import { useCrossTenantCamerasStore } from '../services/crossTenantCameras'

export function CrossTenantCameraBanner() {
  const { isSuperAdmin } = useAuth()
  const toast = useToast()
  const tenants = useCrossTenantCamerasStore((s) => s.tenants)
  const [assumingId, setAssumingId] = useState<string | null>(null)

  // D-48: tenta assumir sozinho quando a grade só tem câmeras de UM tenant
  // estrangeiro. Chamado incondicionalmente (regra dos hooks) — o próprio
  // hook decide se dispara ou não.
  useAutoAssumeTenantContext()

  // Só faz sentido para o superadmin navegando com o próprio token — quem já
  // assumiu contexto está "dentro" de um tenant e não veria câmeras de outro.
  if (!isSuperAdmin || isInTenantContext() || tenants.length === 0) return null

  const handleAssume = async (tenantId: string) => {
    setAssumingId(tenantId)
    try {
      await assumeTenantContext(tenantId) // recarrega a página em caso de sucesso
    } catch (err) {
      setAssumingId(null)
      toast.error('Erro ao assumir contexto', err instanceof Error ? err.message : undefined)
    }
  }

  const single = tenants.length === 1 ? tenants[0] : null

  return (
    <div style={{ position: 'sticky', top: 0, zIndex: 1500 }}>
      <Banner variant="warning" icon={<Building2 size={16} aria-hidden="true" />}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <span>
            {single ? (
              <>
                Estas câmeras pertencem a <strong>{single.tenantName}</strong>. Assumir o
                contexto para visualizar?
              </>
            ) : (
              <>Há câmeras de {tenants.length} tenants diferentes nesta grade.</>
            )}
          </span>
          {tenants.map((t) => (
            <Button
              key={t.tenantId}
              size="sm"
              variant="secondary"
              loading={assumingId === t.tenantId}
              disabled={assumingId !== null && assumingId !== t.tenantId}
              onClick={() => void handleAssume(t.tenantId)}
            >
              {single ? 'Assumir contexto' : `Assumir contexto de ${t.tenantName}`}
            </Button>
          ))}
        </span>
      </Banner>
    </div>
  )
}
