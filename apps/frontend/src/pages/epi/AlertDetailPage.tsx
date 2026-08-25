/**
 * AlertDetailPage — /epi/alerts/:alertId. O deep-link do evento: LEVA AO ACONTECIDO.
 *
 * Mostra o FRAME INTEIRO da evidência com a bbox no LUGAR EXATO (projetada do
 * `bbox` em PIXELS do frame original que o edge gravou), a câmera, a hora REAL de captura
 * (`alerts.timestamp`, que nenhuma outra tela usava) e classe + confiança de
 * cada violação. Substitui o modal sem URL cuja caixa era hardcoded.
 */
import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../../services/api'
import { vars } from '../../styles/theme.css'
import { labelForClass } from '../../utils/labels'
import { Button } from '../../components/ui/Button/Button'
import { LoadingSpinner } from '../../components/shared/LoadingSpinner'
import { ProcedenciaBadge } from '../../components/shared/ProcedenciaBadge'
import { page, pageHeader, pageTitle, emptyBox } from '../AlertsHistoryPage.css'

type Bbox = [number, number, number, number]
interface Violation { class: string; confidence: number; bbox?: Bbox; bbox_unidade?: string }

/** Única unidade de bbox que esta tela sabe projetar (contrato de domain/detectors/base.py). */
export const BBOX_PIXELS = 'pixels_xywh_frame_original'
interface AlertDetail {
  id: string
  camera_id: string | null
  camera_name?: string | null
  violations: Violation[]
  acknowledged: boolean
  captured_at: string | null
  created_at?: string | null
  evidence_url: string | null
  evidence_key?: string | null
}

/**
 * bbox = [x, y, w, h] em PIXELS do frame ORIGINAL (canto superior-esquerdo, NÃO centro)
 * → caixa em % sobre a <img>. O alerta não carrega width/height do frame, então as
 * dimensões vêm da própria imagem carregada (naturalWidth/naturalHeight).
 * Exportada para teste: é a única lógica não-trivial da tela.
 */
export function boxStyle([x, y, w, h]: Bbox, natW: number, natH: number) {
  // toFixed(4) só apara o ruído binário; 4 casas em % é sub-pixel em qualquer frame.
  const pct = (n: number, total: number) => `${+((n / total) * 100).toFixed(4)}%`
  return {
    left: pct(x, natW),
    top: pct(y, natH),
    width: pct(w, natW),
    height: pct(h, natH),
  }
}

export function AlertDetailPage() {
  const { alertId } = useParams<{ alertId: string }>()
  const navigate = useNavigate()
  const [alert, setAlert] = useState<AlertDetail | null>(null)
  const [loading, setLoading] = useState(true)
  // Dimensões do frame ORIGINAL: só existem depois que a <img> carrega.
  const [natural, setNatural] = useState<{ w: number; h: number } | null>(null)

  useEffect(() => {
    let alive = true
    setLoading(true)
    // Frame novo = dimensões novas; sem isto a caixa do próximo alerta cairia
    // projetada nas dimensões do frame anterior até a <img> carregar.
    setNatural(null)
    api.get<{ data?: { alert: AlertDetail } }>(`/alerts/${alertId}`)
      .then(res => { if (alive) setAlert(res.data?.alert ?? null) })
      .catch(() => { if (alive) setAlert(null) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [alertId])

  // Só desenha o que sabemos projetar. Unidade ausente/estranha = origem desconhecida:
  // melhor nenhuma caixa que caixa mentirosa.
  const drawable = (alert?.violations ?? []).filter(v => v.bbox && v.bbox_unidade === BBOX_PIXELS)
  const unknownUnit = (alert?.violations ?? []).filter(v => v.bbox && v.bbox_unidade !== BBOX_PIXELS)

  return (
    <div className={page}>
      <div className={pageHeader}>
        <h2 className={pageTitle}>Detalhe do Alerta</h2>
        <Button size="sm" variant="secondary" onClick={() => navigate('/epi/alerts')}>
          Voltar ao histórico
        </Button>
      </div>

      {loading ? <LoadingSpinner /> : !alert ? (
        <div className={emptyBox}>Alerta não encontrado</div>
      ) : (
        <>
          {alert.evidence_url ? (
            <div style={{
              position: 'relative', display: 'inline-block', maxWidth: '960px',
              width: '100%', borderRadius: '8px', overflow: 'hidden',
              border: `1px solid ${vars.color.borderDefault}`,
            }}>
              <img src={alert.evidence_url} alt="Frame da evidência"
                   style={{ width: '100%', display: 'block' }}
                   onLoad={e => {
                     const img = e.currentTarget
                     if (img.naturalWidth > 0 && img.naturalHeight > 0) {
                       setNatural({ w: img.naturalWidth, h: img.naturalHeight })
                     }
                   }} />
              {natural && drawable.map((v, i) => (
                <div key={i} data-testid="violation-box"
                     style={{
                       position: 'absolute', ...boxStyle(v.bbox as Bbox, natural.w, natural.h),
                       border: `3px solid ${vars.color.danger}`, borderRadius: '4px',
                       pointerEvents: 'none',
                     }}>
                  <span style={{
                    position: 'absolute', top: '-22px', left: '-2px',
                    background: vars.color.danger, color: vars.color.textOnPrimary,
                    fontSize: '11px', padding: '2px 6px', borderRadius: '3px',
                    whiteSpace: 'nowrap',
                  }}>
                    {labelForClass(v.class)} — {(v.confidence * 100).toFixed(0)}%
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className={emptyBox}>Sem imagem de evidência para este evento</div>
          )}

          {alert.evidence_url && alert.violations.every(v => !v.bbox) && (
            <p style={{ color: vars.color.warning, fontSize: '13px', marginTop: '8px' }}>
              Evento sem coordenadas gravadas — frame exibido sem marcação.
            </p>
          )}

          {alert.evidence_url && unknownUnit.length > 0 && (
            <p style={{ color: vars.color.warning, fontSize: '13px', marginTop: '8px' }}>
              Coordenadas de origem desconhecida — caixa não desenhada para{' '}
              {unknownUnit.length === 1 ? '1 violação' : `${unknownUnit.length} violações`}.
            </p>
          )}

          <div style={{
            display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px',
            marginTop: '16px', color: vars.color.textPrimary, fontSize: '14px',
          }}>
            <div>
              <strong style={{ color: vars.color.textMuted }}>Câmera:</strong>{' '}
              {alert.camera_name ?? '—'}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span>
                <strong style={{ color: vars.color.textMuted }}>Captura:</strong>{' '}
                {alert.captured_at ? new Date(alert.captured_at).toLocaleString('pt-BR') : '—'}
              </span>
              {/* A tela do ACONTECIDO é justamente onde a distância entre a
                  captura e a gravação precisa aparecer: sem isto o detalhe
                  mostra uma hora antiga sem dizer que o evento é de coleta
                  retroativa. Mesmo componente do histórico e do dashboard. */}
              <ProcedenciaBadge
                capturadoEm={alert.captured_at}
                gravadoEm={alert.created_at}
              />
            </div>
          </div>

          <ul style={{
            marginTop: '12px', paddingLeft: '18px',
            color: vars.color.textPrimary, fontSize: '14px',
          }}>
            {alert.violations.map((v, i) => (
              <li key={i}>{labelForClass(v.class)} — {(v.confidence * 100).toFixed(0)}%</li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}

export default AlertDetailPage
