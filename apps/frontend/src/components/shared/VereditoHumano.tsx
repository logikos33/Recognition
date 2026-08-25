/**
 * VereditoHumano — o que uma PESSOA julgou sobre o alerta.
 *
 * NÃO confundir com a POLARIDADE do evento ("Violação"/"Conformidade", coluna
 * "Evento"): polaridade é o que o evento É, sai da classe do modelo
 * (yolo_classes.is_violation, ADR-0063, migration 125) e usa verde/vermelho.
 * Veredito é o que o HUMANO decidiu, usa azul/âmbar/cinza e mora em coluna
 * própria. Palavras disjuntas, paletas disjuntas, colunas disjuntas.
 *
 * `alerts.verification_verdict` SOZINHO NÃO SERVE: a task Celery de
 * pré-análise grava o MESMO 'approve'/'reject' com verified_by='claude-haiku'
 * (infrastructure/queue/tasks/verification.py:110-122). A coluna do veredito
 * não sabe dizer se quem julgou foi gente. A prova de humanidade é o prefixo
 * 'user:' em `verified_by`, que `VerificationService.human_review` grava. Sem
 * essa prova a tela diz "Não revisado" — ausência de veredito não é veredito.
 */
import { Badge, type BadgeVariant } from '../ui/Badge/Badge'

export type Veredito = 'procedente' | 'falso-positivo' | 'nao-revisado'

/** Prefixo gravado por VerificationService.human_review em `verified_by`. */
const PREFIXO_HUMANO = 'user:'

/** Função PURA — sem rede, sem estado. É onde mora a regra. */
export function vereditoHumano(
  verdict?: string | null,
  verifiedBy?: string | null,
): Veredito {
  if (!verifiedBy?.startsWith(PREFIXO_HUMANO)) return 'nao-revisado'
  if (verdict === 'approve') return 'procedente'
  if (verdict === 'reject') return 'falso-positivo'
  return 'nao-revisado'
}

const ROTULO: Record<Veredito, string> = {
  procedente: 'Procedente',
  'falso-positivo': 'Falso positivo',
  'nao-revisado': 'Não revisado',
}

const EXPLICACAO: Record<Veredito, string> = {
  procedente: 'Uma pessoa revisou e considerou o alerta correto.',
  'falso-positivo': 'Uma pessoa revisou e considerou a detecção incorreta.',
  'nao-revisado': 'Ninguém julgou este alerta ainda. Não é o mesmo que "falso".',
}

/**
 * Paleta DELIBERADAMENTE disjunta da polaridade, que usa success/danger.
 * Exportada porque o teste assere a disjunção: se alguém puser 'danger' em
 * falso-positivo, veredito e violação viram a mesma cor na mesma linha.
 */
export const VARIANTE_VEREDITO: Record<Veredito, BadgeVariant> = {
  procedente: 'primary',
  'falso-positivo': 'warning',
  'nao-revisado': 'neutral',
}

export function VereditoBadge({
  verdict,
  verifiedBy,
}: {
  verdict?: string | null
  verifiedBy?: string | null
}) {
  const v = vereditoHumano(verdict, verifiedBy)
  return (
    <span title={EXPLICACAO[v]}>
      <Badge variant={VARIANTE_VEREDITO[v]}>{ROTULO[v]}</Badge>
    </span>
  )
}
