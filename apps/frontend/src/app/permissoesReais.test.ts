/**
 * Toda chave `can('...')` do front novo tem de existir no backend.
 *
 * `can()` devolve `false` para chave que não existe. Logo, uma chave inventada
 * não estoura: ela ESCONDE o botão, para sempre, para todo mundo — menos para o
 * superadmin, que passa por cima de tudo e por isso é justamente quem nunca vê
 * o problema. Some da tela do operador e continua funcionando na de quem testa.
 *
 * Aconteceu de verdade: `alerts:review` quase entrou na navegação, e não
 * existe. O certo é `verification:read`.
 *
 * `navPorPerfil.test.ts` já confere as chaves do MENU. Este confere as das 8
 * telas também — que é onde estão os botões que escrevem.
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const APP = path.dirname(fileURLToPath(import.meta.url))
const REGISTRY = path.resolve(APP, '../../../../services/api/app/core/permissions.py')

function arquivosDeCodigo(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = path.join(dir, e.name)
    if (e.isDirectory()) return arquivosDeCodigo(p)
    return /\.tsx?$/.test(e.name) && !/\.test\.tsx?$/.test(e.name) ? [p] : []
  })
}

describe('permissões do front novo', () => {
  it('toda chave usada existe no registry do backend', () => {
    const registry = fs.readFileSync(REGISTRY, 'utf-8')
    const existentes = new Set(
      [...registry.matchAll(/["']([a-z_]+:[a-z_]+)["']/g)].map((m) => m[1]),
    )
    // Se o regex parar de casar, o teste passaria com zero chaves conhecidas e
    // reprovaria tudo — mas o contrário (registry vazio) precisa falhar alto.
    expect(existentes.size, 'não consegui ler o registry de permissões').toBeGreaterThan(20)

    const usadas = new Map<string, string[]>()
    for (const arquivo of arquivosDeCodigo(APP)) {
      const texto = fs.readFileSync(arquivo, 'utf-8')
      const rel = path.relative(APP, arquivo)
      for (const m of texto.matchAll(/can\(\s*['"]([^'"]+)['"]/g)) {
        usadas.set(m[1], [...(usadas.get(m[1]) ?? []), rel])
      }
      for (const m of texto.matchAll(/permissao:\s*'([^']+)'/g)) {
        usadas.set(m[1], [...(usadas.get(m[1]) ?? []), rel])
      }
    }
    expect(usadas.size, 'nenhuma chave encontrada — a varredura quebrou').toBeGreaterThan(5)

    const inexistentes = [...usadas.entries()]
      .filter(([k]) => !existentes.has(k))
      .map(([k, onde]) => `${k}  (${onde.join(', ')})`)
    expect(
      inexistentes,
      'chave que não existe no backend esconde o controle em silêncio:\n' +
        inexistentes.join('\n'),
    ).toEqual([])
  })
})
