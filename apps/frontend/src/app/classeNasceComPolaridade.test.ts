/**
 * Régua: toda tela que CRIA classe manda a polaridade.
 *
 * Por que uma régua e não um teste de render: quando o cadastro passou a exigir
 * `is_violation`, duas telas do anotador continuaram mandando só
 * {name,color,module} e o botão "Criar classe" virou 400 — o elo do flywheel
 * quebrado por um campo. Um teste por tela não teria pego a segunda, e não pega
 * a terceira que alguém escrever amanhã. Esta varre as chamadas.
 *
 * A regra é do produto, não de estilo: classe que nasce sem polaridade nasce
 * MUDA — o modelo pode detectá-la a tarde inteira e nada vira evento, porque
 * `is_violation IS NULL` não entra nem no conjunto de violação nem no de
 * presença (ADR-0065 / migration 125).
 */
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

const RAIZ = join(__dirname, '..')

function arquivosFonte(dir: string, achados: string[] = []): string[] {
  for (const nome of readdirSync(dir)) {
    if (nome === 'node_modules' || nome.startsWith('.')) continue
    const caminho = join(dir, nome)
    if (statSync(caminho).isDirectory()) {
      arquivosFonte(caminho, achados)
    } else if (/\.tsx?$/.test(nome) && !/\.(test|spec)\.tsx?$/.test(nome)) {
      achados.push(caminho)
    }
  }
  return achados
}

/** Corpo do objeto passado ao POST, do `{` até o `}` que o fecha. */
function corpoDoPost(fonte: string, inicio: number): string {
  const abre = fonte.indexOf('{', inicio)
  if (abre === -1) return ''
  let nivel = 0
  for (let i = abre; i < fonte.length; i++) {
    if (fonte[i] === '{') nivel++
    else if (fonte[i] === '}') {
      nivel--
      if (nivel === 0) return fonte.slice(abre, i + 1)
    }
  }
  return fonte.slice(abre)
}

describe('régua: classe nasce com polaridade', () => {
  it('todo POST /classes manda is_violation', () => {
    const semPolaridade: string[] = []

    for (const caminho of arquivosFonte(RAIZ)) {
      const fonte = readFileSync(caminho, 'utf8')
      // Ancorar na ROTA, não no `.post<...>`: o genérico real é aninhado
      // (`api.post<ApiResponse<{ class_id: number }>>(...)`) e um `<[^>]*>`
      // ingênuo não o casa — foi assim que a primeira versão desta régua
      // passou verde com o campo removido.
      const re = /['"`]\/classes['"`]\s*,/g
      let m: RegExpExecArray | null
      while ((m = re.exec(fonte)) !== null) {
        const antes = fonte.slice(Math.max(0, m.index - 120), m.index)
        if (!antes.includes('.post')) continue // GET/PUT em /classes não criam
        const corpo = corpoDoPost(fonte, m.index + m[0].length)
        if (!corpo.includes('is_violation')) {
          const linha = fonte.slice(0, m.index).split('\n').length
          semPolaridade.push(`${caminho.replace(RAIZ, 'src')}:${linha}`)
        }
      }
    }

    expect(
      semPolaridade,
      'Estas telas criam classe sem mandar is_violation — o backend responde 400 e o botão ' +
        'de criar classe fica quebrado. Mande a polaridade escolhida pelo usuário ' +
        '(SeletorPolaridade em components/shared/PolaridadeClasse.tsx), nunca um default.',
    ).toEqual([])
  })
})
