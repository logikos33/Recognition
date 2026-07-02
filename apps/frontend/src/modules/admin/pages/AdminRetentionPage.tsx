import { Clock, Save } from 'lucide-react'
import { useEffect, useState } from 'react'
import { adminService } from '../services/adminService'
import * as s from '../components/admin.css'
import type { Tenant } from '../types/admin'
import { vars } from '../../../styles/theme.css'

// Tiers disponíveis: 1, 7, 30, 90 dias
const TIERS: Array<{ days: number; label: string; description: string; compliance: string }> = [
  {
    days: 1,
    label: '1 dia',
    description: 'Mínimo operacional',
    compliance: 'Não recomendado para LGPD — ciclo de auditoria insuficiente',
  },
  {
    days: 7,
    label: '7 dias',
    description: 'Padrão básico',
    compliance: 'Retenção mínima para auditoria semanal',
  },
  {
    days: 30,
    label: '30 dias',
    description: 'Padrão recomendado',
    compliance: 'Cobre ciclo mensal de inspeções e auditorias internas',
  },
  {
    days: 90,
    label: '90 dias',
    description: 'Conformidade estendida',
    compliance: 'Adequado para auditorias externas e requisitos LGPD mais rigorosos',
  },
]

function TierSelector({
  value,
  onChange,
}: {
  value: number
  onChange: (days: number) => void
}) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
      {TIERS.map((t) => {
        const isSelected = value === t.days
        return (
          <button
            key={t.days}
            onClick={() => onChange(t.days)}
            style={{
              padding: '10px 8px',
              borderRadius: 6,
              border: isSelected ? `2px solid ${vars.color.primary}` : `1px solid ${vars.color.borderDefault}`,
              background: isSelected ? 'rgba(37,99,235,0.07)' : 'transparent',
              cursor: 'pointer',
              textAlign: 'left',
              transition: 'all 0.15s',
            }}
          >
            <div style={{ fontWeight: 700, fontSize: 15, color: isSelected ? vars.color.primary : vars.color.bgSurface }}>
              {t.label}
            </div>
            <div style={{ fontSize: 11, color: vars.color.textMuted, marginTop: 2 }}>{t.description}</div>
          </button>
        )
      })}
    </div>
  )
}

interface TenantRetentionRow {
  tenant: Tenant
  editing: boolean
  draftDays: number
  saving: boolean
  saved: boolean
}

export function AdminRetentionPage() {
  const [rows, setRows] = useState<TenantRetentionRow[]>([])
  const [loading, setLoading] = useState(true)
  const [globalError, setGlobalError] = useState<string | null>(null)

  const load = () => {
    setLoading(true)
    setGlobalError(null)
    adminService
      .getTenants()
      .then((tenants) => {
        setRows(
          tenants.map((t) => ({
            tenant: t,
            editing: false,
            draftDays: (t as Tenant & { video_retention_days?: number }).video_retention_days ?? 30,
            saving: false,
            saved: false,
          })),
        )
      })
      .catch((e: Error) => setGlobalError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const handleEdit = (tenantId: string) => {
    setRows((prev) =>
      prev.map((r) =>
        r.tenant.id === tenantId ? { ...r, editing: true, saved: false } : r,
      ),
    )
  }

  const handleCancel = (tenantId: string) => {
    setRows((prev) =>
      prev.map((r) =>
        r.tenant.id === tenantId
          ? {
              ...r,
              editing: false,
              draftDays:
                (r.tenant as Tenant & { video_retention_days?: number }).video_retention_days ?? 30,
            }
          : r,
      ),
    )
  }

  const handleDraftChange = (tenantId: string, days: number) => {
    setRows((prev) =>
      prev.map((r) => (r.tenant.id === tenantId ? { ...r, draftDays: days } : r)),
    )
  }

  const handleSave = async (tenantId: string, days: number) => {
    setRows((prev) =>
      prev.map((r) => (r.tenant.id === tenantId ? { ...r, saving: true } : r)),
    )
    try {
      await adminService.updateTenant(tenantId, { video_retention_days: days } as Parameters<typeof adminService.updateTenant>[1])
      setRows((prev) =>
        prev.map((r) =>
          r.tenant.id === tenantId
            ? {
                ...r,
                saving: false,
                editing: false,
                saved: true,
                tenant: {
                  ...r.tenant,
                  video_retention_days: days,
                } as Tenant & { video_retention_days: number },
              }
            : r,
        ),
      )
    } catch (e: unknown) {
      setRows((prev) =>
        prev.map((r) => (r.tenant.id === tenantId ? { ...r, saving: false } : r)),
      )
      setGlobalError(e instanceof Error ? e.message : 'Erro ao salvar retenção')
    }
  }

  const activeTierInfo = (days: number) => TIERS.find((t) => t.days === days)

  return (
    <div className={s.pageRoot}>
      <div className={s.pageHeader}>
        <div>
          <div className={s.pageTitle}>Tiers de Retenção</div>
          <div className={s.pageSubtitle}>
            Configura por quantos dias as evidências (frames/clipes) de cada tenant são retidas no
            R2. Tiers: 1, 7, 30 e 90 dias.
          </div>
        </div>
      </div>

      {/* Referência rápida de tiers */}
      <div className={s.card} style={{ marginBottom: 24 }}>
        <div className={s.cardTitle}>Referência de Tiers</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
          {TIERS.map((t) => (
            <div
              key={t.days}
              style={{
                padding: '12px 14px',
                borderRadius: 8,
                border: `1px solid ${vars.color.borderDefault}`,
                background: vars.color.bgSurface,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                <Clock size={13} color={vars.color.textMuted} />
                <span style={{ fontWeight: 700, fontSize: 14, color: vars.color.bgSurface }}>{t.label}</span>
              </div>
              <div style={{ fontSize: 12, color: vars.color.textPrimary, marginBottom: 4 }}>{t.description}</div>
              <div style={{ fontSize: 11, color: vars.color.textSecondary, lineHeight: 1.4 }}>{t.compliance}</div>
            </div>
          ))}
        </div>
      </div>

      {globalError && (
        <div className={s.alertBanner.danger} style={{ marginBottom: 16 }}>
          {globalError}
        </div>
      )}

      {loading ? (
        <div className={s.muted}>Carregando tenants...</div>
      ) : (
        <div className={s.card}>
          <table className={s.table}>
            <thead>
              <tr>
                <th className={s.th}>Tenant</th>
                <th className={s.th}>Plano</th>
                <th className={s.th}>Retenção atual</th>
                <th className={s.th}>Conformidade</th>
                <th className={s.th} style={{ width: 120 }}></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const currentDays =
                  (row.tenant as Tenant & { video_retention_days?: number }).video_retention_days ??
                  30
                const tierInfo = activeTierInfo(currentDays)

                return (
                  <tr key={row.tenant.id}>
                    <td className={s.td}>
                      <div style={{ fontWeight: 600 }}>{row.tenant.name}</div>
                      <div style={{ fontSize: 11, color: vars.color.textMuted }}>{row.tenant.slug}</div>
                    </td>
                    <td className={s.td}>
                      <span
                        className={
                          s.planBadge[row.tenant.plan as keyof typeof s.planBadge] ?? s.badge
                        }
                      >
                        {row.tenant.plan}
                      </span>
                    </td>
                    <td className={s.td}>
                      {row.editing ? (
                        <div style={{ minWidth: 320 }}>
                          <TierSelector
                            value={row.draftDays}
                            onChange={(d) => handleDraftChange(row.tenant.id, d)}
                          />
                        </div>
                      ) : (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span
                            className={s.badge}
                            style={{ background: 'rgba(37,99,235,0.08)', color: vars.color.primary }}
                          >
                            <Clock size={10} /> {currentDays} {currentDays === 1 ? 'dia' : 'dias'}
                          </span>
                          {row.saved && (
                            <span
                              className={s.badge}
                              style={{
                                background: 'rgba(34,197,94,0.1)',
                                color: vars.color.success,
                                fontSize: 10,
                              }}
                            >
                              Salvo
                            </span>
                          )}
                        </div>
                      )}
                    </td>
                    <td className={s.td}>
                      <div style={{ fontSize: 12, color: vars.color.textSecondary, maxWidth: 260 }}>
                        {tierInfo?.compliance ?? '—'}
                      </div>
                    </td>
                    <td className={s.td}>
                      {row.editing ? (
                        <div style={{ display: 'flex', gap: 6 }}>
                          <button
                            className={s.btnPrimary}
                            style={{ padding: '4px 10px', fontSize: 12 }}
                            disabled={row.saving}
                            onClick={() => handleSave(row.tenant.id, row.draftDays)}
                          >
                            <Save size={11} />
                            {row.saving ? 'Salvando…' : 'Salvar'}
                          </button>
                          <button
                            className={s.btnGhost}
                            style={{ padding: '4px 10px', fontSize: 12 }}
                            onClick={() => handleCancel(row.tenant.id)}
                          >
                            Cancelar
                          </button>
                        </div>
                      ) : (
                        <button
                          className={s.btnGhost}
                          style={{ padding: '4px 10px', fontSize: 12 }}
                          onClick={() => handleEdit(row.tenant.id)}
                        >
                          Editar
                        </button>
                      )}
                    </td>
                  </tr>
                )
              })}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={5} className={s.td} style={{ textAlign: 'center', color: vars.color.textSecondary }}>
                    Nenhum tenant encontrado.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
