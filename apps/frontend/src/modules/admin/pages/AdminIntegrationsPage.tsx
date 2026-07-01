import { KeyRound, Save } from 'lucide-react'
import { useEffect, useState } from 'react'
import { adminService } from '../services/adminService'
import * as s from '../components/admin.css'
import type { Integration } from '../types/admin'

export function AdminIntegrationsPage() {
  const [integrations, setIntegrations] = useState<Integration[]>([])
  const [loading, setLoading] = useState(true)
  const [editKey, setEditKey] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')
  const [saving, setSaving] = useState(false)
  const [fetchError, setFetchError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  useEffect(() => {
    adminService.getIntegrations()
      .then(setIntegrations)
      .catch(() => setFetchError('Não foi possível carregar as integrações.'))
      .finally(() => setLoading(false))
  }, [])

  function handleEdit(key: string) {
    setEditKey(key)
    setEditValue('')
    setSaveError(null)
    setSuccessMsg(null)
  }

  function handleCancel() {
    setEditKey(null)
    setEditValue('')
  }

  async function handleSave(key: string) {
    if (!editValue.trim()) return
    setSaving(true)
    setSaveError(null)
    try {
      await adminService.upsertIntegration(key, editValue.trim())
      setSuccessMsg(`Integração "${key}" salva com sucesso.`)
      setEditKey(null)
      setEditValue('')
      const updated = await adminService.getIntegrations()
      setIntegrations(updated)
    } catch {
      setSaveError(`Erro ao salvar "${key}".`)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className={s.pageRoot}>
      <div className={s.pageHeader}>
        <div>
          <div className={s.pageTitle}>Integrações</div>
          <div className={s.pageSubtitle}>Chaves de API e segredos de serviços externos</div>
        </div>
      </div>

      {fetchError && <div className={s.alertBanner.danger} style={{ marginBottom: 16 }}>{fetchError}</div>}
      {saveError && <div className={s.alertBanner.danger} style={{ marginBottom: 16 }}>{saveError}</div>}
      {successMsg && (
        <div className={s.alertBanner.info} style={{ marginBottom: 16 }}>{successMsg}</div>
      )}

      <div className={s.card}>
        <div className={s.cardTitle}>Segredos configurados</div>

        {loading ? (
          <div className={s.muted}>Carregando...</div>
        ) : integrations.length === 0 ? (
          <div className={s.muted}>Nenhuma integração configurada.</div>
        ) : (
          <table className={s.table} style={{ width: '100%' }}>
            <thead>
              <tr>
                <th className={s.th}>Chave</th>
                <th className={s.th}>Tenant</th>
                <th className={s.th}>Atualizado em</th>
                <th className={s.th}></th>
              </tr>
            </thead>
            <tbody>
              {integrations.map((intg) => (
                <tr key={intg.id} className={s.trHover}>
                  <td className={s.td}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <KeyRound size={13} />
                      <code className={s.mono}>{intg.key}</code>
                    </span>
                  </td>
                  <td className={s.td}>{intg.tenant_name ?? intg.tenant_id}</td>
                  <td className={s.td}>{new Date(intg.updated_at).toLocaleString('pt-BR')}</td>
                  <td className={s.td}>
                    {editKey === intg.key ? (
                      <span style={{ display: 'flex', gap: 6 }}>
                        <input
                          type="password"
                          placeholder="Novo valor"
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          className={s.input}
                          style={{ width: 220 }}
                          autoFocus
                        />
                        <button
                          className={s.btnPrimary}
                          onClick={() => handleSave(intg.key)}
                          disabled={saving || !editValue.trim()}
                        >
                          <Save size={13} /> Salvar
                        </button>
                        <button className={s.btnGhost} onClick={handleCancel}>Cancelar</button>
                      </span>
                    ) : (
                      <button className={s.btnGhost} onClick={() => handleEdit(intg.key)}>
                        Atualizar
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
