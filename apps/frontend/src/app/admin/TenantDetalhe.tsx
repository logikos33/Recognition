/**
 * Tenant Detalhe — `/novo/admin/tenants/:tenantId`. Desenho: `Admin
 * Plataforma.dc.html`, seções "Tenant Detalhe" e "White-Label". Paridade
 * funcional: `AdminTenantDetailPage.tsx` (lido função a função — tabs
 * overview/modules/config), reimplementado em UMA página (sem tabs, como o
 * desenho pede) no vocabulário lk.
 *
 * DIVERGÊNCIAS registradas (C-04 — o código vence a prancha):
 *
 *  1. **"Site" / "Blumenau-SC"** do desenho não existe em `Tenant` (sem
 *     endereço no schema) — substituído por **Schema**, campo real
 *     (`schema_name`) mais próximo do que a seção "DADOS" quer mostrar.
 *  2. **Limite de câmeras "3/10"**: `GET /v1/admin/tenants/<id>` não devolve
 *     contagem de câmeras — só o LIMITE (`contract_cameras`, override; senão
 *     `plans.max_cameras`). O numerador real vem de
 *     `GET /v1/admin/tenants/<id>/overview` (`cameras: [...]`, até 50 linhas
 *     do schema do tenant, `routes.py:633-684`) — por isso a barra só aparece
 *     depois que o overview carrega, e conta o que essa rota devolve (nunca
 *     inventa um número).
 *  3. **Limite de usuários**: numerador = `seats_in_use` (calculado pelo GET,
 *     migration 051); denominador = `max_seats` do tenant (override) senão
 *     `max_users` do plano (`GET /v1/admin/plans`, casado por `slug`). Sem
 *     limite em nenhum dos dois → "sem limite" (nunca um `X/∞` fingido).
 *  4. **Cor de marca**: a prévia usa `corDeMarcaUsavel` (clamp real de
 *     contraste, DECISÃO v2 item 3) — a cor exibida/salva é a AJUSTADA, nunca
 *     a crua digitada, e o aviso de ajuste é mostrado (o cliente tem de saber
 *     que a cor dele mudou).
 */
import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Building2, Upload } from 'lucide-react'

import { adminService } from '../../modules/admin/services/adminService'
import type { ModuleCatalogEntry, Plan, Tenant } from '../../modules/admin/types/admin'
import { assumeTenantContext } from '../../services/tenantContext'
import { useToast } from '../../components/ui/Toast/useToast'
import { LogikosLoader } from '../shell/LogikosLoader'
import { corDeMarcaUsavel } from '../tokens/contraste'
import { ACENTOS_MARCA_PRESET, lk } from '../tokens/lk.css'
import { rotaNova } from '../RotasNovas'
import * as s from './TenantDetalhe.css'

const CATALOGO_FALLBACK: ModuleCatalogEntry[] = ['epi', 'quality', 'counting', 'basic'].map((code) => ({
  code,
  label: code,
  description: '',
  status: 'active' as const,
}))

const WORKER_LABEL: Record<string, string> = {
  onpremise: 'Edge · on-premise',
  railway: 'Cloud · Railway',
  offline: 'Offline',
}

const numero = (n: number) => n.toLocaleString('pt-BR')

function Barra({ label, valor, limite }: { label: string; valor: number; limite: number | null }) {
  const pct = limite && limite > 0 ? Math.min(100, Math.round((valor / limite) * 100)) : 0
  return (
    <div className={s.barraLinha}>
      <span className={s.barraLabel}>{label}</span>
      <div className={s.barraTrilho}>
        <div className={s.barraPreenchida} style={{ width: `${pct}%` }} />
      </div>
      <span className={s.barraValor}>{limite === null ? `${numero(valor)} · sem limite` : `${numero(valor)}/${numero(limite)}`}</span>
    </div>
  )
}

export function TenantDetalhe() {
  const { tenantId } = useParams<{ tenantId: string }>()
  const nav = useNavigate()
  const toast = useToast()
  const qc = useQueryClient()

  const tenantQ = useQuery({
    queryKey: ['admin', 'tenant', tenantId],
    queryFn: () => adminService.getTenant(tenantId as string),
    enabled: !!tenantId,
  })
  const overviewQ = useQuery({
    queryKey: ['admin', 'tenant-overview', tenantId],
    queryFn: () => adminService.getTenantOverview(tenantId as string),
    enabled: !!tenantId,
  })
  const plansQ = useQuery({
    queryKey: ['admin', 'plans'],
    queryFn: () => adminService.getPlans(),
    staleTime: 5 * 60_000,
  })
  const catalogQ = useQuery({
    queryKey: ['admin', 'modules-catalog'],
    queryFn: () => adminService.getModulesCatalog(),
    staleTime: 5 * 60_000,
  })
  const brandingQ = useQuery({
    queryKey: ['admin', 'tenant-branding', tenantId],
    queryFn: () => adminService.getTenantBranding(tenantId as string),
    enabled: !!tenantId,
  })

  const [busy, setBusy] = useState(false)
  const [acento, setAcento] = useState<string>(ACENTOS_MARCA_PRESET[0])
  const [salvandoMarca, setSalvandoMarca] = useState(false)
  const [erroMarca, setErroMarca] = useState<string | null>(null)

  useEffect(() => {
    if (brandingQ.data?.color_primary) setAcento(brandingQ.data.color_primary)
  }, [brandingQ.data?.color_primary])

  const resultadoClamp = useMemo(() => corDeMarcaUsavel(acento), [acento])

  const invalidarTenant = () => void qc.invalidateQueries({ queryKey: ['admin', 'tenant', tenantId] })

  const toggleModulo = async (tenant: Tenant, code: string) => {
    const next = (tenant.modules_enabled ?? []).includes(code)
      ? (tenant.modules_enabled ?? []).filter((m) => m !== code)
      : [...(tenant.modules_enabled ?? []), code]
    setBusy(true)
    try {
      await adminService.updateTenant(tenant.id, { modules_enabled: next })
      invalidarTenant()
    } catch (e: unknown) {
      toast.error('Erro ao atualizar módulos', e instanceof Error ? e.message : undefined)
    } finally {
      setBusy(false)
    }
  }

  const suspender = async (tenant: Tenant) => {
    const motivo = window.prompt('Motivo da suspensão:')
    if (!motivo) return
    setBusy(true)
    try {
      await adminService.suspendTenant(tenant.id, motivo)
      invalidarTenant()
    } catch (e: unknown) {
      toast.error('Erro ao suspender tenant', e instanceof Error ? e.message : undefined)
    } finally {
      setBusy(false)
    }
  }

  const reativar = async (tenant: Tenant) => {
    setBusy(true)
    try {
      await adminService.reactivateTenant(tenant.id)
      invalidarTenant()
    } catch (e: unknown) {
      toast.error('Erro ao reativar tenant', e instanceof Error ? e.message : undefined)
    } finally {
      setBusy(false)
    }
  }

  const verComoTenant = async (tenant: Tenant) => {
    try {
      await assumeTenantContext(tenant.id)
    } catch (e: unknown) {
      toast.error('Erro ao assumir contexto', e instanceof Error ? e.message : undefined)
    }
  }

  const salvarMarca = async () => {
    if (!tenantId) return
    setSalvandoMarca(true)
    setErroMarca(null)
    try {
      await adminService.updateTenantBranding(tenantId, { color_primary: resultadoClamp.cor })
      void qc.invalidateQueries({ queryKey: ['admin', 'tenant-branding', tenantId] })
      toast.success('Marca salva', resultadoClamp.ajustada ? 'A cor foi ajustada para manter contraste legível.' : undefined)
    } catch (e: unknown) {
      setErroMarca(e instanceof Error ? e.message : 'Erro ao salvar marca')
    } finally {
      setSalvandoMarca(false)
    }
  }

  const uploadLogo = async (file: File) => {
    if (!tenantId) return
    try {
      await adminService.uploadBrandingLogo(tenantId, file, 'logo')
      void qc.invalidateQueries({ queryKey: ['admin', 'tenant-branding', tenantId] })
      toast.success('Logo enviada')
    } catch (e: unknown) {
      toast.error('Erro ao enviar logo', e instanceof Error ? e.message : undefined)
    }
  }

  if (tenantQ.isPending) {
    return <LogikosLoader estado="waiting" variante="tile" rotulo="CARREGANDO TENANT" />
  }

  if (tenantQ.isError || !tenantQ.data) {
    return (
      <div className={s.centro}>
        <AlertTriangle size={36} strokeWidth={1.5} color={lk.estado.nc} aria-hidden="true" />
        <span className={s.centroTitulo}>Não foi possível carregar este tenant</span>
        <span className={s.centroTecnico}>GET /v1/admin/tenants/{tenantId}</span>
        <button type="button" className={s.botaoRetry} onClick={() => void tenantQ.refetch()}>
          Tentar novamente
        </button>
      </div>
    )
  }

  const tenant = tenantQ.data
  const catalogo = catalogQ.data ?? CATALOGO_FALLBACK
  const enabled = new Set(tenant.modules_enabled ?? [])
  const plano = (plansQ.data ?? []).find((p: Plan) => p.slug === tenant.plan) ?? null

  const overviewCameras = Array.isArray((overviewQ.data as { cameras?: unknown[] } | undefined)?.cameras)
    ? ((overviewQ.data as { cameras: unknown[] }).cameras.length)
    : null
  const limiteCameras = tenant.contract_cameras ?? plano?.max_cameras ?? null
  const usuariosAtuais = tenant.seats_in_use ?? tenant.user_count ?? 0
  const limiteUsuarios = tenant.max_seats ?? plano?.max_users ?? null

  return (
    <div className={s.raiz}>
      <div className={s.cabecalho}>
        <button type="button" className={s.voltar} onClick={() => nav(rotaNova('/admin/tenants'))}>
          ← Tenants
        </button>
        <h1 className={s.titulo}>{tenant.name}</h1>
        <span className={tenant.is_active ? s.statusOk : s.statusNc}>
          <span className={s.dot} />
          {tenant.is_active ? 'Ativo' : 'Suspenso'}
        </span>
        <div className={s.spacer} />
        <button type="button" className={s.botaoSecundario} disabled={busy} onClick={() => void verComoTenant(tenant)}>
          <Building2 size={14} /> Ver como tenant
        </button>
        {tenant.is_active ? (
          <button type="button" className={s.botaoPerigo} disabled={busy} onClick={() => void suspender(tenant)}>
            Suspender
          </button>
        ) : (
          <button type="button" className={s.botaoPrimario} disabled={busy} onClick={() => void reativar(tenant)}>
            Reativar
          </button>
        )}
      </div>

      <div className={s.grid}>
        <div className={s.painel}>
          <span className={s.overline}>Dados</span>
          <div className={s.dadosGrid}>
            <span className={s.dadosLabel}>Identificador</span>
            <span className={s.mono}>{tenant.slug}</span>
            <span className={s.dadosLabel}>Schema</span>
            <span className={s.mono}>{tenant.schema_name}</span>
            <span className={s.dadosLabel}>Processamento</span>
            <span>{tenant.worker_status ? WORKER_LABEL[tenant.worker_status] : '—'}</span>
            <span className={s.dadosLabel}>Desde</span>
            <span className={s.mono}>{new Date(tenant.created_at).toLocaleDateString('pt-BR')}</span>
          </div>

          <div className={s.divisor}>
            <span className={s.overline}>Limites do plano</span>
            {overviewCameras !== null && (
              <Barra label="Câmeras" valor={overviewCameras} limite={limiteCameras} />
            )}
            <Barra label="Usuários" valor={usuariosAtuais} limite={limiteUsuarios} />
          </div>

          <div className={s.divisor}>
            <span className={s.overline}>Módulos habilitados</span>
            {catalogo.map((m) => {
              const ligado = enabled.has(m.code)
              return (
                <button
                  key={m.code}
                  type="button"
                  className={s.moduloLinha}
                  disabled={busy}
                  onClick={() => void toggleModulo(tenant, m.code)}
                >
                  <span className={ligado ? `${s.toggleTrilho} ${s.toggleTrilhoLigado}` : s.toggleTrilho}>
                    <span className={ligado ? `${s.toggleBolinha} ${s.toggleBolinhaLigado}` : s.toggleBolinha} />
                  </span>
                  <span className={s.moduloNome}>{m.label}</span>
                  {m.description && <span className={s.moduloNota}>{m.description}</span>}
                </button>
              )
            })}
          </div>
        </div>

        <div className={s.painel}>
          <span className={s.overline}>Marca do tenant · white-label</span>
          <span className={s.explicacao}>
            Sobrescreve a cor de acento do shell escuro via <code>/v1/admin/tenants/{tenant.id}/branding</code>.
            Estados semânticos (ok/atenção/não-conforme) não são sobrescritíveis.
          </span>

          <div>
            <span className={s.dadosLabel}>Cor de acento (substitui o ciano)</span>
            <div className={s.acentosLinha} style={{ marginTop: 6 }}>
              {ACENTOS_MARCA_PRESET.map((hex) => (
                <button
                  key={hex}
                  type="button"
                  className={acento === hex ? `${s.swatch} ${s.swatchSelecionado}` : s.swatch}
                  style={{ background: hex }}
                  aria-label={`Usar ${hex}`}
                  onClick={() => setAcento(hex)}
                />
              ))}
              <input
                className={s.inputCustom}
                value={acento}
                onChange={(e) => setAcento(e.target.value)}
                aria-label="Cor customizada (hex)"
                placeholder="#RRGGBB"
              />
            </div>
          </div>

          <div>
            <span className={s.dadosLabel}>Logo do tenant (sidebar e kiosk)</span>
            <label className={s.uploadArea} style={{ marginTop: 6 }}>
              {brandingQ.data?.logo_url ? (
                <img src={brandingQ.data.logo_url} alt="Logo atual" className={s.logoPreview} />
              ) : (
                <>
                  <Upload size={16} />
                  Arraste o SVG/PNG — mínimo 90px de largura
                </>
              )}
              <input
                type="file"
                accept="image/svg+xml,image/png"
                style={{ display: 'none' }}
                onChange={(e) => { const f = e.target.files?.[0]; if (f) void uploadLogo(f) }}
              />
            </label>
          </div>

          <div className={s.previaBox}>
            <span className={s.overline}>Prévia</span>
            <div className={s.previaLinha}>
              <span className={s.previaBotao} style={{ background: resultadoClamp.cor }}>Botão primário</span>
              <span className={s.previaItem} style={{ borderLeft: `2px solid ${resultadoClamp.cor}`, color: resultadoClamp.cor }}>
                Item ativo
              </span>
              <a className={s.previaLink} style={{ color: resultadoClamp.cor }}>link</a>
            </div>
            {resultadoClamp.contraste !== null && (
              <span className={s.contrasteTexto}>contraste {resultadoClamp.contraste.toFixed(2)}:1 contra o shell escuro</span>
            )}
            {resultadoClamp.ajustada && (
              <span className={s.avisoAjuste}>
                Cor ajustada automaticamente ({resultadoClamp.cor}) — a original não tinha contraste suficiente sobre o shell escuro.
              </span>
            )}
          </div>

          {erroMarca && <span className={s.erro}>{erroMarca}</span>}
          <button type="button" className={s.botaoPrimario} disabled={salvandoMarca} onClick={() => void salvarMarca()}>
            {salvandoMarca ? 'Salvando...' : 'Salvar marca'}
          </button>
        </div>
      </div>
    </div>
  )
}
