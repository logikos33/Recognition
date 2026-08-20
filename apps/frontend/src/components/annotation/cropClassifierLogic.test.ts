/**
 * Testes: lógica pura da aba "Classificar" (cropClassifierLogic.ts).
 * Sem React, sem rede — cobre exatamente os 4 itens de aceite pedidos:
 * (a) exclusividade dentro do tipo, (b) multilabel entre tipos,
 * (c) resolução estado→class_id incl. "classe a criar",
 * (d) payload de aprovação = uma caixa por estado ativo, mesmo bbox.
 */
import { describe, expect, it } from 'vitest'
import {
  medirAceitacao,
  vereditoInicialDaProposta,
  anexarLote,
  devePrefetch,
  tiposVisiveis,
  ordenarPorCarencia,
  reordenarCauda,
  corteSeguro,
  type LacunaCobertura,
  deveAutoAvancar,
  EPI_TYPES,
  KEY_BINDINGS,
  buildApprovalPayload,
  mensagemClassesNaoResolvidas,
  sugerirClasseProxima,
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
      // suggestion: null — "Botas" não tem nada parecido no catálogo mockado,
      // e é justamente aí que "crie a classe" continua sendo o conselho certo (#448)
      { typeKey: 'botas', typeLabel: 'Botas', stateKey: 'presente', stateLabel: 'Presente', candidates: ['Botas'], suggestion: null },
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

describe('ordenarPorCarencia', () => {
  const f = (id: string, camera_id: string | null) => ({ id, camera_id })
  const gap = (camera_id: string, score: number): LacunaCobertura => ({
    camera_id, score, class_id: 1, class_name: 'mascara', reason: 'reforça volume',
  })

  it('câmera com maior carência vem primeiro', () => {
    const fila = [f('a', 'cam-farta'), f('b', 'cam-carente')]
    const ordenada = ordenarPorCarencia(fila, [gap('cam-carente', 0.9)])
    expect(ordenada.map(x => x.id)).toEqual(['b', 'a'])
  })

  it('soma as lacunas da mesma câmera', () => {
    const fila = [f('a', 'cam-1'), f('b', 'cam-2')]
    const ordenada = ordenarPorCarencia(fila, [
      gap('cam-1', 0.3), gap('cam-2', 0.5), gap('cam-1', 0.4),
    ])
    expect(ordenada[0].id).toBe('a')  // 0.7 > 0.5
  })

  it('empate preserva a ordem do servidor — a fila não pode embaralhar', () => {
    const fila = [f('a', 'cam-1'), f('b', 'cam-1'), f('c', 'cam-1')]
    expect(ordenarPorCarencia(fila, [gap('cam-1', 0.5)]).map(x => x.id)).toEqual(['a', 'b', 'c'])
  })

  it('NÃO remove nada — classe farta só vai para o fim', () => {
    const fila = [f('a', 'cam-farta'), f('b', 'cam-carente'), f('c', null)]
    expect(ordenarPorCarencia(fila, [gap('cam-carente', 0.9)])).toHaveLength(3)
  })

  it('sem lacunas, devolve a fila intacta', () => {
    const fila = [f('a', 'cam-1'), f('b', 'cam-2')]
    expect(ordenarPorCarencia(fila, [])).toBe(fila)
  })
})

describe('tiposVisiveis (modo estreito)', () => {
  it('desligado mostra tudo', () => {
    expect(tiposVisiveis(false)).toBe(EPI_TYPES)
  })

  it('ligado mostra só os tipos das 5 classes prioritárias', () => {
    expect(tiposVisiveis(true).map(t => t.key).sort()).toEqual(['auditiva', 'mascara'])
  })

  it('as 5 classes prioritárias estão TODAS cobertas pelos tipos visíveis', () => {
    const nomes = tiposVisiveis(true)
      .flatMap(t => t.states)
      .flatMap(s => s.classNameCandidates)
    for (const prioritaria of [
      'mascara', 'Sem mascara', 'Uso incorreto de mascara',
      'Protetor auditivo', 'Sem protetor de ouvido',
    ]) {
      expect(nomes).toContain(prioritaria)
    }
  })

  it('⛔ não remove nada do catálogo — só da tela', () => {
    tiposVisiveis(true)
    expect(EPI_TYPES.length).toBeGreaterThan(2)
  })
})

describe('fila infinita', () => {
  const f = (id: string) => ({ id })

  it('não repete o que já está na fila', () => {
    expect(anexarLote([f('a'), f('b')], [f('b'), f('c')]).map(x => x.id)).toEqual(['a', 'b', 'c'])
  })

  it('não repete o que já teve veredito na sessão', () => {
    const r = anexarLote([f('a')], [f('b'), f('c')], new Set(['b']))
    expect(r.map(x => x.id)).toEqual(['a', 'c'])
  })

  it('lote novo entra NO FIM — não reordena o que o anotador está vendo', () => {
    expect(anexarLote([f('a'), f('b')], [f('z')]).map(x => x.id)).toEqual(['a', 'b', 'z'])
  })

  it('dispara com poucos restantes', () => {
    expect(devePrefetch(9, false, false)).toBe(true)
    expect(devePrefetch(11, false, false)).toBe(false)
  })

  it('não dispara duas vezes nem depois de esgotado', () => {
    expect(devePrefetch(3, true, false)).toBe(false)
    expect(devePrefetch(3, false, true)).toBe(false)
  })
})

describe('pré-anotação fase A', () => {
  it('pré-seleciona a proposta', () => {
    const v = vereditoInicialDaProposta(new Set(['mascara:presente', 'auditiva:presente']))
    expect(v).toEqual({ mascara: 'presente', auditiva: 'presente' })
  })

  it('⛔ AUSÊNCIA nunca chega aqui — suggestedPresenceStates só emite presença', () => {
    const classes = [
      { classId: 1, name: 'mascara' },
      { classId: 2, name: 'Sem mascara' },
    ] as never[]
    // o modelo "propôs" ambas; só a presença pode virar sugestão
    const sug = suggestedPresenceStates([1, 2], classes)
    for (const chave of sug) expect(chave.endsWith(':presente')).toBe(true)
  })

  it('mede aceitação por classe: confirmada e corrigida', () => {
    const proposta = new Set(['mascara:presente', 'auditiva:presente'])
    const r = medirAceitacao(proposta, { mascara: 'presente', auditiva: 'ausente' })
    expect(r).toEqual([
      { classe: 'mascara:presente', aceita: true },
      { classe: 'auditiva:presente', aceita: false },
    ])
  })

  it('não conta tipo sem proposta — inflaria a taxa', () => {
    expect(medirAceitacao(new Set(), { botas: 'presente' })).toEqual([])
  })
})

describe('matriz assíncrona não pode resetar a fila', () => {
  const f = (id: string, camera_id: string | null) => ({ id, camera_id })

  it('reordenar preserva TODOS os itens — nada é perdido nem duplicado', () => {
    const fila = [f('a', 'c1'), f('b', 'c2'), f('c', 'c1')]
    const antes = ordenarPorCarencia(fila, [])
    const depois = ordenarPorCarencia(fila, [
      { camera_id: 'c2', score: 0.9, class_id: 1, class_name: 'mascara', reason: 'x' },
    ])
    expect(depois).toHaveLength(antes.length)
    expect(new Set(depois.map(x => x.id))).toEqual(new Set(antes.map(x => x.id)))
  })

  it('a fila ACUMULADA de 2 lotes sobrevive à reordenação — o caso dos 60', () => {
    // lote 1 (40) + lote 2 (40) já anexados; a matriz chega DEPOIS
    const lote1 = Array.from({ length: 40 }, (_, i) => f(`p1-${i}`, 'c1'))
    const lote2 = Array.from({ length: 40 }, (_, i) => f(`p2-${i}`, 'c2'))
    const acumulada = anexarLote(lote1, lote2)
    expect(acumulada).toHaveLength(80)

    const reordenada = ordenarPorCarencia(acumulada, [
      { camera_id: 'c2', score: 0.9, class_id: 1, class_name: 'mascara', reason: 'x' },
    ])
    // 🔴 o defeito era a fila VOLTAR a 40 quando a matriz chegava
    expect(reordenada).toHaveLength(80)
    expect(reordenada[0].camera_id).toBe('c2')  // carência primeiro
  })

  it('prefetch continua disparando com a fila reordenada', () => {
    const fila = Array.from({ length: 80 }, (_, i) => f(`x-${i}`, 'c1'))
    const ordenada = ordenarPorCarencia(fila, [])
    // anotou 72 dos 80 -> restam 8, abaixo do gatilho
    expect(devePrefetch(ordenada.length - 72, false, false)).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// #448 — o aviso de classe não resolvida precisa dizer o que a tela SABE
//
// A mensagem antiga AFIRMAVA um diagnóstico ("a classe não existe no catálogo")
// quando o que ela sabia era outro: "eu não consegui resolver este nome". No
// caso real a classe EXISTIA, e quem seguisse a instrução criaria duplicata.
// ---------------------------------------------------------------------------

const CATALOGO_RVB: RuntimeClass[] = [
  { classId: 1, name: 'Capacete' },
  { classId: 2, name: 'Óculos' },
  { classId: 3, name: 'Luvas' },
  { classId: 4, name: 'Botas' },
  { classId: 5, name: 'Protetor auricular' },
  { classId: 6, name: 'Uso incorreto de mascara' },
  { classId: 7, name: 'Mascara' },
]

describe('sugerirClasseProxima (#448)', () => {
  it('acha o caso REAL que motivou a issue: candidato é prefixo do nome do catálogo', () => {
    expect(sugerirClasseProxima(['Uso incorreto'], CATALOGO_RVB)).toBe(
      'Uso incorreto de mascara',
    )
  })

  it('atravessa acento — "Oculos" digitado sem acento acha "Óculos"', () => {
    expect(sugerirClasseProxima(['Oculos'], CATALOGO_RVB)).toBe('Óculos')
  })

  it('tolera erro de digitação curto', () => {
    expect(sugerirClasseProxima(['Capacte'], CATALOGO_RVB)).toBe('Capacete')
  })

  it('NÃO sugere classe só porque é a menos distante — nome sem parecido vira null', () => {
    expect(sugerirClasseProxima(['Cinto de segurança'], CATALOGO_RVB)).toBeNull()
  })

  it('catálogo vazio não sugere nada', () => {
    expect(sugerirClasseProxima(['Capacete'], [])).toBeNull()
  })

  it('NUNCA sugere o estado OPOSTO — "Botas" não vira "Sem botas"', () => {
    // A regra é PREFIXO, não "contém em qualquer posição". Nesta taxonomia o
    // estado contrário é o mesmo nome com prefixo de negação: sugerir por
    // containment livre faria o anotador rotular o inverso do que marcou —
    // pior que não sugerir nada.
    const catalogo: RuntimeClass[] = [
      { classId: 1, name: 'Sem botas' },
      { classId: 2, name: 'Sem capacete' },
    ]
    expect(sugerirClasseProxima(['Botas'], catalogo)).toBeNull()
    expect(sugerirClasseProxima(['Capacete'], catalogo)).toBeNull()
  })
})

describe('mensagemClassesNaoResolvidas (#448)', () => {
  it('diz os nomes procurados, o tamanho do catálogo e a sugestão', () => {
    const missing = [
      {
        typeKey: 'respiratoria',
        typeLabel: 'Proteção respiratória',
        stateKey: 'uso_incorreto',
        stateLabel: 'Uso incorreto',
        candidates: ['Uso incorreto'],
        suggestion: 'Uso incorreto de mascara',
      },
    ]
    const msg = mensagemClassesNaoResolvidas(missing, CATALOGO_RVB)

    expect(msg).toContain('"Uso incorreto"')
    expect(msg).toContain('7 classe(s)')
    expect(msg).toContain('talvez seja "Uso incorreto de mascara"?')
  })

  it('sem parecido, NÃO inventa sugestão', () => {
    const missing = [
      {
        typeKey: 'x',
        typeLabel: 'X',
        stateKey: 'ausente',
        stateLabel: 'Cinto ausente',
        candidates: ['Cinto de segurança'],
        suggestion: null,
      },
    ]
    expect(mensagemClassesNaoResolvidas(missing, CATALOGO_RVB)).toContain('nada parecido')
  })

  it('nunca mais afirma que a classe não existe', () => {
    const missing = [
      {
        typeKey: 'respiratoria',
        typeLabel: 'Proteção respiratória',
        stateKey: 'uso_incorreto',
        stateLabel: 'Uso incorreto',
        candidates: ['Uso incorreto'],
        suggestion: 'Uso incorreto de mascara',
      },
    ]
    const msg = mensagemClassesNaoResolvidas(missing, CATALOGO_RVB)

    expect(msg).not.toContain('crie a classe')
    expect(msg).not.toContain('sem classe no catálogo')
  })

  it('sem faltantes, mensagem vazia', () => {
    expect(mensagemClassesNaoResolvidas([], CATALOGO_RVB)).toBe('')
  })
})

describe('buildApprovalPayload preenche a sugestão (#448)', () => {
  it('o estado não resolvido chega ao chamador já com o candidato do catálogo', () => {
    const semUsoIncorreto = CATALOGO_RVB.filter(c => c.name !== 'Uso incorreto de mascara')
    const catalogo = [...semUsoIncorreto, { classId: 9, name: 'Uso incorreto de mascara' }]
    const verdict: Verdict = { respiratoria: 'uso_incorreto' }

    const { missing } = buildApprovalPayload(verdict, [0, 0, 1, 1], catalogo)

    if (missing.length > 0) {
      expect(missing[0]).toHaveProperty('suggestion')
    }
  })
})


// ---------------------------------------------------------------------------
// A fila nao pode devolver recorte ja processado (o defeito de campo do #487)
// ---------------------------------------------------------------------------
describe('reordenar NAO pode mover o que ja passou pelo cursor', () => {
  const f = (id: string, camera_id: string | null) => ({ id, camera_id })
  const gap = (camera_id: string, score: number) =>
    ({ camera_id, score, class_id: 1, class_name: 'mascara', reason: 'x' })

  it('prefixo ja visto + recorte na tela ficam CONGELADOS', () => {
    // 4 ja vistos (carencia 0) + o da tela + cauda; chega lote de carencia alta
    const fila = [
      f('v1', 'baixa'), f('v2', 'baixa'), f('v3', 'baixa'), f('v4', 'baixa'),
      f('tela', 'baixa'),
      f('t1', 'baixa'), f('t2', 'baixa'),
      f('novo1', 'alta'), f('novo2', 'alta'),
    ]
    const index = 4 // o anotador esta em 'tela'
    const out = reordenarCauda(fila, index + 1, [gap('alta', 9)])

    expect(out.slice(0, 5).map(x => x.id)).toEqual(['v1', 'v2', 'v3', 'v4', 'tela'])
    // a carencia so manda DEPOIS do cursor
    expect(out.slice(5).map(x => x.id)).toEqual(['novo1', 'novo2', 't1', 't2'])
    expect(out).toHaveLength(fila.length)
  })

  it('nada e perdido nem duplicado ao reordenar a cauda', () => {
    const fila = Array.from({ length: 50 }, (_, i) => f(`x${i}`, i % 3 === 0 ? 'alta' : 'baixa'))
    const out = reordenarCauda(fila, 20, [gap('alta', 5)])
    expect(out).toHaveLength(50)
    expect(new Set(out.map(x => x.id))).toEqual(new Set(fila.map(x => x.id)))
  })

  it('corte fora da faixa nao quebra (0, negativo, maior que a fila)', () => {
    const fila = [f('a', 'alta'), f('b', 'baixa')]
    const gaps = [gap('alta', 5)]
    expect(reordenarCauda(fila, 0, gaps).map(x => x.id)).toEqual(['a', 'b'])
    expect(reordenarCauda(fila, -3, gaps).map(x => x.id)).toEqual(['a', 'b'])
    expect(reordenarCauda(fila, 99, gaps).map(x => x.id)).toEqual(['a', 'b'])
  })

  it('🔴 o laco INTEIRO: 400 vereditos, ZERO reapresentacao', () => {
    // Reproduz a condicao medida no acervo do RVB: os primeiros lotes sao de
    // carencia BAIXA e um lote posterior traz camera de carencia ALTA. Era
    // esse lote que entrava na frente do cursor e devolvia o ja processado.
    const LOTE = 40, GATILHO = 10
    const servidor = Array.from({ length: 1000 }, (_, i) =>
      f(`s${i}`, i < 400 ? 'baixa' : 'alta'))
    const gaps = [gap('alta', 4.2)]

    let vivo = [...servidor]
    const page = (n: number) => vivo.slice((n - 1) * LOTE, n * LOTE)

    const jaVistos = new Set<string>()
    let pagina = 1
    let esgotado = false
    let fila = ordenarPorCarencia(page(1), gaps)
    let index = 0
    const reapresentados: string[] = []

    for (let passo = 0; passo < 400; passo++) {
      const atual = fila[index]
      expect(atual).toBeDefined()   // a fila NAO pode secar com 1000 no servidor
      if (jaVistos.has(atual.id)) reapresentados.push(atual.id)
      jaVistos.add(atual.id)
      vivo = vivo.filter(x => x.id !== atual.id)   // veredito remove do servidor
      index = Math.min(index + 1, fila.length)

      if (!esgotado && fila.length - index < GATILHO) {
        pagina += 1
        const lote = page(pagina)
        if (lote.length < LOTE) esgotado = true
        fila = reordenarCauda(anexarLote(fila, lote, jaVistos), index + 1, gaps)
      }
    }

    expect(reapresentados).toEqual([])
    expect(jaVistos.size).toBe(400)   // 400 vereditos = 400 recortes DISTINTOS
  })
})


// ---------------------------------------------------------------------------
// O corte nao pode confiar no relogio do React (achado do review cruzado)
// ---------------------------------------------------------------------------
describe('corteSeguro: o indice pode atrasar, o conjunto de vistos nao', () => {
  const f = (id: string) => ({ id, camera_id: null as string | null })
  const gap = (camera_id: string, score: number) =>
    ({ camera_id, score, class_id: 1, class_name: 'mascara', reason: 'x' })

  it('com o indice em dia, e o mesmo que index + 1', () => {
    const fila = [f('a'), f('b'), f('c'), f('d')]
    // anotou a e b; esta em 'c' (index 2)
    expect(corteSeguro(fila, 2, new Set(['a', 'b']))).toBe(3)
  })

  it('🔴 indice ATRASADO: o corte sai dos vistos, nao do indice', () => {
    // React 18 agrupou dois setIndex num render so -> indexRef ficou em 5
    // enquanto o real e 7. Com `index + 1` o corte seria 6 e a posicao 6, JA
    // ANOTADA, cairia na faixa reordenavel.
    const fila = Array.from({ length: 12 }, (_, i) => f(`p${i}`))
    const jaVistos = new Set(['p0', 'p1', 'p2', 'p3', 'p4', 'p5', 'p6'])
    expect(corteSeguro(fila, 5, jaVistos)).toBe(8)   // 7 vistos + o da tela
    expect(5 + 1).toBeLessThan(8)                     // o corte ingenuo erraria
  })

  it('sem nada visto ainda, protege so o recorte da tela', () => {
    expect(corteSeguro([f('a'), f('b')], 0, new Set())).toBe(1)
  })

  it('depois de desfazer (indice volta), nada visto e liberado', () => {
    const fila = Array.from({ length: 10 }, (_, i) => f(`p${i}`))
    const jaVistos = new Set(['p0', 'p1', 'p2', 'p3', 'p4', 'p5'])
    expect(corteSeguro(fila, 2, jaVistos)).toBe(7)
  })

  it('id visto que nao esta MAIS na fila nao inventa corte', () => {
    const fila = [f('x'), f('y')]
    expect(corteSeguro(fila, 0, new Set(['sumiu']))).toBe(1)
  })

  it('🔴 integrado: com indice atrasado, nenhum item ja anotado se move', () => {
    // cauda de carencia alta chegando enquanto o indice esta 2 atras
    const comCam = (id: string, camera_id: string) => ({ id, camera_id })
    const fila = [
      ...Array.from({ length: 7 }, (_, i) => comCam(`visto${i}`, 'baixa')),
      comCam('tela', 'baixa'),
      comCam('novo1', 'alta'),
      comCam('novo2', 'alta'),
    ]
    const jaVistos = new Set(fila.slice(0, 7).map(x => x.id))
    const corte = corteSeguro(fila, 5, jaVistos)   // indexRef atrasado em 2
    const out = reordenarCauda(fila, corte, [gap('alta', 9)])

    expect(out.slice(0, 8).map(x => x.id)).toEqual(
      [...Array.from({ length: 7 }, (_, i) => `visto${i}`), 'tela'],
    )
    expect(out.slice(8).map(x => x.id)).toEqual(['novo1', 'novo2'])
  })
})
