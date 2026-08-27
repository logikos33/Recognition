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
 * Por que âmbar e não vermelho: ainda dá para renovar. Vermelho é falha
 * consumada; gastá-lo aqui é ensinar o operador a ignorar o vermelho de verdade.
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
  onRenovar: () => void
  onSair: () => void
  /** Disparado UMA vez quando o contador zera. */
  onExpirou?: () => void
}

export function SessaoExpirando({ expiraEm, onRenovar, onSair, onExpirou }: SessaoExpirandoProps) {
  const alvo = typeof expiraEm === 'number' ? expiraEm : expiraEm.getTime()
  const [agora, setAgora] = useState(() => Date.now())
  const jaExpirou = useRef(false)
  const renovarRef = useRef<HTMLButtonElement>(null)
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

  // Foco no Renovar assim que o aviso aparece: é a ação que o usuário quase
  // sempre quer, e sem isso o teclado teria de varrer a página inteira até cá.
  useEffect(() => {
    if (visivel) renovarRef.current?.focus()
  }, [visivel])

  if (!visivel) return null

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
        Por segurança, a sessão encerra após inatividade. Renove para continuar de onde parou.
      </p>
      <div className={s.acoes}>
        <button ref={renovarRef} type="button" className={s.botaoRenovar} onClick={onRenovar}>
          Renovar sessão
        </button>
        <button type="button" className={s.botaoSair} onClick={onSair}>
          Sair
        </button>
      </div>
    </div>
  )
}
