/**
 * EpiSitesPage — task-093 (ADR-0046): admin do tenant troca o deployment_mode
 * de um site edge pela UI, sem deploy/env var.
 *
 * Consome GET/PATCH /api/v1/edge/sites (já existentes desde task-003/017),
 * já role-gated no backend (has_permission('edge:manage') === admin ou
 * superadmin) e já tenant-scoped (cross-tenant → 404, C-01). O gate de role
 * aqui é defesa em profundidade — o backend é a fonte de verdade.
 *
 * Rota: /epi/sites, alcançada via AppRoutes.SitesHealthRedirect quando o
 * usuário é admin (não superadmin — esses continuam indo para a visão de
 * frota cross-tenant em /admin/observability?tab=edge).
 *
 * Nomenclatura (ADR-0046 vs schema real): o ADR fala em rótulos de produto
 * edge/dual/cloud_only; o valor persistido em public.edge_sites.deployment_mode
 * (migration 065, CHECK) continua sendo cloud/edge/hybrid. O mapeamento
 * rótulo↔valor é só de apresentação — DEPLOYMENT_MODE_LABELS em types/edge.ts.
 * Nenhum valor novo é persistido; não há migration nesta task.
 */
import { useCallback, useEffect, useState } from 'react'
import { Server } from 'lucide-react'
import { useAuth } from '../../hooks/useAuth'
import { useToast } from '../../components/ui/Toast/useToast'
import { edgeService } from '../../services/edgeService'
import { PageHeader } from '../../components/ui/PageHeader/PageHeader'
import { Badge, statusToBadgeVariant } from '../../components/ui/Badge/Badge'
import { EmptyState } from '../../components/ui/EmptyState/EmptyState'
import { Skeleton } from '../../components/ui/Skeleton/Skeleton'
import type { DeploymentMode, EdgeSite } from '../../types/edge'
import { DEPLOYMENT_MODE_LABELS } from '../../types/edge'
import { page, list, row, rowInfo, rowName, rowMeta, rowActions, modeSelect } from './EpiSitesPage.css'
import { vars } from '../../styles/theme.css'

const DEPLOYMENT_MODE_OPTIONS: DeploymentMode[] = ['edge', 'hybrid', 'cloud']

export function EpiSitesPage() {
  const { isAdmin } = useAuth()
  const toast = useToast()
  const [sites, setSites] = useState<EdgeSite[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [savingSiteId, setSavingSiteId] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!isAdmin) {
      setLoading(false)
      return
    }
    setLoading(true)
    setLoadError(null)
    try {
      const result = await edgeService.listSites()
      setSites(result)
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : 'Erro ao carregar sites')
    } finally {
      setLoading(false)
    }
  }, [isAdmin])

  useEffect(() => { load() }, [load])

  const handleModeChange = async (site: EdgeSite, next: DeploymentMode) => {
    if (!isAdmin || next === site.deployment_mode) return // defesa em profundidade
    const previous = sites
    setSavingSiteId(site.id)
    setSites(prev => prev.map(s => (s.id === site.id ? { ...s, deployment_mode: next } : s)))
    try {
      const updated = await edgeService.updateSite(site.id, { deployment_mode: next })
      setSites(prev => prev.map(s => (s.id === site.id ? updated : s)))
      toast.success(`Modo de deployment atualizado para ${DEPLOYMENT_MODE_LABELS[next]}`)
    } catch (err) {
      setSites(previous)
      toast.error(err instanceof Error ? err.message : 'Erro ao atualizar modo de deployment')
    } finally {
      setSavingSiteId(null)
    }
  }

  if (!isAdmin) {
    return (
      <div className={page}>
        <PageHeader title="Sites" subtitle="Sites edge do seu tenant" />
        <EmptyState
          icon={<Server size={28} />}
          title="Acesso restrito"
          description="Só administradores do tenant podem ver e configurar sites edge."
        />
      </div>
    )
  }

  return (
    <div className={page}>
      <PageHeader
        title="Sites"
        subtitle="Modo de deployment por site — edge, dual (edge + cloud) ou cloud-only (ADR-0046)"
      />

      {loading ? (
        <div className={list}>
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} variant="rect" height={64} />
          ))}
        </div>
      ) : loadError ? (
        <EmptyState
          icon={<Server size={28} />}
          title="Erro ao carregar sites"
          description={loadError}
        />
      ) : sites.length === 0 ? (
        <EmptyState
          icon={<Server size={28} />}
          title="Nenhum site cadastrado"
          description="Sites edge são criados durante o provisionamento (enrollment)."
        />
      ) : (
        <div className={list}>
          {sites.map(site => (
            <div key={site.id} className={row}>
              <div className={rowInfo}>
                <span className={rowName}>{site.name}</span>
                <span className={rowMeta}>
                  {site.location && <span>{site.location}</span>}
                  <Badge variant={statusToBadgeVariant(site.status)}>{site.status}</Badge>
                </span>
              </div>
              <div className={rowActions}>
                {savingSiteId === site.id && (
                  <span style={{ fontSize: 12, color: vars.color.textMuted }}>salvando...</span>
                )}
                <select
                  className={modeSelect}
                  value={site.deployment_mode}
                  disabled={savingSiteId !== null}
                  onChange={e => handleModeChange(site, e.target.value as DeploymentMode)}
                  aria-label={`Modo de deployment do site ${site.name}`}
                  style={{ opacity: savingSiteId !== null ? 0.6 : 1 }}
                >
                  {DEPLOYMENT_MODE_OPTIONS.map(mode => (
                    <option key={mode} value={mode}>{DEPLOYMENT_MODE_LABELS[mode]}</option>
                  ))}
                </select>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
