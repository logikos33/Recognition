/**
 * AppShell — aplica a classe de tema Vanilla Extract e o layout raiz da app.
 *
 * POR QUE A CLASSE DE TEMA VAI NO <html>, E NÃO NESTE <div>
 * O vanilla-extract escopa os tokens à classe do tema: `vars.color.*` só
 * resolve DENTRO do elemento que a carrega. Enquanto a classe ficava neste
 * div, tudo que o Radix portaliza para o `<body>` — Modal, Tooltip, Popover,
 * AppDrawer — nascia FORA do escopo e todo `vars.*` resolvia para vazio:
 * painel transparente, sem borda, texto na cor padrão do browser e overlay sem
 * escurecimento. O `backdropFilter: blur(4px)` sobrevivia por ser literal, daí
 * o efeito de tela borrada e clara em vez de escura.
 *
 * Aplicando no `documentElement`, os portais herdam os tokens e os quatro
 * componentes são consertados de uma vez — e o próximo componente portalizado
 * não nasce quebrado.
 *
 * A classe `root` (layout) continua neste div de propósito: ela é o container
 * da app, não o escopo dos tokens. São coisas separadas.
 */
import type { ReactNode } from 'react'
import { useEffect } from 'react'
import { useThemeStore } from '../../../stores/themeStore'
import { recognitionDarkTheme } from '../../../theme/tokens/recognition-dark.css'
import { cyberpunkTheme } from '../../../styles/themes/cyberpunk.css'
import { professionalTheme } from '../../../styles/themes/professional.css'
import { root } from './AppShell.css'

const THEME_CLASS_MAP = {
  'recognition-dark': recognitionDarkTheme,
  cyberpunk: cyberpunkTheme,
  professional: professionalTheme,
} as const

const ALL_THEME_CLASSES = Object.values(THEME_CLASS_MAP)

interface AppShellProps {
  children: ReactNode
}

export function AppShell({ children }: AppShellProps) {
  const mode = useThemeStore((s) => s.mode)
  const themeClass = THEME_CLASS_MAP[mode] ?? recognitionDarkTheme

  useEffect(() => {
    const el = document.documentElement
    // Remove só as classes de tema conhecidas — nunca zera className, que
    // pode conter classes de terceiros/extensões.
    el.classList.remove(...ALL_THEME_CLASSES)
    el.classList.add(themeClass)
    el.setAttribute('data-theme', mode)

    return () => {
      el.classList.remove(themeClass)
    }
  }, [mode, themeClass])

  return <div className={root}>{children}</div>
}
