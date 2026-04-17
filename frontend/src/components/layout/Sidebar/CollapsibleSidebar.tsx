import { useEffect, useCallback } from 'react'
import { NavLink, useNavigate, useLocation } from 'react-router-dom'
import {
  X, LayoutDashboard, Camera, AlertTriangle, Brain,
  FileBarChart, ArrowLeftRight, Settings, LogOut, ShieldCheck, FlaskConical,
} from 'lucide-react'
import { useAppStore } from '../../../stores/appStore'
import { useAuth } from '../../../hooks/useAuth'
import {
  overlay, overlayHidden, overlayVisible,
  sidebar, sidebarClosed, sidebarOpen,
  sidebarHeader, sidebarTitle, closeBtn,
  navSection, navItem, navItemActive, navIcon,
  divider, footerSection, versionBar, statusDot,
} from './Sidebar.css'

// Itens de navegação EPI — sempre visíveis para usuários autenticados
const EPI_NAV_BASE = [
  { to: '/epi/dashboard', label: 'Dashboard', icon: LayoutDashboard, module: null },
  { to: '/epi/cameras',   label: 'Cameras',   icon: Camera,          module: null },
  { to: '/epi/alerts',    label: 'Alertas',   icon: AlertTriangle,   module: null },
  { to: '/epi/reports',   label: 'Relatórios', icon: FileBarChart,   module: null },
]

// Apenas se tenant tiver módulo de treinamento habilitado
const TRAINING_NAV = { to: '/epi/training', label: 'Treinamento', icon: Brain, module: 'epi' }

// Item de Qualidade Industrial — visível apenas se tenant tiver módulo 'quality'
const QUALITY_NAV = { to: '/quality/dashboard', label: 'Qualidade', icon: FlaskConical, module: 'quality' }

interface CollapsibleSidebarProps {
  onLogout: () => void
}

export function CollapsibleSidebar({ onLogout }: CollapsibleSidebarProps) {
  const isOpen = useAppStore((s) => s.sidebarOpen)
  const closeSidebar = useAppStore((s) => s.closeSidebar)
  const clearModule = useAppStore((s) => s.clearModule)
  const selectedModule = useAppStore((s) => s.selectedModule)
  const navigate = useNavigate()
  const location = useLocation()

  // Role e módulos do usuário autenticado
  const { isSuperAdmin, hasModule } = useAuth()

  // Montar lista de nav items baseado nos módulos habilitados
  const trainingModules = ['epi', 'quality', 'counting']
  const showTraining = trainingModules.some((m) => hasModule(m))
  const epiNav = showTraining
    ? [...EPI_NAV_BASE.slice(0, 3), TRAINING_NAV, EPI_NAV_BASE[3]]
    : EPI_NAV_BASE

  const handleEscape = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape') closeSidebar()
  }, [closeSidebar])

  useEffect(() => {
    if (isOpen) {
      document.addEventListener('keydown', handleEscape)
      return () => document.removeEventListener('keydown', handleEscape)
    }
  }, [isOpen, handleEscape])

  const handleSwitchModule = () => {
    clearModule()
    closeSidebar()
    navigate('/modules')
  }

  const handleNavClick = () => {
    closeSidebar()
  }

  // Mostrar item de Qualidade na sidebar se o tenant tiver o módulo habilitado
  const showQuality = hasModule('quality')

  const moduleTitle = selectedModule === 'epi' ? 'EPI Monitor'
    : selectedModule === 'fueling' ? 'Carregamento'
    : selectedModule === 'quality' ? 'Qualidade'
    : 'Módulos'

  return (
    <>
      {/* Overlay */}
      <div
        className={`${overlay} ${isOpen ? overlayVisible : overlayHidden}`}
        onClick={closeSidebar}
        aria-hidden="true"
      />

      {/* Sidebar */}
      <nav
        className={`${sidebar} ${isOpen ? sidebarOpen : sidebarClosed}`}
        aria-label="Menu lateral"
      >
        <div className={sidebarHeader}>
          <span className={sidebarTitle}>
            🦺 {moduleTitle}
          </span>
          <button
            className={closeBtn}
            onClick={closeSidebar}
            aria-label="Fechar menu"
          >
            <X size={18} />
          </button>
        </div>

        <div className={navSection}>
          {epiNav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={handleNavClick}
              className={location.pathname === item.to ? navItemActive : navItem}
            >
              <item.icon size={18} className={navIcon} />
              {item.label}
            </NavLink>
          ))}

          {/* Módulo de Qualidade Industrial — exibido apenas se tenant tiver o módulo habilitado */}
          {showQuality && (
            <NavLink
              to={QUALITY_NAV.to}
              onClick={handleNavClick}
              className={location.pathname.startsWith('/quality') ? navItemActive : navItem}
            >
              <QUALITY_NAV.icon size={18} className={navIcon} />
              {QUALITY_NAV.label}
            </NavLink>
          )}
        </div>

        <div className={divider} />

        <div className={footerSection}>
          {/* Link para painel admin — apenas superadmin */}
          {isSuperAdmin && (
            <NavLink
              to="/admin"
              onClick={handleNavClick}
              className={location.pathname.startsWith('/admin') ? navItemActive : navItem}
            >
              <ShieldCheck size={18} className={navIcon} />
              Painel Admin
            </NavLink>
          )}

          <button className={navItem} onClick={handleSwitchModule}>
            <ArrowLeftRight size={18} className={navIcon} />
            Trocar Módulo
          </button>
          <button className={navItem} onClick={() => { closeSidebar(); navigate('/epi/reports') }}>
            <Settings size={18} className={navIcon} />
            Configurações
          </button>
          <button className={navItem} onClick={onLogout}>
            <LogOut size={18} className={navIcon} />
            Sair
          </button>
        </div>

        <div className={versionBar}>
          <span>v2.1.0</span>
          <span>
            Railway <span className={statusDot} />
          </span>
        </div>
      </nav>
    </>
  )
}
