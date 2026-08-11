/**
 * Tests: propagationUi — mapa de fases (mapJobToPhase), motivos de
 * desabilitado do CTA (disabledReason) e helpers de formatação.
 */
import { describe, expect, it } from 'vitest'
import { capturedAtToIsoDate, disabledReason, formatElapsed, formatUsd, mapJobToPhase } from '../../../components/annotation/propagationUi'
import type {
  PropagationJob,
  PropagationPreflight,
} from '../../../services/propagationService'

function buildJob(overrides: Partial<PropagationJob> = {}): PropagationJob {
  return {
    id: 'job-1',
    status: 'running',
    proposals_count: 0,
    metrics: {},
    created_at: '2026-08-10T12:00:00Z',
    ...overrides,
  }
}

function buildPreflight(overrides: Partial<PropagationPreflight> = {}): PropagationPreflight {
  return {
    pool_total: 10,
    pool_effective: 10,
    validation_only: false,
    seed_frame_count: 1,
    seed_box_count: 2,
    active_job: null,
    third_party_cloud_enabled: true,
    runpod_configured: true,
    gpu: {
      gpu_type: 'RTX4090',
      price_usd_h: 0.5,
      estimated_cost_usd: 1.2,
      max_usd: 5,
      timeout_seconds: 600,
      price_error: false,
    },
    ...overrides,
  }
}

describe('mapJobToPhase', () => {
  it('queued vira "Preparando referências"', () => {
    const phase = mapJobToPhase(buildJob({ status: 'queued', metrics: {} }))
    expect(phase.key).toBe('preparing')
    expect(phase.label).toBe('Preparando referências')
    expect(phase.terminal).toBe(false)
    expect(phase.failed).toBe(false)
  })

  it('stage "preparing" (running) vira "Preparando referências"', () => {
    const phase = mapJobToPhase(buildJob({ status: 'running', metrics: { stage: 'preparing' } }))
    expect(phase.label).toBe('Preparando referências')
  })

  it.each(['creating_pod', 'gpu_starting'])('stage %s avisa que demora (~2 a 4 min)', stage => {
    const phase = mapJobToPhase(buildJob({ metrics: { stage } }))
    expect(phase.key).toBe('gpu_starting')
    expect(phase.label).toContain('Iniciando máquina de GPU')
    expect(phase.label).toContain('2 a 4 min')
  })

  it.each(['manifest', 'deps', 'weights'])('stage %s vira "Carregando modelo na GPU"', stage => {
    const phase = mapJobToPhase(buildJob({ metrics: { stage } }))
    expect(phase.key).toBe('loading_model')
    expect(phase.label).toBe('Carregando modelo na GPU (ainda pode levar minutos)')
  })

  it('stage seed_exemplars vira "Preparando referências na GPU"', () => {
    const phase = mapJobToPhase(buildJob({ metrics: { stage: 'seed_exemplars' } }))
    expect(phase.key).toBe('seed_exemplars')
    expect(phase.label).toBe('Preparando referências na GPU')
  })

  it.each(['propagate', 'pool'])(
    'stage %s vira "Analisando imagens" com counter frames_processed/frames_total',
    stage => {
      const phase = mapJobToPhase(
        buildJob({ metrics: { stage, frames_processed: 247, frames_total: 662 } }),
      )
      expect(phase.key).toBe('propagate')
      expect(phase.label).toBe('Analisando imagens')
      expect(phase.counter).toEqual({ done: 247, total: 662 })
    },
  )

  it('stage propagate sem frames_processed/frames_total não inventa counter', () => {
    const phase = mapJobToPhase(buildJob({ metrics: { stage: 'propagate' } }))
    expect(phase.counter).toBeUndefined()
  })

  it.each(['finalize', 'done'])('stage %s vira "Recebendo propostas"', stage => {
    const phase = mapJobToPhase(buildJob({ metrics: { stage } }))
    expect(phase.key).toBe('finalize')
    expect(phase.label).toBe('Recebendo propostas')
  })

  it('completed usa proposals_count (plural)', () => {
    const phase = mapJobToPhase(buildJob({ status: 'completed', proposals_count: 42 }))
    expect(phase.key).toBe('completed')
    expect(phase.label).toBe('42 propostas encontradas')
    expect(phase.terminal).toBe(true)
    expect(phase.failed).toBe(false)
  })

  it('completed com 1 proposta usa singular', () => {
    const phase = mapJobToPhase(buildJob({ status: 'completed', proposals_count: 1 }))
    expect(phase.label).toBe('1 proposta encontrada')
  })

  it('failed com failure_kind=cost_cap', () => {
    const phase = mapJobToPhase(
      buildJob({ status: 'failed', metrics: { failure_kind: 'cost_cap' } }),
    )
    expect(phase.label).toBe('a busca passou do limite de custo e foi interrompida')
    expect(phase.terminal).toBe(true)
    expect(phase.failed).toBe(true)
  })

  it('failed com failure_kind=timeout', () => {
    const phase = mapJobToPhase(
      buildJob({ status: 'failed', metrics: { failure_kind: 'timeout' } }),
    )
    expect(phase.label).toBe('a busca demorou mais que o permitido')
  })

  it('failed com failure_kind=pod_died', () => {
    const phase = mapJobToPhase(
      buildJob({ status: 'failed', metrics: { failure_kind: 'pod_died' } }),
    )
    expect(phase.label).toBe('a máquina de GPU falhou')
  })

  it('failed com failure_kind=stopped mantém failed=true', () => {
    const phase = mapJobToPhase(
      buildJob({ status: 'failed', metrics: { failure_kind: 'stopped' } }),
    )
    expect(phase.key).toBe('stopped')
    expect(phase.label).toBe('busca interrompida')
    expect(phase.failed).toBe(true)
  })

  it('failed com failure_kind=executor_error expõe error_reason como detalhe', () => {
    const phase = mapJobToPhase(
      buildJob({
        status: 'failed',
        metrics: { failure_kind: 'executor_error' },
        error_reason: 'Traceback: RuntimeError na GPU',
      }),
    )
    expect(phase.label).toBe('a busca falhou')
    expect(phase.detail).toBe('Traceback: RuntimeError na GPU')
  })

  it('failed sem failure_kind (default) também cai no fallback "a busca falhou"', () => {
    const phase = mapJobToPhase(
      buildJob({ status: 'failed', metrics: {}, error_reason: 'motivo cru' }),
    )
    expect(phase.label).toBe('a busca falhou')
    expect(phase.detail).toBe('motivo cru')
  })

  it('status stopped (nível do job, sem passar por "failed")', () => {
    const phase = mapJobToPhase(buildJob({ status: 'stopped', metrics: {} }))
    expect(phase.key).toBe('stopped')
    expect(phase.label).toBe('busca interrompida')
    expect(phase.terminal).toBe(true)
    expect(phase.failed).toBe(false)
  })

  it('stage desconhecido nunca quebra a barra — fallback "Processando"', () => {
    const phase = mapJobToPhase(buildJob({ metrics: { stage: 'algum-stage-novo-do-executor' } }))
    expect(phase.key).toBe('unknown')
    expect(phase.label).toBe('Processando')
    expect(phase.terminal).toBe(false)
    expect(phase.failed).toBe(false)
  })
})

describe('disabledReason', () => {
  it('sem caixas desenhadas: motivo 1', () => {
    expect(disabledReason(false, buildPreflight())).toBe(
      'desenhe ao menos uma caixa para usar como referência',
    )
  })

  it('sem caixas tem prioridade mesmo se o preflight também estiver ruim', () => {
    expect(
      disabledReason(false, buildPreflight({ runpod_configured: false })),
    ).toBe('desenhe ao menos uma caixa para usar como referência')
  })

  it('runpod não configurado: motivo 2', () => {
    expect(
      disabledReason(true, buildPreflight({ runpod_configured: false })),
    ).toBe('treino em nuvem não configurado')
  })

  it('nuvem de terceiro desabilitada no tenant: motivo 3', () => {
    expect(
      disabledReason(true, buildPreflight({ third_party_cloud_enabled: false })),
    ).toBe('envio para nuvem externa não autorizado neste tenant')
  })

  it('já existe job ativo: motivo 4', () => {
    expect(
      disabledReason(
        true,
        buildPreflight({ active_job: { id: 'j', status: 'running', created_at: 'x' } }),
      ),
    ).toBe('busca em andamento')
  })

  it('tudo liberado: null', () => {
    expect(disabledReason(true, buildPreflight())).toBeNull()
  })
})

describe('formatUsd', () => {
  it('formata com duas casas decimais e prefixo US$', () => {
    expect(formatUsd(1.2)).toBe('US$ 1.20')
    expect(formatUsd(0)).toBe('US$ 0.00')
  })

  it('null/undefined vira travessão', () => {
    expect(formatUsd(null)).toBe('—')
    expect(formatUsd(undefined)).toBe('—')
  })
})

describe('formatElapsed', () => {
  it('sem startIso vira 00:00', () => {
    expect(formatElapsed(null)).toBe('00:00')
    expect(formatElapsed(undefined)).toBe('00:00')
  })

  it('calcula mm:ss a partir de um timestamp no passado', () => {
    const start = new Date(Date.now() - 65_000).toISOString()
    expect(formatElapsed(start)).toBe('01:05')
  })
})

describe('capturedAtToIsoDate', () => {
  it('converte o formato RFC 1123 do jsonify (o que o backend realmente manda)', () => {
    expect(capturedAtToIsoDate('Thu, 31 Jul 2026 19:16:00 GMT')).toBe('2026-07-31')
  })

  it('aceita ISO direto', () => {
    expect(capturedAtToIsoDate('2026-07-31T19:16:00Z')).toBe('2026-07-31')
  })

  it('null/lixo viram null', () => {
    expect(capturedAtToIsoDate(null)).toBeNull()
    expect(capturedAtToIsoDate(undefined)).toBeNull()
    expect(capturedAtToIsoDate('nao-e-data')).toBeNull()
  })
})
