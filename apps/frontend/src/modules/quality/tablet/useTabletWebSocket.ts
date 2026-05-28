/**
 * useTabletWebSocket — hook para conexão WebSocket do tablet de bancada.
 *
 * Conecta ao namespace /quality do SocketIO e filtra eventos por stationCode.
 * Segue o mesmo padrão de useQualityWebSocket (dynamic import de socket.io-client).
 *
 * Eventos assinados:
 *   quality_gate_result      → resultado de inspeção (ok/nok)
 *   quality_station_state    → estado atual da bancada (peça, torre)
 *   quality_piece_identified → peça identificada (OCR/barcode/manual)
 */
import { useEffect, useRef, useState, useCallback } from 'react'
import type { InspectionResultEvent, StationStateEvent, PieceIdentifiedEvent } from '../types/gate'

// Estado interno exposto pelo hook
interface TabletWebSocketState {
  isConnected: boolean
  lastResult: InspectionResultEvent | null
  stationState: StationStateEvent | null
  lastIdentified: PieceIdentifiedEvent | null
  lastError: string | null
}

export function useTabletWebSocket(stationCode: string) {
  const [state, setState] = useState<TabletWebSocketState>({
    isConnected: false,
    lastResult: null,
    stationState: null,
    lastIdentified: null,
    lastError: null,
  })

  // Referência ao socket para cleanup correto
  const socketRef = useRef<ReturnType<typeof import('socket.io-client')['io']> | null>(null)

  useEffect(() => {
    let socket: ReturnType<typeof import('socket.io-client')['io']> | null = null

    async function connect() {
      const { io } = await import('socket.io-client')
      const wsBase =
        import.meta.env.VITE_WS_URL ||
        import.meta.env.VITE_API_URL ||
        window.location.origin

      socket = io(`${wsBase}/quality`, {
        transports: ['websocket', 'polling'],
        autoConnect: true,
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionAttempts: Infinity,
      })

      socketRef.current = socket

      socket.on('connect', () =>
        setState(s => ({ ...s, isConnected: true, lastError: null }))
      )

      socket.on('disconnect', () =>
        setState(s => ({ ...s, isConnected: false }))
      )

      socket.on('connect_error', (err: Error) =>
        setState(s => ({ ...s, lastError: err.message }))
      )

      // Resultado de inspeção do gate (ok/nok) — não filtra por station aqui,
      // pois o piece_id é único por peça e o kiosk já tem o contexto da peça atual.
      socket.on('quality_gate_result', (data: InspectionResultEvent) => {
        if (data.piece_id) {
          setState(s => ({ ...s, lastResult: data }))
        }
      })

      // Estado da bancada — filtra por stationCode para isolar cada tablet
      socket.on('quality_station_state', (data: StationStateEvent) => {
        if (data.station_code === stationCode) {
          setState(s => ({ ...s, stationState: data }))
        }
      })

      // Peça identificada — filtra por stationCode
      socket.on('quality_piece_identified', (data: PieceIdentifiedEvent) => {
        if (data.station_code === stationCode) {
          setState(s => ({ ...s, lastIdentified: data }))
        }
      })
    }

    connect()

    return () => {
      socket?.disconnect()
      socketRef.current = null
    }
  }, [stationCode])

  // Limpa o último resultado de inspeção (chamado após o kiosk processar o resultado)
  const clearResult = useCallback(
    () => setState(s => ({ ...s, lastResult: null })),
    []
  )

  // Limpa o último evento de peça identificada
  const clearIdentified = useCallback(
    () => setState(s => ({ ...s, lastIdentified: null })),
    []
  )

  return { ...state, clearResult, clearIdentified }
}
