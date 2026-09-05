/**
 * ProcedenciaEvento — QUEM desenhou a caixa deste evento, na LISTA.
 *
 * Existe porque a procedência tinha DOIS critérios e só um deles chegava às
 * listas. O de primeira mão é `violations[].origem`, DECLARADO por quem gravou
 * o evento; o outro é o atraso entre captura e gravação
 * (`classificarLatencia`, em `ProcedenciaBadge.tsx`), que é INDÍCIO.
 *
 * MEDIDO em 05/09 (issue #670): 4.609 dos 5.174 eventos do DEV têm caixa
 * desenhada por PESSOA (`origem = 'anotacao_humana'`, semeados por
 * `scripts/ops/eventos_acervo_rvb.py`), e o script grava
 * `created_at == timestamp` — o critério temporal NUNCA acende neles. Resultado:
 * a lista de eventos, os dois widgets do dashboard e o histórico antigo
 * apresentavam 4.609 anotações humanas como se fossem detecção do modelo em
 * produção. O PR #669 já tinha corrigido isto na tela de DETALHE; aqui a
 * mesma regra passa a ter UM dono, em vez de ser reescrita em cada superfície.
 *
 * Ordem: **declaração vence indício**. Sem nenhuma das duas, sem badge — sem
 * afirmação (mesma regra do `ProcedenciaBadge`, que continua sendo o dono do
 * critério temporal e é reusado inteiro aqui, não recopiado).
 */
import { Badge } from '../ui/Badge/Badge'
import { ProcedenciaBadge } from './ProcedenciaBadge'

/**
 * O MÍNIMO de uma violação para decidir procedência. Frouxo de propósito: as
 * listas tipam `violations` de formas diferentes (`{class, confidence}` no
 * `useDashboardAlerts`, com bbox no detalhe) e nenhuma delas precisa mudar
 * para passar por aqui — `class` opcional mantém a compatibilidade estrutural
 * (sem ela o TypeScript recusaria os tipos existentes por "weak type").
 */
export interface ViolacaoProcedencia {
  class?: string
  confidence?: number
  /** Quem desenhou ESTA caixa, declarado por quem gravou o evento. */
  origem?: string
  /** Ferramenta da anotação humana ('manual', proposta aceita…). */
  anotacao_source?: string
  /** Marca da carga em lote do acervo de demonstração. */
  lote?: string
}

/** Caixa desenhada/aceita por PESSOA no estúdio de anotação. */
export const ORIGEM_HUMANA = 'anotacao_humana'
/** Caixa desenhada pelo detector servido (ONNX). */
export const ORIGEM_MODELO = 'modelo_onnx'

export interface ProcedenciaDeclarada {
  origem: 'humana' | 'modelo'
  rotulo: string
  titulo: string
}

/**
 * Procedência DECLARADA no dado — `violations[].origem` — e não a distância
 * entre captura e gravação.
 *
 * Função PURA — sem relógio, sem rede, sem estado. Origem ausente ou
 * desconhecida → `null`: sem declaração, sem afirmação.
 *
 * (Nasceu em `app/epi/EventoDetalhe.tsx` no PR #669 e foi movida para cá
 * intacta, para que as listas leiam a MESMA regra em vez de uma cópia.)
 */
export function procedenciaDeclarada(
  violations: ViolacaoProcedencia[] | null | undefined,
): ProcedenciaDeclarada | null {
  const vs = violations ?? []
  const humana = vs.some((v) => v.origem === ORIGEM_HUMANA)
  const modelo = vs.some((v) => v.origem === ORIGEM_MODELO)
  if (!humana && !modelo) return null
  const lote = vs.find((v) => v.lote)?.lote
  const origem = humana ? 'humana' : 'modelo'
  return {
    origem,
    rotulo: [
      humana ? 'anotação humana' : 'detecção do modelo',
      lote ? 'demonstração' : null,
    ].filter(Boolean).join(' · '),
    titulo: (humana
      ? 'A caixa deste evento foi desenhada por uma pessoa na anotação, não pelo modelo.'
      : 'A caixa deste evento foi desenhada pelo modelo de visão.')
      + (lote ? ` Carregado em lote para demonstração (${lote}).` : ''),
  }
}

/**
 * Badge das listas: origem declarada quando existe, senão o badge temporal
 * de sempre (`ProcedenciaBadge`, que segue decidindo o próprio critério).
 *
 * `warning` para a caixa humana — é a ressalva que faltava; `neutral` para a
 * do modelo, que é o caso esperado e não é ressalva nenhuma.
 */
export function ProcedenciaEvento({
  violations,
  capturadoEm,
  gravadoEm,
}: {
  violations?: ViolacaoProcedencia[] | null
  capturadoEm?: string | null
  gravadoEm?: string | null
}) {
  const declarada = procedenciaDeclarada(violations)
  if (!declarada) return <ProcedenciaBadge capturadoEm={capturadoEm} gravadoEm={gravadoEm} />
  return (
    <span title={declarada.titulo} data-testid="procedencia">
      <Badge variant={declarada.origem === 'humana' ? 'warning' : 'neutral'}>
        {declarada.rotulo}
      </Badge>
    </span>
  )
}
