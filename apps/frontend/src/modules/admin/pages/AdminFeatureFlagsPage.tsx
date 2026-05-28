import { useEffect, useState } from 'react'
import { adminService } from '../services/adminService'
import * as s from '../components/admin.css'
import type { FeatureFlag } from '../types/admin'

export function AdminFeatureFlagsPage() {
  const [flags, setFlags] = useState<FeatureFlag[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState<string | null>(null)

  useEffect(() => {
    adminService.getFeatureFlags()
      .then(setFlags)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const toggle = async (flag: FeatureFlag) => {
    setSaving(flag.flag_key)
    try {
      await adminService.updateFeatureFlag(flag.flag_key, !flag.flag_value)
      setFlags((prev) => prev.map((f) => f.flag_key === flag.flag_key ? { ...f, flag_value: !f.flag_value } : f))
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Erro ao atualizar flag')
    } finally { setSaving(null) }
  }

  return (
    <div className={s.pageRoot}>
      <div className={s.pageHeader}>
        <div>
          <div className={s.pageTitle}>Feature Flags</div>
          <div className={s.pageSubtitle}>Flags globais da plataforma</div>
        </div>
      </div>

      {error && <div className={s.alertBanner.danger}>{error}</div>}

      <div className={s.card}>
        {loading ? <div className={s.muted}>Carregando...</div> : (
          <table className={s.table}>
            <thead>
              <tr>
                <th className={s.th}>Flag</th>
                <th className={s.th}>Descrição</th>
                <th className={s.th}>Última atualização</th>
                <th className={s.th}>Valor</th>
              </tr>
            </thead>
            <tbody>
              {flags.map((f) => (
                <tr key={f.flag_key}>
                  <td className={s.td}><span className={s.mono}>{f.flag_key}</span></td>
                  <td className={s.td}><span className={s.muted}>{f.description ?? '—'}</span></td>
                  <td className={s.td}><span className={s.muted}>{f.updated_at ? new Date(f.updated_at).toLocaleDateString('pt-BR') : '—'}</span></td>
                  <td className={s.td}>
                    <button
                      className={f.flag_value ? s.btnPrimary : s.btnGhost}
                      style={{ fontSize: 11, padding: '3px 12px' }}
                      disabled={saving === f.flag_key}
                      onClick={() => toggle(f)}
                    >
                      {f.flag_value ? 'Ativo' : 'Inativo'}
                    </button>
                  </td>
                </tr>
              ))}
              {flags.length === 0 && (
                <tr><td colSpan={4} className={s.td} style={{ textAlign: 'center' }}><span className={s.muted}>Nenhuma flag cadastrada</span></td></tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
