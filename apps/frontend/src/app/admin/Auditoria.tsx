/**
 * Auditoria — `/novo/admin/auditoria` (F5 SR2 PR-3). Desenho: `Admin
 * Plataforma.dc.html`, seção "Auditoria".
 *
 * PARIDADE FUNCIONAL com `modules/admin/pages/AdminAuditLogPage.tsx` (porte
 * de COMPORTAMENTO, não de markup — mesmo raciocínio de `estudio/Classes.tsx`):
 * mesmo endpoint, mesmo service, sem `raw fetch`. O legado já usa
 * `adminService.getAuditLog`/`exportAuditLog` (o "usa RAW FETCH" do wiring
 * spec é achado histórico da leva antiga — código atual já foi corrigido,
 * C-04 manda o código vencer o documento).
 *
 * MEDIÇÃO DO BACKEND (`services/api/app/api/v1/admin/routes.py`):
 *
 *  - `GET /v1/admin/audit-log` (linha 2202) aceita `tenant_id`, `actor_id`,
 *    `action`, `target_type`, `date_from`, `date_to`, `page` — devolve
 *    `{items, total}`. O filtro de período do desenho ("Últimas 24h"/"7
 *    dias") vira `date_from` calculado no cliente.
 *  - `GET /v1/admin/audit-log/export` (linha 2264) é CSV; o wrapper
 *    `adminService.exportAuditLog` só encaminha `tenant_id`/`action` — SEM
 *    `date_from`/`date_to`, mesmo o backend aceitando. Não dá para estender
 *    o wrapper aqui (`modules/**` é intocável nesta pista); então o export
 *    hoje sai do período selecionado na tela: sempre as últimas 10 mil
 *    linhas. Divergência assumida, não fabricação de filtro.
 *  - Sem enum de "tipo" no backend (`action` é texto livre) — a cor do pill
 *    é heurística por palavra-chave (`corTipo`), não um campo real.
 */
import { useState } from 'react'
import { AlertTriangle, Download } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'

import { EmptyState } from '../../components/ui/EmptyState/EmptyState'
import { adminService } from '../../modules/admin/services/adminService'
import type { AuditEntry } from '../../modules/admin/types/admin'
import { LogikosLoader } from '../shell/LogikosLoader'
import { lk } from '../tokens/lk.css'
import * as s from './Auditoria.css'

const PER_PAGE = 20

const PERIODOS = [
  { valor: '24h', rotulo: 'Últimas 24h', horas: 24 },
  { valor: '7d', rotulo: '7 dias', horas: 24 * 7 },
] as const

type PeriodoValor = (typeof PERIODOS)[number]['valor']

function dateFromPeriodo(valor: PeriodoValor): string {
  const horas = PERIODOS.find((p) => p.valor === valor)?.horas ?? 24
  return new Date(Date.now() - horas * 3600_000).toISOString()
}

/** Heurística por palavra-chave — `action` é texto livre, o backend não tem
 * taxonomia de tipo. Vermelho para ações destrutivas, verde para positivas,
 * âmbar para o resto (reset, restart, update...). */
function corTipo(action: string): string {
  const a = action.toLowerCase()
  if (/delet|revok|suspend|reject|deactivat|remov/.test(a)) return lk.estado.nc
  if (/creat|activat|approv|restor|login/.test(a)) return lk.estado.ok
  return lk.estado.atencao
}

function detalheDe(e: AuditEntry): string {
  const alvo = e.target_type + (e.target_id ? ` #${e.target_id.slice(0, 8)}` : '')
  return e.tenant_name ? `${alvo} · ${e.tenant_name}` : alvo
}

export function Auditoria() {
  const [periodo, setPeriodo] = useState<PeriodoValor>('24h')
  const [page, setPage] = useState(1)
  const [exportando, setExportando] = useState(false)

  const consulta = useQuery({
    queryKey: ['admin', 'audit-log', periodo, page],
    queryFn: () => adminService.getAuditLog({ date_from: dateFromPeriodo(periodo), page }),
    staleTime: 15_000,
  })

  const exportarCsv = async () => {
    setExportando(true)
    try {
      const blob = await adminService.exportAuditLog({})
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `audit-log-${new Date().toISOString().slice(0, 10)}.csv`
      a.click()
      URL.revokeObjectURL(url)
    } finally {
      setExportando(false)
    }
  }

  const cabecalho = (
    <div className={s.cabecalho}>
      <h1 className={s.titulo}>Auditoria</h1>
      <div style={{ flex: 1 }} />
      <select
        className={s.seletorPeriodo}
        value={periodo}
        onChange={(e) => {
          setPeriodo(e.target.value as PeriodoValor)
          setPage(1)
        }}
        aria-label="Período"
      >
        {PERIODOS.map((p) => (
          <option key={p.valor} value={p.valor}>{p.rotulo}</option>
        ))}
      </select>
      <button type="button" className={s.botaoExportar} onClick={() => void exportarCsv()} disabled={exportando}>
        <Download size={14} strokeWidth={1.8} aria-hidden="true" />
        {exportando ? 'Exportando...' : 'Exportar CSV'}
      </button>
    </div>
  )

  if (consulta.isPending) {
    return (
      <div className={s.raiz}>
        {cabecalho}
        <LogikosLoader estado="waiting" variante="tile" rotulo="CARREGANDO AUDITORIA" />
      </div>
    )
  }

  if (consulta.isError) {
    return (
      <div className={s.raiz}>
        {cabecalho}
        <div className={s.centro}>
          <AlertTriangle size={36} strokeWidth={1.5} color={lk.estado.nc} aria-hidden="true" />
          <span className={s.centroTitulo}>Não foi possível carregar a auditoria</span>
          <span className={s.centroTecnico}>GET /v1/admin/audit-log</span>
          <button type="button" className={s.botaoRetry} onClick={() => void consulta.refetch()}>
            Tentar novamente
          </button>
        </div>
      </div>
    )
  }

  const { items, total } = consulta.data
  const totalPaginas = Math.max(1, Math.ceil(total / PER_PAGE))

  return (
    <div className={s.raiz}>
      {cabecalho}

      {items.length === 0 ? (
        <EmptyState
          title="Nenhum registro"
          description="Nenhuma ação de auditoria no período selecionado."
        />
      ) : (
        <div className={s.lista}>
          {items.map((e) => (
            <div key={e.id} className={s.linha}>
              <span className={s.quando}>{new Date(e.created_at).toLocaleString('pt-BR')}</span>
              <span className={s.quem}>{e.actor_email ?? e.actor_role}</span>
              <span className={s.tipo} style={{ '--tipo-cor': corTipo(e.action) } as React.CSSProperties}>
                {e.action}
              </span>
              <span className={s.detalhe}>{detalheDe(e)}</span>
            </div>
          ))}
        </div>
      )}

      {totalPaginas > 1 && (
        <div className={s.paginacao}>
          <button
            type="button"
            className={s.botaoPaginacao}
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            Anterior
          </button>
          <span className={s.paginaAtual}>Pág {page} de {totalPaginas}</span>
          <button
            type="button"
            className={s.botaoPaginacao}
            disabled={page >= totalPaginas}
            onClick={() => setPage((p) => p + 1)}
          >
            Próxima
          </button>
        </div>
      )}
    </div>
  )
}
