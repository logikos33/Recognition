/**
 * Monitor Andon — exibição fullscreen sem autenticação JWT.
 * Acesso restrito por IP interno (validado no backend).
 * Polling a cada 15s. Flash vermelho em NOK. Status CEP com cores.
 */
import { useState, useEffect, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { qualityService } from '../services/qualityService'
import type { AndonData } from '../types/quality'

export function QualityAndonDisplay() {
  const { cameraId } = useParams<{ cameraId: string }>()
  const [data, setData] = useState<AndonData | null>(null)
  const [flash, setFlash] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastResult, setLastResult] = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    if (!cameraId) return
    try {
      const res = await qualityService.getAndon(cameraId)
      const newData = res.data

      // Flash vermelho se último resultado mudou para NOK
      if (newData.last_result === 'nok' && lastResult !== 'nok') {
        setFlash(true)
        setTimeout(() => setFlash(false), 1500)
      }

      setLastResult(newData.last_result)
      setData(newData)
      setError(null)
    } catch {
      setError('Erro de comunicação com o servidor')
    }
  }, [cameraId, lastResult])

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 15_000)
    return () => clearInterval(interval)
  }, [fetchData])

  const nokRatePct = data ? (data.nok_rate_1h * 100).toFixed(1) : '—'
  const cepColor =
    data?.cep_status === 'out_of_control'
      ? '#EF5350'
      : data?.cep_status === 'in_control'
      ? '#43D186'
      : '#888'

  return (
    <div
      style={{
        minHeight: '100vh',
        background: flash ? '#3a0a0a' : '#0a0a0a',
        transition: 'background 0.3s ease',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        fontFamily: 'monospace',
        color: '#fff',
        padding: '32px',
      }}
    >
      {error ? (
        <div style={{ color: '#EF5350', fontSize: '18px' }}>{error}</div>
      ) : (
        <>
          <div style={{ fontSize: '14px', color: '#555', marginBottom: '8px', letterSpacing: '0.1em' }}>
            ANDON MONITOR
          </div>
          <div style={{ fontSize: '22px', fontWeight: 700, color: '#aaa', marginBottom: '32px' }}>
            {data?.camera_name ?? cameraId}
          </div>

          {/* Status principal */}
          <div
            style={{
              fontSize: '96px',
              fontWeight: 900,
              color: data?.last_result === 'nok' ? '#EF5350' : data?.last_result === 'ok' ? '#43D186' : '#555',
              lineHeight: 1,
              marginBottom: '24px',
              letterSpacing: '-4px',
            }}
          >
            {data?.last_result?.toUpperCase() ?? '—'}
          </div>

          {/* Métricas */}
          <div style={{ display: 'flex', gap: '48px', marginBottom: '32px' }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '48px', fontWeight: 700, color: '#43D186' }}>{data?.total_ok ?? '—'}</div>
              <div style={{ fontSize: '12px', color: '#555', letterSpacing: '0.1em' }}>APROVADOS</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '48px', fontWeight: 700, color: '#EF5350' }}>{data?.total_nok ?? '—'}</div>
              <div style={{ fontSize: '12px', color: '#555', letterSpacing: '0.1em' }}>REPROVADOS</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '48px', fontWeight: 700, color: '#FFB74D' }}>{nokRatePct}%</div>
              <div style={{ fontSize: '12px', color: '#555', letterSpacing: '0.1em' }}>TAXA NOK/1H</div>
            </div>
          </div>

          {/* Status CEP */}
          <div
            style={{
              fontSize: '16px',
              fontWeight: 600,
              color: cepColor,
              padding: '8px 24px',
              border: `2px solid ${cepColor}`,
              borderRadius: '4px',
              letterSpacing: '0.1em',
              marginBottom: '32px',
            }}
          >
            {data?.cep_status === 'out_of_control'
              ? '⚠ PROCESSO FORA DE CONTROLE'
              : data?.cep_status === 'in_control'
              ? '✓ PROCESSO EM CONTROLE'
              : 'CEP: SEM BASELINE'}
          </div>

          {/* Últimas inspeções */}
          {data && data.recent_inspections.length > 0 && (
            <div style={{ display: 'flex', gap: '8px' }}>
              {data.recent_inspections.slice(-5).map((insp, i) => (
                <div
                  key={i}
                  style={{
                    width: '40px',
                    height: '40px',
                    borderRadius: '4px',
                    background: insp.result === 'ok' ? 'rgba(67,209,134,0.2)' : 'rgba(239,83,80,0.2)',
                    border: `2px solid ${insp.result === 'ok' ? '#43D186' : '#EF5350'}`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '14px',
                    fontWeight: 700,
                    color: insp.result === 'ok' ? '#43D186' : '#EF5350',
                  }}
                >
                  {insp.result === 'ok' ? '✓' : '✗'}
                </div>
              ))}
            </div>
          )}

          <div style={{ marginTop: '32px', fontSize: '11px', color: '#333' }}>
            Atualizado a cada 15s · {new Date().toLocaleTimeString('pt-BR')}
          </div>
        </>
      )}
    </div>
  )
}
