/**
 * Tenants — `/novo/admin/tenants`. Desenho: `Admin Plataforma.dc.html`, seção
 * "Tenants". Paridade funcional: `AdminTenantsPage.tsx` (lido função a
 * função), reimplementado no vocabulário lk (zero import de `styles/theme.css`
 * — dois sistemas visuais coexistindo na mesma tela seria pior que nenhum).
 *
 * DIVERGÊNCIAS do desenho / do antigo, registradas aqui (C-04 — o código
 * vence a prancha):
 *
 *  1. **Coluna "Câmeras"** do desenho NÃO existe nesta lista: `GET
 *     /v1/admin/tenants` (`routes.py:263-291`) devolve só
 *     `id,slug,name,plan,schema_name,is_active,modules_enabled,created_at,
 *     suspended_at,user_count` — sem contagem de câmeras. Buscar isso exigiria
 *     N+1 chamadas a `/tenants/<id>/overview` por linha só para preencher uma
 *     coluna da lista; a contagem real (via overview) já aparece no Detalhe,
 *     que busca UM tenant só. `AdminTenantsPage.tsx` (antigo) também nunca
 *     teve essa coluna — o desenho pediu dado que a lista não tem.
 *  2. **Coluna "Worker"** do antigo foi OMITIDA aqui — o item da missão pediu
 *     nome/módulos/câmeras/usuários/status/ação; worker não estava na lista
 *     pedida e mantém a tabela no formato do desenho.
 *  3. **Criação de tenant**: NÃO é multi-etapa no antigo (`AdminTenantsPage`
 *     usa um único modal: nome, slug, plano, módulos) — por isso o botão
 *     "Novo tenant" abre um modal PRÓPRIO aqui, em vez de linkar para a tela
 *     antiga. `POST /v1/admin/tenants` devolve `admin_email` + `temp_password`
 *     (`routes.py:349-360`) — o antigo mostrava isso num `alert()`; aqui vira
 *     o mesmo padrão "exibe uma vez com copiar" usado no reset de senha de
 *     Usuários, por honestidade (não é recuperável depois).
 */
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Building2, Check, Copy, HelpCircle } from 'lucide-react'

import { adminService } from '../../modules/admin/services/adminService'
import type { ModuleCatalogEntry, Tenant, TenantPlan } from '../../modules/admin/types/admin'
import { assumeTenantContext, listAvailableTenants } from '../../services/tenantContext'
import { EmptyState } from '../../components/ui/EmptyState/EmptyState'
import { useToast } from '../../components/ui/Toast/useToast'
import { LogikosLoader } from '../shell/LogikosLoader'
import { lk } from '../tokens/lk.css'
import { rotaNova } from '../RotasNovas'
import * as s from './Tenants.css'

const PLANOS: TenantPlan[] = ['basic', 'standard', 'premium', 'enterprise']

const CATALOGO_FALLBACK: ModuleCatalogEntry[] = ['epi', 'quality', 'counting', 'basic'].map((code) => ({
  code,
  label: code,
  description: '',
  status: 'active' as const,
}))

const numero = (n: number) => n.toLocaleString('pt-BR')

function ModalNovoTenant({ onClose, onCriado }: { onClose: () => void; onCriado: () => void }) {
  const toast = useToast()
  const catalogo = useQuery({
    queryKey: ['admin', 'modules-catalog'],
    queryFn: () => adminService.getModulesCatalog(),
    staleTime: 5 * 60_000,
  })
  const [nome, setNome] = useState('')
  const [slug, setSlug] = useState('')
  const [plano, setPlano] = useState<TenantPlan>('standard')
  const [modulos, setModulos] = useState<string[]>(['epi', 'basic'])
  const [salvando, setSalvando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [criado, setCriado] = useState<{ admin_email: string; temp_password: string } | null>(null)
  const [copiado, setCopiado] = useState(false)

  const lista = catalogo.data ?? CATALOGO_FALLBACK

  const toggleModulo = (code: string) =>
    setModulos((m) => (m.includes(code) ? m.filter((x) => x !== code) : [...m, code]))

  const criar = async () => {
    setSalvando(true)
    setErro(null)
    try {
      const res = await adminService.createTenant({ name: nome, slug, plan: plano, modules_enabled: modulos })
      setCriado({ admin_email: res.admin_email, temp_password: res.temp_password })
      onCriado()
    } catch (e: unknown) {
      setErro(e instanceof Error ? e.message : 'Erro ao criar tenant')
    } finally {
      setSalvando(false)
    }
  }

  const copiar = async () => {
    if (!criado) return
    try {
      await navigator.clipboard.writeText(criado.temp_password)
      setCopiado(true)
      toast.success('Copiado', 'Senha temporária copiada.')
    } catch {
      toast.error('Não foi possível copiar', 'Copie manualmente o valor exibido.')
    }
  }

  return (
    <div className={s.overlay} role="dialog" aria-modal="true" aria-label="Novo tenant">
      <div className={s.modal}>
        {criado ? (
          <>
            <span className={s.modalTitulo}>Tenant criado</span>
            <span className={s.campoLabel}>
              Guarde a senha agora — ela só é exibida esta vez.
            </span>
            <div className={s.credenciais}>
              <div className={s.credenciaisLinha}>
                <span className={s.campoLabel}>Admin</span>
                <span className={s.credenciaisCodigo}>{criado.admin_email}</span>
              </div>
              <div className={s.credenciaisLinha}>
                <span className={s.campoLabel}>Senha temp.</span>
                <span className={s.credenciaisCodigo}>{criado.temp_password}</span>
                <button type="button" className={s.botaoSecundario} onClick={() => void copiar()}>
                  {copiado ? <Check size={13} /> : <Copy size={13} />} {copiado ? 'Copiado' : 'Copiar'}
                </button>
              </div>
            </div>
            <div className={s.acoesModal}>
              <button type="button" className={s.botaoPrimario} onClick={onClose}>Fechar</button>
            </div>
          </>
        ) : (
          <>
            <span className={s.modalTitulo}>Novo tenant</span>
            <label className={s.campoLabel} htmlFor="nt-nome">Nome da empresa</label>
            <input id="nt-nome" className={s.campo} value={nome} onChange={(e) => setNome(e.target.value)} />
            <label className={s.campoLabel} htmlFor="nt-slug">Slug (ex: empresa-abc)</label>
            <input
              id="nt-slug"
              className={s.campo}
              value={slug}
              onChange={(e) => setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '-'))}
            />
            <label className={s.campoLabel} htmlFor="nt-plano">Plano</label>
            <select id="nt-plano" className={s.campo} value={plano} onChange={(e) => setPlano(e.target.value as TenantPlan)}>
              {PLANOS.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
            <span className={s.campoLabel}>Módulos habilitados</span>
            <div className={s.modulosGrid}>
              {lista.map((m) => (
                <label key={m.code} className={s.moduloItem}>
                  <input type="checkbox" checked={modulos.includes(m.code)} onChange={() => toggleModulo(m.code)} />
                  {m.label}
                  {m.description && <HelpCircle size={12} color={lk.cor.cinzaNevoa} aria-label={m.description} />}
                </label>
              ))}
            </div>
            {erro && <span className={s.erro}>{erro}</span>}
            <div className={s.acoesModal}>
              <button type="button" className={s.botaoSecundario} onClick={onClose}>Cancelar</button>
              <button
                type="button"
                className={s.botaoPrimario}
                disabled={salvando || !nome || !slug}
                onClick={() => void criar()}
              >
                {salvando ? 'Criando...' : 'Criar tenant'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export function Tenants() {
  const nav = useNavigate()
  const [busca, setBusca] = useState('')
  const [modalAberto, setModalAberto] = useState(false)
  const [assumindoId, setAssumindoId] = useState<string | null>(null)
  const [erroAssumir, setErroAssumir] = useState<string | null>(null)

  const consulta = useQuery({
    queryKey: ['admin', 'tenants'],
    queryFn: () => adminService.getTenants(),
    staleTime: 30_000,
  })
  const qc = useQueryClient()

  // Best-effort: quais tenants são elegíveis a "ver como tenant" (ativos, com
  // schema válido). Falhar aqui não pode derrubar a lista — só esconde a ação.
  const elegiveis = useQuery({
    queryKey: ['admin', 'tenant-context', 'available'],
    queryFn: () => listAvailableTenants(),
    retry: false,
  })
  const idsElegiveis = useMemo(
    () => new Set((elegiveis.data ?? []).map((t) => t.id)),
    [elegiveis.data],
  )

  const verComoTenant = async (t: Tenant) => {
    setAssumindoId(t.id)
    setErroAssumir(null)
    try {
      await assumeTenantContext(t.id)
    } catch (e: unknown) {
      setErroAssumir(e instanceof Error ? e.message : 'Erro ao assumir contexto')
      setAssumindoId(null)
    }
  }

  if (consulta.isPending) {
    return <LogikosLoader estado="waiting" variante="tile" rotulo="CARREGANDO TENANTS" />
  }

  if (consulta.isError) {
    return (
      <div className={s.centro}>
        <AlertTriangle size={36} strokeWidth={1.5} color={lk.estado.nc} aria-hidden="true" />
        <span className={s.centroTitulo}>Não foi possível carregar os tenants</span>
        <span className={s.centroTecnico}>GET /v1/admin/tenants</span>
        <button type="button" className={s.botaoRetry} onClick={() => void consulta.refetch()}>
          Tentar novamente
        </button>
      </div>
    )
  }

  const tenants = consulta.data
  const filtrados = tenants.filter(
    (t) => !busca || t.name.toLowerCase().includes(busca.toLowerCase()) || t.slug.includes(busca.toLowerCase()),
  )

  return (
    <div className={s.raiz}>
      <div className={s.cabecalho}>
        <h1 className={s.titulo}>Tenants</h1>
        <span className={s.subtitulo}>{numero(tenants.length)} clientes cadastrados</span>
        <div className={s.spacer} />
        <input
          className={s.busca}
          placeholder="Buscar por nome ou slug..."
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          aria-label="Buscar tenant"
        />
        <button type="button" className={s.botaoPrimario} onClick={() => setModalAberto(true)}>
          Novo tenant
        </button>
      </div>

      {erroAssumir && <span className={s.erro}>{erroAssumir}</span>}

      {tenants.length === 0 ? (
        <EmptyState
          title="Nenhum tenant cadastrado ainda"
          description="Crie o primeiro tenant para começar a operar a plataforma."
        />
      ) : (
        <div className={s.tabelaWrap}>
          <table className={s.tabela}>
            <thead>
              <tr>
                <th className={s.th}>Tenant</th>
                <th className={s.th}>Módulos</th>
                <th className={s.th}>Usuários</th>
                <th className={s.th}>Status</th>
                <th className={s.th}></th>
              </tr>
            </thead>
            <tbody>
              {filtrados.map((t) => (
                <tr key={t.id}>
                  <td className={s.td}>
                    <button type="button" className={s.linkNome} onClick={() => nav(rotaNova(`/admin/tenants/${t.id}`))}>
                      {t.name}
                    </button>
                  </td>
                  <td className={s.td}>
                    <div className={s.badges}>
                      {(t.modules_enabled ?? []).map((m) => (
                        <span key={m} className={s.badge}>{m.toUpperCase()}</span>
                      ))}
                    </div>
                  </td>
                  <td className={s.td}>{numero(t.user_count ?? 0)}</td>
                  <td className={s.td}>
                    <span className={t.is_active ? s.statusOk : s.statusNc}>
                      <span className={s.dot} />
                      {t.is_active ? 'Ativo' : 'Suspenso'}
                    </span>
                  </td>
                  <td className={s.td}>
                    {idsElegiveis.has(t.id) && (
                      <button
                        type="button"
                        className={s.botaoSecundario}
                        disabled={assumindoId !== null}
                        onClick={() => void verComoTenant(t)}
                        title="Ativa a impersonação com banner âmbar — toda ação fica registrada na auditoria como sua"
                      >
                        <Building2 size={13} /> {assumindoId === t.id ? 'Assumindo...' : 'Ver como tenant'}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {filtrados.length === 0 && (
                <tr><td className={s.td} colSpan={5}>Nenhum tenant encontrado para "{busca}".</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      <span className={s.rodape}>
        "Ver como tenant" ativa a impersonação com o banner âmbar no topo — toda ação fica registrada na auditoria como sua.
      </span>

      {modalAberto && (
        <ModalNovoTenant
          onClose={() => setModalAberto(false)}
          onCriado={() => void qc.invalidateQueries({ queryKey: ['admin', 'tenants'] })}
        />
      )}
    </div>
  )
}
