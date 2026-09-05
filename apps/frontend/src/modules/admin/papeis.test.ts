/**
 * A tela de criação de usuário é o último lugar onde alguém lê o que um papel
 * faz antes de dar esse papel a uma pessoa de verdade. Se a frase mente, o
 * usuário só descobre num 403.
 *
 * `matriz-papeis.json` é gerada do registry real
 * (`services/api/app/core/permissions.py`) e é a MESMA fonte que
 * `navPorPerfil.test.ts` usa. Aqui ela vira o juiz das frases de `papeis.ts`.
 */
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

import { PAPEIS_ATRIBUIVEIS, PAPEL_LABEL, SEM_PAPEL } from './papeis'

const MATRIZ: Record<string, string[]> = JSON.parse(
  readFileSync(join(__dirname, '..', '..', 'test', 'e2e', 'matriz-papeis.json'), 'utf8'),
)

describe('vocabulário de papéis atribuíveis', () => {
  it('a matriz do backend foi lida (senão os testes abaixo passariam vazios)', () => {
    expect(Object.keys(MATRIZ).sort()).toEqual(
      ['admin', 'analyst', 'operator', 'superadmin', 'trainer', 'viewer'],
    )
  })

  it('não inventa papel: todo papel oferecido existe no backend', () => {
    for (const p of PAPEIS_ATRIBUIVEIS) {
      expect(MATRIZ[p.valor], p.valor).toBeDefined()
    }
  })

  it('não oferece superadmin — a tela nunca criou um, e o backend só aceita de outro superadmin', () => {
    expect(PAPEIS_ATRIBUIVEIS.map((p) => p.valor)).not.toContain('superadmin')
  })

  it('o `resumo` só promete o que o papel REALMENTE tem', () => {
    for (const p of PAPEIS_ATRIBUIVEIS) {
      const faltando = p.concede.filter((k) => !MATRIZ[p.valor].includes(k))
      expect(faltando, `"${p.resumo}" promete o que ${p.valor} não tem`).toEqual([])
    }
  })

  it('o `alerta` só nega o que o papel REALMENTE não tem', () => {
    for (const p of PAPEIS_ATRIBUIVEIS) {
      const mentira = p.nega.filter((k) => MATRIZ[p.valor].includes(k))
      expect(mentira, `"${p.alerta}" nega o que ${p.valor} tem`).toEqual([])
    }
  })

  it('todo papel diz o que NÃO alcança — papel sem limite declarado é papel que surpreende', () => {
    for (const p of PAPEIS_ATRIBUIVEIS) {
      expect(p.alerta.trim().length, p.valor).toBeGreaterThan(0)
      expect(p.nega.length, p.valor).toBeGreaterThan(0)
    }
  })

  it('operator NÃO tem training:write — a razão de "Operador" ter deixado de ser o padrão', () => {
    // Pino de regressão ao contrário: se um dia o registry der training:write
    // ao operator, este teste fica vermelho e alguém revisita o alerta acima.
    expect(MATRIZ.operator).not.toContain('training:write')
    expect(MATRIZ.operator).toContain('frames:annotate')
  })

  it('há um papel que de fato aguenta o Estúdio inteiro (senão o alerta não teria saída)', () => {
    const donos = PAPEIS_ATRIBUIVEIS
      .filter((p) => MATRIZ[p.valor].includes('training:write'))
      .map((p) => p.valor)
    expect(donos).toEqual(['admin', 'trainer'])
  })

  it('todo papel do backend tem rótulo pt-BR — nunca a chave técnica na tela', () => {
    for (const papel of Object.keys(MATRIZ)) {
      const rotulo = PAPEL_LABEL[papel as keyof typeof PAPEL_LABEL]
      expect(rotulo, papel).toBeTruthy()
      expect(rotulo, papel).not.toBe(papel)
    }
  })

  it('SEM_PAPEL é vazio — nenhum papel nasce escolhido', () => {
    expect(SEM_PAPEL).toBe('')
    expect(PAPEIS_ATRIBUIVEIS.map((p) => p.valor)).not.toContain(SEM_PAPEL as never)
  })
})
