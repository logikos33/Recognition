import { describe, expect, it } from 'vitest'
import {
  CLASS_LABELS,
  COUNTING_SESSION_OVERRIDES,
  DIRECTION_LABELS,
  INTEGRATION_LABELS,
  MODULE_LABELS,
  PERIOD_LABELS,
  PRESET_LABELS,
  ROLE_LABELS,
  STATUS_LABELS,
  TRAINING_STATUS_OVERRIDES,
  humanize,
  labelForClass,
  labelForModule,
  roleLabel,
  statusToLabel,
} from '../../utils/labels'
import { statusToBadgeVariant } from '../../components/ui/Badge/Badge'

describe('labels — labelForClass', () => {
  it('prefere display_name da API sobre o mapa estático', () => {
    expect(labelForClass('helmet', 'Capacete de obra')).toBe('Capacete de obra')
  })

  it('usa o mapa estático quando a API não fornece display_name', () => {
    expect(labelForClass('no_helmet')).toBe('Sem capacete')
    expect(labelForClass('fuel_nozzle')).toBe('Bico de combustível')
    expect(labelForClass('truck')).toBe('Caminhão')
  })

  it('cai em humanize para classe desconhecida', () => {
    expect(labelForClass('mystery_class')).toBe('Mystery class')
  })
})

describe('labels — statusToLabel', () => {
  it('traduz status conhecidos', () => {
    expect(statusToLabel('active')).toBe('Ativo')
    expect(statusToLabel('completed')).toBe('Concluído')
    expect(statusToLabel('idle')).toBe('Ocioso')
  })

  it('aplica override de contexto sobre o mapa geral', () => {
    expect(statusToLabel('running', TRAINING_STATUS_OVERRIDES)).toBe('Treinando')
    expect(statusToLabel('active', COUNTING_SESSION_OVERRIDES)).toBe('Em andamento')
    expect(statusToLabel('completed', COUNTING_SESSION_OVERRIDES)).toBe('Finalizada')
  })

  it('status desconhecido nunca renderiza vazio — cai em humanize', () => {
    expect(statusToLabel('some_new_status')).toBe('Some new status')
  })
})

describe('labels — humanize', () => {
  it('converte snake_case em frase capitalizada', () => {
    expect(humanize('fuel_nozzle')).toBe('Fuel nozzle')
    expect(humanize('kebab-case-key')).toBe('Kebab case key')
  })

  it('retorna a própria chave quando vazia', () => {
    expect(humanize('')).toBe('')
  })
})

describe('labels — módulos e papéis', () => {
  it('traduz módulos conhecidos', () => {
    expect(labelForModule('epi')).toBe('EPI')
    expect(labelForModule('fueling')).toBe('Abastecimento')
  })

  it('módulo desconhecido cai em humanize', () => {
    expect(labelForModule('warehouse')).toBe('Warehouse')
  })

  it('traduz papéis conhecidos e desconhecidos', () => {
    expect(roleLabel('operator')).toBe('Operador')
    expect(roleLabel('mystery_role')).toBe('Mystery role')
  })
})

describe('labels — completude dos dicionários', () => {
  it('nenhuma chave conhecida retorna vazio', () => {
    const allMaps = [
      CLASS_LABELS, MODULE_LABELS, STATUS_LABELS, ROLE_LABELS,
      DIRECTION_LABELS, PERIOD_LABELS, INTEGRATION_LABELS, PRESET_LABELS,
      TRAINING_STATUS_OVERRIDES, COUNTING_SESSION_OVERRIDES,
    ]
    for (const map of allMaps) {
      for (const [key, value] of Object.entries(map)) {
        expect(value, `chave "${key}" sem tradução`).toBeTruthy()
      }
    }
  })

  it('todas as chaves de statusToBadgeVariant têm entrada em STATUS_LABELS', () => {
    // Chaves mapeadas em statusToBadgeVariant (ui/Badge/Badge.tsx)
    const badgeStatuses = [
      'active', 'online', 'completed', 'extracted',
      'pending', 'starting', 'extracting',
      'error', 'failed',
      'running', 'uploaded',
      'stopped', 'inactive', 'offline',
    ]
    for (const status of badgeStatuses) {
      // sanidade: a chave é reconhecida pelo variant (não default por typo)
      expect(typeof statusToBadgeVariant(status)).toBe('string')
      expect(STATUS_LABELS[status], `status "${status}" sem tradução em STATUS_LABELS`).toBeTruthy()
    }
  })
})
