/**
 * Testes: lógica pura da aba "Classificar" (cropClassifierLogic.ts).
 * Sem React, sem rede — cobre exatamente os 4 itens de aceite pedidos:
 * (a) exclusividade dentro do tipo, (b) multilabel entre tipos,
 * (c) resolução estado→class_id incl. "classe a criar",
 * (d) payload de aprovação = uma caixa por estado ativo, mesmo bbox.
 */
import { describe, expect, it } from 'vitest'
import {
  deveAutoAvancar,
  EPI_TYPES,
  KEY_BINDINGS,
  buildApprovalPayload,
  resolveClassId,
  setVerdictState,
  stateForKey,
  suggestedPresenceStates,
  type RuntimeClass,
  type Verdict,
} from './cropClassifierLogic'

const CLASSES: RuntimeClass[] = [
  { classId: 101, name: 'Protetor auditivo' },
  { classId: 102, name: 'Sem protetor de ouvido' },
  { classId: 103, name: 'mascara' },
  { classId: 104, name: 'Sem mascara' },
  { classId: 105, name: 'Sem botas' },
  { classId: 106, name: 'óculos' }, // catálogo real tem minúsculo
]

describe('setVerdictState — exclusividade dentro do tipo', () => {
  it('trocar de Presente para Ausente no MESMO tipo substitui, nunca acumula', () => {
    let v: Verdict = {}
    v = setVerdictState(v, 'auditiva', 'presente')
    expect(v.auditiva).toBe('presente')
    v = setVerdictState(v, 'auditiva', 'ausente')
    expect(v.auditiva).toBe('ausente')
    // impossível marcar as duas ao mesmo tempo — é uma única chave no objeto
    expect(Object.keys(v).filter(k => k === 'auditiva')).toHaveLength(1)
  })
})

describe('setVerdictState — multilabel entre tipos', () => {
  it('auditiva=Presente E máscara=Ausente coexistem no mesmo veredito', () => {
    let v: Verdict = {}
    v = setVerdictState(v, 'auditiva', 'presente')
    v = setVerdictState(v, 'mascara', 'ausente')
    expect(v).toEqual({ auditiva: 'presente', mascara: 'ausente' })
  })

  it('decidir um tipo não mexe nos outros já decididos', () => {
    let v: Verdict = { auditiva: 'presente', botas: 'nao_visivel' }
    v = setVerdictState(v, 'oculos', 'ausente')
    expect(v.auditiva).toBe('presente')
    expect(v.botas).toBe('nao_visivel')
    expect(v.oculos).toBe('ausente')
  })
})

describe('resolveClassId — estado→class_id incl. "classe a criar"', () => {
  it('resolve por nome, case-insensitive/trim', () => {
    expect(resolveClassId(['Óculos', 'óculos'], CLASSES)).toBe(106)
    expect(resolveClassId(['PROTETOR AUDITIVO'], CLASSES)).toBe(101)
  })

  it('candidato ausente do catálogo → null ("classe a criar")', () => {
    expect(resolveClassId(['Botas'], CLASSES)).toBeNull() // não existe "Botas" no catálogo mockado
    expect(resolveClassId(['Uso incorreto'], CLASSES)).toBeNull()
  })

  it('lista de candidatos vazia (não visível) → null, sem heurística', () => {
    expect(resolveClassId([], CLASSES)).toBeNull()
  })
})

describe('buildApprovalPayload — payload de Aprovar', () => {
  const bbox: [number, number, number, number] = [0.1, 0.2, 0.5, 0.6] // x,y,w,h

  it('uma caixa por estado ATIVO resolvido, todas com o MESMO bbox do recorte', () => {
    const verdict: Verdict = { auditiva: 'presente', mascara: 'ausente' }
    const { payload, missing } = buildApprovalPayload(verdict, bbox, CLASSES)
    expect(payload).toHaveLength(2)
    expect(payload).toEqual(
      expect.arrayContaining([
        { class_id: 101, class_name: 'Protetor auditivo', module_code: 'epi', x_center: 0.35, y_center: 0.5, width: 0.5, height: 0.6 },
        { class_id: 104, class_name: 'Sem mascara', module_code: 'epi', x_center: 0.35, y_center: 0.5, width: 0.5, height: 0.6 },
      ]),
    )
    expect(missing).toHaveLength(0)
  })

  it('"não visível" nunca gera caixa', () => {
    const verdict: Verdict = { auditiva: 'nao_visivel' }
    const { payload, missing } = buildApprovalPayload(verdict, bbox, CLASSES)
    expect(payload).toHaveLength(0)
    expect(missing).toHaveLength(0)
  })

  it('estado sem classe no catálogo vira "missing" e NÃO trava os outros tipos do recorte', () => {
    const verdict: Verdict = { auditiva: 'presente', botas: 'presente' } // "Botas" não está no catálogo mockado
    const { payload, missing } = buildApprovalPayload(verdict, bbox, CLASSES)
    expect(payload).toEqual([
      { class_id: 101, class_name: 'Protetor auditivo', module_code: 'epi', x_center: 0.35, y_center: 0.5, width: 0.5, height: 0.6 },
    ])
    expect(missing).toEqual([
      { typeKey: 'botas', typeLabel: 'Botas', stateKey: 'presente', stateLabel: 'Presente', candidates: ['Botas'] },
    ])
  })

  it('tipo não decidido (undefined) não entra no payload nem em missing', () => {
    const { payload, missing } = buildApprovalPayload({}, bbox, CLASSES)
    expect(payload).toHaveLength(0)
    expect(missing).toHaveLength(0)
  })
})

describe('suggestedPresenceStates — sugestão soft (bloco 3)', () => {
  it('sugere só o estado de PRESENÇA cuja classe bate com uma proposta de IA', () => {
    const suggested = suggestedPresenceStates([101], CLASSES) // proposta = "Protetor auditivo"
    expect(suggested.has('auditiva:presente')).toBe(true)
    expect(suggested.size).toBe(1)
  })

  it('NUNCA sugere estado de ausência, mesmo se a classe bater', () => {
    // 102 = "Sem protetor de ouvido" (ausente) — não deve gerar sugestão nenhuma
    const suggested = suggestedPresenceStates([102], CLASSES)
    expect(suggested.size).toBe(0)
  })

  it('sem proposta correspondente → conjunto vazio, sem inventar nada', () => {
    expect(suggestedPresenceStates([], CLASSES).size).toBe(0)
    expect(suggestedPresenceStates([9999], CLASSES).size).toBe(0)
  })
})

describe('KEY_BINDINGS — sem colisão de tecla', () => {
  it('cada tecla aparece uma única vez', () => {
    const keys = KEY_BINDINGS.map(b => b.key)
    expect(new Set(keys).size).toBe(keys.length)
  })

  it('toda combinação typeKey/stateKey do mapa de teclas existe em EPI_TYPES', () => {
    for (const binding of KEY_BINDINGS) {
      const type = EPI_TYPES.find(t => t.key === binding.typeKey)
      expect(type, `tipo ${binding.typeKey} não existe`).toBeTruthy()
      const state = type?.states.find(s => s.key === binding.stateKey)
      expect(state, `estado ${binding.typeKey}.${binding.stateKey} não existe`).toBeTruthy()
    }
  })

  it('stateForKey resolve minúsculo/maiúsculo pra mesma combinação', () => {
    expect(stateForKey('a')).toEqual({ key: 'a', typeKey: 'botas', stateKey: 'presente' })
    expect(stateForKey('A')).toEqual({ key: 'a', typeKey: 'botas', stateKey: 'presente' })
    expect(stateForKey('9')).toBeNull()
  })
})

describe('buildApprovalPayload — campos exigidos pelo backend (regressão)', () => {
  const bbox: [number, number, number, number] = [0, 0, 1, 1]

  // annotation_service._validate_class recusa o batch INTEIRO com 400 se
  // class_name ou module_code vierem vazios. Omiti-los fazia todo "Aprovar"
  // da aba Classificar falhar de forma permanente — a aprovação ficava
  // pendente para sempre e nenhum retry resolvia.
  it('toda caixa leva class_name e module_code não-vazios', () => {
    const verdict: Verdict = { auditiva: 'presente', mascara: 'ausente' }
    const { payload } = buildApprovalPayload(verdict, bbox, CLASSES)
    expect(payload.length).toBeGreaterThan(0)
    for (const box of payload) {
      expect(box.class_name).toBeTruthy()
      expect(box.module_code).toBeTruthy()
    }
  })

  it('o nome enviado é o da classe resolvida, não um rótulo inventado', () => {
    const { payload } = buildApprovalPayload({ auditiva: 'presente' }, bbox, CLASSES)
    const cls = CLASSES.find(c => c.classId === payload[0].class_id)
    expect(payload[0].class_name).toBe(cls?.name)
  })

  it('module_code é configurável e cai em "epi" por padrão', () => {
    const { payload } = buildApprovalPayload({ auditiva: 'presente' }, bbox, CLASSES, 'qualidade')
    expect(payload[0].module_code).toBe('qualidade')
    const { payload: def } = buildApprovalPayload({ auditiva: 'presente' }, bbox, CLASSES)
    expect(def[0].module_code).toBe('epi')
  })
})

describe('deveAutoAvancar', () => {
  const bindingMascara = { key: 'q', typeKey: 'mascara', stateKey: 'presente' } as const

  it('avança quando a tecla é do tipo em foco', () => {
    expect(deveAutoAvancar(bindingMascara, 'mascara', true)).toBe(true)
  })

  it('NÃO avança sem classe em foco — o recorte pode precisar de vários tipos', () => {
    expect(deveAutoAvancar(bindingMascara, null, true)).toBe(false)
  })

  it('NÃO avança quando a tecla é de outro tipo que não o em foco', () => {
    expect(deveAutoAvancar(bindingMascara, 'botas', true)).toBe(false)
  })

  it('respeita o desligamento', () => {
    expect(deveAutoAvancar(bindingMascara, 'mascara', false)).toBe(false)
  })
})
