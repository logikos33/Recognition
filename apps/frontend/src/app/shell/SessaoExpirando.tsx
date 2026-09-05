/**
 * SessaoExpirando — o aviso de 5 minutos antes da sessão morrer.
 *
 * Handoff: "Sessão expirando: aviso 5 min antes, countdown mono, Renovar/Sair."
 *
 * Por que ele NÃO decodifica o JWT: quem monta o shell já sabe quando a sessão
 * acaba (login, refresh, claim `exp`). Se este componente decodificasse token,
 * passaria a existir uma SEGUNDA fonte de verdade sobre expiração — e as duas
 * divergiriam no primeiro refresh. Ele recebe `expiraEm` e só conta.
 *
 * Por que âmbar e não vermelho: ainda dá tempo de salvar o que está aberto.
 * Vermelho é falha consumada; gastá-lo aqui é ensinar o operador a ignorar o
 * vermelho de verdade.
 *
 * ── "RENOVAR SESSÃO" VOLTOU, E AGORA RENOVA (issue #667) ────────────────────
 *
 * O botão já existiu e era mentira: chamava `window.location.reload()`, que
 * volta com o MESMO token e o MESMO `exp` — o aviso reaparecia em segundos. A
 * onda 1 o removeu porque não havia rota de refresh; esta onda criou a rota
 * (`POST /api/auth/refresh`) e o botão voltou fazendo o que promete: troca o
 * token vivo por outro com prazo cheio, sem recarregar a página e sem perder o
 * que estiver aberto.
 *
 * O foco vai no primário SÓ porque ele deixou de ser destrutivo. Enquanto o
 * primário era "Entrar de novo", focá-lo transformava um Enter distraído em
 * trabalho perdido — um cartão que aparece sozinho não pode roubar o foco para
 * uma ação que mata a sessão. "Renovar" não custa nada se clicado sem querer.
 *
 * Falha ao renovar não navega sozinha: mostra o motivo, mantém o "Renovar"
 * (pode ter sido a rede) e revela o "Entrar de novo". Arrancar a página para o
 * login no clique que falhou descartaria o trabalho aberto antes de a pessoa
 * ler por quê.
 *
 * Por que `aria-live="polite"` e não `assertive`: o número muda a cada segundo.
 * `assertive` interromperia o leitor de tela 300 vezes seguidas e tornaria a
 * tela inoperável justamente para quem depende dele.
 */
import { useEffect, useId, useRef, useState } from 'react'
import { Clock } from 'lucide-react'

import { renovarSessao } from '../../hooks/useAuth'
import * as s from './SessaoExpirando.css'

/** O aviso abre faltando 5 minutos — número do handoff. */
const AVISO_MS = 5 * 60 * 1000

export interface SessaoExpirandoProps {
  /** Instante em que a sessão morre. Aceita Date ou epoch em ms. */
  expiraEm: Date | number
  /** Derruba o token e leva ao login. Saída de emergência e fim de sessão. */
  onEntrarDeNovo: () => void
  /**
   * Injetável só para teste. Em produção é o `renovarSessao` de verdade — o
   * componente não recebe isso do `Shell` de propósito: o pai não tem como
   * saber renovar melhor do que a própria camada de auth, e uma prop
   * obrigatória a mais seria mais um lugar onde esquecer de ligar o botão.
   */
  renovar?: () => Promise<number>
  /** Disparado UMA vez quando o contador zera. */
  onExpirou?: () => void
}

export function SessaoExpirando({
  expiraEm,
  onEntrarDeNovo,
  onExpirou,
  renovar = renovarSessao,
}: SessaoExpirandoProps) {
  const alvoProp = typeof expiraEm === 'number' ? expiraEm : expiraEm.getTime()
  // Prazo que a renovação acabou de devolver. O `Shell` relê o `exp` do token
  // só de minuto em minuto: sem isto, o cartão ficaria até 1 min na tela
  // contando o prazo VELHO depois de uma renovação bem-sucedida — e a pessoa
  // clicaria de novo achando que não funcionou. Mesma fonte (o token), lida
  // mais cedo; por isso `max`, e não substituição.
  const [alvoRenovado, setAlvoRenovado] = useState<number | null>(null)
  const alvo = Math.max(alvoProp, alvoRenovado ?? 0)
  const [agora, setAgora] = useState(() => Date.now())
  const [dispensado, setDispensado] = useState(false)
  const [renovando, setRenovando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const jaExpirou = useRef(false)
  const focoRef = useRef<HTMLButtonElement>(null)
  const idTitulo = useId()

  const restanteMs = Math.max(0, alvo - agora)
  const visivel = restanteMs <= AVISO_MS
  const expirou = restanteMs === 0

  // Uma batida por segundo. Depois de zerar não há mais o que contar — o
  // intervalo é encerrado em vez de girar em vão até desmontarem o componente.
  useEffect(() => {
    if (expirou) return
    const id = setInterval(() => setAgora(Date.now()), 1000)
    return () => clearInterval(id)
  }, [expirou])

  // Guard de uma vez só: sem ele, um `onExpirou` que re-renderiza o pai viraria
  // laço — e "sessão expirou" disparado em loop derruba o app.
  useEffect(() => {
    if (!expirou || jaExpirou.current) return
    jaExpirou.current = true
    onExpirou?.()
  }, [expirou, onExpirou])

  // "Agora não" vale por SESSÃO, não para sempre. O `Shell` relê o `exp` de
  // minuto em minuto porque o token troca sem desmontar o shell (renovação do
  // contexto assumido, login em outra aba) — e o cartão não desmonta junto.
  // Sem este reset, quem dispensasse uma vez ficaria sem o aviso do token
  // SEGUINTE e descobriria a expiração pela tela parando de responder.
  useEffect(() => {
    setDispensado(false)
    // Prazo novo = situação nova: a falha de renovação anterior não descreve
    // mais o que está acontecendo.
    setErro(null)
  }, [alvo])

  // Foco no aviso assim que ele aparece — senão o teclado teria de varrer a
  // página inteira até cá. Vai no botão NÃO destrutivo (ver docstring).
  useEffect(() => {
    if (visivel) focoRef.current?.focus()
  }, [visivel])

  // Renovação. Guard contra clique duplo: dois refresh em voo emitem dois
  // tokens, e com `single_session` ligado o segundo REVOGA o primeiro — a
  // sessão morreria por excesso de zelo do usuário.
  const aoRenovar = async () => {
    if (renovando) return
    setRenovando(true)
    setErro(null)
    try {
      setAlvoRenovado(await renovar())
    } catch (e) {
      // Mensagem do servidor quando existe (ex.: contexto assumido não renova
      // por aqui); genérica quando é rede/timeout.
      const motivo = e instanceof Error && e.message ? e.message : ''
      // "HTTP 401" é o que o `api.ts` devolve quando não acha mensagem no
      // corpo — e é exatamente o que acontece nos erros de JWT (token
      // expirado por relógio adiantado, revogado por single_session, conta
      // desativada), que respondem noutro envelope. Código de status não é
      // recado para operador de fábrica: cai na frase genérica, que já vem
      // acompanhada do "Entrar de novo".
      const jargao = !motivo || /^HTTP \d+$/.test(motivo)
      setErro(jargao ? 'Não foi possível renovar a sessão.' : motivo)
    } finally {
      setRenovando(false)
    }
  }

  if (!visivel) return null
  // "Agora não" some com o cartão enquanto ainda dá tempo de salvar. Depois de
  // expirar ele volta: aí não há mais nada a terminar, e esconder o aviso seria
  // deixar o operador clicando numa tela que já não fala com o servidor.
  if (dispensado && !expirou) return null

  // `ceil` para que o último pedaço de segundo ainda mostre 00:01 — mostrar
  // 00:00 antes de expirar de fato seria mentira.
  const totalSeg = Math.ceil(restanteMs / 1000)
  const mm = String(Math.floor(totalSeg / 60)).padStart(2, '0')
  const ss = String(totalSeg % 60).padStart(2, '0')

  return (
    <div className={s.cartao} role="alertdialog" aria-labelledby={idTitulo}>
      <div className={s.cabecalho}>
        <Clock className={s.icone} size={17} strokeWidth={1.8} aria-hidden="true" />
        {/* Cor + ícone + palavra, sempre: âmbar sozinho não é estado. */}
        <span className={s.titulo} id={idTitulo}>
          {expirou ? 'Sua sessão expirou' : 'Sua sessão está expirando'}
        </span>
        {!expirou && (
          <span className={s.contador} aria-live="polite">
            {mm}:{ss}
          </span>
        )}
      </div>
      <p className={s.descricao}>
        {expirou
          ? 'Entre de novo para continuar de onde parou.'
          : 'Renove para continuar sem perder o que estiver aberto.'}
      </p>
      {/* Depois de expirar, renovar não é mais possível: o backend recusa
          token morto. Sobra a única ação que resolve. */}
      {expirou ? (
        <div className={s.acoes}>
          <button
            ref={focoRef}
            type="button"
            className={s.botaoPrimario}
            onClick={onEntrarDeNovo}
          >
            Entrar de novo
          </button>
        </div>
      ) : (
        <>
          {erro && (
            <p className={s.erro} role="status">
              {erro}
            </p>
          )}
          <div className={s.acoes}>
            <button
              ref={focoRef}
              type="button"
              className={s.botaoPrimario}
              onClick={aoRenovar}
              disabled={renovando}
              aria-busy={renovando}
            >
              {renovando ? 'Renovando…' : 'Renovar sessão'}
            </button>
            <button
              type="button"
              className={s.botaoSecundario}
              onClick={() => setDispensado(true)}
            >
              Agora não
            </button>
            {/* Só depois de falhar: até lá, "Entrar de novo" seria um botão
                destrutivo ao lado do que resolve, esperando um clique errado. */}
            {erro && (
              <button
                type="button"
                className={s.botaoSecundario}
                onClick={onEntrarDeNovo}
              >
                Entrar de novo
              </button>
            )}
          </div>
        </>
      )}
    </div>
  )
}
