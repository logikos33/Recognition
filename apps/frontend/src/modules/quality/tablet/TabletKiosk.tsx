/**
 * TabletKiosk — wrapper principal do tablet de bancada do Quality Gate.
 *
 * Rota pública (/tablet/:station) — sem JWT, acesso restrito por IP interno.
 * Recebe o código da bancada via URL param (bench_a | bench_b).
 *
 * Máquina de estados da view:
 *   idle         → nenhuma peça na bancada
 *   identified   → peça identificada, aguardando operador iniciar inspeção
 *   validating   → inspeção YOLO em andamento
 *   ok           → inspeção aprovada (auto-avança após 3s)
 *   nok          → inspeção reprovada, operador escolhe corrigir ou FP
 *   transition   → V1+V2 OK na Bancada A, aguardando movimentação para B
 *   approved     → todas validações aprovadas (3/3)
 */
import { useParams } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { useTabletWebSocket } from './useTabletWebSocket'
import { TabletIdle } from './TabletIdle'
import { TabletIdentified } from './TabletIdentified'
import { TabletValidating } from './TabletValidating'
import { TabletResultOK } from './TabletResultOK'
import { TabletResultNOK } from './TabletResultNOK'
import { TabletTransition } from './TabletTransition'
import { TabletApproved } from './TabletApproved'
import type { QualityPiece } from '../types/gate'

// Possíveis telas do kiosk
type TabletView =
  | 'idle'
  | 'identified'
  | 'validating'
  | 'ok'
  | 'nok'
  | 'transition'
  | 'approved'

export function TabletKiosk() {
  // station vem da URL: /tablet/bench_a ou /tablet/bench-a (ambos aceitos)
  const { station: rawStation = 'bench_a' } = useParams<{ station: string }>()
  // Normaliza hífens para underscore para casar com StationCode
  const station = rawStation.replace('-', '_')

  const { stationState, lastResult, lastIdentified, clearResult } =
    useTabletWebSocket(station)

  const [currentView, setCurrentView] = useState<TabletView>('idle')
  const [currentPiece, setCurrentPiece] = useState<QualityPiece | null>(null)

  // Sincroniza a view com o estado da bancada recebido via WebSocket
  useEffect(() => {
    if (!stationState) return
    const piece = stationState.current_piece
    setCurrentPiece(piece)

    if (!piece) {
      setCurrentView('idle')
      return
    }

    const s = piece.status

    // Mapeamento de status → view
    if (s === 'idle') setCurrentView('idle')
    else if (s === 'identified') setCurrentView('identified')
    else if (s === 'validating_v1' || s === 'validating_v2' || s === 'validating_v3')
      setCurrentView('validating')
    else if (s === 'waiting_bench_b' && station === 'bench_a')
      setCurrentView('transition')
    else if (s === 'rework_v1' || s === 'rework_v2' || s === 'rework_v3')
      setCurrentView('nok')
    else if (s === 'approved') setCurrentView('approved')
    else if (s === 'rejected') setCurrentView('nok')
  }, [stationState, station])

  // Reage ao resultado de inspeção do worker (ok/nok)
  useEffect(() => {
    if (!lastResult) return
    if (lastResult.result === 'ok') {
      setCurrentView('ok')
      // A view TabletResultOK vai chamar onAdvance após 3s — clearResult lá dentro
    } else {
      setCurrentView('nok')
    }
  }, [lastResult])

  // lastIdentified: peça nova identificada — muda view independente de stationState
  useEffect(() => {
    if (!lastIdentified) return
    setCurrentView('identified')
  }, [lastIdentified])

  // Estilo base: fullscreen kiosk
  const baseStyle: React.CSSProperties = {
    width: '100vw',
    height: '100vh',
    overflow: 'hidden',
    fontFamily: 'system-ui, -apple-system, sans-serif',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
  }

  return (
    <div style={baseStyle}>
      {currentView === 'idle' && (
        <TabletIdle station={station} />
      )}

      {currentView === 'identified' && (
        <TabletIdentified piece={currentPiece} station={station} />
      )}

      {currentView === 'validating' && (
        <TabletValidating piece={currentPiece} />
      )}

      {currentView === 'ok' && (
        <TabletResultOK
          piece={currentPiece}
          result={lastResult}
          onAdvance={() => {
            clearResult()
            setCurrentView('validating')
          }}
        />
      )}

      {currentView === 'nok' && (
        <TabletResultNOK
          piece={currentPiece}
          result={lastResult}
          station={station}
          onCorrected={() => setCurrentView('validating')}
        />
      )}

      {currentView === 'transition' && (
        <TabletTransition piece={currentPiece} />
      )}

      {currentView === 'approved' && (
        <TabletApproved piece={currentPiece} />
      )}
    </div>
  )
}
