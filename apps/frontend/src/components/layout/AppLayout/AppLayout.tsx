import type { ReactNode } from 'react'
import type { User } from '../../../hooks/useAuth'
import { TopBar } from '../TopBar/TopBar'
import { CollapsibleSidebar } from '../Sidebar/CollapsibleSidebar'
import { HealthFooter } from '../HealthFooter/HealthFooter'
import { layout, mainContent } from './AppLayout.css'

interface AppLayoutProps {
  user: User
  onLogout: () => void
  children: ReactNode
}

export function AppLayout({ user, onLogout, children }: AppLayoutProps) {
  return (
    <div className={layout}>
      <TopBar user={user} onLogout={onLogout} />
      <CollapsibleSidebar onLogout={onLogout} />
      <main className={mainContent}>
        {children}
      </main>
      <HealthFooter />
    </div>
  )
}
