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
import { existsSync, mkdtempSync, readFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

import { describe, expect, it } from 'vitest'

const RAIZ = join(__dirname, '..', '..', '..')
const MANIFESTO = join(RAIZ, '..', '..', 'docs', 'migration', 'MANIFESTO-FRONT-ANTIGO.md')

describe('manifesto do front antigo', () => {
  it('existe', () => {
    expect(existsSync(MANIFESTO)).toBe(true)
  })

  it('está ATUALIZADO com o repositório', () => {
    // Manifesto velho é pior que manifesto nenhum: dá a impressão de que alguém
    // conferiu.
    //
    // Gera para um arquivo TEMPORÁRIO e compara. Antes ele regenerava por cima
    // do versionado — então falhava na primeira execução, CONSERTAVA o arquivo,
    // e passava na segunda. Quem rodasse a suíte duas vezes via verde e
    // commitava um manifesto velho. Foi assim que um desatualizado chegou ao CI.
    const temp = join(mkdtempSync(join(tmpdir(), 'manifesto-')), 'gerado.md')
    execFileSync('node', [join(RAIZ, 'scripts', 'gera-manifesto-front-antigo.mjs')], {
      env: { ...process.env, MANIFESTO_SAIDA: temp },
    })
    expect(
      readFileSync(temp, 'utf8'),
      'manifesto desatualizado — rode `npm run manifesto` e commite',
    ).toBe(readFileSync(MANIFESTO, 'utf8'))
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

  it('não lista o front NOVO como candidato a remoção', () => {
    // O manifesto é a lista do que SAI. `src/app/` é o front novo — o que FICA.
    // O gerador já os classificou como INFRA uma vez, e INFRA neste documento
    // significa "decidir caso a caso na remoção": o front novo teria ido parar
    // na pauta de apagar.
    const manifesto = readFileSync(MANIFESTO, 'utf8')
    expect(manifesto).not.toMatch(/`src\/app\//)
  })

  it('separa "tem substituta" de "pode apagar"', () => {
    // O manifesto chegou a marcar 7 telas como MIGRADO — que ele mesmo define
    // como "PODE ser removido". A comparação função-a-função depois achou 22
    // perdas confirmadas nessas telas. Ter substituta e poder ser apagado não
    // são a mesma coisa, e confundir as duas é o caminho mais curto para
    // apagar função que o cliente usa.
    const manifesto = readFileSync(MANIFESTO, 'utf8')
    expect(manifesto).toContain('SUBSTITUIDA')
    // A regra tem de estar ESCRITA, não só implícita na tabela — quem for
    // apagar lê o documento, não o gerador. Sem crase no meio: o texto formata
    // os status com backtick e um regex literal quebraria à toa.
    const semFormato = manifesto.replace(/[`*]/g, '')
    expect(semFormato).toMatch(/Fase 3 só apaga MIGRADO/i)
    expect(semFormato).toMatch(/SUBSTITUIDA fica/i)
  })

  it('nenhuma tela com paridade aberta está marcada como removível', () => {
    // A trava de verdade: arquivo que declara @paridade-pendente NUNCA pode
    // aparecer como MIGRADO no manifesto.
    const manifesto = readFileSync(MANIFESTO, 'utf8')
    const linhas = manifesto.split('\n').filter((l) => l.includes('| `MIGRADO` |'))
    for (const linha of linhas) {
      const arquivo = linha.match(/`(src\/[^`]+)`/)?.[1]
      if (!arquivo) continue
      const fonte = readFileSync(join(RAIZ, arquivo), 'utf8')
      expect(
        fonte.includes('@paridade-pendente'),
        `${arquivo} está como MIGRADO (removível) mas declara paridade pendente`,
      ).toBe(false)
    }
  })
})
