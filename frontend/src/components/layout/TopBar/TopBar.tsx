import { NavLink, useLocation } from 'react-router-dom'
import { Menu } from 'lucide-react'
import type { User } from '../../../hooks/useAuth'
import { useAppStore } from '../../../stores/appStore'
import { ThemeToggle } from '../../ui/ThemeToggle/ThemeToggle'
import { NotificationBell } from '../../ui/NotificationBell/NotificationBell'
import { vars } from '../../../styles/theme.css'
import {
  topBar, leftSection, hamburgerBtn, logoLink, logoEmoji, logoText,
  breadcrumb, breadcrumbSep, breadcrumbCurrent, breadcrumbLink,
  rightSection, userInfo, userName, roleBadge, logoutButton,
} from './TopBar.css'

const ROUTE_LABELS: Record<string, string> = {
  '/modules': 'Módulos',
  '/epi/dashboard': 'Dashboard',
  '/epi/cameras': 'Câmeras',
  '/epi/alerts': 'Alertas',
  '/epi/training': 'Treinamento',
  '/epi/training/classes': 'Classes',
  '/epi/reports': 'Relatórios',
  '/epi/health': 'Saúde do Sistema',
  '/epi/verification': 'Verificação',
  '/epi/counting': 'Contagem',
  '/admin': 'Painel Admin',
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

const MODULE_BRAND: Record<string, { emoji: string; label: string }> = {
  epi:     { emoji: '🦺', label: 'EPI' },
  quality: { emoji: '✅', label: 'Qualidade' },
  fueling: { emoji: '⛽', label: 'Carregamento' },
  admin:   { emoji: '🛡️', label: 'Painel Admin' },
}

export function TopBar({ user, onLogout }: TopBarProps) {
  const openSidebar = useAppStore((s) => s.openSidebar)
  const selectedModule = useAppStore((s) => s.selectedModule)
  const location = useLocation()

  const currentLabel = ROUTE_LABELS[location.pathname] || ''
  const isAdminRoute = location.pathname.startsWith('/admin')
  const brand = isAdminRoute
    ? MODULE_BRAND.admin
    : MODULE_BRAND[selectedModule ?? ''] ?? { emoji: '🦺', label: 'EPI' }
  const moduleLabel = isAdminRoute ? null : (MODULE_BRAND[selectedModule ?? '']?.label ?? null)

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
          <span className={logoEmoji}>{brand.emoji}</span>
          <span className={logoText}>{brand.label}</span>
        </NavLink>

        {(moduleLabel || currentLabel) && (
          <div className={breadcrumb}>
            {moduleLabel && selectedModule && (
              <>
                <span className={breadcrumbSep}>/</span>
                <NavLink to={`/${selectedModule}/dashboard`} className={breadcrumbLink}>
                  {moduleLabel}
                </NavLink>
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
        <NotificationBell />
        <ThemeToggle />

        <div className={userInfo}>
          <span className={userName}>{user.name}</span>
          <span
            className={roleBadge}
            style={{
              background: user.role === 'admin' ? vars.color.primaryDark : vars.color.success,
              color: '#fff', // allow: white on colored badge
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
