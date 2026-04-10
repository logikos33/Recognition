import { NavLink, useLocation } from 'react-router-dom'
import { Menu } from 'lucide-react'
import type { User } from '../../../hooks/useAuth'
import { useAppStore } from '../../../stores/appStore'
import { ThemeToggle } from '../../ui/ThemeToggle/ThemeToggle'
import { vars } from '../../../styles/theme.css'
import {
  topBar, leftSection, hamburgerBtn, logoLink, logoEmoji, logoText,
  breadcrumb, breadcrumbSep, breadcrumbCurrent,
  rightSection, userInfo, userName, roleBadge, logoutButton,
} from './TopBar.css'

const ROUTE_LABELS: Record<string, string> = {
  '/modules': 'Módulos',
  '/epi/dashboard': 'Dashboard',
  '/epi/cameras': 'Câmeras',
  '/epi/alerts': 'Alertas',
  '/monitoring': 'Monitoramento',
  '/annotation': 'Anotação',
  '/training': 'Treinamento',
  '/alerts': 'Alertas',
  '/cameras': 'Câmeras',
  '/dashboard': 'Dashboard',
}

interface TopBarProps {
  user: User
  onLogout: () => void
}

export function TopBar({ user, onLogout }: TopBarProps) {
  const openSidebar = useAppStore((s) => s.openSidebar)
  const selectedModule = useAppStore((s) => s.selectedModule)
  const location = useLocation()

  const currentLabel = ROUTE_LABELS[location.pathname] || ''
  const moduleLabel = selectedModule === 'epi' ? 'EPI Monitor' : selectedModule === 'fueling' ? 'Carregamento' : null

  return (
    <header className={topBar}>
      <div className={leftSection}>
        <button
          className={hamburgerBtn}
          onClick={openSidebar}
          aria-label="Abrir menu lateral"
        >
          <Menu size={20} />
        </button>

        <NavLink to={selectedModule ? `/${selectedModule}/dashboard` : '/modules'} className={logoLink}>
          <span className={logoEmoji}>🦺</span>
          <span className={logoText}>EPI Monitor</span>
        </NavLink>

        {(moduleLabel || currentLabel) && (
          <div className={breadcrumb}>
            {moduleLabel && (
              <>
                <span className={breadcrumbSep}>/</span>
                <span>{moduleLabel}</span>
              </>
            )}
            {currentLabel && (
              <>
                <span className={breadcrumbSep}>/</span>
                <span className={breadcrumbCurrent}>{currentLabel}</span>
              </>
            )}
          </div>
        )}
      </div>

      <div className={rightSection}>
        <ThemeToggle />

        <div className={userInfo}>
          <span className={userName}>{user.name}</span>
          <span
            className={roleBadge}
            style={{
              background: user.role === 'admin' ? vars.color.purple600 : vars.color.success,
              color: '#fff',
            }}
          >
            {user.role}
          </span>
        </div>

        <button className={logoutButton} onClick={onLogout} aria-label="Sair">
          Sair
        </button>
      </div>
    </header>
  )
}
