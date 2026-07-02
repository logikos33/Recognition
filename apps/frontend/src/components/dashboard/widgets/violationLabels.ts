/**
 * Tradução backend→humano das classes de violação (pt-BR).
 *
 * TODO(WS2): migrar para o glossário central de termos quando o WS2
 * (onboarding cognitivo) disponibilizar o módulo compartilhado.
 */
export const VIOLATION_LABELS: Record<string, string> = {
  no_helmet: 'Sem capacete',
  no_vest: 'Sem colete',
  no_gloves: 'Sem luvas',
  no_safety_glasses: 'Sem óculos',
  no_glasses: 'Sem óculos',
}

export function violationLabel(className: string): string {
  return VIOLATION_LABELS[className] ?? className
}
