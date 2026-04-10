import { useEffect, useCallback } from 'react'
import { NavLink, useNavigate, useLocation } from 'react-router-dom'
import {
  X, LayoutDashboard, Camera, AlertTriangle, Brain,
  FileBarChart, ArrowLeftRight, Settings, LogOut,
} from 'lucide-react'
import { useAppStore } from '../../../stores/appStore'
import {
  overlay, overlayHidden, overlayVisible,
  sidebar, sidebarClosed, sidebarOpen,
  sidebarHeader, sidebarTitle, closeBtn,
  navSection, navItem, navItemActive, navIcon,
  divider, footerSection, versionBar, statusDot,
} from './Sidebar.css'

const EPI_NAV = [
  { to: '/epi/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/epi/monitoring', label: 'Monitoramento', icon: Camera },
  { to: '/epi/alerts', label: 'Alertas', icon: AlertTriangle },
  { to: '/epi/training', label: 'Treinamento', icon: Brain },
  { to: '/epi/reports', label: 'Relatorios', icon: FileBarChart },
]

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

  const moduleTitle = selectedModule === 'epi' ? 'EPI Monitor' : selectedModule === 'fueling' ? 'Carregamento' : 'Módulos'

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
          {EPI_NAV.map((item) => (
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
        </div>

        <div className={divider} />

        <div className={footerSection}>
          <button className={navItem} onClick={handleSwitchModule}>
            <ArrowLeftRight size={18} className={navIcon} />
            Trocar Módulo
          </button>
          <button className={navItem} onClick={() => { closeSidebar(); navigate('/settings') }}>
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
