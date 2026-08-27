/**
 * Trava: ZERO hex solto em `src/app/**` — o front novo.
 *
 * O guard-rail antigo (`theme/__tests__/no-offbrand-colors.test.ts`) é uma
 * lista de PROIBIDOS: pega o azul do Bootstrap, o branco hardcoded, o rgba
 * inventado. Ele existe porque o front antigo nasceu sem contrato de cor e a
 * regra possível era conter a regressão.
 *
 * Aqui a regra é a oposta e mais dura: nada de hex, ponto. Toda cor do front
 * novo vem de `lk.css.ts`, e é isso que faz o white-label funcionar — um hex
 * escrito direto no componente é uma cor que o tema do tenant não alcança, e
 * ninguém descobre isso até o primeiro cliente com marca própria abrir a tela.
 *
 * A ÚNICA exceção é `lk.css.ts`: é lá que os valores do desenho moram.
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const APP = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

/** Onde os valores do desenho legitimamente moram. */
const FONTE_DOS_VALORES = 'tokens/lk.css.ts'

/** `#fff`, `#00E5FF`, `#0A0A0FCC` — 3, 4, 6 ou 8 dígitos. */
const HEX = /#[0-9a-fA-F]{3,8}\b/

function arquivos(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = path.join(dir, e.name)
    if (e.isDirectory()) return arquivos(p)
    // Testes ficam de fora: um hex num teste é uma AFIRMAÇÃO sobre cor
    // ("o fallback tem de ser #00E5FF"), não uma cor pintada na tela — e é
    // exatamente o que o segundo caso deste arquivo precisa poder escrever.
    return /\.tsx?$/.test(e.name) && !/\.test\.tsx?$/.test(e.name) ? [p] : []
  })
}

describe('front novo: cor só por token', () => {
  it('não tem hex solto fora de lk.css.ts', () => {
    const infratores: string[] = []
    for (const arquivo of arquivos(APP)) {
      const rel = path.relative(APP, arquivo)
      if (rel === FONTE_DOS_VALORES) continue
      fs.readFileSync(arquivo, 'utf-8').split('\n').forEach((linha, i) => {
        // `#` de comentário, de âncora e de JSDoc não é cor.
        if (HEX.test(linha)) infratores.push(`${rel}:${i + 1}  ${linha.trim()}`)
      })
    }
    expect(infratores, `hex solto — use um token de lk.css.ts:\n${infratores.join('\n')}`)
      .toEqual([])
  })

  it('lk.css.ts liga as superfícies ao white-label do tenant', () => {
    // Se alguém "limpar" os var(--color-*) para hex direto, o tema do cliente
    // para de valer nas telas novas SEM nenhum teste ficar vermelho. Este é.
    const fonte = fs.readFileSync(path.join(APP, FONTE_DOS_VALORES), 'utf-8')
    for (const v of [
      '--color-bg-base', '--color-bg-surface', '--color-border',
      '--color-text-primary', '--color-text-secondary', '--color-primary',
    ]) {
      expect(fonte, `${v} deixou de ser lido — white-label quebra em silêncio`)
        .toContain(`var(${v},`)
    }
  })

  it('estado e magenta ficam FORA do white-label', () => {
    // Decisão registrada no cabeçalho de lk.css.ts: verde/âmbar/vermelho são
    // semântica de segurança e o magenta é assinatura da Logikos. Se virarem
    // var(--color-*), um tenant passa a poder repintar "não conforme".
    const fonte = fs.readFileSync(path.join(APP, FONTE_DOS_VALORES), 'utf-8')
    const bloco = fonte.slice(fonte.indexOf('estado: {'), fonte.indexOf('fonte: {'))
    expect(bloco).not.toContain('var(--color')
    expect(fonte.match(/magentaGlitch: '[^']*'/)?.[0]).not.toContain('var(--color')
  })
})
