/**
 * A memória local da triagem do gabarito — o que faz a tela sobreviver à rede
 * móvel do chão de fábrica.
 *
 * O PROBLEMA REAL: quem vai anotar está de celular, andando pela RVB, em rede
 * que oscila. Uma tela que grava direto no servidor perde a resposta toda vez
 * que o sinal cai — e pior, perde EM SILÊNCIO: o dono toca SIM, a tela avança,
 * e o veredito nunca existiu. Num gabarito de ~150 imagens, algumas respostas
 * fantasma bastam para o A/B medir errado sem ninguém desconfiar.
 *
 * A ESCOLHA: `localStorage` como fonte da verdade LOCAL, servidor como destino
 * eventual. Toda resposta é gravada aqui PRIMEIRO e só então enviada; o envio
 * que falha deixa a resposta marcada como pendente e é retentado (ao responder
 * a próxima, ao voltar a rede, ao reabrir a tela). A tela lê daqui, não do
 * servidor — por isso ela continua respondendo com o avião ligado.
 *
 * Por que não Service Worker / IndexedDB / uma lib de fila offline: o volume é
 * ~150 respostas de ~200 bytes. `localStorage` é síncrono (nada some entre o
 * toque e o `unload`), tem quota de sobra, e já é onde o resto do app guarda
 * sessão. Um Service Worker traria ciclo de vida, versionamento de cache e
 * invalidação para resolver um problema que cabe em cinco funções.
 *
 * Efeito colateral de graça, e que o pedido exige: fechar e reabrir o
 * navegador não perde nada — nem as respostas, nem a posição na fila.
 *
 * ⛔ Todo acesso a `localStorage` é embrulhado: em aba anônima do Safari com
 * cota zerada, `setItem` LANÇA. Uma exceção aqui derrubaria a tela inteira no
 * meio da triagem — que é exatamente o momento em que ela não pode cair.
 */

/** Resposta a uma classe: os três estados. Nunca binário — ver a migration 135. */
export type Veredito = 'sim' | 'nao' | 'nao_sei'

export interface RespostaLocal {
  /** class_id → veredito. Só as classes já respondidas aparecem. */
  verdicts: Record<number, Veredito>
  /** 'sem_pessoa' quando veio do atalho de um toque; ausente caso contrário. */
  reason?: 'sem_pessoa'
  /** false = ainda não confirmada pelo servidor; o flush retenta. */
  enviado: boolean
}

export type Respostas = Record<string, RespostaLocal>

const CHAVE_RESPOSTAS = 'gabarito:respostas'
const CHAVE_POSICAO = 'gabarito:posicao'

function lerBruto<T>(chave: string, padrao: T): T {
  try {
    const cru = localStorage.getItem(chave)
    return cru ? (JSON.parse(cru) as T) : padrao
  } catch {
    return padrao
  }
}

function gravarBruto(chave: string, valor: unknown): void {
  try {
    localStorage.setItem(chave, JSON.stringify(valor))
  } catch {
    // Cota estourada ou storage bloqueado. A resposta segue em memória (o
    // React já tem o estado) e o flush ainda tenta enviá-la — perder a
    // persistência é ruim, derrubar a tela no meio da triagem é pior.
  }
}

export const lerRespostas = (): Respostas => lerBruto<Respostas>(CHAVE_RESPOSTAS, {})

export const gravarRespostas = (r: Respostas): void => gravarBruto(CHAVE_RESPOSTAS, r)

export const lerPosicao = (): number => {
  const n = lerBruto<number>(CHAVE_POSICAO, 0)
  return Number.isInteger(n) && n >= 0 ? n : 0
}

export const gravarPosicao = (i: number): void => gravarBruto(CHAVE_POSICAO, i)

/**
 * Aplica uma resposta sobre o estado local. SEMPRE marca `enviado: false` —
 * é o envio bem-sucedido que promove para `true`, nunca a intenção de enviar.
 *
 * Mescla com o que já havia no quadro (`...anterior.verdicts`) porque a tela
 * responde uma classe por vez: sobrescrever o objeto inteiro apagaria a
 * resposta dada à classe anterior do MESMO quadro.
 */
export function aplicarResposta(
  respostas: Respostas,
  frameId: string,
  verdicts: Record<number, Veredito>,
  reason?: 'sem_pessoa',
): Respostas {
  const anterior = respostas[frameId]
  return {
    ...respostas,
    [frameId]: {
      verdicts: { ...(anterior?.verdicts ?? {}), ...verdicts },
      // O atalho "não há pessoa" carimba o quadro; responder classe a classe
      // depois APAGA o carimbo, porque a afirmação deixou de ser verdadeira.
      ...(reason ? { reason } : {}),
      enviado: false,
    },
  }
}

/** Os quadros com resposta ainda não confirmada pelo servidor. */
export const pendentes = (respostas: Respostas): string[] =>
  Object.keys(respostas).filter((id) => !respostas[id].enviado)

/**
 * Semeia o estado local com o que o servidor já tem, SEM pisar em pendência.
 *
 * A regra que importa: uma resposta local ainda não enviada VENCE a do
 * servidor. O contrário perderia justamente a resposta que a rede engoliu —
 * o único dado que existe em um lugar só.
 */
export function semear(
  respostas: Respostas,
  doServidor: Record<string, { verdicts: Record<number, Veredito>; reason?: 'sem_pessoa' }>,
): Respostas {
  const saida: Respostas = { ...respostas }
  for (const [frameId, remoto] of Object.entries(doServidor)) {
    if (respostas[frameId] && !respostas[frameId].enviado) continue
    saida[frameId] = { ...remoto, enviado: true }
  }
  return saida
}
