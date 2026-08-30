/**
 * O que este arquivo não pode deixar passar: a vista errada para o status da
 * peça (é literalmente a máquina de estados do Quality Gate, herdada de
 * `TabletKiosk` sem reescrita), e qualquer importação de componente visual do
 * kiosk antigo — a lei desta rodada é reusar só hook + tipos.
 */
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { QualityPiece, StationStateEvent, InspectionResultEvent } from '../../modules/quality/types/gate'

const useTabletWebSocket = vi.fn()
vi.mock('../../modules/quality/tablet/useTabletWebSocket', () => ({
  useTabletWebSocket: (...a: unknown[]) => useTabletWebSocket(...a),
}))

const post = vi.fn().mockResolvedValue({})
vi.mock('../../services/api', () => ({
  api: { post: (...a: unknown[]) => post(...a) },
  API_BASE: 'http://api.test/api',
}))

vi.mock('react-router-dom', async (orig) => ({
  ...(await orig<typeof import('react-router-dom')>()),
  useParams: () => ({ station: 'bench_a' }),
}))

import { Kiosk } from './Kiosk'

/** Peça mínima válida — só os campos que as vistas realmente leem. */
const peca = (extra: Partial<QualityPiece> = {}): QualityPiece => ({
  id: 'p1',
  piece_number: 'PC-0042',
  work_order: 'OP-9',
  product_type: null,
  status: 'idle',
  current_station: 'bench_a',
  operator_id: null,
  started_at: '2026-08-29T10:00:00Z',
  completed_at: null,
  total_rework_count: 0,
  total_rework_time_seconds: 0,
  photo_quality_path: null,
  photo_quality_r2_key: null,
  wiser_exported: false,
  wiser_exported_at: null,
  created_at: '2026-08-29T10:00:00Z',
  updated_at: '2026-08-29T10:00:00Z',
  ...extra,
})

const estadoBancada = (p: QualityPiece | null): StationStateEvent => ({
  station_code: 'bench_a',
  current_piece: p,
  tower_state: 'idle',
  timestamp: '2026-08-29T10:00:00Z',
})

const resultado = (over: Partial<InspectionResultEvent> = {}): InspectionResultEvent => ({
  piece_id: 'p1',
  validation_type: 'v1',
  camera_id: 'cam1',
  result: 'ok',
  confidence: 0.9,
  ok_ratio: 1,
  detections: [],
  photo_path: null,
  photo_r2_key: null,
  timestamp: '2026-08-29T10:00:00Z',
  ...over,
})

const hook = (over: Partial<ReturnType<typeof useTabletWebSocket>> = {}) => ({
  isConnected: true,
  lastResult: null,
  stationState: null,
  lastIdentified: null,
  lastError: null,
  clearResult: vi.fn(),
  clearIdentified: vi.fn(),
  ...over,
})

const montar = () => render(<MemoryRouter><Kiosk /></MemoryRouter>)

beforeEach(() => {
  useTabletWebSocket.mockReset()
  post.mockClear()
})

describe('a vista certa para cada estado da máquina do Quality Gate', () => {
  it('ociosa — sem peça na bancada', () => {
    useTabletWebSocket.mockReturnValue(hook({ stationState: estadoBancada(null) }))
    montar()
    expect(screen.getByText('BANCADA A')).toBeTruthy()
  })

  it('identificada — peça aguardando início da inspeção', () => {
    useTabletWebSocket.mockReturnValue(hook({ stationState: estadoBancada(peca({ status: 'identified' })) }))
    montar()
    expect(screen.getByText('PC-0042')).toBeTruthy()
    expect(screen.getByText('INICIAR INSPEÇÃO')).toBeTruthy()
  })

  it('validando — inspeção V1 em andamento', () => {
    useTabletWebSocket.mockReturnValue(hook({ stationState: estadoBancada(peca({ status: 'validating_v1' })) }))
    montar()
    expect(screen.getByText('Validando')).toBeTruthy()
  })

  it('transição — V1+V2 aprovadas na Bancada A, aguardando ida para B', () => {
    useTabletWebSocket.mockReturnValue(hook({ stationState: estadoBancada(peca({ status: 'waiting_bench_b' })) }))
    montar()
    expect(screen.getByText('CONFIRMAR MOVIMENTAÇÃO')).toBeTruthy()
  })

  it('reprovada — validação com retrabalho pendente', () => {
    useTabletWebSocket.mockReturnValue(hook({ stationState: estadoBancada(peca({ status: 'rework_v1' })) }))
    montar()
    expect(screen.getByText('NÃO CONFORME')).toBeTruthy()
  })

  it('aprovada — peça 3/3', () => {
    useTabletWebSocket.mockReturnValue(hook({ stationState: estadoBancada(peca({ status: 'approved' })) }))
    montar()
    expect(screen.getByText('APROVADA 3/3')).toBeTruthy()
  })

  it('conforme — resultado ok do worker (view intermediária entre validações)', () => {
    useTabletWebSocket.mockReturnValue(hook({ lastResult: resultado({ result: 'ok' }) }))
    montar()
    expect(screen.getByText('CONFORME')).toBeTruthy()
  })
})

describe('coexistência com o kiosk antigo', () => {
  const SRC = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
  const leia = (rel: string) => fs.readFileSync(path.join(SRC, rel), 'utf-8')

  it('a rota antiga /tablet/:station segue registrada e serve o TabletKiosk original', () => {
    const appRoutes = leia('AppRoutes.tsx')
    expect(appRoutes).toContain('path="/tablet/:station"')
    expect(appRoutes).toContain('TabletKiosk')
  })

  it('Kiosk.tsx não importa nenhum componente visual do kiosk antigo — só hook e tipos', () => {
    const fonte = leia('app/kiosk/Kiosk.tsx')
    const doModuloTablet = [...fonte.matchAll(/from '([^']*modules\/quality[^']*)'/g)].map((m) => m[1])
    for (const de of doModuloTablet) {
      expect(de, `import de "${de}" — só useTabletWebSocket e types/gate são permitidos aqui`).toMatch(
        /(useTabletWebSocket|types\/gate)$/,
      )
    }
    // Nenhum dos componentes visuais do kiosk antigo é citado no arquivo.
    for (const antigo of ['TabletIdle', 'TabletIdentified', 'TabletValidating', 'TabletResultOK', 'TabletResultNOK', 'TabletTransition', 'TabletApproved']) {
      expect(fonte).not.toContain(antigo)
    }
  })
})
