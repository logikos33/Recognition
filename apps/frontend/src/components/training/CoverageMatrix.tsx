import { useEffect, useMemo, useState } from 'react'

import { api } from '../../services/api'
import * as s from './CoverageMatrix.css'

// --- tipos do endpoint GET /api/training/coverage-matrix ---
interface Targets {
  images_per_class: number; cameras_per_class: number; max_camera_share: number
  floor_images: number; floor_cameras: number
}
interface Totals {
  boxes: number; images: number; boxes_in_rows: number; rows_match_export: boolean
  cameras_total: number; cameras_active: number; cameras_with_annotation: number
  classes_met: number; classes_active: number
}
interface ClassRow {
  class_id: number; class_name: string; color: string; display_order: number | null
  in_taxonomy: boolean; boxes: number; images: number; cameras_present: number
  max_camera_share: number; humana: number; auto_aprovada: number; status: string
}
interface CameraCol {
  camera_id: string; camera_name: string; is_active: boolean; images: number; boxes: number
  classes_present: number; days: number; last_annotation: string | null
  available_frames: number; classes_zero: string[]; classes_zero_count: number
}
interface Cell { class_id: number; camera_id: string; boxes: number; images: number }
interface Gap {
  class_id: number; class_name: string; camera_id: string; camera_name: string
  available_frames: number; score: number; reason: string
}
interface NeedsCollection { camera_id: string; camera_name: string; available_frames: number; boxes: number; reason: string }
interface Imbalance { ratio: number; high: { name: string; boxes: number }; low: { name: string; boxes: number } }
interface Warnings {
  orphan_boxes: number
  orphans: { class_id: number; class_name: string | null; camera_name: string; boxes: number }[]
  archived_excluded: { class_name: string; boxes: number }[]
}
interface CoverageData {
  targets: Targets; totals: Totals; classes: ClassRow[]; cameras: CameraCol[]
  matrix: Cell[]; gaps: Gap[]; needs_collection: NeedsCollection[]
  imbalance: Imbalance | null; warnings: Warnings
}

interface Props {
  /** Leva o Vitor direto para anotar aquela câmera (aba Imagens, não anotadas). */
  onAnnotateCamera: (cameraId: string) => void
  /** Leva direto pra aba "Classificar" (CropClassifier) já filtrada nessa
   * câmera, com o tipo dono de `classId` em destaque. Só nas lacunas
   * priorizadas (`gaps`) — sem este prop, a linha continua só com "anotar →". */
  onClassifyCell?: (cameraId: string, classId?: number) => void
}

function shortCode(name: string): string {
  const m = name.match(/(\d+)\s*$/)
  if (name.toLowerCase().startsWith('canal') && m) return m[1]
  if (m) return name.replace(/[^A-Z0-9]/gi, '').slice(0, 1).toUpperCase() + m[1]
  return name.slice(0, 3)
}

function heatClass(boxes: number): string {
  if (boxes === 0) return s.cellZero
  if (boxes < 10) return s.cellLow
  if (boxes < 50) return s.cellMid
  return s.cellHigh
}

export function CoverageMatrix({ onAnnotateCamera, onClassifyCell }: Props) {
  const [data, setData] = useState<CoverageData | null>(null)
  const [error, setError] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    api.get<{ success: boolean; data: CoverageData }>('/training/coverage-matrix')
      .then(res => { if (!cancelled) { setData(res.data); setError(false) } })
      .catch(() => { if (!cancelled) setError(true) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  const cellIndex = useMemo(() => {
    const m = new Map<string, Cell>()
    data?.matrix.forEach(c => m.set(`${c.class_id}|${c.camera_id}`, c))
    return m
  }, [data])

  if (loading) return <div className={s.state}>Carregando cobertura…</div>
  if (error || !data) return <div className={s.state}>Não foi possível carregar a matriz de cobertura.</div>

  const { targets: t, totals: tot, classes, cameras, gaps, needs_collection, imbalance, warnings } = data
  const humanaTotal = classes.reduce((n, c) => n + c.humana, 0)
  const autoTotal = classes.reduce((n, c) => n + c.auto_aprovada, 0)

  return (
    <div className={s.wrap}>
      <div className={s.header}>
        <div className={s.title}>Cobertura de anotação por câmera</div>
        <div className={s.subtitle}>
          Conta igual ao export de treino (só anotação humana/aprovada, sem classe arquivada).
          A célula vermelha é a informação mais valiosa: a classe que aquela câmera nunca viu.
        </div>
      </div>

      <div className={s.summary}>
        <span><span className={s.summaryStrong}>{tot.boxes}</span> caixas</span>
        <span><span className={s.summaryStrong}>{tot.images}</span> imagens</span>
        <span><span className={s.summaryStrong}>{humanaTotal}</span> humanas · {autoTotal} auto-aprovadas</span>
        <span><span className={s.summaryStrong}>{tot.cameras_with_annotation}</span>/{tot.cameras_active} câmeras com anotação</span>
        <span><span className={s.summaryStrong}>{tot.classes_met}</span>/{tot.classes_active} classes na meta</span>
      </div>

      <div className={s.subtitle}>
        Meta: ≥{t.images_per_class} imagens por classe, em ≥{t.cameras_per_class} câmeras,
        nenhuma câmera com mais de {Math.round(t.max_camera_share * 100)}% da classe.
      </div>

      {warnings.orphan_boxes > 0 && (
        <div className={`${s.banner} ${s.bannerDanger}`}>
          ⚠️ {warnings.orphan_boxes} caixa(s) órfã(s) — class_id não resolve, descartada(s) em silêncio pelo export:{' '}
          {warnings.orphans.map(o => `#${o.class_id}${o.class_name ? ` "${o.class_name}"` : ''} em ${o.camera_name} (${o.boxes})`).join(', ')}.
        </div>
      )}
      {warnings.archived_excluded.length > 0 && (
        <div className={`${s.banner} ${s.bannerWarn}`}>
          Classes arquivadas fora da contagem (confirmadas):{' '}
          {warnings.archived_excluded.map(a => `${a.class_name} (${a.boxes})`).join(', ')}.
        </div>
      )}
      {imbalance && (
        <div className={`${s.banner} ${s.bannerWarn}`}>
          Desbalanceamento {imbalance.ratio}×: {imbalance.high.name} tem {imbalance.high.boxes} caixas,
          {' '}{imbalance.low.name} tem {imbalance.low.boxes}. O modelo vai errar muito na classe menor.
        </div>
      )}
      {!tot.rows_match_export && (
        <div className={`${s.banner} ${s.bannerDanger}`}>
          ⚠️ A soma das linhas ({tot.boxes_in_rows}) não bate com o export ({tot.boxes}).
        </div>
      )}

      <div className={s.legend}>
        <span className={s.legendItem}><span className={`${s.swatch} ${s.cellZero}`} />zero (nunca anotada)</span>
        <span className={s.legendItem}><span className={`${s.swatch} ${s.cellLow}`} />1–9</span>
        <span className={s.legendItem}><span className={`${s.swatch} ${s.cellMid}`} />10–49</span>
        <span className={s.legendItem}><span className={`${s.swatch} ${s.cellHigh}`} />50+</span>
      </div>

      <div className={s.scroll}>
        <table className={s.table}>
          <thead>
            <tr>
              <th className={s.cornerTh}>Classe \ Câmera</th>
              {cameras.map(cam => (
                <th
                  key={cam.camera_id}
                  className={`${s.camTh} ${cam.is_active ? '' : s.camThInactive}`}
                  title={`${cam.camera_name} · ${cam.images} img · ${cam.boxes} caixas · ${cam.classes_zero_count} classe(s) zerada(s)${cam.is_active ? '' : ' · inativa'}`}
                  onClick={() => onAnnotateCamera(cam.camera_id)}
                >
                  <div className={s.camCode}>{shortCode(cam.camera_name)}</div>
                  <div className={s.camMeta}>{cam.images}</div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {classes.map(cls => {
              const imgOk = cls.images >= t.images_per_class
              const camOk = cls.cameras_present >= t.cameras_per_class
              const shareBad = cls.max_camera_share > t.max_camera_share
              return (
                <tr key={cls.class_id} className={cls.in_taxonomy ? '' : s.stragglerRow}>
                  <td className={s.classTd}>
                    <div className={s.classNameRow}>
                      <span className={s.dot} style={{ background: cls.color }} />
                      <span className={s.classLabel}>{cls.class_name}</span>
                      {!cls.in_taxonomy && <span className={s.chip}>fora da taxonomia (D-103)</span>}
                    </div>
                    {cls.in_taxonomy && (
                      <div className={s.chips}>
                        <span className={`${s.chip} ${imgOk ? s.chipOk : cls.images < t.floor_images ? s.chipBad : s.chipWarn}`}>
                          {cls.images}/{t.images_per_class} img
                        </span>
                        <span className={`${s.chip} ${camOk ? s.chipOk : cls.cameras_present < t.floor_cameras ? s.chipBad : s.chipWarn}`}>
                          {cls.cameras_present}/{t.cameras_per_class} câm
                        </span>
                        <span className={`${s.chip} ${shareBad ? s.chipWarn : s.chipOk}`}>
                          {Math.round(cls.max_camera_share * 100)}% máx
                        </span>
                      </div>
                    )}
                  </td>
                  {cameras.map(cam => {
                    const c = cellIndex.get(`${cls.class_id}|${cam.camera_id}`)
                    const boxes = c ? c.boxes : 0
                    return (
                      <td
                        key={cam.camera_id}
                        className={`${s.cell} ${heatClass(boxes)}`}
                        title={`${cls.class_name} · ${cam.camera_name}: ${boxes} caixas${c ? ` em ${c.images} imagens` : ' — ir anotar'}`}
                        onClick={() => onAnnotateCamera(cam.camera_id)}
                      >
                        {boxes > 0 ? boxes : ''}
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <div className={s.panels}>
        <div className={s.panel}>
          <div className={s.panelTitle}>Onde anotar primeiro — as 10 lacunas que mais destravam</div>
          {gaps.length === 0 && <div className={s.subtitle}>Sem lacunas prioritárias.</div>}
          {gaps.map((g, i) => (
            <div key={`${g.class_id}-${g.camera_id}-${i}`} className={s.gapRow} onClick={() => onAnnotateCamera(g.camera_id)}>
              <div className={s.gapLeft}>
                <span className={s.gapClass}>{g.class_name} → {g.camera_name}</span>
                <span className={s.gapReason}>{g.reason} · {g.available_frames} frames disponíveis</span>
              </div>
              <span className={s.gapCtaGroup}>
                {onClassifyCell && (
                  <span
                    className={s.gapCtaSecondary}
                    onClick={e => { e.stopPropagation(); onClassifyCell(g.camera_id, g.class_id) }}
                  >
                    classificar →
                  </span>
                )}
                <span className={s.gapCta}>anotar →</span>
              </span>
            </div>
          ))}
        </div>

        <div className={s.panel}>
          <div className={s.panelTitle}>Câmeras para voltar a coletar ({needs_collection.length})</div>
          <div className={s.subtitle} style={{ marginBottom: 8 }}>
            Ativas cujo material raso esgota antes da meta — sem coleta nova, a lacuna vira diagnóstico sem remédio.
          </div>
          {needs_collection.map(c => (
            <div key={c.camera_id} className={s.gapRow} onClick={() => onAnnotateCamera(c.camera_id)}>
              <div className={s.gapLeft}>
                <span className={s.gapClass}>{c.camera_name}</span>
                <span className={s.gapReason}>{c.reason} · {c.available_frames} frames disponíveis</span>
              </div>
              <span className={s.gapCta}>ver →</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
