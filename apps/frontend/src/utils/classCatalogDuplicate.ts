/**
 * Duplicata catálogo padrão × classe do tenant — lógica pura, testável.
 *
 * Incidente de 01/09: um script de ops criou 3 classes no catálogo do
 * TENANT com nomes que já existiam no catálogo GLOBAL ('Sem Óculos', 'Sem
 * Luvas', 'Óculos'). A tela de Classes passou a mostrar cada nome DUAS
 * vezes — uma com as anotações, outra zerada para sempre (as anotações
 * antigas ficam presas ao class_id GLOBAL, nunca ao da linha nova).
 *
 * A regra de casamento espelha `AlertRepository._nomes_por_polaridade`
 * (backend): os DOIS nomes do catálogo global entram — `class_name`
 * (id técnico) E `display_name` (rótulo) — porque é isso que o backend
 * une para decidir a polaridade servida (ADR-0071). "União não subtrai":
 * uma classe do tenant homônima NÃO substitui a linha global, só duplica.
 */

export interface EntradaCatalogo {
  class_name: string
  display_name: string
  polaridade?: 'violacao' | 'conformidade' | 'indefinida'
}

/** Acha, case-insensitive, a entrada do catálogo cujo class_name OU
 * display_name bate com `nome`. `null` = sem duplicata. */
export function achaDuplicataNoCatalogo(
  nome: string,
  catalogo: EntradaCatalogo[],
): EntradaCatalogo | null {
  const alvo = nome.trim().toLowerCase()
  if (!alvo) return null
  return (
    catalogo.find(
      (c) => c.class_name.toLowerCase() === alvo || c.display_name.toLowerCase() === alvo,
    ) ?? null
  )
}
