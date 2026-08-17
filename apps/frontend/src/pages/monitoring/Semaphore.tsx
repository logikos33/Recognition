/**
 * Semaphore — semáforo geral do box computado no cliente (última amostra +
 * thresholds). Mostra o PIOR motivo em destaque + a lista dos demais, cada
 * um com a linha de runbook ("o que fazer").
 */
import { Badge } from '../../components/ui/Badge/Badge'
import type { HealthSummary } from './health'
import * as s from './monitoring.css'

const LEVEL_LABELS = {
  ok: 'Saudável',
  warn: 'Atenção',
  crit: 'Crítico',
} as const

interface SemaphoreProps {
  summary: HealthSummary
  /** false enquanto não há nenhuma amostra — não afirmar "saudável" sem dado. */
  hasData: boolean
}

export function Semaphore({ summary, hasData }: SemaphoreProps) {
  if (!hasData) {
    return (
      <div className={s.semaphoreCard} role="status">
        <div className={s.semaphoreHead}>
          <span className={s.semaphoreDot.warn} aria-hidden="true" />
          <span className={s.semaphoreTitle}>Sem dados do box</span>
          <span className={s.semaphoreReason}>
            Aguardando a primeira resposta do coletor — nada aqui é estado atual.
          </span>
        </div>
      </div>
    )
  }

  const [worst, ...rest] = summary.reasons

  return (
    <div className={s.semaphoreCard} role="status" aria-label={`Estado geral: ${LEVEL_LABELS[summary.level]}`}>
      <div className={s.semaphoreHead}>
        <span className={s.semaphoreDot[summary.level]} aria-hidden="true" />
        <span className={s.semaphoreTitle}>{LEVEL_LABELS[summary.level]}</span>
        {worst ? (
          <span className={s.semaphoreReason}>{worst.label}</span>
        ) : (
          <span className={s.semaphoreReason}>Todos os indicadores dentro dos limiares.</span>
        )}
      </div>
      {worst?.runbook && <span className={s.runbookText}>O que fazer: {worst.runbook}</span>}
      {rest.length > 0 && (
        <ul className={s.reasonList}>
          {rest.map((r) => (
            <li key={r.id} className={s.reasonItem}>
              <Badge variant={r.severity === 'crit' ? 'danger' : 'warning'}>
                {r.severity === 'crit' ? 'Crítico' : 'Atenção'}
              </Badge>
              <span>{r.label}</span>
              {r.runbook && <span className={s.runbookText}>— {r.runbook}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
