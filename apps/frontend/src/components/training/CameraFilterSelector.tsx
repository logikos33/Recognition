/**
 * CameraFilterSelector — seletor recolhido de câmera do filtro de
 * treinamento (multi-seleção via checkbox, popover).
 *
 * Substitui a parede de pílulas (1 botão por câmera) que virou ilegível com
 * 29 câmeras (8 ativas + 21 draft) — ver TrainingGallery.tsx.
 *
 * Convenção de seleção vazia = "todas" (nenhum filtro de câmera aplicado),
 * mesma regra usada no resto da galeria. "Todas" marca cada checkbox
 * individualmente (ponto de partida útil pra depois desmarcar só algumas);
 * "Nenhuma" desmarca tudo — o que, por essa convenção, volta ao estado sem
 * filtro (mesmo resultado de não ter marcado nada nunca).
 */
import { useMemo, useState } from 'react'
import { ChevronDown, Search } from 'lucide-react'
import { Popover } from '../ui/Popover/Popover'
import * as s from './CameraFilterSelector.css'

export interface CameraFilterOption {
  cameraId: string
  /** Número do canal — critério de ordenação da lista (requisito 2). */
  channel: number
  name: string | null
  /** Contagem de frames já filtrada pelas outras dimensões ativas (facetas
   * cruzadas — câmera sem frame no filtro atual mostra 0, nunca some). */
  count: number
}

interface CameraFilterSelectorProps {
  cameras: CameraFilterOption[]
  selected: Set<string>
  onChange: (next: Set<string>) => void
  /** Busca por nome/canal aparece só acima deste total de câmeras. */
  searchThreshold?: number
}

export function CameraFilterSelector({
  cameras,
  selected,
  onChange,
  searchThreshold = 15,
}: CameraFilterSelectorProps) {
  const [query, setQuery] = useState('')
  const sorted = useMemo(() => [...cameras].sort((a, b) => a.channel - b.channel), [cameras])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return sorted
    return sorted.filter(
      c => (c.name || '').toLowerCase().includes(q) || String(c.channel).includes(q),
    )
  }, [sorted, query])

  const triggerLabel = useMemo(() => {
    if (selected.size === 0) return 'todas'
    if (selected.size === 1) {
      const [onlyId] = selected
      const only = sorted.find(c => c.cameraId === onlyId)
      return only ? only.name || `Canal ${only.channel}` : '1 selecionada'
    }
    return `${selected.size} selecionadas`
  }, [selected, sorted])

  function toggle(id: string) {
    const next = new Set(selected)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    onChange(next)
  }

  return (
    <Popover
      align="start"
      trigger={
        <button type="button" className={s.trigger}>
          <span>Câmera: {triggerLabel}</span>
          <ChevronDown size={14} aria-hidden="true" />
        </button>
      }
    >
      <div className={s.panel}>
        {sorted.length > searchThreshold && (
          <div className={s.searchWrap}>
            <Search size={13} className={s.searchIcon} aria-hidden="true" />
            <input
              type="text"
              className={s.searchInput}
              placeholder="Buscar por nome ou canal..."
              value={query}
              onChange={e => setQuery(e.target.value)}
            />
          </div>
        )}
        <div className={s.quickActions}>
          <button
            type="button"
            className={s.quickAction}
            onClick={() => onChange(new Set(sorted.map(c => c.cameraId)))}
          >
            Todas
          </button>
          <button type="button" className={s.quickAction} onClick={() => onChange(new Set())}>
            Nenhuma
          </button>
        </div>
        <div className={s.list}>
          {filtered.length === 0 ? (
            <p className={s.empty}>Nenhuma câmera encontrada.</p>
          ) : (
            filtered.map(cam => (
              <label key={cam.cameraId} className={s.row}>
                <span className={s.rowLeft}>
                  <input
                    type="checkbox"
                    className={s.checkbox}
                    checked={selected.has(cam.cameraId)}
                    onChange={() => toggle(cam.cameraId)}
                  />
                  <span className={s.channel}>{cam.channel || '—'}</span>
                  <span className={s.name}>{cam.name || '—'}</span>
                </span>
                <span className={s.count}>{cam.count.toLocaleString('pt-BR')}</span>
              </label>
            ))
          )}
        </div>
      </div>
    </Popover>
  )
}
