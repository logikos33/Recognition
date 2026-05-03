import { NavLink } from 'react-router-dom'
import type { User } from '../../../hooks/useAuth'
import { vars } from '../../../styles/theme.css'
import { ThemeToggle } from '../../ui/ThemeToggle/ThemeToggle'
import {
  header, left, logoLink, logoText, logoEmoji, nav, navLink, navLinkActive,
  right, userInfo, userName, roleBadge, logoutButton,
} from './Header.css'

const NAV_ITEMS = [
  { to: '/', label: 'Home', end: true },
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/epi/dashboard', label: 'EPI' },
  { to: '/monitoring', label: 'Monitoramento' },
  { to: '/alerts', label: 'Alertas' },
  { to: '/annotation', label: 'Anotação' },
  { to: '/training', label: 'Treinamento' },
]

interface HeaderProps {
  user: User
  onLogout: () => void
}

export function Header({ user, onLogout }: HeaderProps) {
  return (
    <header className={header}>
      <div className={left}>
        <NavLink to="/" className={logoLink}>
          <span className={logoEmoji}>🦺</span>
          <span className={logoText}>EPI Monitor V2</span>
        </NavLink>

        <nav className={nav}>
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => isActive ? navLinkActive : navLink}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </div>

      <div className={right}>
        <ThemeToggle />

        <div className={userInfo}>
          <span className={userName}>{user.name}</span>
          <span
            className={roleBadge}
            style={{
              background: user.role === 'admin' ? vars.color.primaryDark : vars.color.success,
              color: '#fff',
            }}
          >
            {user.role}
          </span>
        </div>

        <button className={logoutButton} onClick={onLogout}>
          Sair
        </button>
      </div>
    </header>
  )
}
