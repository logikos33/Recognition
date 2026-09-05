/**
 * CreateUserWizard — jornada unificada de criação de usuário (WS9).
 *
 * Wizard de 3 passos no Modal do kit:
 *   1. Dados       — email (validação no blur), role de sistema (com descrição),
 *                    tenant via SELECT com busca (substitui UUID colado à mão)
 *   2. Acesso      — módulos habilitados do tenant (read-only + cross-link),
 *                    role customizada opcional (liga setUserCustomRole),
 *                    expiração de acesso opcional
 *   3. Credenciais — temp_password e first_access_token mascarados, com
 *                    revelar/copiar (Toast) — elimina o alert() nativo
 *
 * Contrato de Operabilidade: estados de loading/erro/sucesso em toda ação;
 * página inteira é superadmin (AdminRoute cobre a rota /admin/users).
 */
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Copy, Eye, EyeOff, ShieldAlert } from 'lucide-react'
import { Modal } from '../../../components/ui/Modal/Modal'
import { Stepper } from '../../../components/ui/Stepper/Stepper'
import { Banner } from '../../../components/ui/Banner/Banner'
import { Button } from '../../../components/ui/Button/Button'
import { useToast } from '../../../components/ui/Toast/useToast'
import { adminService } from '../services/adminService'
import * as s from './admin.css'
import type { CustomRole, Tenant, UserRole } from '../types/admin'
import { PAPEIS_ATRIBUIVEIS, ROTULO_SEM_PAPEL, SEM_PAPEL } from '../papeis'

const STEPS = [{ label: 'Dados' }, { label: 'Acesso' }, { label: 'Credenciais' }]

const MODULE_LABELS: Record<string, string> = {
  epi: 'EPI Monitor',
  fueling: 'Controle de Abastecimento',
  quality: 'Qualidade',
  counting: 'Contagem',
}

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

interface CreatedCredentials {
  email: string
  temp_password: string
  first_access_token: string | null
}

interface CreateUserWizardProps {
  open: boolean
  onClose: () => void
  /** Chamado após criação bem-sucedida (para recarregar a lista). */
  onCreated: () => void
}

export function CreateUserWizard({ open, onClose, onCreated }: CreateUserWizardProps) {
  const toast = useToast()

  const [step, setStep] = useState(0)

  // Passo 1 — Dados
  const [email, setEmail] = useState('')
  const [emailError, setEmailError] = useState<string | null>(null)
  const [role, setRole] = useState<UserRole | typeof SEM_PAPEL>(SEM_PAPEL)
  const [tenantId, setTenantId] = useState('')
  const [tenantSearch, setTenantSearch] = useState('')
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [tenantsLoading, setTenantsLoading] = useState(false)
  const [tenantsError, setTenantsError] = useState<string | null>(null)

  // Passo 2 — Acesso
  const [tenantDetail, setTenantDetail] = useState<Tenant | null>(null)
  const [tenantDetailLoading, setTenantDetailLoading] = useState(false)
  const [customRoles, setCustomRoles] = useState<CustomRole[]>([])
  const [customRoleId, setCustomRoleId] = useState('')
  const [accessExpiresAt, setAccessExpiresAt] = useState('')

  // Criação + Passo 3 — Credenciais
  const [saving, setSaving] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [credentials, setCredentials] = useState<CreatedCredentials | null>(null)
  const [showPassword, setShowPassword] = useState(false)
  const [showToken, setShowToken] = useState(false)

  // Carrega tenants ao abrir; reseta estado ao fechar
  useEffect(() => {
    if (!open) return
    setStep(0)
    setEmail(''); setEmailError(null); setRole(SEM_PAPEL)
    setTenantId(''); setTenantSearch('')
    setTenantDetail(null); setCustomRoles([]); setCustomRoleId(''); setAccessExpiresAt('')
    setCreateError(null); setCredentials(null); setShowPassword(false); setShowToken(false)

    setTenantsLoading(true)
    setTenantsError(null)
    adminService.getTenants()
      .then(setTenants)
      .catch((e: unknown) =>
        setTenantsError(e instanceof Error ? e.message : 'Erro ao carregar tenants'))
      .finally(() => setTenantsLoading(false))
  }, [open])

  // Ao entrar no passo 2: carrega detalhe do tenant + roles customizadas
  useEffect(() => {
    if (!open || step !== 1 || !tenantId) return
    setTenantDetailLoading(true)
    Promise.allSettled([
      adminService.getTenant(tenantId),
      adminService.getRoles(tenantId),
    ]).then(([tenantRes, rolesRes]) => {
      if (tenantRes.status === 'fulfilled') setTenantDetail(tenantRes.value)
      if (rolesRes.status === 'fulfilled') setCustomRoles(rolesRes.value.roles)
      setTenantDetailLoading(false)
    })
  }, [open, step, tenantId])

  const filteredTenants = useMemo(() => {
    const q = tenantSearch.trim().toLowerCase()
    if (!q) return tenants
    return tenants.filter(
      (t) => t.name.toLowerCase().includes(q) || t.slug.toLowerCase().includes(q),
    )
  }, [tenants, tenantSearch])

  const selectedTenant = tenants.find((t) => t.id === tenantId) ?? null
  const selectedRole = PAPEIS_ATRIBUIVEIS.find((r) => r.valor === role) ?? null

  const validateEmail = (): boolean => {
    if (!EMAIL_RE.test(email.trim())) {
      setEmailError('Informe um email válido (ex.: nome@empresa.com)')
      return false
    }
    setEmailError(null)
    return true
  }

  // `selectedRole` entra na validação: sem papel escolhido o wizard não avança.
  const step1Valid = EMAIL_RE.test(email.trim()) && Boolean(tenantId) && Boolean(selectedRole)

  const handleCreate = async () => {
    setSaving(true)
    setCreateError(null)
    try {
      const res = await adminService.createUser({
        email: email.trim().toLowerCase(),
        role,
        tenant_id: tenantId,
        ...(accessExpiresAt ? { access_expires_at: accessExpiresAt } : {}),
      })

      // Role customizada é opcional e best-effort: falha não desfaz a criação
      if (customRoleId) {
        try {
          await adminService.setUserCustomRole(res.user.id, customRoleId)
        } catch {
          toast.warning(
            'Usuário criado, mas a role customizada não pôde ser atribuída',
            'Atribua manualmente em Roles.',
          )
        }
      }

      setCredentials({
        email: res.user.email,
        temp_password: res.temp_password,
        first_access_token: res.first_access_token,
      })
      setStep(2)
      onCreated()
    } catch (e: unknown) {
      setCreateError(e instanceof Error ? e.message : 'Erro ao criar usuário')
    } finally {
      setSaving(false)
    }
  }

  const copyValue = async (value: string, label: string) => {
    try {
      await navigator.clipboard.writeText(value)
      toast.success('Copiado', `${label} copiado para a área de transferência.`)
    } catch {
      toast.error('Não foi possível copiar', 'Copie manualmente o valor revelado.')
    }
  }

  const mask = (value: string) => '•'.repeat(Math.min(value.length, 24))

  const footer = (
    <div className={s.flex} style={{ justifyContent: 'flex-end', width: '100%' }}>
      {step === 0 && (
        <>
          <Button variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button
            variant="primary"
            disabled={!step1Valid}
            onClick={() => { if (validateEmail()) setStep(1) }}
          >
            Avançar
          </Button>
        </>
      )}
      {step === 1 && (
        <>
          <Button variant="ghost" disabled={saving} onClick={() => setStep(0)}>Voltar</Button>
          <Button variant="primary" loading={saving} onClick={handleCreate}>
            {saving ? 'Criando...' : 'Criar usuário'}
          </Button>
        </>
      )}
      {step === 2 && (
        <Button variant="primary" onClick={onClose}>Concluir</Button>
      )}
    </div>
  )

  return (
    <Modal open={open} onClose={onClose} title="Novo usuário" maxWidth="560px" footer={footer}>
      <div style={{ marginBottom: 20 }}>
        <Stepper steps={STEPS} current={step} />
      </div>

      {step === 0 && (
        <div>
          <div style={{ marginBottom: 14 }}>
            <label className={s.muted} htmlFor="cuw-email" style={{ display: 'block', marginBottom: 4 }}>
              Email
            </label>
            <input
              id="cuw-email"
              type="email"
              className={s.input}
              style={{ width: '100%', boxSizing: 'border-box' }}
              placeholder="nome@empresa.com"
              value={email}
              onChange={(e) => { setEmail(e.target.value); if (emailError) setEmailError(null) }}
              onBlur={() => { if (email.trim()) validateEmail() }}
            />
            {emailError && (
              <div style={{ marginTop: 6 }}>
                <Banner variant="danger">{emailError}</Banner>
              </div>
            )}
          </div>

          <div style={{ marginBottom: 14 }}>
            <label className={s.muted} htmlFor="cuw-role" style={{ display: 'block', marginBottom: 4 }}>
              Role de sistema
            </label>
            <select
              id="cuw-role"
              className={s.select}
              style={{ width: '100%', boxSizing: 'border-box' }}
              value={role}
              onChange={(e) => setRole(e.target.value as UserRole)}
            >
              <option value={SEM_PAPEL}>{ROTULO_SEM_PAPEL}</option>
              {PAPEIS_ATRIBUIVEIS.map((r) => (
                <option key={r.valor} value={r.valor}>{r.rotulo}</option>
              ))}
            </select>
            {selectedRole && (
              <>
                <div className={s.muted} style={{ marginTop: 4 }}>{selectedRole.resumo}</div>
                <div style={{ marginTop: 4 }}>
                  <Banner variant="warning">{selectedRole.alerta}</Banner>
                </div>
              </>
            )}
          </div>

          <div style={{ marginBottom: 4 }}>
            <label className={s.muted} htmlFor="cuw-tenant-search" style={{ display: 'block', marginBottom: 4 }}>
              Tenant
            </label>
            {tenantsError ? (
              <Banner variant="danger">{tenantsError}</Banner>
            ) : (
              <>
                <input
                  id="cuw-tenant-search"
                  className={s.input}
                  style={{ width: '100%', boxSizing: 'border-box', marginBottom: 6 }}
                  placeholder="Buscar tenant por nome ou slug..."
                  value={tenantSearch}
                  onChange={(e) => setTenantSearch(e.target.value)}
                />
                <select
                  aria-label="Selecionar tenant"
                  className={s.select}
                  style={{ width: '100%', boxSizing: 'border-box' }}
                  value={tenantId}
                  onChange={(e) => setTenantId(e.target.value)}
                  disabled={tenantsLoading}
                >
                  <option value="">
                    {tenantsLoading ? 'Carregando tenants...' : 'Selecione um tenant'}
                  </option>
                  {filteredTenants.map((t) => (
                    <option key={t.id} value={t.id}>{t.name} ({t.slug})</option>
                  ))}
                </select>
                {!tenantsLoading && filteredTenants.length === 0 && (
                  <div className={s.muted} style={{ marginTop: 4 }}>
                    Nenhum tenant encontrado para essa busca.
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {step === 1 && (
        <div>
          <div className={s.card} style={{ marginBottom: 14 }}>
            <div className={s.muted} style={{ marginBottom: 6 }}>
              Módulos habilitados de {selectedTenant?.name ?? 'tenant selecionado'}
            </div>
            {tenantDetailLoading ? (
              <div className={s.muted}>Carregando módulos...</div>
            ) : (
              <div className={s.flex} style={{ flexWrap: 'wrap', gap: 6 }}>
                {(tenantDetail?.modules_enabled ?? selectedTenant?.modules_enabled ?? []).map((m) => (
                  <span key={m} className={s.card} style={{ padding: '4px 10px', fontSize: 12 }}>
                    {MODULE_LABELS[m] ?? m}
                  </span>
                ))}
                {(tenantDetail?.modules_enabled ?? selectedTenant?.modules_enabled ?? []).length === 0 && (
                  <span className={s.muted}>Nenhum módulo habilitado neste tenant.</span>
                )}
              </div>
            )}
            <div style={{ marginTop: 8 }}>
              <Link to={`/admin/tenants/${tenantId}`} onClick={onClose}>
                Gerenciar módulos deste tenant →
              </Link>
            </div>
          </div>

          <div style={{ marginBottom: 14 }}>
            <label className={s.muted} htmlFor="cuw-custom-role" style={{ display: 'block', marginBottom: 4 }}>
              Role customizada (opcional)
            </label>
            <select
              id="cuw-custom-role"
              className={s.select}
              style={{ width: '100%', boxSizing: 'border-box' }}
              value={customRoleId}
              onChange={(e) => setCustomRoleId(e.target.value)}
              disabled={tenantDetailLoading}
            >
              <option value="">Nenhuma — usar apenas a role de sistema</option>
              {customRoles.map((r) => (
                <option key={r.id} value={r.id}>{r.name}</option>
              ))}
            </select>
            {!tenantDetailLoading && customRoles.length === 0 && (
              <div className={s.muted} style={{ marginTop: 4 }}>
                Este tenant não possui roles customizadas.
              </div>
            )}
          </div>

          <div style={{ marginBottom: 4 }}>
            <label className={s.muted} htmlFor="cuw-expires" style={{ display: 'block', marginBottom: 4 }}>
              Acesso expira em (opcional)
            </label>
            <input
              id="cuw-expires"
              type="date"
              className={s.input}
              style={{ width: '100%', boxSizing: 'border-box' }}
              value={accessExpiresAt}
              onChange={(e) => setAccessExpiresAt(e.target.value)}
            />
          </div>

          {createError && (
            <div style={{ marginTop: 12 }}>
              <Banner variant="danger">{createError}</Banner>
            </div>
          )}
        </div>
      )}

      {step === 2 && credentials && (
        <div>
          <Banner variant="warning" icon={<ShieldAlert size={16} />}>
            Guarde estas credenciais agora — elas não poderão ser exibidas novamente.
            O token de primeiro acesso expira em 48h.
          </Banner>

          <div className={s.card} style={{ marginTop: 14 }}>
            <div className={s.muted} style={{ marginBottom: 4 }}>Usuário criado</div>
            <div style={{ marginBottom: 12, fontWeight: 600 }}>{credentials.email}</div>

            <div className={s.muted} style={{ marginBottom: 4 }}>Senha temporária</div>
            <div className={s.flex} style={{ marginBottom: 12, alignItems: 'center' }}>
              <code style={{ flex: 1, wordBreak: 'break-all' }}>
                {showPassword ? credentials.temp_password : mask(credentials.temp_password)}
              </code>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? 'Ocultar senha temporária' : 'Revelar senha temporária'}
              >
                {showPassword ? <EyeOff size={14} /> : <Eye size={14} />}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => copyValue(credentials.temp_password, 'Senha temporária')}
                aria-label="Copiar senha temporária"
              >
                <Copy size={14} />
              </Button>
            </div>

            <div className={s.muted} style={{ marginBottom: 4 }}>Token de primeiro acesso</div>
            {credentials.first_access_token ? (
              <div className={s.flex} style={{ alignItems: 'center' }}>
                <code style={{ flex: 1, wordBreak: 'break-all' }}>
                  {showToken ? credentials.first_access_token : mask(credentials.first_access_token)}
                </code>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowToken((v) => !v)}
                  aria-label={showToken ? 'Ocultar token de primeiro acesso' : 'Revelar token de primeiro acesso'}
                >
                  {showToken ? <EyeOff size={14} /> : <Eye size={14} />}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => copyValue(credentials.first_access_token as string, 'Token de primeiro acesso')}
                  aria-label="Copiar token de primeiro acesso"
                >
                  <Copy size={14} />
                </Button>
              </div>
            ) : (
              <div className={s.muted}>
                Token indisponível no momento — o usuário pode entrar com a senha temporária.
              </div>
            )}
          </div>
        </div>
      )}
    </Modal>
  )
}
