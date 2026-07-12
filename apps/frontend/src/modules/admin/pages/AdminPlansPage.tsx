import { Info, Package, Plus } from 'lucide-react'
import { useEffect, useState } from 'react'
import { adminService } from '../services/adminService'
import * as s from '../components/admin.css'
import type { ModuleRegistryEntry, Plan } from '../types/admin'
import { Badge } from '../../../components/ui/Badge/Badge'
import { Banner } from '../../../components/ui/Banner/Banner'
import { Button } from '../../../components/ui/Button/Button'
import { ConfirmDialog } from '../../../components/ui/ConfirmDialog/ConfirmDialog'
import { EmptyState } from '../../../components/ui/EmptyState/EmptyState'
import { Field, Input } from '../../../components/ui/Input/Input'
import { Modal } from '../../../components/ui/Modal/Modal'
import { Skeleton } from '../../../components/ui/Skeleton/Skeleton'
import { Tooltip } from '../../../components/ui/Tooltip/Tooltip'
import { useToast } from '../../../components/ui/Toast/useToast'

const SLUG_RE = /^[a-z0-9_-]{2,50}$/
const SLUG_HELP = 'Slug identifica o plano nos contratos dos clientes e não pode mudar'

interface PlanForm {
  id: string
  slug: string
  name: string
  modules_allowed: string[]
  max_cameras: number
  max_users: number | null
  video_retention_days: number
  api_rate_per_minute: number
  requires_training_approval: boolean
  price_per_camera: Record<string, number>
  module_features: Record<string, string[]>
  active: boolean
  tenant_count: number
}

function emptyForm(): PlanForm {
  return {
    id: '',
    slug: '',
    name: '',
    modules_allowed: [],
    max_cameras: 10,
    max_users: null,
    video_retention_days: 7,
    api_rate_per_minute: 120,
    requires_training_approval: false,
    price_per_camera: {},
    module_features: {},
    active: true,
    tenant_count: 0,
  }
}

function toForm(plan: Plan): PlanForm {
  return {
    id: plan.id,
    slug: plan.slug,
    name: plan.name,
    modules_allowed: plan.modules_allowed ?? [],
    max_cameras: plan.max_cameras ?? 10,
    max_users: plan.max_users ?? null,
    video_retention_days: plan.video_retention_days ?? 7,
    api_rate_per_minute: plan.api_rate_per_minute ?? 120,
    requires_training_approval: plan.requires_training_approval ?? false,
    price_per_camera: plan.price_per_camera ?? {},
    module_features: plan.module_features ?? {},
    active: plan.active ?? true,
    tenant_count: plan.tenant_count ?? 0,
  }
}

const brl = (value: number) =>
  value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })

export function AdminPlansPage() {
  const [plans, setPlans] = useState<Plan[]>([])
  const [registry, setRegistry] = useState<ModuleRegistryEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [pageError, setPageError] = useState<string | null>(null)
  const [form, setForm] = useState<PlanForm | null>(null)
  const [isNew, setIsNew] = useState(false)
  const [modalError, setModalError] = useState<string | null>(null)
  const [slugError, setSlugError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [confirmDeactivate, setConfirmDeactivate] = useState(false)
  const toast = useToast()

  const load = () => {
    setLoading(true)
    Promise.all([adminService.getPlans(), adminService.getModulesRegistry()])
      .then(([plansData, registryData]) => {
        setPlans(plansData)
        setRegistry(registryData)
        setPageError(null)
      })
      .catch((e: unknown) =>
        setPageError(e instanceof Error ? e.message : 'Erro ao carregar planos'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const moduleLabel = (code: string) =>
    registry.find((m) => m.module_code === code)?.label ?? code

  const openCreate = () => {
    setModalError(null)
    setSlugError(null)
    setIsNew(true)
    setForm(emptyForm())
  }

  const openEdit = (plan: Plan) => {
    setModalError(null)
    setSlugError(null)
    setIsNew(false)
    setForm(toForm(plan))
  }

  const closeModal = () => {
    setForm(null)
    setModalError(null)
    setSlugError(null)
    setConfirmDeactivate(false)
  }

  const validateSlug = (slug: string) => {
    if (!SLUG_RE.test(slug)) {
      setSlugError('Use 2-50 caracteres: letras minúsculas, números, hífen ou underscore')
      return false
    }
    setSlugError(null)
    return true
  }

  const toggleModule = (entry: ModuleRegistryEntry) => {
    setForm((prev) => {
      if (!prev) return prev
      const code = entry.module_code
      if (prev.modules_allowed.includes(code)) {
        const features = { ...prev.module_features }
        delete features[code]
        const prices = { ...prev.price_per_camera }
        delete prices[code]
        return {
          ...prev,
          modules_allowed: prev.modules_allowed.filter((m) => m !== code),
          module_features: features,
          price_per_camera: prices,
        }
      }
      return {
        ...prev,
        modules_allowed: [...prev.modules_allowed, code],
        // Todas marcadas por padrão = sem restrição de funcionalidades
        module_features: {
          ...prev.module_features,
          [code]: entry.features.map((f) => f.key),
        },
      }
    })
  }

  const toggleFeature = (moduleCode: string, featureKey: string) => {
    setForm((prev) => {
      if (!prev) return prev
      const current = prev.module_features[moduleCode] ?? []
      const next = current.includes(featureKey)
        ? current.filter((k) => k !== featureKey)
        : [...current, featureKey]
      return {
        ...prev,
        module_features: { ...prev.module_features, [moduleCode]: next },
      }
    })
  }

  const setPrice = (moduleCode: string, raw: string) => {
    setForm((prev) => {
      if (!prev) return prev
      const prices = { ...prev.price_per_camera }
      if (raw === '') {
        delete prices[moduleCode]
      } else {
        const value = Number(raw)
        if (!Number.isNaN(value) && value >= 0) prices[moduleCode] = value
      }
      return { ...prev, price_per_camera: prices }
    })
  }

  const handleActiveChange = (checked: boolean) => {
    if (!form) return
    if (!checked && !isNew && form.tenant_count > 0) {
      setConfirmDeactivate(true)
      return
    }
    setForm((prev) => (prev ? { ...prev, active: checked } : prev))
  }

  const handleSave = async () => {
    if (!form) return
    if (!form.name.trim()) {
      setModalError('Nome do plano é obrigatório')
      return
    }
    if (isNew && !validateSlug(form.slug)) return

    setSaving(true)
    setModalError(null)
    try {
      const payload: Partial<Plan> = {
        name: form.name.trim(),
        modules_allowed: form.modules_allowed,
        max_cameras: form.max_cameras,
        max_users: form.max_users,
        video_retention_days: form.video_retention_days,
        api_rate_per_minute: form.api_rate_per_minute,
        requires_training_approval: form.requires_training_approval,
        price_per_camera: form.price_per_camera,
        module_features: form.module_features,
        active: form.active,
      }
      if (isNew) {
        await adminService.createPlan({ ...payload, slug: form.slug })
        toast.success('Plano criado', `${form.name} disponível para novos clientes`)
      } else {
        await adminService.updatePlan(form.id, payload)
        toast.success('Plano salvo', `${form.name} atualizado com sucesso`)
      }
      closeModal()
      load()
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : 'Erro ao salvar plano'
      setModalError(message)
      toast.error('Erro ao salvar plano', message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className={s.pageRoot}>
      <div className={s.pageHeader}>
        <div>
          <div className={s.pageTitle}>Planos</div>
          <div className={s.pageSubtitle}>{plans.length} planos cadastrados</div>
        </div>
        <Button variant="primary" onClick={openCreate}>
          <Plus size={14} /> Novo Plano
        </Button>
      </div>

      {pageError && (
        <Banner variant="danger" onDismiss={() => setPageError(null)}>
          {pageError}
        </Banner>
      )}

      {loading ? (
        <div className={s.plansGrid}>
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} variant="rect" height={180} />
          ))}
        </div>
      ) : plans.length === 0 ? (
        <EmptyState
          icon={<Package size={32} />}
          title="Nenhum plano cadastrado"
          description="Crie o primeiro plano para liberar módulos e limites aos clientes."
          action={
            <Button variant="primary" onClick={openCreate}>
              <Plus size={14} /> Novo Plano
            </Button>
          }
        />
      ) : (
        <div className={s.plansGrid}>
          {plans.map((p) => (
            <div key={p.id} className={s.card} style={{ cursor: 'pointer' }} onClick={() => openEdit(p)}>
              <div className={s.flex}>
                <span style={{ fontWeight: 700, flex: 1 }}>{p.name}</span>
                <span className={s.planBadge[p.slug as keyof typeof s.planBadge] ?? s.badge}>{p.slug}</span>
                {!p.active && <Badge variant="warning">Inativo</Badge>}
              </div>
              <div className={s.muted} style={{ marginTop: 8 }}>Máx câmeras: {p.max_cameras}</div>
              <div className={s.muted}>
                Usuários: {p.max_users == null ? 'Ilimitado' : p.max_users}
              </div>
              <div className={s.muted}>Retenção: {p.video_retention_days} dias</div>
              <div className={s.muted}>
                Aprovação de treino: {p.requires_training_approval ? 'Sim' : 'Não'}
              </div>
              <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {(p.modules_allowed ?? []).map((m) => (
                  <Badge key={m} variant="primary">{moduleLabel(m)}</Badge>
                ))}
              </div>
              {Object.keys(p.price_per_camera ?? {}).length > 0 && (
                <div className={s.muted} style={{ marginTop: 8 }}>
                  {Object.entries(p.price_per_camera)
                    .map(([mod, value]) => `${moduleLabel(mod)}: ${brl(value)}/câmera`)
                    .join(' · ')}
                </div>
              )}
              <div className={s.muted} style={{ marginTop: 8 }}>
                {p.tenant_count ?? 0} {(p.tenant_count ?? 0) === 1 ? 'cliente' : 'clientes'}
              </div>
            </div>
          ))}
        </div>
      )}

      {form !== null && (
        <Modal
          open
          onClose={closeModal}
          title={isNew ? 'Novo Plano' : 'Editar Plano'}
          maxWidth="560px"
          footer={
            <>
              <Button variant="ghost" onClick={closeModal} disabled={saving}>Cancelar</Button>
              <Button variant="primary" onClick={handleSave} loading={saving}>
                {saving ? 'Salvando...' : 'Salvar'}
              </Button>
            </>
          }
        >
          {modalError && (
            <Banner variant="danger" onDismiss={() => setModalError(null)}>
              {modalError}
            </Banner>
          )}

          <Field label="Nome">
            <Input
              aria-label="Nome"
              maxLength={100}
              value={form.name}
              onChange={(e) => setForm((prev) => (prev ? { ...prev, name: e.target.value } : prev))}
            />
          </Field>

          <Field label="Slug" error={slugError ?? undefined}>
            {isNew ? (
              <Input
                aria-label="Slug"
                value={form.slug}
                placeholder="ex: standard"
                onBlur={(e) => validateSlug(e.target.value)}
                onChange={(e) =>
                  setForm((prev) => (prev ? { ...prev, slug: e.target.value } : prev))}
              />
            ) : (
              <Tooltip label={SLUG_HELP}>
                <div className={s.flex}>
                  <Input aria-label="Slug" value={form.slug} readOnly disabled />
                  <Info size={14} aria-hidden="true" />
                </div>
              </Tooltip>
            )}
          </Field>

          <div className={s.twoColumn}>
            <Field label="Máx. câmeras">
              <Input
                aria-label="Máx. câmeras"
                type="number"
                min={0}
                value={form.max_cameras}
                onChange={(e) =>
                  setForm((prev) =>
                    prev ? { ...prev, max_cameras: Math.max(0, Number(e.target.value)) } : prev)}
              />
            </Field>
            <Field label="Máx. usuários">
              <Input
                aria-label="Máx. usuários"
                type="number"
                min={0}
                placeholder="Ilimitado"
                value={form.max_users ?? ''}
                onChange={(e) =>
                  setForm((prev) =>
                    prev
                      ? {
                          ...prev,
                          max_users: e.target.value === '' ? null : Math.max(0, Number(e.target.value)),
                        }
                      : prev)}
              />
            </Field>
          </div>
          <div className={s.muted} style={{ marginBottom: 12 }}>
            Vazio = ilimitado; pode ser sobrescrito por cliente na tela de Tenants
          </div>

          <div className={s.twoColumn}>
            <Field label="Retenção de vídeo (dias)">
              <Input
                aria-label="Retenção de vídeo (dias)"
                type="number"
                min={1}
                value={form.video_retention_days}
                onChange={(e) =>
                  setForm((prev) =>
                    prev
                      ? { ...prev, video_retention_days: Math.max(1, Number(e.target.value)) }
                      : prev)}
              />
            </Field>
            <Field label="Requisições API/min">
              <Input
                aria-label="Requisições API/min"
                type="number"
                min={1}
                value={form.api_rate_per_minute}
                onChange={(e) =>
                  setForm((prev) =>
                    prev
                      ? { ...prev, api_rate_per_minute: Math.max(1, Number(e.target.value)) }
                      : prev)}
              />
            </Field>
          </div>

          <Field label="Módulos liberados">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {registry.map((entry) => {
                const checked = form.modules_allowed.includes(entry.module_code)
                return (
                  <div key={entry.module_code}>
                    <label className={s.flex} style={{ cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleModule(entry)}
                      />
                      <span>{entry.label}</span>
                    </label>
                    {checked && (
                      <div style={{ marginLeft: 24, marginTop: 4, display: 'flex', flexDirection: 'column', gap: 4 }}>
                        <span className={s.muted}>
                          Funcionalidades (todas marcadas = sem restrição)
                        </span>
                        {entry.features.map((feature) => (
                          <label key={feature.key} className={s.flex} style={{ cursor: 'pointer' }}>
                            <input
                              type="checkbox"
                              checked={(form.module_features[entry.module_code] ?? []).includes(feature.key)}
                              onChange={() => toggleFeature(entry.module_code, feature.key)}
                            />
                            <span className={s.muted}>{feature.label}</span>
                          </label>
                        ))}
                        <Field label={`R$ por câmera/mês — ${entry.label}`}>
                          <Input
                            aria-label={`R$ por câmera/mês — ${entry.label}`}
                            type="number"
                            min={0}
                            step={0.01}
                            placeholder="0,00"
                            value={form.price_per_camera[entry.module_code] ?? ''}
                            onChange={(e) => setPrice(entry.module_code, e.target.value)}
                          />
                        </Field>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </Field>

          <label className={s.flex} style={{ marginBottom: 8, cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={form.requires_training_approval}
              onChange={(e) =>
                setForm((prev) =>
                  prev ? { ...prev, requires_training_approval: e.target.checked } : prev)}
            />
            <span>Requer aprovação de treinamento</span>
          </label>

          <label className={s.flex} style={{ cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={form.active}
              onChange={(e) => handleActiveChange(e.target.checked)}
            />
            <span>Ativo</span>
          </label>

          <ConfirmDialog
            open={confirmDeactivate}
            onClose={() => setConfirmDeactivate(false)}
            onConfirm={() => {
              setForm((prev) => (prev ? { ...prev, active: false } : prev))
              setConfirmDeactivate(false)
            }}
            title="Desativar plano"
            description={`Este plano tem ${form.tenant_count} ${form.tenant_count === 1 ? 'cliente' : 'clientes'} ativo(s). Desativá-lo impede novas contratações, mas não altera os clientes existentes. Deseja continuar?`}
            confirmLabel="Desativar"
          />
        </Modal>
      )}
    </div>
  )
}
