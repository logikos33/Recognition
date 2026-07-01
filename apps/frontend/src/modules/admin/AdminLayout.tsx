import { lazy, Suspense, useEffect, useRef, useState, type ReactNode } from 'react'
import { Navigate, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import {
  Bell,
  BookOpen,
  Brain,
  Building2,
  Camera,
  ChevronLeft,
  Clock,
  CreditCard,
  FileText,
  Flag,
  HeartPulse,
  History,
  LayoutGrid,
  Megaphone,
  Menu,
  Monitor,
  Palette,
  Server,
  Settings,
  Ticket,
  Users,
  Video,
  X,
} from 'lucide-react'
import { useAuth } from '../../hooks/useAuth'
import { adminService } from './services/adminService'
import * as s from './AdminLayout.css'

// ── Lazy pages ───────────────────────────────────────────────────────────────
const AdminBrandingTenantsPage  = lazy(() => import('./pages/AdminBrandingTenantsPage').then(m => ({ default: m.AdminBrandingTenantsPage })))
const AdminBrandingEditorPage   = lazy(() => import('./pages/AdminBrandingEditorPage').then(m => ({ default: m.AdminBrandingEditorPage })))
const AdminBrandingDefaultPage  = lazy(() => import('./pages/AdminBrandingDefaultPage').then(m => ({ default: m.AdminBrandingDefaultPage })))
const AdminBrandingSandboxPage  = lazy(() => import('./pages/AdminBrandingSandboxPage').then(m => ({ default: m.AdminBrandingSandboxPage })))
const AdminDashboard           = lazy(() => import('./pages/AdminDashboard').then(m => ({ default: m.AdminDashboard })))
const AdminTenantsPage         = lazy(() => import('./pages/AdminTenantsPage').then(m => ({ default: m.AdminTenantsPage })))
const AdminTenantDetailPage    = lazy(() => import('./pages/AdminTenantDetailPage').then(m => ({ default: m.AdminTenantDetailPage })))
const AdminUsersPage           = lazy(() => import('./pages/AdminUsersPage').then(m => ({ default: m.AdminUsersPage })))
const AdminTrainingApprovalsPage = lazy(() => import('./pages/AdminTrainingApprovalsPage').then(m => ({ default: m.AdminTrainingApprovalsPage })))
const AdminWorkersPage         = lazy(() => import('./pages/AdminWorkersPage').then(m => ({ default: m.AdminWorkersPage })))
const AdminPlansPage           = lazy(() => import('./pages/AdminPlansPage').then(m => ({ default: m.AdminPlansPage })))
const AdminRetentionPage       = lazy(() => import('./pages/AdminRetentionPage').then(m => ({ default: m.AdminRetentionPage })))
const AdminFeatureFlagsPage    = lazy(() => import('./pages/AdminFeatureFlagsPage').then(m => ({ default: m.AdminFeatureFlagsPage })))
const AdminTicketsPage         = lazy(() => import('./pages/AdminTicketsPage').then(m => ({ default: m.AdminTicketsPage })))
const AdminAuditLogPage        = lazy(() => import('./pages/AdminAuditLogPage').then(m => ({ default: m.AdminAuditLogPage })))
const AdminAnnouncementsPage   = lazy(() => import('./pages/AdminAnnouncementsPage').then(m => ({ default: m.AdminAnnouncementsPage })))
const AdminHealthPage          = lazy(() => import('./pages/AdminHealthPage').then(m => ({ default: m.AdminHealthPage })))
const AdminSettingsPage        = lazy(() => import('./pages/AdminSettingsPage').then(m => ({ default: m.AdminSettingsPage })))
const AdminVersionsPage        = lazy(() => import('./pages/AdminVersionsPage').then(m => ({ default: m.AdminVersionsPage })))
const AdminChangelogPage       = lazy(() => import('./pages/AdminChangelogPage').then(m => ({ default: m.AdminChangelogPage })))
const DemoVideosPage           = lazy(() => import('./pages/DemoVideosPage').then(m => ({ default: m.DemoVideosPage })))

// ── Nav item ─────────────────────────────────────────────────────────────────
interface NavItemProps {
  to: string
  icon: ReactNode
  label: string
  badge?: number
  end?: boolean
  onClick?: () => void
}

function NavItem({ to, icon, label, badge, end: endProp, onClick }: NavItemProps) {
  return (
    <NavLink
      to={to}
      end={endProp ?? to === '/admin'}
      className={({ isActive }) => isActive ? s.navItemActive : s.navItem}
      onClick={onClick}
    >
      {icon}
      <span style={{ flex: 1 }}>{label}</span>
      {badge !== undefined && badge > 0 && (
        <span className={s.navBadge}>{badge > 99 ? '99+' : badge}</span>
      )}
    </NavLink>
  )
}

// ── Layout ───────────────────────────────────────────────────────────────────
export function AdminLayout() {
  const { isSuperAdmin } = useAuth()
  const location = useLocation()
  const [pendingApprovals, setPendingApprovals] = useState(0)
  const [openTickets, setOpenTickets] = useState(0)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const sidebarRef = useRef<HTMLElement>(null)

  if (!isSuperAdmin) return <Navigate to="/" replace />

  // Load badge counts once on mount and on route change
  useEffect(() => {
    adminService.getDashboard()
      .then((r) => {
        setPendingApprovals(r.training_approvals_pending)
        setOpenTickets(r.tickets_open)
      })
      .catch(() => {})
  }, [location.pathname])

  // Close sidebar on route change (mobile)
  useEffect(() => {
    setSidebarOpen(false)
  }, [location.pathname])

  // Close sidebar on outside click (mobile)
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (sidebarOpen && sidebarRef.current && !sidebarRef.current.contains(e.target as Node)) {
        setSidebarOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [sidebarOpen])

  const closeSidebar = () => setSidebarOpen(false)

  return (
    <div className={s.adminRoot}>
      {/* ── Mobile topbar ── */}
      <div className={s.mobileTopbar}>
        <button
          className={s.hamburgerBtn}
          onClick={() => setSidebarOpen(true)}
          aria-label="Abrir menu"
        >
          <Menu size={18} />
        </button>
        <span className={s.mobileTopbarTitle}>Painel Admin</span>
      </div>

      {/* ── Mobile overlay ── */}
      {sidebarOpen && (
        <div
          className={s.sidebarOverlay}
          onClick={closeSidebar}
          aria-hidden="true"
        />
      )}

      {/* ── Sidebar ── */}
      <aside
        ref={sidebarRef}
        className={`${s.sidebar}${sidebarOpen ? ` ${s.sidebarOpenClass}` : ''}`}
      >
        <div className={s.sidebarHeader}>
          <div className={s.sidebarHeaderText}>
            <div className={s.sidebarTitle}>Painel Admin</div>
            <div className={s.sidebarSubtitle}>Logikos · Recognition</div>
          </div>
          <button
            className={s.sidebarCloseBtn}
            onClick={closeSidebar}
            aria-label="Fechar menu"
          >
            <X size={16} />
          </button>
        </div>

        <nav className={s.sidebarNav}>

          {/* ── Visão Geral ── */}
          <div className={s.sidebarGroup}>
            <div className={s.sidebarGroupLabel}>Visão Geral</div>
            <NavItem to="/admin" icon={<LayoutGrid size={15} />} label="Dashboard" />
          </div>

          {/* ── Operação ── */}
          <div className={s.sidebarGroup}>
            <div className={s.sidebarGroupLabel}>Operação</div>
            <NavItem to="/epi/dashboard" end icon={<Monitor size={15} />}   label="Monitoramento" onClick={closeSidebar} />
            <NavItem to="/epi/cameras"   end icon={<Camera size={15} />}    label="Câmeras"       onClick={closeSidebar} />
            <NavItem to="/epi/alerts"    end icon={<Bell size={15} />}      label="Alertas"       onClick={closeSidebar} />
          </div>

          {/* ── Modelos & Treino ── */}
          <div className={s.sidebarGroup}>
            <div className={s.sidebarGroupLabel}>Modelos &amp; Treino</div>
            <NavItem
              to="/admin/training-approvals"
              icon={<Brain size={15} />}
              label="Aprovações"
              badge={pendingApprovals}
            />
            <NavItem to="/admin/versions"  icon={<BookOpen size={15} />} label="Registry" />
            <NavItem to="/admin/changelog" icon={<History size={15} />}  label="Changelog" />
          </div>

          {/* ── Relatórios ── */}
          <div className={s.sidebarGroup}>
            <div className={s.sidebarGroupLabel}>Relatórios</div>
            <NavItem to="/admin/audit-log"    icon={<FileText size={15} />}    label="Compliance" />
            <NavItem to="/admin/announcements" icon={<Megaphone size={15} />}  label="Comunicados" />
          </div>

          {/* ── Administração ── */}
          <div className={s.sidebarGroup}>
            <div className={s.sidebarGroupLabel}>Administração</div>
            <NavItem to="/admin/tenants"      icon={<Building2 size={15} />}   label="Tenants" />
            <NavItem to="/admin/users"        icon={<Users size={15} />}       label="Usuários" />
            <NavItem to="/admin/feature-flags" icon={<Flag size={15} />}       label="Permissões" />
            <NavItem to="/admin/plans"        icon={<CreditCard size={15} />}  label="Planos" />
            <NavItem to="/admin/retention"    icon={<Clock size={15} />}       label="Retenção" />
            <NavItem to="/admin/settings"     icon={<Settings size={15} />}    label="Integrações" />
            <NavItem to="/admin/branding/tenants" icon={<Palette size={15} />} label="White-label" />
            <NavItem to="/admin/demo-videos"  icon={<Video size={15} />}       label="Vídeos Demo" />
          </div>

          {/* ── Saúde ── */}
          <div className={s.sidebarGroup}>
            <div className={s.sidebarGroupLabel}>Saúde</div>
            <NavItem to="/admin/workers" icon={<Server size={15} />}     label="Workers" />
            <NavItem
              to="/admin/tickets"
              icon={<Ticket size={15} />}
              label="Tickets"
              badge={openTickets}
            />
            <NavItem to="/admin/health"  icon={<HeartPulse size={15} />} label="Health" />
          </div>

        </nav>

        <div className={s.sidebarFooter}>
          <NavLink to="/" className={s.backButton}>
            <ChevronLeft size={14} /> Voltar ao sistema
          </NavLink>
        </div>
      </aside>

      {/* ── Main ── */}
      <main className={s.mainContent}>
        <Suspense fallback={<div style={{ padding: 32 }}>Carregando...</div>}>
          <Routes>
            <Route index                        element={<AdminDashboard />} />
            <Route path="tenants"               element={<AdminTenantsPage />} />
            <Route path="tenants/:id"           element={<AdminTenantDetailPage />} />
            <Route path="users"                 element={<AdminUsersPage />} />
            <Route path="training-approvals"    element={<AdminTrainingApprovalsPage />} />
            <Route path="workers"               element={<AdminWorkersPage />} />
            <Route path="plans"                 element={<AdminPlansPage />} />
            <Route path="retention"             element={<AdminRetentionPage />} />
            <Route path="feature-flags"         element={<AdminFeatureFlagsPage />} />
            <Route path="tickets"               element={<AdminTicketsPage />} />
            <Route path="audit-log"             element={<AdminAuditLogPage />} />
            <Route path="announcements"         element={<AdminAnnouncementsPage />} />
            <Route path="health"                element={<AdminHealthPage />} />
            <Route path="settings"              element={<AdminSettingsPage />} />
            <Route path="versions"              element={<AdminVersionsPage />} />
            <Route path="changelog"             element={<AdminChangelogPage />} />
            <Route path="branding/tenants"      element={<AdminBrandingTenantsPage />} />
            <Route path="branding/tenants/:id"  element={<AdminBrandingEditorPage />} />
            <Route path="branding/default"      element={<AdminBrandingDefaultPage />} />
            <Route path="branding/sandbox"      element={<AdminBrandingSandboxPage />} />
            <Route path="demo-videos"           element={<DemoVideosPage />} />
            <Route path="*"                     element={<Navigate to="/admin" replace />} />
          </Routes>
        </Suspense>
      </main>
    </div>
  )
}
