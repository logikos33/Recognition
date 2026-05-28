import { X } from 'lucide-react'
import { useState } from 'react'
import * as s from './admin.css'
import type { Announcement, AnnouncementType } from '../types/admin'

const typeToVariant: Record<AnnouncementType, keyof typeof s.alertBanner> = {
  info:        'info',
  maintenance: 'maintenance',
  feature:     'info',
  security:    'danger',
}

const typeLabel: Record<AnnouncementType, string> = {
  info:        'Informativo',
  maintenance: 'Manutenção',
  feature:     'Novidade',
  security:    'Segurança',
}

export function AnnouncementBanner({ announcement }: { announcement: Announcement }) {
  const [dismissed, setDismissed] = useState(false)
  if (dismissed) return null

  const variant = typeToVariant[announcement.type]

  return (
    <div className={s.alertBanner[variant]} style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
      <div style={{ flex: 1 }}>
        <span style={{ fontWeight: 600, marginRight: 6 }}>[{typeLabel[announcement.type]}]</span>
        <strong>{announcement.title}</strong>
        {announcement.content && <div style={{ marginTop: 2, fontSize: 12 }}>{announcement.content}</div>}
      </div>
      <button
        onClick={() => setDismissed(true)}
        style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 2, opacity: 0.6 }}
      >
        <X size={14} />
      </button>
    </div>
  )
}
