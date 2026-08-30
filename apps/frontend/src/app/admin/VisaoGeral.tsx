/**
 * Visão geral do Admin — `/novo/admin` (índice). Desenho: `Admin
 * Plataforma.dc.html`, seção "Visão geral".
 *
 * DIVERGÊNCIAS do desenho, registradas aqui e no entregável da PR (C-04 — o
 * código vence a prancha):
 *
 *  1. **KPI "Boxes edge"** (nº de Jetsons + disco) NÃO existe no dashboard —
 *     `GET /v1/admin/dashboard` não devolve nada parecido. Substituído por
 *     **Workers**, que é o campo real mais próximo (contagem onpremise /
 *     railway / offline, `routes.py:219-230`).
 *  2. **`cameras_online`, `alerts_24h`, `tickets_open`, `mrr_estimated`** —
 *     o handler devolve estes quatro campos **hardcoded em 0**
 *     (`services/api/app/api/v1/admin/routes.py:246-250`, não é query real).
 *     Mostrar "0" nesses cards seria dado falso com cara de medição — omitidos.
 *  3. **"Saúde por tenant"** (ponto colorido + status por tenant) não tem
 *     fonte no dashboard: não há `status`/`health` por tenant no shape, só
 *     `top_tenants_users` (nome + contagem de usuários). O painel esquerdo
 *     virou **"Tenants por usuários"** com o que existe, sem inventar cor.
 *  4. **"Pendências da plataforma"** — sem endpoint de pendências dedicado.
 *     Usa `recent_critical_events` (audit log: suspensão, rejeição de treino,
 *     reinício de worker, desativação), que é o mais próximo de "coisa que
 *     merece atenção" que o backend realmente guarda.
 *  5. Banner "contexto assumido" não entra aqui — já é `GlobalBanners`
 *     (`App.tsx`, fora das rotas), ver `Admin.tsx`.
 */
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle } from 'lucide-react'

import { adminService } from '../../modules/admin/services/adminService'
import type { AuditEntry } from '../../modules/admin/types/admin'
import { EmptyState } from '../../components/ui/EmptyState/EmptyState'
import { LogikosLoader } from '../shell/LogikosLoader'
import { lk } from '../tokens/lk.css'
import * as s from './VisaoGeral.css'

const numero = (n: number) => n.toLocaleString('pt-BR')

const ROTULO_ACAO: Record<string, string> = {
  suspended: 'Tenant suspenso',
  worker_restart: 'Reinício de worker',
  training_rejected: 'Treino rejeitado',
  deactivated: 'Usuário desativado',
}

function rotuloEvento(e: AuditEntry) {
  return ROTULO_ACAO[e.action] ?? e.action
}

interface KpiProps {
  label: string
  valor: number
  sub: string
  cor: string
}

function Kpi({ label, valor, sub, cor }: KpiProps) {
  return (
    <div className={s.kpiCard} style={{ '--kpi-cor': cor } as React.CSSProperties}>
      <span className={s.kpiLabel}>{label}</span>
      <span className={s.kpiValor}>{numero(valor)}</span>
      <span className={s.kpiSub}>{sub}</span>
    </div>
  )
}

export function VisaoGeral() {
  const consulta = useQuery({
    queryKey: ['admin', 'dashboard'],
    queryFn: () => adminService.getDashboard(),
    staleTime: 30_000,
    refetchInterval: 60_000,
  })

  if (consulta.isPending) {
    return <LogikosLoader estado="waiting" variante="tile" rotulo="CARREGANDO VISÃO GERAL" />
  }

  if (consulta.isError) {
    return (
      <div className={s.centro}>
        <AlertTriangle size={36} strokeWidth={1.5} color={lk.estado.nc} aria-hidden="true" />
        <span className={s.centroTitulo}>Não foi possível carregar a visão geral</span>
        <span className={s.centroTecnico}>GET /v1/admin/dashboard</span>
        <button
          type="button"
          className={s.botaoRetry}
          onClick={() => void consulta.refetch()}
        >
          Tentar novamente
        </button>
      </div>
    )
  }

  const d = consulta.data

  if (d.tenants_active === 0 && d.users_total === 0) {
    return (
      <EmptyState
        title="Nenhum tenant cadastrado ainda"
        description="A plataforma ainda não tem tenants nem usuários. Crie o primeiro tenant para a visão geral ganhar dado."
      />
    )
  }

  const { workers } = d
  const corWorkers = workers.offline > 0 ? lk.estado.nc : workers.fallback > 0 ? lk.estado.atencao : lk.estado.ok
  const subWorkers =
    workers.fallback === 0 && workers.offline === 0
      ? 'todos on-premise'
      : `${numero(workers.fallback)} fallback · ${numero(workers.offline)} offline`

  return (
    <div className={s.raiz}>
      <h1 className={s.titulo}>Visão geral</h1>

      <div className={s.kpiGrid}>
        <Kpi label="Tenants ativos" valor={d.tenants_active} sub="ativos agora" cor={lk.cor.cinzaNevoa} />
        <Kpi label="Usuários" valor={d.users_total} sub="cadastrados" cor={lk.cor.cinzaNevoa} />
        <Kpi
          label="Aprovações pendentes"
          valor={d.training_approvals_pending}
          sub="treino aguardando aprovação"
          cor={d.training_approvals_pending > 0 ? lk.estado.atencao : lk.estado.ok}
        />
        <Kpi label="Workers" valor={workers.online} sub={subWorkers} cor={corWorkers} />
      </div>

      <div className={s.painelGrid}>
        <div className={s.painel}>
          <span className={s.painelTitulo}>Tenants por usuários</span>
          {d.top_tenants_users.length === 0 ? (
            <span className={s.painelVazio}>Nenhum tenant ativo ainda.</span>
          ) : (
            d.top_tenants_users.map((t) => (
              <div key={t.tenant_name} className={s.linha}>
                <span className={s.linhaNome}>{t.tenant_name}</span>
                <span className={s.linhaValor}>{numero(t.user_count)} usuário{t.user_count !== 1 ? 's' : ''}</span>
              </div>
            ))
          )}
        </div>

        <div className={s.painel}>
          <span className={s.painelTitulo}>Eventos críticos recentes</span>
          {d.recent_critical_events.length === 0 ? (
            <span className={s.painelVazio}>Nenhum evento crítico recente.</span>
          ) : (
            d.recent_critical_events.map((e) => (
              <div key={e.id} className={s.linha}>
                <AlertTriangle size={14} strokeWidth={1.8} color={lk.estado.atencao} aria-hidden="true" />
                <span className={s.linhaNome}>
                  {rotuloEvento(e)} · {e.tenant_name ?? 'sem tenant'}
                </span>
                <span className={s.linhaValor}>{new Date(e.created_at).toLocaleString('pt-BR')}</span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
