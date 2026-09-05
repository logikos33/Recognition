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
 * ── POR QUE NÃO EXISTE MAIS "RENOVAR SESSÃO" ────────────────────────────────
 *
 * Existia, e era mentira: o botão chamava `window.location.reload()`, que volta
 * com o MESMO token e o MESMO `exp` — o aviso reaparecia em segundos. E não há
 * como renovar de verdade: `services/api/app/api/v1/auth/routes.py` expõe
 * register, login, me, forgot-password e reset-password. Nenhuma rota de
 * refresh. Enquanto ela não existir (issue aberta), o aviso diz o que de fato
 * vai acontecer e oferece a única ação que funciona: entrar de novo.
 *
 * Por isso também o foco NÃO vai para o botão primário: "Entrar de novo" mata a
 * sessão. Um cartão que aparece sozinho e rouba o foco para uma ação destrutiva
 * transforma um Enter distraído em trabalho perdido. O foco vai para "Agora
 * não" — a ação que não custa nada — e o primário fica a um Tab.
 *
 * Por que `aria-live="polite"` e não `assertive`: o número muda a cada segundo.
 * `assertive` interromperia o leitor de tela 300 vezes seguidas e tornaria a
 * tela inoperável justamente para quem depende dele.
 */
import { useEffect, useId, useRef, useState } from 'react'
import { Clock } from 'lucide-react'

import * as s from './SessaoExpirando.css'

/** O aviso abre faltando 5 minutos — número do handoff. */
const AVISO_MS = 5 * 60 * 1000

export interface SessaoExpirandoProps {
  /** Instante em que a sessão morre. Aceita Date ou epoch em ms. */
  expiraEm: Date | number
  /** Derruba o token e leva ao login. É a única ação que resolve. */
  onEntrarDeNovo: () => void
  /** Disparado UMA vez quando o contador zera. */
  onExpirou?: () => void
}

export function SessaoExpirando({ expiraEm, onEntrarDeNovo, onExpirou }: SessaoExpirandoProps) {
  const alvo = typeof expiraEm === 'number' ? expiraEm : expiraEm.getTime()
  const [agora, setAgora] = useState(() => Date.now())
  const [dispensado, setDispensado] = useState(false)
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

  // Foco no aviso assim que ele aparece — senão o teclado teria de varrer a
  // página inteira até cá. Vai no botão NÃO destrutivo (ver docstring).
  useEffect(() => {
    if (visivel) focoRef.current?.focus()
  }, [visivel])

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
          : 'Salve o que estiver fazendo: quando o contador zerar, será preciso entrar de novo.'}
      </p>
      <div className={s.acoes}>
        <button
          ref={expirou ? focoRef : undefined}
          type="button"
          className={s.botaoPrimario}
          onClick={onEntrarDeNovo}
        >
          Entrar de novo
        </button>
        {!expirou && (
          <button
            ref={focoRef}
            type="button"
            className={s.botaoSecundario}
            onClick={() => setDispensado(true)}
          >
            Agora não
          </button>
        )}
      </div>
    </div>
  )
}
