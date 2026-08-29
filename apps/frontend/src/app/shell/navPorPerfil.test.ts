/**
 * A nav não pode inventar permissão.
 *
 * Este teste cruza CADA permissão citada na navegação com o registry REAL do
 * backend (`services/api/app/core/permissions.py`). Um nome inventado faz o
 * item sumir para todo mundo que não é superadmin — e o sintoma é silencioso:
 * ninguém reclama de menu que não aparece.
 *
 * Foi assim que `alerts:review` quase entrou: soa plausível, não existe. O
 * certo é `verification:read`.
 */
import { readFileSync } from 'node:fs'
import { join } from 'node:path'

import { describe, expect, it } from 'vitest'

import { NAV_EPI, NAV_ESTUDIO, navVisivel } from './navPorPerfil'

const REGISTRY = join(
  __dirname, '..', '..', '..', '..', '..',
  'services', 'api', 'app', 'core', 'permissions.py',
)

/** Chaves `dominio:acao` declaradas no registry do backend. */
function permissoesReais(): Set<string> {
  const py = readFileSync(REGISTRY, 'utf8')
  return new Set([...py.matchAll(/"([a-z_]+:[a-z_]+)":\s*_entry/g)].map((m) => m[1]))
}

describe('nav por perfil', () => {
  it('toda permissão citada EXISTE no registry do backend', () => {
    const reais = permissoesReais()
    expect(reais.size, 'não consegui ler o registry').toBeGreaterThan(20)
    const inventadas = [...NAV_EPI, ...NAV_ESTUDIO].flatMap((g) => g.itens)
      .map((i) => i.permissao)
      .filter((p): p is string => p !== null)
      .filter((p) => !reais.has(p))
    expect(inventadas, 'permissão que não existe → item some em silêncio').toEqual([])
  })

  it('Estúdio aparece para quem anota (matriz real) e some para analyst/viewer', () => {
    const MATRIZ: Record<string, string[]> = JSON.parse(
      readFileSync(join(__dirname, '..', '..', 'test', 'e2e', 'matriz-papeis.json'), 'utf8'),
    )
    const podeDo = (papel: string) => (p: string) =>
      papel === 'superadmin' || (MATRIZ[papel] ?? []).includes(p)
    for (const papel of ['superadmin', 'admin', 'operator', 'trainer']) {
      const itens = navVisivel(NAV_ESTUDIO, podeDo(papel)).flatMap((g) => g.itens)
      expect(itens.map((i) => i.rotulo), papel).toContain('Estúdio')
    }
    for (const papel of ['analyst', 'viewer']) {
      expect(navVisivel(NAV_ESTUDIO, podeDo(papel)), papel).toEqual([])
    }
  })

  it('quem não pode nada só vê o que não exige permissão', () => {
    const visivel = navVisivel(NAV_EPI, () => false)
    const itens = visivel.flatMap((g) => g.itens)
    expect(itens.every((i) => i.permissao === null)).toBe(true)
    expect(itens.map((i) => i.rota)).toContain('/epi/dashboard')
  })

  it('quem pode tudo vê tudo', () => {
    const visivel = navVisivel(NAV_EPI, () => true)
    expect(visivel.flatMap((g) => g.itens)).toHaveLength(
      NAV_EPI.flatMap((g) => g.itens).length,
    )
  })

  it('grupo que ficou sem item some — não fica cabeçalho órfão', () => {
    const grupos = [{ titulo: 'Só admin', itens: [{ ...NAV_EPI[0].itens[1], permissao: 'admin:panel' }] }]
    expect(navVisivel(grupos, () => false)).toEqual([])
  })

  it('a ordem é a da jornada DETECTAR→TRIAR→AGIR→PROVAR, não alfabética', () => {
    const rotas = NAV_EPI[0].itens.map((i) => i.rota)
    expect(rotas.indexOf('/epi/live')).toBeLessThan(rotas.indexOf('/epi/eventos'))
    expect(rotas.indexOf('/epi/eventos')).toBeLessThan(rotas.indexOf('/epi/verificacao'))
    expect(rotas.indexOf('/epi/verificacao')).toBeLessThan(rotas.indexOf('/epi/acoes'))
    expect(rotas.indexOf('/epi/acoes')).toBeLessThan(rotas.indexOf('/epi/relatorios'))
  })
})
