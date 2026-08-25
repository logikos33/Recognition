/**
 * ProcedenciaBadge — procedência temporal do evento (defeito 3: "o evento não
 * pode PARECER ao vivo sem ser").
 *
 * Enquanto não há inferência em tempo real (issue #519), o shadow roda sobre
 * frames JÁ COLETADOS: `alerts.timestamp` é a hora REAL da captura e
 * `alerts.created_at` é quando o evento foi gravado. A distância entre os dois
 * é o ÚNICO dado que separa "ao vivo" de "coleta retroativa" — nada aqui
 * adivinha, tudo sai do par de datas que o `GET /api/alerts` já devolve
 * (o repository faz `SELECT a.*`).
 */
import { Badge } from '../ui/Badge/Badge'

export type Procedencia = 'ao-vivo' | 'retroativa' | 'desconhecida'

/** Acima de 5 min entre captura e gravação o evento não é contemporâneo. */
export const LIMIAR_RETROATIVO_MS = 5 * 60_000

/**
 * Normaliza a data do backend antes de comparar. `/api/alerts` serializa via
 * jsonify (RFC 822: "Mon, 24 Aug 2026 12:00:00 GMT") e `/api/v1/events` via
 * isoformat() naive ("2026-08-24T12:00:00"), que o JS interpretaria como hora
 * LOCAL — em BRT isso daria −3h e carimbaria "retroativa" em tudo. Anexamos 'Z'
 * só no ISO sem offset (mesma intenção do toUtcMs de utils/timeBuckets.ts, que
 * não dá pra reusar aqui: o teste dele quebra na string RFC 822).
 */
function paraMs(valor: string | null | undefined): number | null {
  if (!valor) return null
  const isoNaive = /^\d{4}-\d{2}-\d{2}T[\d:.]+$/.test(valor)
  const ms = new Date(isoNaive ? `${valor}Z` : valor).getTime()
  return Number.isNaN(ms) ? null : ms
}

/**
 * Classifica a procedência pelo atraso entre captura e gravação.
 * Função PURA — sem relógio, sem rede, sem estado.
 */
export function classificarLatencia(
  capturadoEm: string | null | undefined,
  gravadoEm: string | null | undefined,
  limiarMs: number = LIMIAR_RETROATIVO_MS,
): Procedencia {
  const captura = paraMs(capturadoEm)
  const gravacao = paraMs(gravadoEm)
  if (captura === null || gravacao === null) return 'desconhecida'
  const atraso = gravacao - captura
  // Captura "no futuro" além do limiar = relógio do device fora de sincronia.
  // Não sabemos o que aconteceu, então não afirmamos nada.
  if (atraso < -limiarMs) return 'desconhecida'
  return atraso >= limiarMs ? 'retroativa' : 'ao-vivo'
}

/**
 * Só renderiza a afirmação NEGATIVA. Hoje `alerts.timestamp` ainda nasce com
 * DEFAULT NOW() igual ao created_at (migration 004), então carimbar "AO VIVO"
 * nas linhas existentes trocaria uma mentira por outra — que é justamente o
 * defeito. Ausência de badge = ausência de afirmação.
 *
 * ponytail: quando existir inferência em tempo real de verdade (#519), o ramo
 * 'ao-vivo' vira um Badge variant="success" aqui — um `if` a mais, nada além.
 */
export function ProcedenciaBadge({
  capturadoEm,
  gravadoEm,
}: {
  capturadoEm?: string | null
  gravadoEm?: string | null
}) {
  if (classificarLatencia(capturadoEm, gravadoEm) !== 'retroativa') return null
  return (
    <span title={`Capturado: ${capturadoEm} · gravado: ${gravadoEm}`}>
      <Badge variant="warning">coleta retroativa</Badge>
    </span>
  )
}
