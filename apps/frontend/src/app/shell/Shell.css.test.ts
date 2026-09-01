/**
 * F5-LEVE (identidade): guarda o remap `paletaLkSobreTemaLegado` (Shell.css.ts)
 * que corta o roxo do tema legado (professional/cyberpunk) vazando pro shell
 * novo através de componentes compartilhados (`CameraPlayer`, `TrainingGallery`,
 * ...) que ainda leem `vars.color.primary*` do contrato antigo.
 *
 * POR QUE NÃO renderizar + `getComputedStyle` (o que o pedido sugeria como
 * primeira opção): spike feito antes de escrever este teste — neste repo, o
 * Vitest processa `.css.ts` só até o nível JS (nomes de classe/CSS vars),
 * sem injetar `<style>` real no `document` (`document.querySelectorAll('style')`
 * fica vazio). `getComputedStyle` em cima de uma classe vanilla-extract
 * devolve só o default de UA do jsdom (ex.: background de `<button>` sempre
 * "buttonface", roxo ou ciano, tema certo ou errado) — um teste assim passa
 * ou falha igual dos dois jeitos: vácuo. A garantia real está na FONTE: no
 * objeto que `assignVars` produz e que alimenta `vars:` de `raiz` — que é
 * exatamente o que se desfaz se alguém reverter o remap.
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { paletaLkSobreTemaLegado } from './Shell.css'
import { vars } from '../../styles/theme.css'
import { lk } from '../tokens/lk.css'

// Família roxa dos temas legados (professional.css.ts / cyberpunk.css.ts) —
// se qualquer valor mapeado aqui voltar a citar algum destes, o vazamento
// que este PR fechou reabriu.
const ROXO_LEGADO = ['#8b5cf6', '#a78bfa', '#7c3aed', '139, 92, 246']

describe('paletaLkSobreTemaLegado — remap do shell novo sobre o tema legado', () => {
  const valores = Object.values(paletaLkSobreTemaLegado)

  it('sobrescreve as 4 vars da família primary (primary/primaryLight/primaryDark/primaryAlpha)', () => {
    expect(valores).toHaveLength(4)
  })

  it('primary e primaryLight resolvem pro ciano interativo lk', () => {
    expect(paletaLkSobreTemaLegado[vars.color.primary]).toBe(lk.cor.cianoVisao)
    expect(paletaLkSobreTemaLegado[vars.color.primaryLight]).toBe(lk.cor.cianoVisao)
  })

  it('primaryDark resolve pro hover/pressed lk', () => {
    expect(paletaLkSobreTemaLegado[vars.color.primaryDark]).toBe(lk.cor.cianoProfundo)
  })

  it('primaryAlpha deriva do ciano lk, não de um roxo travado', () => {
    expect(paletaLkSobreTemaLegado[vars.color.primaryAlpha]).toContain(lk.cor.cianoVisao)
  })

  it('nenhum valor referencia a família roxa dos temas legados', () => {
    for (const roxo of ROXO_LEGADO) {
      for (const v of valores) expect(v).not.toContain(roxo)
    }
  })

  it('a raiz do shell realmente consome o remap (não fica órfão)', () => {
    const aqui = path.dirname(fileURLToPath(import.meta.url))
    const fonte = fs.readFileSync(path.join(aqui, 'Shell.css.ts'), 'utf-8')
    const raiz = fonte.slice(fonte.indexOf('export const raiz'))
    expect(raiz).toContain('vars: paletaLkSobreTemaLegado')
  })

  /**
   * F5-LEVE (identidade, rodada 2): `.raiz` só cobre quem está DENTRO da
   * árvore DOM do shell — Radix Portal (Modal/Popover/Tooltip) e o
   * `ToastProvider` escapam pra fora dela (ver Shell.tsx/`identidade-rotas.
   * spec.ts`, achado: "Arquivar câmera" saía roxo mesmo com `.raiz` remapado).
   * Guarda que o alcance pro `documentElement` também não fica órfão — é
   * exatamente esse buraco que reabriu a régua da vez passada.
   */
  it('o remap TAMBÉM alcança document.documentElement (portais escapam de .raiz)', () => {
    const aqui = path.dirname(fileURLToPath(import.meta.url))
    const fonte = fs.readFileSync(path.join(aqui, 'Shell.css.ts'), 'utf-8')
    expect(fonte).toContain("globalStyle('html[data-lk-shell]'")

    const shellTsx = fs.readFileSync(path.join(aqui, 'Shell.tsx'), 'utf-8')
    expect(shellTsx).toContain("setAttribute('data-lk-shell'")
    // Sem remover no unmount, o front antigo herdaria ciano depois de
    // navegar de volta — a limpeza é parte do contrato, não um detalhe.
    expect(shellTsx).toContain("removeAttribute('data-lk-shell')")
  })
})
