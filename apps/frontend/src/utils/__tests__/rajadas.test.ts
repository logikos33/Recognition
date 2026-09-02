/**
 * agruparPorRajada — o agregador reusado por Eventos, Ações, Verificação e o
 * sino (ux2/dedup). Mesmo critério do backend (VerificationService): câmera +
 * classe, gap ≤ janela fecha a rajada.
 */
import { describe, expect, it } from 'vitest'
import { agruparPorRajada, maisIncerto } from '../rajadas'

interface Evento {
  id: string
  camera_id: string
  classe: string
  created_at: string
  confidence?: number
}

const item = (id: string, camera_id: string, classe: string, created_at: string, confidence?: number): Evento => ({
  id, camera_id, classe, created_at, confidence,
})

const OPCOES = {
  cameraId: (e: Evento) => e.camera_id,
  classe: (e: Evento) => e.classe,
  criadoEm: (e: Evento) => e.created_at,
}

describe('agruparPorRajada', () => {
  it('agrupa itens da MESMA câmera+classe dentro da janela em UMA rajada', () => {
    const itens = [
      item('a', 'cam-1', 'no_helmet', '2026-08-25T13:39:00Z'),
      item('b', 'cam-1', 'no_helmet', '2026-08-25T13:39:20Z'),
      item('c', 'cam-1', 'no_helmet', '2026-08-25T13:39:50Z'),
    ]
    const grupos = agruparPorRajada(itens, OPCOES)
    expect(grupos).toHaveLength(1)
    expect(grupos[0].tamanho).toBe(3)
    expect(grupos[0].repeticoes.map((i) => i.id)).toEqual(['a', 'b', 'c'])
  })

  it('gap MAIOR que a janela abre uma NOVA rajada (não filtra, nunca esconde)', () => {
    const itens = [
      item('a', 'cam-1', 'no_helmet', '2026-08-25T13:00:00Z'),
      item('b', 'cam-1', 'no_helmet', '2026-08-25T13:05:00Z'), // 5min depois
    ]
    const grupos = agruparPorRajada(itens, OPCOES)
    expect(grupos).toHaveLength(2)
    expect(grupos.every((g) => g.tamanho === 1)).toBe(true)
    // O item de entrada continua presente em ALGUM grupo — nunca some.
    const idsQueAparecem = grupos.flatMap((g) => g.repeticoes.map((i) => i.id))
    expect(idsQueAparecem.sort()).toEqual(['a', 'b'])
  })

  it('CÂMERA diferente nunca agrupa, mesmo na mesma classe e no mesmo segundo', () => {
    const itens = [
      item('a', 'cam-1', 'no_helmet', '2026-08-25T13:39:00Z'),
      item('b', 'cam-2', 'no_helmet', '2026-08-25T13:39:00Z'),
    ]
    const grupos = agruparPorRajada(itens, OPCOES)
    expect(grupos).toHaveLength(2)
  })

  it('CLASSE diferente nunca agrupa, mesmo na mesma câmera e no mesmo segundo', () => {
    const itens = [
      item('a', 'cam-1', 'no_helmet', '2026-08-25T13:39:00Z'),
      item('b', 'cam-1', 'no_vest', '2026-08-25T13:39:00Z'),
    ]
    const grupos = agruparPorRajada(itens, OPCOES)
    expect(grupos).toHaveLength(2)
  })

  it('reproduz o achado medido: 33+33 numa câmera em 2min viram 2 situações', () => {
    const mascaras = Array.from({ length: 33 }, (_, i) =>
      item(`m${i}`, 'cam-eb15', 'Sem mascara', new Date(Date.parse('2026-08-25T13:39:17Z') + i * 4000).toISOString()),
    )
    const luvas = Array.from({ length: 33 }, (_, i) =>
      item(`l${i}`, 'cam-eb15', 'Sem Luvas', new Date(Date.parse('2026-08-25T13:39:20Z') + i * 4000).toISOString()),
    )
    const grupos = agruparPorRajada([...mascaras, ...luvas], OPCOES)
    expect(grupos).toHaveLength(2)
    expect(grupos.reduce((soma, g) => soma + g.tamanho, 0)).toBe(66)
  })

  it('representante default é o MAIS RECENTE (listas já abrem created_at DESC)', () => {
    const itens = [
      item('velho', 'cam-1', 'no_helmet', '2026-08-25T13:39:00Z'),
      item('novo', 'cam-1', 'no_helmet', '2026-08-25T13:39:30Z'),
    ]
    const [grupo] = agruparPorRajada(itens, OPCOES)
    expect(grupo.representante.id).toBe('novo')
  })

  it('não perde nenhum item de entrada — soma de repeticoes bate com o total', () => {
    const itens = [
      item('a', 'cam-1', 'x', '2026-08-25T10:00:00Z'),
      item('b', 'cam-1', 'x', '2026-08-25T10:00:10Z'),
      item('c', 'cam-2', 'y', '2026-08-25T11:00:00Z'),
      item('d', 'cam-1', 'x', '2026-08-25T12:00:00Z'),
    ]
    const grupos = agruparPorRajada(itens, OPCOES)
    const total = grupos.reduce((soma, g) => soma + g.tamanho, 0)
    expect(total).toBe(itens.length)
  })

  it('janelaSegundos custom é respeitada (não hardcoded)', () => {
    const itens = [
      item('a', 'cam-1', 'x', '2026-08-25T10:00:00Z'),
      item('b', 'cam-1', 'x', '2026-08-25T10:00:05Z'),
    ]
    // 5s de gap: com janela de 10s agrupa, com janela de 2s não agrupa.
    expect(agruparPorRajada(itens, { ...OPCOES, janelaSegundos: 10 })).toHaveLength(1)
    expect(agruparPorRajada(itens, { ...OPCOES, janelaSegundos: 2 })).toHaveLength(2)
  })
})

describe('maisIncerto — representante custom para Verificação', () => {
  it('escolhe o item com confiança mais próxima de 0.5 (mais em dúvida)', () => {
    const itens = [
      item('certo', 'cam-1', 'x', '2026-08-25T10:00:00Z', 0.95),
      item('duvidoso', 'cam-1', 'x', '2026-08-25T10:00:10Z', 0.55),
    ]
    const grupos = agruparPorRajada(itens, {
      ...OPCOES,
      melhorRepresentante: maisIncerto((e: Evento) => e.confidence),
    })
    expect(grupos[0].representante.id).toBe('duvidoso')
  })

  it('sem confiança nenhuma, vai para o FIM (mesmo COALESCE(…,1.0) do backend)', () => {
    const itens = [
      item('sem_confianca', 'cam-1', 'x', '2026-08-25T10:00:00Z', undefined),
      item('duvidoso', 'cam-1', 'x', '2026-08-25T10:00:10Z', 0.51),
    ]
    const grupos = agruparPorRajada(itens, {
      ...OPCOES,
      melhorRepresentante: maisIncerto((e: Evento) => e.confidence),
    })
    expect(grupos[0].representante.id).toBe('duvidoso')
  })
})
