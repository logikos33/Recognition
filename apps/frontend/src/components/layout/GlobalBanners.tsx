/**
 * GlobalBanners — wrapper único para os banners globais (impersonation +
 * contexto de tenant assumido), montado em App.tsx fora das rotas.
 *
 * POR QUE A CSS VAR `--global-banner-offset`
 * Este wrapper é `position: sticky` e ocupa espaço normal no fluxo do
 * documento — quem vem depois dele (AppLayout, rotas) é empurrado para
 * baixo automaticamente. Mas várias telas usam `position: fixed` ancorado
 * no topo do viewport (ex.: AnnotationStudio em tela cheia, overlays,
 * sidebar) — elementos fixed IGNORAM o fluxo normal e não são empurrados
 * por nada, então nascem por baixo do banner sticky (mesmo com z-index
 * maior no banner, o conteúdo fixed fica inacessível na área coberta).
 *
 * A solução: medir a altura real deste wrapper (0 quando nenhum banner
 * renderiza, N px quando um ou os dois renderizam) e publicar como custom
 * property no `documentElement`. Telas fixed no topo leem essa variável
 * (`top: 'var(--global-banner-offset, 0px)'`) e descem exatamente o
 * espaço que os banners ocupam — nunca cobrem conteúdo, nunca precisam de
 * z-index maior que o banner.
 */
import { useEffect, useRef } from 'react'
import { ImpersonationBanner } from '../ImpersonationBanner'
import { TenantContextBanner } from '../TenantContextBanner'

const BANNER_OFFSET_VAR = '--global-banner-offset'

export function GlobalBanners() {
  const wrapperRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const node = wrapperRef.current
    if (!node) return

    const updateOffset = () => {
      document.documentElement.style.setProperty(BANNER_OFFSET_VAR, `${node.offsetHeight}px`)
    }

    updateOffset()

    const observer = new ResizeObserver(updateOffset)
    observer.observe(node)

    return () => {
      observer.disconnect()
      document.documentElement.style.setProperty(BANNER_OFFSET_VAR, '0px')
    }
  }, [])

  return (
    <div ref={wrapperRef} style={{ position: 'sticky', top: 0, zIndex: 2001 }}>
      <ImpersonationBanner />
      <TenantContextBanner />
    </div>
  )
}
