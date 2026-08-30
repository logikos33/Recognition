/**
 * O que esta tela não pode errar (paridade com `pages/TrainingPage.tsx`,
 * aba "treino" — ver comentário de topo de `Treino.tsx`):
 *
 *  · banner de GPU off quando `gpu_enabled: false` — sem ele, o treino falha
 *    calado e ninguém sabe por quê;
 *  · "Novo treino" manda o payload exato que o backend espera
 *    (`POST /training/jobs`);
 *  · "Parar" manda `POST /training/jobs/<id>/stop`;
 *  · o histórico mostra `current_epoch` — o REAL rodado — nunca
 *    `total_epochs` (o pedido). Mutação verificada à mão durante a
 *    implementação (trocar por `total_epochs` no JSX quebra este teste);
 *  · o status ao vivo do WebSocket (`useTrainingSocket`) tem prioridade sobre
 *    o poll de 3s ao mostrar a época atual.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

// jsdom não implementa scrollIntoView (usado no auto-scroll do log de eventos).
beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn()
})

const get = vi.fn()
const post = vi.fn()
vi.mock('../../services/api', () => ({
  api: {
    get: (...a: unknown[]) => get(...a),
    post: (...a: unknown[]) => post(...a),
  },
  getToken: () => 'tok-123',
}))

const auth = vi.hoisted(() => ({ modules: ['epi'] as string[], isSuperAdmin: false }))
vi.mock('../../hooks/useAuth', () => ({ useAuth: () => auth }))

const toastOk = vi.fn()
const toastErro = vi.fn()
vi.mock('../../components/ui/Toast/useToast', () => ({
  useToast: () => ({ success: toastOk, error: toastErro, warning: vi.fn(), info: vi.fn() }),
}))

const liveJobs = vi.hoisted(() => ({ current: {} as Record<string, unknown> }))
vi.mock('../../hooks/useTrainingSocket', () => ({
  useTrainingSocket: () => ({ connected: true, jobs: liveJobs.current }),
}))

import { Treino } from './Treino'

// ── fixtures: colunas reais de training_jobs ────────────────────────────────

function statusEnvelope(job: unknown, gpuEnabled = true) {
  return { success: true, data: { job, gpu_enabled: gpuEnabled, live: null } }
}
function jobsEnvelope(jobs: unknown[]) {
  return { success: true, data: jobs }
}

function job(id: string, extra: Record<string, unknown> = {}) {
  return {
    id,
    preset: 'balanced',
    model_size: 'yolo26n',
    status: 'pending',
    progress: 0,
    current_epoch: 0,
    total_epochs: 50,
    metrics: {},
    created_at: '2026-08-29T11:00:00Z',
    ...extra,
  }
}

/** `get` roteado por endpoint — cada teste ajusta as respostas via mockImplementation. */
function mockApi({ status, jobs = [] }: { status: ReturnType<typeof statusEnvelope>; jobs?: unknown[] }) {
  get.mockImplementation((path: string) => {
    if (path === '/training/jobs/current/status') return Promise.resolve(status)
    if (path === '/training/jobs') return Promise.resolve(jobsEnvelope(jobs))
    return Promise.resolve({ success: true, data: null })
  })
}

beforeEach(() => {
  get.mockReset()
  post.mockReset()
  post.mockResolvedValue({ success: true })
  toastOk.mockReset()
  toastErro.mockReset()
  auth.modules = ['epi']
  auth.isSuperAdmin = false
  liveJobs.current = {}
})

describe('Treino (Estúdio — treino ao vivo)', () => {
  it('gpu_enabled=false mostra o banner honesto', async () => {
    mockApi({ status: statusEnvelope(null, false) })
    render(<Treino />)
    await screen.findByText(/Chave de GPU não configurada/)
  })

  it('gpu_enabled=true não mostra o banner', async () => {
    mockApi({ status: statusEnvelope(null, true) })
    render(<Treino />)
    await waitFor(() => expect(get).toHaveBeenCalledWith('/training/jobs/current/status'))
    expect(screen.queryByText(/Chave de GPU não configurada/)).toBeNull()
  })

  it('"Novo treino" envia o payload certo para POST /training/jobs', async () => {
    mockApi({ status: statusEnvelope(null, true) })
    render(<Treino />)
    await waitFor(() => expect(get).toHaveBeenCalledWith('/training/jobs/current/status'))

    fireEvent.click(screen.getByText('Novo treino'))
    fireEvent.click(screen.getByText('Iniciar Treinamento'))

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/training/jobs', {
        preset: 'balanced',
        module: 'epi',
        model_size: 'yolo26n',
        total_epochs: 50,
        batch_size: 16,
        learning_rate: 0.01,
      }),
    )
    expect(toastOk).toHaveBeenCalledWith('Treinamento iniciado')
  })

  it('"Parar" chama POST /training/jobs/<id>/stop', async () => {
    mockApi({ status: statusEnvelope(job('job-9', { status: 'running', current_epoch: 5 }), true) })
    render(<Treino />)
    const parar = await screen.findByText('Parar')

    fireEvent.click(parar)

    await waitFor(() => expect(post).toHaveBeenCalledWith('/training/jobs/job-9/stop', {}))
  })

  it('histórico mostra current_epoch (REAL rodado), não total_epochs (o pedido)', async () => {
    mockApi({
      status: statusEnvelope(null, true),
      jobs: [job('job-2', { status: 'completed', current_epoch: 45, total_epochs: 60 })],
    })
    render(<Treino />)

    // 45 é o que RODOU de verdade (parou antes das 60 pedidas — early stop/falha).
    // Trocar a leitura por total_epochs faria a tela mostrar "60/60 ép." aqui.
    await screen.findByText('45/60 ép.')
  })

  it('status ao vivo do socket sobrepõe o poll ao mostrar a época', async () => {
    mockApi({
      status: statusEnvelope(job('job-1', { status: 'running', current_epoch: 5, total_epochs: 50, progress: 10 }), true),
    })
    liveJobs.current = {
      'job-1': {
        status: 'training',
        progress: 40,
        epoch: 20,
        total_epochs: 50,
        metrics: {},
        eta_seconds: 0,
        lossHistory: [],
        map50History: [],
      },
    }
    render(<Treino />)

    await screen.findByText((text) => text.includes('20/50'))
  })

  describe('anti-vazamento de stack interno (política F5-LEVE)', () => {
    it('current job: model_size interno (yolo26n) nunca aparece — mostra "Logikos" genérico', async () => {
      mockApi({ status: statusEnvelope(job('job-9', { model_size: 'yolo26n', status: 'running' }), true) })
      render(<Treino />)
      await screen.findByText(/Logikos/)
      expect(document.body.innerHTML).not.toMatch(/yolo|rf-?detr|onnx/i)
    })

    it('histórico: model_size interno nunca aparece — mostra "Logikos" + sufixo de job id', async () => {
      mockApi({
        status: statusEnvelope(null, true),
        jobs: [job('job-abc12345', { model_size: 'yolo26m', status: 'completed' })],
      })
      render(<Treino />)
      await screen.findByText(/Logikos/)
      expect(screen.getByText(/#job-abc1/)).toBeTruthy()
      expect(document.body.innerHTML).not.toMatch(/yolo|rf-?detr|onnx/i)
    })
  })
})
