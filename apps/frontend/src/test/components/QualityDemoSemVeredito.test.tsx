/**
 * A demo de Qualidade não pode inventar veredito humano.
 *
 * `makeInspections()` sorteava `feedback_status` de
 * ['pending','pending','pending','confirmed','confirmed','rejected'] — 1 em
 * cada 3 linhas exibia um julgamento que ninguém deu, e o sorteio era
 * independente do `result`, produzindo linhas "OK + Rejeitado". Simular
 * detecção numa demo é legítimo; simular a decisão de uma pessoa não é.
 */
import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const fonte = readFileSync(
  resolve(process.cwd(), 'src/modules/quality/pages/QualityInspectionsPage.tsx'),
  'utf8',
)

describe('demo de Qualidade', () => {
  it('não sorteia veredito humano', () => {
    // Guarda de texto porque o gerador roda no import do módulo (ALL_INSPECTIONS
    // é const de topo) e sortear 200 linhas tornaria o teste probabilístico.
    expect(fonte).not.toMatch(/feedbacks\[Math\.floor\(Math\.random/)
    expect(fonte).not.toMatch(/const feedbacks: FeedbackStatus\[\]/)
  })

  it('toda inspeção da demo nasce pendente de julgamento', () => {
    expect(fonte).toMatch(/feedback_status: 'pending' as FeedbackStatus/)
  })

  it('a tela continua se declarando demonstração', () => {
    expect(fonte).toContain('MODO DEMONSTRAÇÃO')
  })
})
