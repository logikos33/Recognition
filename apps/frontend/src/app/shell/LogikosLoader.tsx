/**
 * LogikosLoader — o estado de espera da Logikos Vision.
 *
 * Porte React do `lk-loader.js` do handoff (conceito C2, "tranca de cofre").
 * A MÁQUINA DE ESTADOS é a mesma, deliberadamente — não uma parecida:
 *
 *   entering  → glitch + gira    (entrou na espera)
 *   waiting   → gira             (esperando; SEM glitch, senão vira decoração)
 *   retry     → glitch + gira    (tentou de novo — o glitch marca a nova tentativa)
 *   resolving → glitch 300ms, para de girar, 360ms depois emite `lk-resolved`
 *   idle      → parado
 *
 * O glitch aparece SÓ em entrada/retry/saída. Um glitch em `waiting` seria
 * loop decorativo, e o motion desta marca "termina em repouso".
 *
 * `steps()` em tudo: o giro é discreto, de catraca — não é um spinner que
 * desliza. É o que faz a espera parecer mecanismo, não enfeite.
 *
 * `prefers-reduced-motion` troca giro e glitch por pulso de opacidade.
 */
import { useEffect, useRef } from 'react'

import * as s from './LogikosLoader.css'

export type EstadoLoader = 'entering' | 'waiting' | 'retry' | 'resolving' | 'idle'
export type VarianteLoader = 'fullscreen' | 'tile' | 'spinner'

/** Duração do glitch por estado, em ms. `null` = sem glitch. */
const GLITCH: Record<EstadoLoader, number | null> = {
  entering: 500,
  retry: 500,
  resolving: 300,
  waiting: null,
  idle: null,
}

/** Gira em: entering, waiting, retry. Para em: resolving, idle. */
const GIRA: Record<EstadoLoader, boolean> = {
  entering: true,
  waiting: true,
  retry: true,
  resolving: false,
  idle: false,
}

/** Tamanho padrão por variante — spinner ≤24px é regra do handoff. */
const TAMANHO: Record<VarianteLoader, number> = {
  fullscreen: 112,
  tile: 64,
  spinner: 22,
}

export interface LogikosLoaderProps {
  estado?: EstadoLoader
  variante?: VarianteLoader
  /** Texto overline sob o símbolo. Vazio em `spinner`. */
  rotulo?: string
  tamanho?: number
  /** Disparado 360ms após entrar em `resolving` — o mesmo do custom element. */
  onResolvido?: () => void
}

export function LogikosLoader({
  estado = 'waiting',
  variante = 'fullscreen',
  rotulo,
  tamanho,
  onResolvido,
}: LogikosLoaderProps) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout>>()

  useEffect(() => {
    const dur = GLITCH[estado]
    const w = wrapRef.current
    if (!w) return
    clearTimeout(timerRef.current)

    if (dur !== null) {
      w.style.setProperty('--lk-glitch-dur', `${dur}ms`)
      w.classList.remove(s.rajada)
      // reflow: sem isto o navegador não reinicia a animação quando o estado
      // vai de retry para retry.
      void w.offsetWidth
      w.classList.add(s.rajada)
    }

    if (estado === 'resolving') {
      timerRef.current = setTimeout(() => {
        wrapRef.current?.classList.add(s.resolvido)
        onResolvido?.()
      }, 360)
    }
    return () => clearTimeout(timerRef.current)
  }, [estado, onResolvido])

  const px = tamanho ?? TAMANHO[variante]
  const mostraRotulo = variante !== 'spinner' && !!rotulo

  return (
    <div
      className={s.raiz[variante]}
      role="status"
      aria-live="polite"
      aria-busy={estado !== 'idle' && estado !== 'resolving'}
      data-estado={estado}
    >
      <div
        ref={wrapRef}
        className={GIRA[estado] ? `${s.wrap} ${s.girando}` : s.wrap}
        style={{ ['--lk-size' as string]: `${px}px` }}
      >
        <svg className={s.simbolo} viewBox="0 0 100 100" aria-hidden="true">
          {/* Geometria canônica da fechadura — a MESMA do lk-loader.js.
              ⛔ Nunca distorcer, recolorir ou sombrear. */}
          <path
            className={s.corpo}
            d="M40 55.3 A20 20 0 1 1 60 55.3 L67 88 L33 88 Z"
          />
          <path className={s.franjaCiano} d="M40 55.3 A20 20 0 1 1 60 55.3 L67 88 L33 88 Z" />
          <path className={s.franjaMagenta} d="M40 55.3 A20 20 0 1 1 60 55.3 L67 88 L33 88 Z" />
        </svg>
        <div className={s.anel} aria-hidden="true" />
      </div>
      {mostraRotulo && <p className={s.rotulo}>{rotulo}</p>}
      {/* Leitor de tela precisa do texto mesmo quando o rótulo não aparece. */}
      {!mostraRotulo && <span className={s.apenasLeitor}>Carregando</span>}
    </div>
  )
}
