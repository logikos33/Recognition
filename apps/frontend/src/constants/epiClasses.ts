/**
 * epiClasses — catálogo único de classes EPI com rótulo pt-BR.
 *
 * Fonte única para chips/checkboxes de classes (WS5).
 * O payload das APIs continua usando o `value` em inglês (ids YOLO);
 * apenas a exibição usa o `label` em pt-BR.
 */

export interface EpiClassOption {
  value: string
  label: string
}

export const EPI_CLASS_OPTIONS: EpiClassOption[] = [
  { value: 'helmet',     label: 'Capacete' },
  { value: 'no_helmet',  label: 'Sem Capacete' },
  { value: 'vest',       label: 'Colete' },
  { value: 'no_vest',    label: 'Sem Colete' },
  { value: 'gloves',     label: 'Luvas' },
  { value: 'no_gloves',  label: 'Sem Luvas' },
  { value: 'glasses',    label: 'Óculos' },
  { value: 'no_glasses', label: 'Sem Óculos' },
]

/** Rótulo pt-BR de uma classe EPI (fallback: o próprio id). */
export function epiClassLabel(value: string): string {
  return EPI_CLASS_OPTIONS.find(o => o.value === value)?.label ?? value
}
