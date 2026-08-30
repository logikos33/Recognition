/**
 * Cabeçalho de marca das telas de Acesso — mesmo monograma do topo de
 * `Modulos.tsx`, mesma máscara. Compartilhado porque as 3 telas o repetem
 * idêntico (spec: `Acesso Logikos.dc.html`, linhas 17-21).
 */
import { lk } from '../tokens/lk.css'
import * as s from './Acesso.css'

export function Marca() {
  return (
    <div className={s.marcaWrap}>
      <svg viewBox="0 0 100 100" width="56" height="56" aria-hidden="true">
        <defs>
          <mask id="lk-monograma-acesso">
            <rect width="100" height="100" fill="white" />
            <g transform="translate(24,22.4) scale(0.52)">
              <path d="M40 55.3 A20 20 0 1 1 60 55.3 L67 88 L33 88 Z" fill="black" />
            </g>
          </mask>
        </defs>
        <circle cx="50" cy="50" r="44" fill={lk.cor.brancoSinal} mask="url(#lk-monograma-acesso)" />
      </svg>
      <span className={s.marcaTitulo}>LOGIKOS</span>
      <span className={s.marcaSub}>VISION · A RAZÃO QUE ENXERGA</span>
    </div>
  )
}
