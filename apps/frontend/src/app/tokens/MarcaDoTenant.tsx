/**
 * Publica a cor de marca JÁ CLAMPADA como `--lk-marca`.
 *
 * O `ThemeProvider` (front antigo, montado acima das rotas) injeta
 * `--color-primary` cru, do cadastro do tenant. Os tokens do front novo leem
 * `--lk-marca`, não `--color-primary` — assim a cor que chega na tela é sempre
 * a que passa do piso de contraste (DECISÃO v2 item 3).
 *
 * Fica no front NOVO de propósito: mexer no `resolveTheme` clamparia a cor do
 * front antigo junto, que é claro e tem outro piso. Uma decisão sobre o shell
 * escuro não deve mudar o shell claro por tabela.
 */
import { useEffect, useState } from 'react'

import { corDeMarcaUsavel, type ResultadoClamp } from './contraste'

/** Variável que os tokens consomem. */
export const VAR_MARCA = '--lk-marca'

/** Onde o tema do tenant publica a cor crua. */
const VAR_ORIGEM = '--color-primary'

export function useMarcaDoTenant(): ResultadoClamp | null {
  const [r, setR] = useState<ResultadoClamp | null>(null)

  useEffect(() => {
    const aplicar = () => {
      const cru = getComputedStyle(document.documentElement)
        .getPropertyValue(VAR_ORIGEM)
        .trim()
      const res = corDeMarcaUsavel(cru || null)
      document.documentElement.style.setProperty(VAR_MARCA, res.cor)
      setR(res)
    }

    aplicar()
    // O tema do tenant chega por fetch, DEPOIS do primeiro render. Sem observar,
    // a marca ficaria no padrão para sempre e o white-label não valeria nada.
    const obs = new MutationObserver(aplicar)
    obs.observe(document.head, { childList: true, subtree: true })
    return () => obs.disconnect()
  }, [])

  return r
}
