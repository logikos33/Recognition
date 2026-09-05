/**
 * A dobra do perfil é onde um erro vira mentira silenciosa: hora errada move
 * violação de turno, dia errado move violação de data, e as duas coisas saem
 * na tela como número plausível. Por isso os casos aqui são montados à mão,
 * com o resultado conferido no braço.
 *
 * Fuso fixado em America/Sao_Paulo (`vitest.config`/`TZ` não garantem) — o
 * ponto do exercício é justamente a conversão UTC→local, então rodar num fuso
 * qualquer da máquina de quem executa não provaria nada.
 */
import { describe, expect, it } from 'vitest'

import type { ProfileRow } from '../services/eventsService'
import { agregarPerfil, picoDeViolacao, rotuloDia } from './perfilEventos'

const TZ_LOCAL = new Date('2026-08-21T13:00:00Z').getHours()
/** 13h UTC vira 10h em BRT (UTC−3). Se a máquina não estiver em BRT, o
 *  deslocamento é outro e os casos se ajustam por este delta. */
const desloca = (horaUtc: number) => (horaUtc + (TZ_LOCAL - 13) + 24) % 24

function linha(bucket: string, kind: ProfileRow['kind'], count: number): ProfileRow {
  return { bucket, kind, count }
}

describe('agregarPerfil — hora do dia', () => {
  it('soma no MESMO horário local buckets de dias diferentes', () => {
    const perfil = agregarPerfil([
      linha('2026-08-21T13:00:00', 'violacao', 4),
      linha('2026-08-22T13:00:00', 'violacao', 6),
      linha('2026-08-22T13:00:00', 'conformidade', 1),
    ])
    const hora = perfil.porHora[desloca(13)]
    expect(hora.violacoes).toBe(10)
    expect(hora.total).toBe(11)
  })

  it('devolve sempre 24 posições — hora sem evento é informação, não buraco', () => {
    const perfil = agregarPerfil([linha('2026-08-21T13:00:00', 'violacao', 1)])
    expect(perfil.porHora).toHaveLength(24)
    expect(perfil.porHora.map((p) => p.hora)).toEqual([...Array(24).keys()])
    expect(perfil.porHora.filter((p) => p.total > 0)).toHaveLength(1)
  })

  it('converte o bucket naive do backend como UTC, não como hora local', () => {
    // Sem o 'Z' implícito, "13:00:00" seria lido como 13h local e o pico
    // apareceria 3 horas adiante do que a fábrica de fato registrou.
    const perfil = agregarPerfil([linha('2026-08-21T13:00:00', 'violacao', 9)])
    expect(perfil.porHora[desloca(13)].violacoes).toBe(9)
  })

  it('ignora linha sem bucket em vez de contá-la na hora zero', () => {
    const perfil = agregarPerfil([
      { bucket: null, kind: 'violacao', count: 99 },
      linha('2026-08-21T13:00:00', 'violacao', 2),
    ])
    expect(perfil.total).toBe(2)
    expect(perfil.porHora[0].total).toBe(0)
  })
})

describe('agregarPerfil — dia', () => {
  it('preenche o dia SEM registro entre dois dias com registro', () => {
    const perfil = agregarPerfil([
      linha('2026-08-21T13:00:00', 'violacao', 3),
      linha('2026-08-23T13:00:00', 'violacao', 5),
    ])
    expect(perfil.porDia.map((p) => p.dia)).toEqual(['2026-08-21', '2026-08-22', '2026-08-23'])
    expect(perfil.porDia[1].total).toBe(0)
    // O buraco é preenchido para o gráfico, mas não conta como dia operado.
    expect(perfil.diasComRegistro).toBe(2)
  })

  it('não preenche nada ANTES do primeiro nem DEPOIS do último registro', () => {
    const perfil = agregarPerfil([linha('2026-08-21T13:00:00', 'conformidade', 1)])
    expect(perfil.porDia).toEqual([{ dia: '2026-08-21', total: 1, violacoes: 0 }])
  })

  it('sem linha nenhuma devolve série vazia, nunca um dia zerado de enfeite', () => {
    const perfil = agregarPerfil([])
    expect(perfil.porDia).toEqual([])
    expect(perfil.total).toBe(0)
    expect(perfil.diasComRegistro).toBe(0)
  })
})

describe('agregarPerfil — polaridade', () => {
  it('separa os três baldes e só chama de violação o que é violação', () => {
    const perfil = agregarPerfil([
      linha('2026-08-21T13:00:00', 'violacao', 66),
      linha('2026-08-21T14:00:00', 'conformidade', 302),
      linha('2026-08-21T15:00:00', 'indefinido', 55),
    ])
    expect(perfil.porTipo).toEqual({ violacao: 66, conformidade: 302, indefinido: 55 })
    expect(perfil.total).toBe(423)
    // 'conformidade' é EPI EM USO: soma ao total e não pode virar violação.
    expect(perfil.violacoes).toBe(66)
  })
})

describe('picoDeViolacao', () => {
  it('aponta a hora com mais violações, ignorando a hora de maior VOLUME', () => {
    const perfil = agregarPerfil([
      linha('2026-08-21T13:00:00', 'conformidade', 500),
      linha('2026-08-21T13:00:00', 'violacao', 2),
      linha('2026-08-21T17:00:00', 'violacao', 9),
    ])
    expect(picoDeViolacao(perfil.porHora)?.hora).toBe(desloca(17))
    expect(picoDeViolacao(perfil.porHora)?.violacoes).toBe(9)
  })

  it('sem violação nenhuma devolve null — não elege a hora zero como pico', () => {
    const perfil = agregarPerfil([linha('2026-08-21T13:00:00', 'conformidade', 400)])
    expect(picoDeViolacao(perfil.porHora)).toBeNull()
  })
})

describe('rotuloDia', () => {
  it('formata em pt-BR sem passar por Date (que reinterpretaria o fuso)', () => {
    expect(rotuloDia('2026-08-21')).toBe('21/08')
  })
})
