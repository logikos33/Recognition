/**
 * Tests: duplicata catálogo padrão × classe do tenant (lógica pura).
 */
import { describe, expect, it } from 'vitest'

import { achaDuplicataNoCatalogo } from '../../utils/classCatalogDuplicate'

const catalogo = [
  { class_name: 'no_glasses', display_name: 'Sem Óculos', polaridade: 'violacao' as const },
  { class_name: 'no_gloves', display_name: 'Sem Luvas', polaridade: 'indefinida' as const },
]

describe('achaDuplicataNoCatalogo', () => {
  it('acha por display_name, case-insensitive', () => {
    expect(achaDuplicataNoCatalogo('sem óculos', catalogo)?.class_name).toBe('no_glasses')
  })

  it('acha por class_name (id técnico), não só display_name', () => {
    // Achado de 01/09: o script olhou só class_name e não viu que
    // display_name já batia — a regra tem de casar os DOIS.
    expect(achaDuplicataNoCatalogo('no_gloves', catalogo)?.display_name).toBe('Sem Luvas')
  })

  it('ignora espaço nas pontas', () => {
    expect(achaDuplicataNoCatalogo('  Sem Óculos  ', catalogo)).not.toBeNull()
  })

  it('nome que não existe no catálogo → null', () => {
    expect(achaDuplicataNoCatalogo('Protetor Auricular', catalogo)).toBeNull()
  })

  it('nome vazio → null (não bate com nada por acidente)', () => {
    expect(achaDuplicataNoCatalogo('   ', catalogo)).toBeNull()
  })

  it('catálogo vazio → null', () => {
    expect(achaDuplicataNoCatalogo('Sem Óculos', [])).toBeNull()
  })
})
