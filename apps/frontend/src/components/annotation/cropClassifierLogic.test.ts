/**
 * Testes: lógica pura da aba "Classificar" (cropClassifierLogic.ts).
 * Sem React, sem rede — cobre exatamente os 4 itens de aceite pedidos:
 * (a) exclusividade dentro do tipo, (b) multilabel entre tipos,
 * (c) resolução estado→class_id incl. "classe a criar",
 * (d) payload de aprovação = uma caixa por estado ativo, mesmo bbox.
 */
import {
  describe, expect, it,
} from 'vitest'
import {
  EPI_TYPES,
  KEY_BINDINGS,
  TIPOS_PRIORITARIOS,
  anexarLote,
  buildApprovalPayload,
  confiancaDasPropostas,
  corteSeguro,
  deveAutoAvancar,
  devePrefetch,
  lacunasDosTipos,
  medirAceitacao,
  mensagemClassesNaoResolvidas,
  nomesDeClasseDosTipos,
  ordenarPorCarencia,
  reordenarCauda,
  resolveClassId,
  setVerdictState,
  stateForKey,
  sugerirClasseProxima,
  suggestedPresenceStates,
  tiposVisiveis,
  intercalar,
  numeroDoBloco,
  reordenarCaudaIntercalada,
  temProposta,
  cadenciaValida,
  nomesDePresencaDosTipos,
  type Cadencia,
  type LacunaCobertura,
  type RuntimeClass,
  type Verdict,
  vereditoInicialDaProposta,
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

describe('tiposVisiveis (filtro por classe)', () => {
  const PRIORITARIAS = new Set<string>(TIPOS_PRIORITARIOS)

  it('sem escolha (conjunto vazio) mostra tudo — ⛔ nunca tela vazia', () => {
    expect(tiposVisiveis(new Set())).toBe(EPI_TYPES)
  })

  it('preset prioritárias mostra só os tipos prioritários (núcleo pós-reunião Paulo)', () => {
    expect(tiposVisiveis(PRIORITARIAS).map(t => t.key).sort()).toEqual(['auditiva', 'luvas', 'mascara', 'oculos'])
  })

  it('escolha arbitrária mostra exatamente os tipos escolhidos, na ordem do catálogo', () => {
    expect(tiposVisiveis(new Set(['luvas', 'mascara'])).map(t => t.key)).toEqual(['mascara', 'luvas'])
  })

  it('as 5 classes prioritárias estão TODAS cobertas pelos tipos visíveis', () => {
    const nomes = tiposVisiveis(PRIORITARIAS)
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
    tiposVisiveis(PRIORITARIAS)
    expect(EPI_TYPES.length).toBeGreaterThan(2)
  })
})

describe('nomesDeClasseDosTipos (param ?proposal_classes= da fila)', () => {
  it('vazio = sem filtro', () => {
    expect(nomesDeClasseDosTipos(new Set())).toEqual([])
  })

  it('traz presença E ausência E uso incorreto do tipo — proposta de "Sem mascara" é do tipo máscara', () => {
    const nomes = nomesDeClasseDosTipos(new Set(['mascara']))
    expect(nomes).toEqual(expect.arrayContaining(['mascara', 'Sem mascara', 'Uso incorreto de mascara']))
    expect(nomes).not.toContain('gloves')
  })

  it('sem duplicata', () => {
    const nomes = nomesDeClasseDosTipos(new Set(EPI_TYPES.map(t => t.key)))
    expect(new Set(nomes).size).toBe(nomes.length)
  })
})

describe('lacunasDosTipos (priorização por classe)', () => {
  // Nomes exatos que a matriz de cobertura emite (yolo_classes.name do tenant).
  const gap = (class_id: number, class_name: string, camera_id: string, score: number): LacunaCobertura =>
    ({ class_id, class_name, camera_id, score, reason: 'amplia cobertura' })

  const GAPS: LacunaCobertura[] = [
    gap(4, 'Protetor auditivo', 'cam-auditiva', 0.9),
    gap(7, 'Botas', 'cam-botas', 0.8),
    gap(3, 'mascara', 'cam-mascara', 0.7),
  ]

  it('sem escolha, não filtra nada (mesmo array)', () => {
    expect(lacunasDosTipos(GAPS, new Set())).toBe(GAPS)
  })

  it('escolher um tipo deixa só as lacunas das classes DELE', () => {
    expect(lacunasDosTipos(GAPS, new Set(['mascara'])).map(g => g.camera_id)).toEqual(['cam-mascara'])
  })

  it('pega qualquer estado do tipo (presença E ausência), case-insensitive', () => {
    const g = [gap(9, 'SEM MASCARA', 'cam-x', 0.5), gap(8, 'Botas', 'cam-y', 0.5)]
    expect(lacunasDosTipos(g, new Set(['mascara'])).map(x => x.camera_id)).toEqual(['cam-x'])
  })

  it('insensível a acento: "Oculos" da matriz casa com "Óculos" da tela (normParaComparar)', () => {
    const g = [gap(11, 'Oculos', 'cam-oc', 0.5), gap(12, 'SEM ÓCULOS', 'cam-oc2', 0.4), gap(8, 'Botas', 'cam-y', 0.5)]
    expect(lacunasDosTipos(g, new Set(['oculos'])).map(x => x.camera_id)).toEqual(['cam-oc', 'cam-oc2'])
  })

  it('🔴 NÃO casa por class_id — o id cru colide entre os dois catálogos', () => {
    // `class_id` 4 é `gloves` no catálogo global do módulo, mas a matriz emite
    // o id CRU de yolo_classes: aqui, 4 = 'Protetor auditivo' do tenant.
    // Casar por id priorizaria a câmera errada em silêncio (task-077).
    expect(lacunasDosTipos(GAPS, new Set(['luvas']))).toEqual([])
    expect(lacunasDosTipos(GAPS, new Set(['auditiva'])).map(g => g.camera_id)).toEqual(['cam-auditiva'])
  })

  it('a ordenação por carência responde ao filtro — a fila muda de ordem', () => {
    const fila = [
      { id: 'a', camera_id: 'cam-auditiva' },
      { id: 'b', camera_id: 'cam-mascara' },
    ]
    expect(ordenarPorCarencia(fila, lacunasDosTipos(GAPS, new Set())).map(x => x.id)).toEqual(['a', 'b'])
    expect(
      ordenarPorCarencia(fila, lacunasDosTipos(GAPS, new Set(['mascara']))).map(x => x.id),
    ).toEqual(['b', 'a'])
  })

  it('⛔ filtro NÃO encurta a fila — só muda o peso da ordenação', () => {
    const fila = [
      { id: 'a', camera_id: 'cam-auditiva' },
      { id: 'b', camera_id: 'cam-mascara' },
      { id: 'c', camera_id: null as string | null },
    ]
    expect(ordenarPorCarencia(fila, lacunasDosTipos(GAPS, new Set(['mascara'])))).toHaveLength(3)
  })
})

describe('🔴 tipo ESCONDIDO pelo filtro nunca vira anotação (#516)', () => {
  const bbox: [number, number, number, number] = [0, 0, 1, 1]
  const soMascara = tiposVisiveis(new Set(['mascara']))

  it('buildApprovalPayload ignora veredito de tipo fora de `tipos`', () => {
    // Veredito com chave de tipo escondido: rascunho restaurado de sessão com
    // outro filtro, ou proposta pré-selecionada antes de o filtro estreitar.
    const verdict: Verdict = { mascara: 'presente', luvas: 'presente', botas: 'ausente' }
    const { payload, missing } = buildApprovalPayload(verdict, bbox, CLASSES, 'epi', soMascara)
    expect(payload.map(p => p.class_name)).toEqual(['mascara'])
    expect(missing).toEqual([])
  })

  it('default (sem `tipos`) continua cobrindo todos — compat com quem não filtra', () => {
    const { payload } = buildApprovalPayload({ mascara: 'presente', auditiva: 'presente' }, bbox, CLASSES)
    expect(payload.map(p => p.class_name).sort()).toEqual(['Protetor auditivo', 'mascara'])
  })

  it('vereditoInicialDaProposta não pré-seleciona tipo escondido', () => {
    const v = vereditoInicialDaProposta(new Set(['mascara:presente', 'luvas:presente']), soMascara)
    expect(v).toEqual({ mascara: 'presente' })
  })

  it('medirAceitacao não conta tipo escondido — ninguém o julgou', () => {
    const r = medirAceitacao(
      new Set(['mascara:presente', 'luvas:presente']),
      { mascara: 'presente' },
      soMascara,
    )
    expect(r).toEqual([{ classe: 'mascara:presente', aceita: true }])
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

  it('confiancaDasPropostas: maior % por estado, null sem confiança, ausência nunca', () => {
    const m = confiancaDasPropostas(
      [
        { class_id: 101, confidence: 0.62 },
        { class_id: 101, confidence: 0.78 }, // duas caixas da mesma classe → fica a maior
        { class_id: 103 }, // DINO legado: sem confiança
        { class_id: 102, confidence: 0.99 }, // "Sem protetor de ouvido" = ausência → ignorada
      ],
      CLASSES,
    )
    expect(m.get('auditiva:presente')).toBe(0.78)
    expect(m.get('mascara:presente')).toBeNull()
    expect(m.size).toBe(2)
    // mesmas chaves que a sugestão soft — o % só se anexa, nunca muda quem é sugerido
    expect(new Set(m.keys())).toEqual(suggestedPresenceStates([101, 103, 102], CLASSES))
    expect(confiancaDasPropostas([], CLASSES).size).toBe(0)
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

describe('cobertura contra o catálogo REAL do tenant', () => {
  // Nomes exatos de GET /api/modules/epi/classes no DEV, 2026-08-18.
  // ⚠️ O catálogo nomeia em INGLÊS o que a tela chamava em português — foi por
  // isso que Óculos nunca resolveu, silenciosamente, como "Uso incorreto" antes.
  const CATALOGO = [
    'Protetor auditivo', 'Sem protetor de ouvido', 'mascara',
    'Uso incorreto de mascara', 'Sem mascara', 'Botas', 'Sem botas',
    'helmet', 'no_helmet', 'vest', 'no_vest',
    'gloves', 'no_gloves', 'glasses', 'no_glasses',
  ].map((name, i) => ({ classId: 100000 + i, name }))

  it('🔴 TODO estado com classe declarada resolve no catálogo real', () => {
    const orfaos: string[] = []
    for (const tipo of EPI_TYPES) {
      for (const estado of tipo.states) {
        if (estado.classNameCandidates.length === 0) continue  // 'não visível'
        if (resolveClassId(estado.classNameCandidates, CATALOGO as never) == null) {
          orfaos.push(`${tipo.key}:${estado.key}`)
        }
      }
    }
    expect(orfaos).toEqual([])
  })

  it('os tipos prioritários incluem luvas e óculos (núcleo pós-reunião)', () => {
    expect([...TIPOS_PRIORITARIOS].sort()).toEqual(['auditiva', 'luvas', 'mascara', 'oculos'])
  })

  it('todo tipo prioritário aparece no preset "só prioritárias"', () => {
    const visiveis = tiposVisiveis(new Set(TIPOS_PRIORITARIOS)).map(t => t.key).sort()
    expect(visiveis).toEqual([...TIPOS_PRIORITARIOS].sort())
  })

  it('todo estado tem tecla, menos "não visível" que já tinha', () => {
    for (const tipo of EPI_TYPES) {
      for (const estado of tipo.states) {
        expect(
          KEY_BINDINGS.some(b => b.typeKey === tipo.key && b.stateKey === estado.key),
          `${tipo.key}:${estado.key} sem tecla`,
        ).toBe(true)
      }
    }
  })

  it('⛔ nenhuma tecla duplicada', () => {
    const teclas = KEY_BINDINGS.map(b => b.key)
    expect(new Set(teclas).size).toBe(teclas.length)
  })
})

describe('intercalação normais/propostas (D5)', () => {
  // n = normal, p = com proposta pendente; id carrega a ordem de origem.
  const n = (id: string) => ({ id, camera_id: null, pending_proposals_count: 0 })
  const p = (id: string) => ({ id, camera_id: null, pending_proposals_count: 2 })
  const ids = (xs: { id: string }[]) => xs.map(x => x.id)
  const fila = [n('n1'), p('p1'), n('n2'), n('n3'), p('p2'), n('n4'), p('p3'), p('p4'), n('n5')]

  it('temProposta sem classes no item: contagem > 0, ausente/null = normal', () => {
    expect(temProposta({ pending_proposals_count: 1 })).toBe(true)
    expect(temProposta({ pending_proposals_count: 0 })).toBe(false)
    expect(temProposta({ pending_proposals_count: null })).toBe(false)
    expect(temProposta({})).toBe(false)
  })

  describe('temProposta olha só PRESENÇA de tipo VISÍVEL — braço "propostas" sem nada pré-selecionado é fila normal', () => {
    // Espelha vereditoInicialDaProposta/suggestedPresenceStates: ausência e
    // tipo escondido nunca são pré-selecionados, logo o recorte não ganharia
    // o "Enter confirma" — não pode entrar no braço de propostas.
    const soMascara = tiposVisiveis(new Set(['mascara']))

    it('nomesDePresencaDosTipos: só candidatos de kind=presente, normalizados como o filtro por classe', () => {
      const nomes = nomesDePresencaDosTipos(soMascara)
      expect(nomes.has('mascara')).toBe(true)
      expect(nomes.has('sem mascara')).toBe(false)
      expect(nomes.has('uso incorreto de mascara')).toBe(false)
      expect(nomesDePresencaDosTipos(EPI_TYPES).has('oculos')).toBe(true) // "Óculos" sem acento
    })

    it('proposta só de AUSÊNCIA (100% rejeitadas, nunca pré-selecionada) = normal', () => {
      expect(temProposta({ pending_proposals_count: 2, pending_proposal_classes: ['sem mascara'] })).toBe(false)
    })

    it('proposta de presença de tipo ESCONDIDO pelo filtro = normal', () => {
      expect(temProposta({ pending_proposals_count: 1, pending_proposal_classes: ['gloves'] }, soMascara)).toBe(false)
      expect(temProposta({ pending_proposals_count: 1, pending_proposal_classes: ['gloves'] })).toBe(true)
    })

    it('proposta de presença de tipo visível = proposta (case/acento-insensível)', () => {
      expect(temProposta({ pending_proposals_count: 1, pending_proposal_classes: ['MASCARA'] }, soMascara)).toBe(true)
      expect(temProposta({ pending_proposals_count: 3, pending_proposal_classes: ['sem mascara', 'Óculos'] })).toBe(true)
      expect(temProposta({ pending_proposals_count: 1, pending_proposal_classes: ['person'] })).toBe(false)
    })

    it('item sem `pending_proposal_classes` (API antiga) cai na contagem', () => {
      expect(temProposta({ pending_proposals_count: 1, pending_proposal_classes: null }, soMascara)).toBe(true)
    })

    it('intercalar e numeroDoBloco seguem a mesma regra', () => {
      const q = [
        { id: 'a', camera_id: null, pending_proposals_count: 0 },
        { id: 'b', camera_id: null, pending_proposals_count: 1, pending_proposal_classes: ['sem mascara'] },
        { id: 'c', camera_id: null, pending_proposals_count: 1, pending_proposal_classes: ['gloves'] },
        { id: 'd', camera_id: null, pending_proposals_count: 1, pending_proposal_classes: ['mascara'] },
      ]
      // só máscara visível: b (ausência) e c (luvas escondidas) são normais → a b c d com 1/1 vira a d b c
      expect(ids(intercalar(q, { normais: 1, propostas: 1 }, [], soMascara))).toEqual(['a', 'd', 'b', 'c'])
      expect(numeroDoBloco(intercalar(q, { normais: 1, propostas: 1 }, [], soMascara), 1, soMascara)).toBe(1)
      expect(numeroDoBloco(intercalar(q, { normais: 1, propostas: 1 }, [], soMascara), 2, soMascara)).toBe(0)
      // todos os tipos visíveis: c (gloves = luvas presente) também é proposta
      expect(ids(intercalar(q, { normais: 1, propostas: 1 }))).toEqual(['a', 'c', 'b', 'd'])
      expect(ids(reordenarCaudaIntercalada(q, 1, [], { normais: 1, propostas: 1 }, soMascara))).toEqual(['a', 'd', 'b', 'c'])
    })
  })

  it('N normais, depois M propostas, e repete — ordem RELATIVA de cada grupo preservada', () => {
    expect(ids(intercalar(fila, { normais: 2, propostas: 1 }))).toEqual([
      'n1', 'n2', 'p1', 'n3', 'n4', 'p2', 'n5', 'p3', 'p4',
    ])
  })

  it('nada perdido nem duplicado', () => {
    const saida = intercalar(fila, { normais: 3, propostas: 2 })
    expect(ids(saida).sort()).toEqual(ids(fila).sort())
    expect(new Set(ids(saida)).size).toBe(fila.length)
  })

  it('grupo esgotado → o resto do outro vem em sequência', () => {
    expect(ids(intercalar([p('p1'), n('n1'), p('p2'), p('p3')], { normais: 5, propostas: 1 })))
      .toEqual(['n1', 'p1', 'p2', 'p3'])
  })

  it('null ou 0/0 = fila como está', () => {
    expect(ids(intercalar(fila, null))).toEqual(ids(fila))
    expect(ids(intercalar(fila, { normais: 0, propostas: 0 }))).toEqual(ids(fila))
  })

  it('só um dos grupos presente = fila como está', () => {
    const soNormais = [n('a'), n('b'), n('c')]
    const soPropostas = [p('a'), p('b')]
    expect(ids(intercalar(soNormais, { normais: 1, propostas: 1 }))).toEqual(['a', 'b', 'c'])
    expect(ids(intercalar(soPropostas, { normais: 1, propostas: 1 }))).toEqual(['a', 'b'])
    expect(intercalar([], { normais: 1, propostas: 1 })).toEqual([])
  })

  it('um dos lados em 0 = sem intercalação (0/10 inclusive): fila como está', () => {
    expect(ids(intercalar(fila, { normais: 0, propostas: 10 }))).toEqual(ids(fila))
    expect(ids(intercalar(fila, { normais: 10, propostas: 0 }))).toEqual(ids(fila))
  })

  // 🔴 Bloqueador da verificação: Math.floor(undefined) = NaN passava pelo
  // guard `n === 0 && m === 0` e o while nunca avançava (loop infinito).
  // Cadência vem de localStorage/<select> — lixo é entrada normal.
  it('🔴 cadência inválida (NaN/ausente/negativa) NÃO trava — devolve a fila como está', () => {
    const lixo = [
      {},
      { normais: NaN, propostas: 2 },
      { normais: -1, propostas: 2 },
      { normais: 2, propostas: undefined },
      { normais: 2, propostas: 0 },
      { normais: Infinity, propostas: 2 },
      { normais: '3', propostas: 2 },
    ] as unknown as Cadencia[]
    for (const c of lixo) {
      expect(ids(intercalar(fila, c))).toEqual(ids(fila))
      expect(ids(reordenarCaudaIntercalada(fila, 2, [], c))).toEqual(ids(fila))
    }
  }, 2000)

  it('cadenciaValida: inteiro ≥1 dos dois lados ou null; é o que intercalar usa', () => {
    expect(cadenciaValida({ normais: 5, propostas: 3 })).toEqual({ normais: 5, propostas: 3 })
    expect(cadenciaValida({ normais: 2.9, propostas: 1.2 })).toEqual({ normais: 2, propostas: 1 })
    expect(cadenciaValida(null)).toBeNull()
    expect(cadenciaValida(undefined)).toBeNull()
    expect(cadenciaValida({})).toBeNull()
    expect(cadenciaValida({ normais: NaN, propostas: 2 })).toBeNull()
    expect(cadenciaValida({ normais: 0, propostas: 10 })).toBeNull()
    expect(cadenciaValida({ normais: -1, propostas: 1 })).toBeNull()
    expect(cadenciaValida('5/3')).toBeNull()
  })

  it('reordenarCaudaIntercalada NÃO move o prefixo nem o recorte da tela', () => {
    const saida = reordenarCaudaIntercalada(fila, 3, [], { normais: 1, propostas: 1 })
    expect(ids(saida).slice(0, 3)).toEqual(['n1', 'p1', 'n2'])
    // Prefixo termina em n2 = bloco de 1 normal completo → a cauda abre com proposta.
    expect(ids(saida).slice(3)).toEqual(['p2', 'n3', 'p3', 'n4', 'p4', 'n5'])
  })

  it('a fase CONTINUA do prefixo congelado — reordenar a cauda não reinicia o bloco', () => {
    // Fila 2/2 intercalada: n1 n2 p1 p2 n3 n4 p3 p4 n5. Anotador em n1 (corte 1):
    // o prefixo [n1] já gastou 1 dos 2 normais → a cauda abre com UM normal.
    const q = intercalar(fila, { normais: 2, propostas: 2 })
    expect(ids(reordenarCaudaIntercalada(q, 1, [], { normais: 2, propostas: 2 }))).toEqual(ids(q))
    // Prefixo termina com 1 proposta de um bloco de 2 → a cauda abre com a
    // proposta que falta, depois 2 normais.
    expect(ids(reordenarCaudaIntercalada(q, 3, [], { normais: 2, propostas: 2 }))).toEqual(ids(q))
    // Prefixo já completou o bloco de propostas → a cauda abre com normais.
    expect(ids(intercalar([p('x'), n('y'), n('z')], { normais: 2, propostas: 2 }, [p('a'), p('b')])))
      .toEqual(['y', 'z', 'x'])
    // Prefixo vazio = fase do zero (normais primeiro).
    expect(ids(intercalar([p('x'), n('y')], { normais: 1, propostas: 1 }, []))).toEqual(['y', 'x'])
  })

  it('reordenarCaudaIntercalada sem cadência = reordenarCauda de sempre', () => {
    expect(ids(reordenarCaudaIntercalada(fila, 3, [], null))).toEqual(ids(reordenarCauda(fila, 3, [])))
    expect(ids(reordenarCauda(fila, 3, []))).toEqual(ids(fila))
  })

  it('numeroDoBloco: 0 em recorte normal, 1-based por bloco, estável na mesma posição', () => {
    const q = intercalar(fila, { normais: 2, propostas: 2 })
    // n1 n2 p1 p2 n3 n4 p3 p4 n5
    expect(numeroDoBloco(q, 0)).toBe(0)
    expect(numeroDoBloco(q, 2)).toBe(1)
    expect(numeroDoBloco(q, 3)).toBe(1)
    expect(numeroDoBloco(q, 4)).toBe(0)
    expect(numeroDoBloco(q, 6)).toBe(2)
    expect(numeroDoBloco(q, 7)).toBe(2)
    // Backspace volta pra 6: mesmo bloco — contador não abre lote novo
    expect(numeroDoBloco(q, 6)).toBe(2)
    expect(numeroDoBloco(q, -1)).toBe(0)
    expect(numeroDoBloco(q, 99)).toBe(0)
  })
})
