/**
 * ThresholdsModal — limiares editáveis na própria página (GET/PUT
 * /monitoring/sites/<id>/thresholds). O semáforo e os badges usam
 * estes valores; defaults do cliente quando o GET vier vazio.
 */
import { useEffect, useState } from 'react'
import { Modal } from '../../components/ui/Modal/Modal'
import { Button } from '../../components/ui/Button/Button'
import { Field, Input } from '../../components/ui/Input/Input'
import type { MonitoringThresholds } from '../../types/monitoring'
import { EXPECTED_POWER_MODE } from './health'
import * as s from './monitoring.css'

type NumericKey = Exclude<keyof MonitoringThresholds, 'alert_power_mode'>

const FIELDS: { key: NumericKey; label: string }[] = [
  { key: 'ram_pct_warn', label: 'RAM — atenção (%)' },
  { key: 'ram_pct_crit', label: 'RAM — crítico (%)' },
  { key: 'temp_warn_c', label: 'Temperatura — atenção (°C)' },
  { key: 'temp_crit_c', label: 'Temperatura — crítico (°C)' },
  { key: 'disk_min_free_gb', label: 'Disco livre mínimo (GB)' },
  { key: 'heartbeat_max_min', label: 'Sem detecção — alerta (min)' },
  { key: 'gw_loss_warn_pct', label: 'Perda no gateway — atenção (%)' },
  { key: 'api_rtt_warn_ms', label: 'RTT da API — atenção (ms)' },
  { key: 'restarts_warn', label: 'Restarts de unit — atenção' },
  { key: 'swap_warn_pct', label: 'Swap — atenção (%)' },
]

interface ThresholdsModalProps {
  open: boolean
  initial: MonitoringThresholds
  saving: boolean
  onSave: (values: MonitoringThresholds) => void
  onClose: () => void
}

export function ThresholdsModal({ open, initial, saving, onSave, onClose }: ThresholdsModalProps) {
  const [form, setForm] = useState<Record<NumericKey, string>>(() => toForm(initial))
  const [alertPowerMode, setAlertPowerMode] = useState(initial.alert_power_mode)

  useEffect(() => {
    if (open) {
      setForm(toForm(initial))
      setAlertPowerMode(initial.alert_power_mode)
    }
  }, [open, initial])

  const handleSave = () => {
    const values: MonitoringThresholds = { ...initial, alert_power_mode: alertPowerMode }
    for (const { key } of FIELDS) {
      const n = Number(form[key])
      if (Number.isFinite(n) && n >= 0) values[key] = n
    }
    onSave(values)
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Limiares de alerta"
      maxWidth="560px"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={saving}>Cancelar</Button>
          <Button variant="primary" onClick={handleSave} loading={saving}>Salvar</Button>
        </>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <p className={s.muted} style={{ margin: 0 }}>
          O semáforo e os badges desta página usam estes valores. Campos vazios
          ou inválidos mantêm o valor anterior.
        </p>
        <div className={s.thresholdsGrid}>
          {FIELDS.map(({ key, label }) => (
            <Field key={key} label={label}>
              <Input
                type="number"
                inputMode="decimal"
                min={0}
                value={form[key]}
                onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
              />
            </Field>
          ))}
        </div>
        <label className={s.checkboxRow}>
          <input
            type="checkbox"
            checked={alertPowerMode}
            onChange={(e) => setAlertPowerMode(e.target.checked)}
          />
          Alertar quando o power mode for diferente de {EXPECTED_POWER_MODE}
        </label>
      </div>
    </Modal>
  )
}

function toForm(t: MonitoringThresholds): Record<NumericKey, string> {
  const out = {} as Record<NumericKey, string>
  for (const { key } of FIELDS) out[key] = String(t[key])
  return out
}
