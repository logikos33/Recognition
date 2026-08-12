/**
 * Tests: searchContentUi — mapeamento de termos prontos → payload,
 * agrupamento de achados, fase do job de busca por conteúdo, motivos de
 * desabilitado do CTA e ressurgimento pós-reload.
 */
import { beforeEach, describe, expect, it } from 'vitest'
import {
  MAX_TERMS_PER_JOB,
  READY_TERMS,
  buildSearchTerms,
  dismissSearchJob,
  groupFindings,
  ineligibleReasonLabel,
  isSearchJobDismissed,
  mapSearchJobToPhase,
  pickSearchJobToResurface,
  searchSubmitDisabledReason,
  summarizeIneligible,
} from '../../../components/annotation/searchContentUi'
import type { SearchFinding, SearchJob, SearchPreflight } from '../../../services/searchService'

function buildJob(overrides: Partial<SearchJob> = {}): SearchJob {
  return {
    id: 'search-1',
    status: 'running',
    selected_frame_ids: [],
    terms: [],
    results: [],
    findings_count: 0,
    metrics: {},
    created_at: '2026-08-11T12:00:00Z',
    ...overrides,
  }
}

function buildPreflight(overrides: Partial<SearchPreflight> = {}): SearchPreflight {
  return {
    selected_count: 10,
    eligible_count: 10,
    ineligible: [],
    terms_count: 1,
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
    allowed_dates: [],
    ...overrides,
  }
}

function buildFinding(overrides: Partial<SearchFinding> = {}): SearchFinding {
  return {
    frame_id: 'f1',
    term: 'safety helmet',
    label: 'capacete',
    bbox: [0.1, 0.1, 0.2, 0.2],
    confidence: 0.8,
    ...overrides,
  }
}

describe('buildSearchTerms', () => {
  it('mapeia termos prontos marcados pro payload {label pt-BR, query em inglês}', () => {
    const terms = buildSearchTerms(new Set(['capacete', 'luva']), [])
    expect(terms).toEqual([
      { label: 'capacete', query: 'safety helmet' },
      { label: 'luva', query: 'glove' },
    ])
  })

  it('preserva a ordem de READY_TERMS independente da ordem de marcação', () => {
    const terms = buildSearchTerms(new Set(['bota', 'capacete']), [])
    expect(terms.map(t => t.query)).toEqual(['safety helmet', 'safety boots'])
  })

  it('termo livre vira {label: termo, query: termo}', () => {
    const terms = buildSearchTerms(new Set(), ['forklift'])
    expect(terms).toEqual([{ label: 'forklift', query: 'forklift' }])
  })

  it('termos prontos vêm antes dos livres', () => {
    const terms = buildSearchTerms(new Set(['capacete']), ['forklift'])
    expect(terms.map(t => t.query)).toEqual(['safety helmet', 'forklift'])
  })

  it('descarta termo livre vazio/só espaço', () => {
    const terms = buildSearchTerms(new Set(), ['  ', ''])
    expect(terms).toEqual([])
  })

  it('dedupe por query, case-insensitive — termo livre repetindo um pronto não duplica', () => {
    const terms = buildSearchTerms(new Set(['capacete']), ['Safety Helmet', 'safety helmet'])
    expect(terms).toEqual([{ label: 'capacete', query: 'safety helmet' }])
  })

  it('dedupe por LABEL (case-insensitive) — a constraint real do backend é por label, não por query (_parse_terms rejeita "term.label duplicado" com 400)', () => {
    const terms = buildSearchTerms(new Set(['capacete']), ['Capacete', 'CAPACETE'])
    expect(terms).toEqual([{ label: 'capacete', query: 'safety helmet' }])
  })

  it('nenhum termo selecionado → payload vazio', () => {
    expect(buildSearchTerms(new Set(), [])).toEqual([])
  })

  it('MAX_TERMS_PER_JOB bate com _MAX_TERMS de search_handlers.py', () => {
    expect(MAX_TERMS_PER_JOB).toBe(12)
  })

  it('READY_TERMS cobre os 7 termos de EPI do contrato', () => {
    expect(READY_TERMS.map(t => t.key)).toEqual([
      'capacete', 'oculos', 'luva', 'colete', 'protetor_auricular', 'mascara', 'bota',
    ])
    expect(READY_TERMS.find(t => t.key === 'colete')?.query).toBe('high-visibility safety vest')
    expect(READY_TERMS.find(t => t.key === 'protetor_auricular')?.query).toBe('hearing protection ear muffs')
  })
})

describe('ineligibleReasonLabel', () => {
  // Códigos reais de search_cloud_guard.py::classify_frame_eligibility —
  // snake_case pra máquina, traduzidos aqui pro pt-BR do painel.
  it.each([
    ['frame_not_found', 'imagem não encontrada'],
    ['missing_r2_key', 'imagem sem arquivo salvo'],
    ['missing_captured_at', 'imagem sem data de captura registrada'],
    ['date_not_allowed', 'fora das datas liberadas para busca em nuvem'],
  ])('%s → %s', (code, label) => {
    expect(ineligibleReasonLabel(code)).toBe(label)
  })

  it('código desconhecido nunca esconde o motivo — devolve o código cru', () => {
    expect(ineligibleReasonLabel('algum_motivo_novo_do_backend')).toBe('algum_motivo_novo_do_backend')
  })
})

describe('summarizeIneligible', () => {
  it('agrupa por motivo (código cru) e traduz pro pt-BR no resultado', () => {
    const summary = summarizeIneligible([
      { reason: 'date_not_allowed' },
      { reason: 'date_not_allowed' },
      { reason: 'missing_r2_key' },
    ])
    expect(summary).toEqual([
      { reason: 'fora das datas liberadas para busca em nuvem', count: 2 },
      { reason: 'imagem sem arquivo salvo', count: 1 },
    ])
  })

  it('lista vazia → resumo vazio', () => {
    expect(summarizeIneligible([])).toEqual([])
  })
})

describe('searchSubmitDisabledReason', () => {
  it('nuvem desabilitada tem prioridade sobre tudo', () => {
    expect(searchSubmitDisabledReason(0, null, true)).toBe('busca em nuvem desabilitada neste tenant')
  })

  it('sem termos: motivo específico', () => {
    expect(searchSubmitDisabledReason(0, buildPreflight(), false)).toBe(
      'marque ao menos um termo pronto ou digite um termo livre',
    )
  })

  it('preflight ainda não chegou: motivo de carregamento', () => {
    expect(searchSubmitDisabledReason(1, null, false)).toBe('calculando custo…')
  })

  it('runpod não configurado (mesmo gate de propagationUi.disabledReason)', () => {
    expect(
      searchSubmitDisabledReason(1, buildPreflight({ runpod_configured: false }), false),
    ).toBe('busca em nuvem não configurada')
  })

  it('nuvem de terceiro desabilitada no tenant', () => {
    expect(
      searchSubmitDisabledReason(1, buildPreflight({ third_party_cloud_enabled: false }), false),
    ).toBe('envio para nuvem externa não autorizado neste tenant')
  })

  it('nenhum frame elegível', () => {
    expect(
      searchSubmitDisabledReason(1, buildPreflight({ eligible_count: 0 }), false),
    ).toBe('nenhuma das imagens selecionadas é elegível para a busca em nuvem')
  })

  it('preço indisponível', () => {
    expect(
      searchSubmitDisabledReason(
        1,
        buildPreflight({ gpu: { ...buildPreflight().gpu, price_error: true } }),
        false,
      ),
    ).toBe('não foi possível estimar o custo — tente de novo')
  })

  it('tudo liberado: null', () => {
    expect(searchSubmitDisabledReason(1, buildPreflight(), false)).toBeNull()
  })
})

describe('mapSearchJobToPhase', () => {
  it('queued vira "Na fila"', () => {
    const phase = mapSearchJobToPhase(buildJob({ status: 'queued', metrics: {} }))
    expect(phase.key).toBe('queued')
    expect(phase.label).toBe('Na fila')
    expect(phase.terminal).toBe(false)
    expect(phase.failed).toBe(false)
  })

  it('running sem stage também vira "Na fila" (nunca quebra a barra)', () => {
    const phase = mapSearchJobToPhase(buildJob({ status: 'running', metrics: {} }))
    expect(phase.key).toBe('queued')
  })

  it.each(['creating_pod', 'gpu_boot', 'pod_starting'])('stage %s avisa cold start', stage => {
    const phase = mapSearchJobToPhase(buildJob({ metrics: { stage } }))
    expect(phase.key).toBe('gpu_starting')
    expect(phase.label).toContain('Iniciando máquina de GPU')
  })

  it.each(['manifest', 'deps', 'model'])(
    'stage %s (executor real, training/search_content.py) vira "Carregando modelo na GPU"',
    stage => {
      const phase = mapSearchJobToPhase(buildJob({ metrics: { stage } }))
      expect(phase.key).toBe('loading_model')
      expect(phase.label).toBe('Carregando modelo na GPU (ainda pode levar minutos)')
    },
  )

  it('stage de busca com frames_processed/selected_frame_ids vira counter (fallback sem frames_total)', () => {
    const phase = mapSearchJobToPhase(
      buildJob({
        metrics: { stage: 'searching', frames_processed: 4 },
        selected_frame_ids: ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'],
      }),
    )
    expect(phase.key).toBe('searching')
    expect(phase.counter).toEqual({ done: 4, total: 8 })
  })

  it('stage de busca prefere metrics.frames_total (o que o executor real manda) sobre selected_frame_ids.length', () => {
    const phase = mapSearchJobToPhase(
      buildJob({
        metrics: { stage: 'searching', frames_processed: 4, frames_total: 20 },
        selected_frame_ids: ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'],
      }),
    )
    expect(phase.counter).toEqual({ done: 4, total: 20 })
  })

  it('stage de busca sem frames_processed não inventa counter', () => {
    const phase = mapSearchJobToPhase(
      buildJob({ metrics: { stage: 'searching' }, selected_frame_ids: ['a', 'b'] }),
    )
    expect(phase.counter).toBeUndefined()
  })

  it('completed usa findings_count (plural)', () => {
    const phase = mapSearchJobToPhase(buildJob({ status: 'completed', findings_count: 5 }))
    expect(phase.key).toBe('completed')
    expect(phase.label).toBe('5 achados encontrados')
    expect(phase.terminal).toBe(true)
  })

  it('completed com 1 achado usa singular', () => {
    const phase = mapSearchJobToPhase(buildJob({ status: 'completed', findings_count: 1 }))
    expect(phase.label).toBe('1 achado encontrado')
  })

  it('completed com 0 achados', () => {
    const phase = mapSearchJobToPhase(buildJob({ status: 'completed', findings_count: 0 }))
    expect(phase.label).toBe('0 achados encontrados')
  })

  it('failed expõe error_reason como detalhe quando não há failure_kind conhecido', () => {
    const phase = mapSearchJobToPhase(
      buildJob({ status: 'failed', error_reason: 'Traceback: RuntimeError na GPU' }),
    )
    expect(phase.key).toBe('failed')
    expect(phase.label).toBe('a busca falhou')
    expect(phase.detail).toBe('Traceback: RuntimeError na GPU')
    expect(phase.failed).toBe(true)
    expect(phase.terminal).toBe(true)
  })

  // failure_kind é gravado por tasks/search.py::_record_failure_metrics — mesmo
  // vocabulário de tasks/propagation.py::_classify_failure_kind.
  it('failed com failure_kind=cost_cap', () => {
    const phase = mapSearchJobToPhase(
      buildJob({ status: 'failed', metrics: { failure_kind: 'cost_cap' } }),
    )
    expect(phase.label).toBe('a busca passou do limite de custo e foi interrompida')
    expect(phase.detail).toBeUndefined()
  })

  it('failed com failure_kind=timeout', () => {
    const phase = mapSearchJobToPhase(
      buildJob({ status: 'failed', metrics: { failure_kind: 'timeout' } }),
    )
    expect(phase.label).toBe('a busca demorou mais que o permitido')
  })

  it('failed com failure_kind=pod_died', () => {
    const phase = mapSearchJobToPhase(
      buildJob({ status: 'failed', metrics: { failure_kind: 'pod_died' } }),
    )
    expect(phase.label).toBe('a máquina de GPU falhou')
  })

  it('failed com failure_kind=stopped vira key "stopped" (mesmo failed=true)', () => {
    const phase = mapSearchJobToPhase(
      buildJob({ status: 'failed', metrics: { failure_kind: 'stopped' } }),
    )
    expect(phase.key).toBe('stopped')
    expect(phase.label).toBe('busca interrompida')
    expect(phase.failed).toBe(true)
  })

  it('failed com failure_kind=executor_error (desconhecido) cai no error_reason cru', () => {
    const phase = mapSearchJobToPhase(
      buildJob({
        status: 'failed',
        metrics: { failure_kind: 'executor_error' },
        error_reason: 'ValueError: manifesto sem termos',
      }),
    )
    expect(phase.label).toBe('a busca falhou')
    expect(phase.detail).toBe('ValueError: manifesto sem termos')
  })

  it('stopped', () => {
    const phase = mapSearchJobToPhase(buildJob({ status: 'stopped' }))
    expect(phase.key).toBe('stopped')
    expect(phase.label).toBe('busca interrompida')
    expect(phase.terminal).toBe(true)
    expect(phase.failed).toBe(false)
  })

  it('stage desconhecido nunca quebra a barra — fallback "Processando"', () => {
    const phase = mapSearchJobToPhase(buildJob({ metrics: { stage: 'algo-novo-do-executor' } }))
    expect(phase.key).toBe('unknown')
    expect(phase.label).toBe('Processando')
    expect(phase.terminal).toBe(false)
    expect(phase.failed).toBe(false)
  })
})

describe('groupFindings', () => {
  it('agrupa por termo preservando ordem de primeira ocorrência', () => {
    const results = [
      buildFinding({ term: 'glove', label: 'luva', frame_id: 'f1', confidence: 0.9 }),
      buildFinding({ term: 'safety helmet', label: 'capacete', frame_id: 'f2', confidence: 0.7 }),
      buildFinding({ term: 'glove', label: 'luva', frame_id: 'f1', confidence: 0.5 }),
    ]
    const groups = groupFindings(results)
    expect(groups.map(g => g.term)).toEqual(['glove', 'safety helmet'])
  })

  it('conta imagens DISTINTAS (frameCount) mesmo com múltiplos achados no mesmo frame', () => {
    const results = [
      buildFinding({ term: 'glove', frame_id: 'f1' }),
      buildFinding({ term: 'glove', frame_id: 'f1' }),
      buildFinding({ term: 'glove', frame_id: 'f2' }),
    ]
    const [group] = groupFindings(results)
    expect(group.frameCount).toBe(2)
    expect(group.indices).toEqual([0, 1, 2])
  })

  it('calcula confiança média do grupo', () => {
    const results = [
      buildFinding({ term: 'glove', confidence: 1.0 }),
      buildFinding({ term: 'glove', confidence: 0.5 }),
    ]
    const [group] = groupFindings(results)
    expect(group.avgConfidence).toBeCloseTo(0.75)
  })

  it('lista vazia → nenhum grupo', () => {
    expect(groupFindings([])).toEqual([])
  })
})

describe('ressurgimento pós-reload (isSearchJobDismissed/dismissSearchJob/pickSearchJobToResurface)', () => {
  beforeEach(() => {
    const mem = new Map<string, string>()
    ;(globalThis as Record<string, unknown>).localStorage = {
      getItem: (k: string) => (mem.has(k) ? mem.get(k)! : null),
      setItem: (k: string, v: string) => void mem.set(k, v),
      removeItem: (k: string) => void mem.delete(k),
    }
  })

  // created_at dinâmico: o buildJob usa uma data FIXA ('2026-08-11T12:00Z'),
  // que virou bomba-relógio — "terminal recente (<24h) ressurge" passou até
  // 2026-08-12T12:00Z e começou a falhar em TODO PR do repo exatamente às
  // 12:00Z (quebra observada no CI do PR #369, docs-only). Ressurgimento
  // depende de Date.now() — fixtures deste bloco precisam de "agora".
  const base = (over: Partial<SearchJob>): SearchJob =>
    buildJob({ status: 'completed', created_at: new Date().toISOString(), ...over })

  it('job ativo vence sempre, mesmo mais antigo', () => {
    const oldActive = base({ id: 'a', status: 'running', created_at: new Date(Date.now() - 3600_000).toISOString() })
    const newDone = base({ id: 'b', status: 'completed' })
    expect(pickSearchJobToResurface([newDone, oldActive])?.id).toBe('a')
  })

  it('terminal recente não dispensado ressurge', () => {
    const failed = base({ id: 'f', status: 'failed' })
    expect(pickSearchJobToResurface([failed])?.id).toBe('f')
  })

  it('terminal dispensado não ressurge', () => {
    const failed = base({ id: 'dispensado', status: 'failed' })
    dismissSearchJob('dispensado')
    expect(isSearchJobDismissed('dispensado')).toBe(true)
    expect(pickSearchJobToResurface([failed])).toBeNull()
  })

  it('terminal velho (>24h) não ressurge', () => {
    const old = base({ id: 'v', status: 'failed', created_at: new Date(Date.now() - 25 * 3600_000).toISOString() })
    expect(pickSearchJobToResurface([old])).toBeNull()
  })

  it('lista vazia → null', () => {
    expect(pickSearchJobToResurface([])).toBeNull()
  })
})
