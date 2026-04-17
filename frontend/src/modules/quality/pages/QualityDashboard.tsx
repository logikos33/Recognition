/**
 * Dashboard principal do módulo de qualidade.
 * KPI cards + últimas 10 NOK + pareto de defeitos + métricas de turno.
 */
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { qualityService } from '../services/qualityService'
import { ShiftMetricsBar } from '../components/ShiftMetricsBar'
import { DefectPareto } from '../components/DefectPareto'
import { InspectionCard } from '../components/InspectionCard'
import { useShiftMetrics } from '../hooks/useShiftMetrics'
import { useQualityWebSocket } from '../hooks/useQualityWebSocket'
import { card, cardHeader, cardTitle, cardValue } from '../components/quality.css'
import type { QualityInspection, QualityCamera, QualityClass, ShiftReport } from '../types/quality'

export function QualityDashboard() {
  const navigate = useNavigate()
  const [recentNok, setRecentNok] = useState<QualityInspection[]>([])
  const [cameras, setCameras] = useState<QualityCamera[]>([])
  const [classes, setClasses] = useState<QualityClass[]>([])
  const [shiftReport, setShiftReport] = useState<ShiftReport | null>(null)
  const [loading, setLoading] = useState(true)

  const { summary } = useShiftMetrics()
  const { lastInspection } = useQualityWebSocket()

  useEffect(() => {
    async function init() {
      try {
        const [nokRes, camsRes, clsRes, reportRes] = await Promise.allSettled([
          qualityService.getInspections({ result: 'nok', per_page: 10, page: 1 }),
          qualityService.getCameras(),
          qualityService.getClasses(),
          qualityService.getShiftReport(),
        ])

        if (nokRes.status === 'fulfilled') setRecentNok(nokRes.value.data.inspections ?? [])
        if (camsRes.status === 'fulfilled') setCameras(camsRes.value.data.cameras ?? [])
        if (clsRes.status === 'fulfilled') setClasses(clsRes.value.data.classes ?? [])
        if (reportRes.status === 'fulfilled') setShiftReport(reportRes.value.data)
      } catch { /* silent */ }
      setLoading(false)
    }
    init()
  }, [])

  // Atualizar lista de NOK quando chega nova inspeção via WebSocket
  useEffect(() => {
    if (!lastInspection || lastInspection.result !== 'nok') return
    setRecentNok(prev => {
      const updated: QualityInspection = {
        id: lastInspection.inspection_id,
        camera_id: lastInspection.camera_id,
        result: 'nok',
        defect_class: lastInspection.defect_class,
        defect_category: null,
        confidence: lastInspection.confidence,
        evidence_r2_key: null,
        production_order: null,
        product_type: null,
        shift: 'morning',
        clip_status: 'pending',
        clip_r2_key: null,
        clip_start: null,
        clip_end: null,
        is_first_ok_of_order: false,
        rolling_nok_rate_1h: lastInspection.nok_rate_1h,
        rolling_nok_rate_8h: null,
        is_cep_alert: false,
        feedback_status: 'pending',
        feedback_by: null,
        feedback_at: null,
        feedback_notes: null,
        annotation_status: null,
        created_at: lastInspection.timestamp,
      }
      return [updated, ...prev.slice(0, 9)]
    })
  }, [lastInspection])

  if (loading) return <div style={{ padding: '32px', color: '#888' }}>Carregando dashboard…</div>

  const classLabels = Object.fromEntries((classes ?? []).map(c => [c.id, c.label]))

  return (
    <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Métricas de turno */}
      <section>
        <div className={cardHeader} style={{ marginBottom: '12px' }}>
          <span className={cardTitle}>Turno Atual</span>
        </div>
        <ShiftMetricsBar summary={summary} />
      </section>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
        {/* Câmeras ativas */}
        <div className={card}>
          <div className={cardHeader}>
            <span className={cardTitle}>Câmeras ({cameras.length})</span>
            <button
              onClick={() => navigate('/quality/cameras')}
              style={{ fontSize: '11px', color: '#4FC3F7', background: 'none', border: 'none', cursor: 'pointer' }}
            >
              Ver todas →
            </button>
          </div>
          {cameras.length === 0 ? (
            <div style={{ fontSize: '13px', color: '#888' }}>
              Nenhuma câmera configurada.{' '}
              <button onClick={() => navigate('/quality/cameras')} style={{ color: '#4FC3F7', background: 'none', border: 'none', cursor: 'pointer', fontSize: '13px' }}>
                Adicionar câmera
              </button>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {cameras.slice(0, 5).map(cam => (
                <div
                  key={cam.id}
                  style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid #1a1a1a' }}
                >
                  <span style={{ fontSize: '13px', fontWeight: 500 }}>{cam.name}</span>
                  <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                    {cam.is_setup_mode && (
                      <span style={{ fontSize: '10px', color: '#FFB74D', fontWeight: 600 }}>SETUP</span>
                    )}
                    <span style={{ fontSize: '11px', color: '#888' }}>{cam.production_order ?? '—'}</span>
                  </div>
                </div>
              ))}
              {cameras.length > 5 && (
                <div style={{ fontSize: '12px', color: '#888', textAlign: 'center' }}>
                  +{cameras.length - 5} câmeras
                </div>
              )}
            </div>
          )}
        </div>

        {/* Pareto de defeitos */}
        <div className={card}>
          <div className={cardHeader}>
            <span className={cardTitle}>Pareto de Defeitos (Turno)</span>
          </div>
          <DefectPareto
            pareto={shiftReport?.defect_pareto ?? []}
            classLabels={classLabels}
          />
        </div>
      </div>

      {/* Últimas NOK */}
      <section>
        <div className={cardHeader} style={{ marginBottom: '12px' }}>
          <span className={cardTitle}>Últimas NOK</span>
          <button
            onClick={() => navigate('/quality/inspections?result=nok')}
            style={{ fontSize: '11px', color: '#4FC3F7', background: 'none', border: 'none', cursor: 'pointer' }}
          >
            Ver todas →
          </button>
        </div>

        {recentNok.length === 0 ? (
          <div style={{ fontSize: '13px', color: '#888' }}>Nenhuma inspeção NOK recente.</div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: '12px' }}>
            {recentNok.map(insp => (
              <InspectionCard
                key={insp.id}
                inspection={insp}
                classes={classes}
                onClick={() => navigate(`/quality/inspections/${insp.id}`)}
              />
            ))}
          </div>
        )}
      </section>

      {/* Totais do turno */}
      {shiftReport && (
        <section>
          <div className={cardHeader} style={{ marginBottom: '12px' }}>
            <span className={cardTitle}>Resumo do Turno</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px' }}>
            <div className={card} style={{ textAlign: 'center' }}>
              <div className={cardValue} style={{ color: '#43D186' }}>{shiftReport.total_ok.toLocaleString()}</div>
              <div style={{ fontSize: '12px', color: '#888', marginTop: '4px' }}>Aprovados</div>
            </div>
            <div className={card} style={{ textAlign: 'center' }}>
              <div className={cardValue} style={{ color: '#EF5350' }}>{shiftReport.total_nok.toLocaleString()}</div>
              <div style={{ fontSize: '12px', color: '#888', marginTop: '4px' }}>Reprovados</div>
            </div>
            <div className={card} style={{ textAlign: 'center' }}>
              <div className={cardValue} style={{ color: '#FFB74D' }}>{(shiftReport.nok_rate * 100).toFixed(2)}%</div>
              <div style={{ fontSize: '12px', color: '#888', marginTop: '4px' }}>Taxa NOK</div>
            </div>
          </div>
        </section>
      )}
    </div>
  )
}
