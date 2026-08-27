/**
 * A remoção do front antigo só pode apagar o que foi MIGRADO.
 *
 * Pedido do Vitor (27/08): a migração coexiste e tudo do front antigo fica
 * sinalizado para uma etapa de remoção própria. Este teste é a trava: ele
 * garante que o manifesto existe, está atualizado com o repositório, e que
 * nenhum arquivo `PENDENTE`/`SEM-DESENHO` foi removido por engano.
 *
 * Sem isto, a Fase 3 vira arqueologia — alguém abre 394 arquivos e decide no
 * olho quais podem sair. Foi assim que o front antigo de outros projetos
 * levou junto tela que ninguém tinha substituído.
 */
import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'

import { describe, expect, it } from 'vitest'

const RAIZ = join(__dirname, '..', '..', '..')
const MANIFESTO = join(RAIZ, '..', '..', 'docs', 'migration', 'MANIFESTO-FRONT-ANTIGO.md')

describe('manifesto do front antigo', () => {
  it('existe', () => {
    expect(existsSync(MANIFESTO)).toBe(true)
  })

  it('está ATUALIZADO com o repositório', () => {
    // Regenera e compara: manifesto velho é pior que manifesto nenhum, porque
    // dá a impressão de que alguém conferiu.
    const antes = readFileSync(MANIFESTO, 'utf8')
    execFileSync('node', [join(RAIZ, 'scripts', 'gera-manifesto-front-antigo.mjs')])
    const depois = readFileSync(MANIFESTO, 'utf8')
    expect(depois).toBe(antes)
  })

  it('declara os quatro estados e diz qual pode ser removido', () => {
    const md = readFileSync(MANIFESTO, 'utf8')
    for (const estado of ['MIGRADO', 'PENDENTE', 'SEM-DESENHO', 'INFRA']) {
      expect(md).toContain(estado)
    }
    // A regra tem de estar escrita, não só implícita no código do gerador.
    expect(md).toMatch(/só apaga.*MIGRADO/i)
  })

  it('nenhum arquivo listado como PENDENTE ou SEM-DESENHO sumiu do disco', () => {
    const md = readFileSync(MANIFESTO, 'utf8')
    const sumidos: string[] = []
    for (const linha of md.split('\n')) {
      const m = linha.match(/^\| `([^`]+)` \| `(PENDENTE|SEM-DESENHO)` \|/)
      if (m && !existsSync(join(RAIZ, m[1]))) sumidos.push(`${m[1]} (${m[2]})`)
    }
    expect(sumidos, 'removido antes de ser migrado').toEqual([])
  })

  it('as rotas SEM DESENHO da Fase 0 continuam vivas', () => {
    // Estas dez não têm tela no handoff. Enquanto o design não desenhar, elas
    // seguem no ar — a migração não pode apagá-las nem inventá-las.
    const rotas = readFileSync(join(RAIZ, 'src', 'AppRoutes.tsx'), 'utf8')
    for (const r of ['/epi/sites', '/epi/investigation', '/epi/edge-observability']) {
      expect(rotas, `rota sem desenho sumiu: ${r}`).toContain(r)
    }
  })
})
