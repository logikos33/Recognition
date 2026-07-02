/**
 * timeBuckets — zero-fill, alinhamento de bucket e rótulos pt-BR.
 */
import { describe, expect, it } from 'vitest'
import { fillBuckets, formatBucketLabel, rangeForPeriod } from '../timeBuckets'

describe('fillBuckets', () => {
  it('gera 24 pontos zero-filled para janela de 24h sem dados', () => {
    const points = fillBuckets(
      '2026-06-01T00:00:00Z',
      '2026-06-02T00:00:00Z',
      'hour',
      []
    )
    expect(points).toHaveLength(24)
    expect(points.every((p) => p.count === 0)).toBe(true)
    expect(points[0].bucket).toBe('2026-06-01T00:00:00.000Z')
  })

  it('gera 7 pontos para janela de 7 dias', () => {
    const points = fillBuckets(
      '2026-06-01T00:00:00Z',
      '2026-06-08T00:00:00Z',
      'day',
      []
    )
    expect(points).toHaveLength(7)
  })

  it('preenche counts nos buckets correspondentes e zera o resto', () => {
    const points = fillBuckets(
      '2026-06-01T00:00:00Z',
      '2026-06-01T06:00:00Z',
      'hour',
      [
        { bucket: '2026-06-01T02:00:00+00:00', count: 5 },
        { bucket: '2026-06-01T04:00:00+00:00', count: 2 },
      ]
    )
    expect(points).toHaveLength(6)
    expect(points.map((p) => p.count)).toEqual([0, 0, 5, 0, 2, 0])
  })

  it('interpreta timestamp naive do backend (date_trunc) como UTC', () => {
    // Backend devolve "2026-06-01T02:00:00" sem offset — deve casar o bucket UTC
    const points = fillBuckets(
      '2026-06-01T00:00:00Z',
      '2026-06-01T03:00:00Z',
      'hour',
      [{ bucket: '2026-06-01T02:00:00', count: 9 }]
    )
    expect(points.map((p) => p.count)).toEqual([0, 0, 9])
  })

  it('retorna [] para janela invertida ou datas inválidas', () => {
    expect(
      fillBuckets('2026-06-02T00:00:00Z', '2026-06-01T00:00:00Z', 'hour', [])
    ).toEqual([])
    expect(fillBuckets('nope', '2026-06-01T00:00:00Z', 'hour', [])).toEqual([])
  })

  it('ignora linhas com bucket null', () => {
    const points = fillBuckets(
      '2026-06-01T00:00:00Z',
      '2026-06-01T02:00:00Z',
      'hour',
      [{ bucket: null, count: 3 }]
    )
    expect(points.map((p) => p.count)).toEqual([0, 0])
  })
})

describe('formatBucketLabel', () => {
  it('formata hora como HHh', () => {
    const label = formatBucketLabel('2026-06-01T13:00:00Z', 'hour')
    expect(label).toMatch(/^\d{2}h$/)
  })

  it('formata dia como dd/mm (pt-BR)', () => {
    const label = formatBucketLabel('2026-06-01T12:00:00Z', 'day')
    expect(label).toMatch(/^\d{2}\/\d{2}$/)
  })

  it('retorna — para data inválida', () => {
    expect(formatBucketLabel('invalid', 'hour')).toBe('—')
  })
})

describe('rangeForPeriod', () => {
  const now = new Date('2026-06-15T14:37:22Z')

  it('24h → bucket hour e exatamente 24 pontos após fillBuckets', () => {
    const r = rangeForPeriod('24h', now)
    expect(r.bucket).toBe('hour')
    expect(fillBuckets(r.from, r.to, r.bucket, [])).toHaveLength(24)
  })

  it('7d → bucket day e exatamente 7 pontos', () => {
    const r = rangeForPeriod('7d', now)
    expect(r.bucket).toBe('day')
    expect(fillBuckets(r.from, r.to, r.bucket, [])).toHaveLength(7)
  })

  it('30d → bucket day e exatamente 30 pontos', () => {
    const r = rangeForPeriod('30d', now)
    expect(fillBuckets(r.from, r.to, r.bucket, [])).toHaveLength(30)
  })

  it('inclui o bucket corrente como último ponto', () => {
    const r = rangeForPeriod('24h', now)
    const points = fillBuckets(r.from, r.to, r.bucket, [])
    expect(points[points.length - 1].bucket).toBe('2026-06-15T14:00:00.000Z')
  })
})
