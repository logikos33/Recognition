/**
 * Alerta de desbalanceamento de classes — lógica pura, testável.
 *
 * Classe rara é a causa silenciosa nº 1 de modelo que parece bom e falha em
 * produção. Grita quando, entre classes ativas:
 *   - com uso > 0: a maior tem ≥ 10× as caixas da menor; e/ou
 *   - existe classe ativa com 0 caixas (só depois que a anotação começou —
 *     projeto zerado não é desbalanceamento, é ponto de partida).
 */

export const IMBALANCE_RATIO = 10

export interface ClassUsage {
  name: string
  usage: number
}

export interface ImbalanceResult {
  triggered: boolean
  /** Classes com uso > 0 que a maior domina por ≥ IMBALANCE_RATIO. */
  rare: ClassUsage[]
  /** Classes ativas sem nenhuma caixa (com anotação já em andamento). */
  zeroUsage: string[]
  /** A classe mais anotada (referência das mensagens). */
  max: ClassUsage | null
}

export function computeImbalance(classes: ClassUsage[]): ImbalanceResult {
  const used = classes.filter(c => c.usage > 0)
  const max = used.reduce<ClassUsage | null>(
    (acc, c) => (acc === null || c.usage > acc.usage ? c : acc),
    null,
  )
  const rare =
    max === null
      ? []
      : used.filter(c => c !== max && max.usage >= IMBALANCE_RATIO * c.usage)
  const zeroUsage = max === null ? [] : classes.filter(c => c.usage === 0).map(c => c.name)
  return {
    triggered: rare.length > 0 || zeroUsage.length > 0,
    rare,
    zeroUsage,
    max,
  }
}

/** Mensagens pt-BR do banner, nomeando as classes raras. */
export function imbalanceMessages(result: ImbalanceResult): string[] {
  if (!result.triggered || !result.max) return []
  const messages: string[] = []
  for (const cls of result.rare) {
    messages.push(
      `${cls.name} tem ${cls.usage} caixa${cls.usage !== 1 ? 's' : ''}; ` +
        `${result.max.name} tem ${result.max.usage} — o modelo vai ignorar ${cls.name}.`,
    )
  }
  if (result.zeroUsage.length > 0) {
    messages.push(
      `Sem nenhuma caixa: ${result.zeroUsage.join(', ')} — ` +
        'anote-as ou arquive-as antes de treinar.',
    )
  }
  return messages
}
