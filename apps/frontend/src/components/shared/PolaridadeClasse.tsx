/**
 * PolaridadeClasse — o que um evento daquela classe É.
 *
 * NÃO confundir com VereditoHumano, que é o que uma PESSOA julgou sobre um
 * alerta. Palavras disjuntas, paletas disjuntas: polaridade usa
 * success/danger (verde/vermelho), veredito usa primary/warning/neutral.
 * A regra está escrita nos dois arquivos de propósito.
 *
 * TRÊS estados, não dois. `yolo_classes.is_violation` é NULLABLE, e NULL
 * significa "ninguém decidiu" — que a ADR-0065 proíbe tratar como presença.
 * A API expõe isso no campo `polaridade`; o booleano `is_violation` continua
 * existindo para quem decide alerta (lá o colapso NULL→false é o lado seguro),
 * mas para EXIBIR ele mentiria: "não definida" apareceria como "conformidade".
 *
 * Catálogo GLOBAL não é editável por tenant: a polaridade de `no_gloves` vale
 * para todos os clientes, e mexer nela aqui mudaria o significado da classe
 * para todo mundo. A tela mostra e explica; não deixa editar.
 */
import { Badge, type BadgeVariant } from '../ui/Badge/Badge'
import { vars } from '../../styles/theme.css'

export type Polaridade = 'violacao' | 'conformidade' | 'indefinida'

export const ROTULO_POLARIDADE: Record<Polaridade, string> = {
  violacao: 'Violação',
  conformidade: 'Conformidade',
  indefinida: 'Não definida',
}

export const EXPLICACAO_POLARIDADE: Record<Polaridade, string> = {
  violacao:
    'Um evento desta classe é uma violação — pode virar alerta. Ex.: "Sem protetor de ouvido".',
  conformidade:
    'Um evento desta classe é conformidade — vira telemetria, nunca alerta. Ex.: "Protetor auditivo".',
  indefinida:
    'Ninguém decidiu ainda. O modelo pode detectar esta classe a tarde inteira e nada vira evento.',
}

/**
 * Paleta DELIBERADAMENTE disjunta do veredito humano (primary/warning/neutral).
 * Exportada porque o teste assere a disjunção.
 */
export const VARIANTE_POLARIDADE: Record<Polaridade, BadgeVariant> = {
  violacao: 'danger',
  conformidade: 'success',
  indefinida: 'neutral',
}

export function PolaridadeBadge({ polaridade }: { polaridade: Polaridade }) {
  return (
    <span title={EXPLICACAO_POLARIDADE[polaridade]} style={{ display: 'inline-flex' }}>
      <Badge variant={VARIANTE_POLARIDADE[polaridade]}>
        {ROTULO_POLARIDADE[polaridade]}
      </Badge>
    </span>
  )
}

export interface SeletorPolaridadeProps {
  polaridade: Polaridade
  /** Catálogo global → só leitura (a polaridade é compartilhada entre tenants). */
  editavel: boolean
  onChange: (nova: Exclude<Polaridade, 'indefinida'>) => void
}

/**
 * Dois botões, não um toggle: com três estados possíveis, um interruptor
 * binário obrigaria "não definida" a parecer um dos dois. Aqui nenhum dos dois
 * aparece marcado enquanto ninguém decidiu.
 */
export function SeletorPolaridade({
  polaridade,
  editavel,
  onChange,
}: SeletorPolaridadeProps) {
  if (!editavel) {
    return (
      <span
        title={`${EXPLICACAO_POLARIDADE[polaridade]} Esta classe é do catálogo global: a polaridade vale para todos os clientes e não é editável aqui.`}
        style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
      >
        <PolaridadeBadge polaridade={polaridade} />
        <span style={{ fontSize: 11, color: vars.color.textMuted }}>catálogo</span>
      </span>
    )
  }

  const opcoes: Array<Exclude<Polaridade, 'indefinida'>> = ['violacao', 'conformidade']
  return (
    <span
      role="group"
      aria-label="Polaridade da classe"
      style={{ display: 'inline-flex', gap: 4 }}
    >
      {opcoes.map(op => {
        const ativo = polaridade === op
        return (
          <button
            key={op}
            type="button"
            aria-pressed={ativo}
            onClick={() => onChange(op)}
            title={EXPLICACAO_POLARIDADE[op]}
            style={{
              padding: '3px 9px',
              fontSize: 11,
              fontWeight: ativo ? 700 : 500,
              borderRadius: 6,
              cursor: 'pointer',
              border: `1px solid ${
                ativo
                  ? op === 'violacao'
                    ? vars.color.danger
                    : vars.color.success
                  : vars.color.borderDefault
              }`,
              background: ativo
                ? op === 'violacao'
                  ? vars.color.dangerMuted
                  : vars.color.successMuted
                : 'transparent',
              color: ativo
                ? op === 'violacao'
                  ? vars.color.danger
                  : vars.color.success
                : vars.color.textMuted,
            }}
          >
            {ROTULO_POLARIDADE[op]}
          </button>
        )
      })}
      {polaridade === 'indefinida' && (
        <span
          title={EXPLICACAO_POLARIDADE.indefinida}
          style={{ fontSize: 11, color: vars.color.warning, alignSelf: 'center' }}
        >
          não definida
        </span>
      )}
    </span>
  )
}
