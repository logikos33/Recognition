/**
 * App.tsx — apenas routing e auth gate.
 * LIÇÃO V1: App.tsx não deve ter lógica de negócio.
 * Toda lógica vai para hooks e componentes dedicados.
 */
import { useAuth } from './hooks/useAuth'
import { Login } from './pages/Login'
import type { User } from './hooks/useAuth'

function MainApp({ user, onLogout }: { user: User; onLogout: () => void }) {
  return (
    <div style={{ minHeight: '100vh', background: '#0f172a', color: 'white', fontFamily: 'Inter, sans-serif' }}>
      <header style={{
        background: '#1e293b', borderBottom: '1px solid #334155',
        padding: '12px 24px', display: 'flex',
        alignItems: 'center', justifyContent: 'space-between'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 22 }}>👁️</span>
          <span style={{ fontWeight: 700, fontSize: 18 }}>EPI Monitor V2</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ color: '#94a3b8', fontSize: 14 }}>{user.name}</span>
          <span style={{
            padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 700,
            background: user.role === 'admin' ? '#1d4ed8' : '#059669', color: 'white'
          }}>{user.role.toUpperCase()}</span>
          <button onClick={onLogout} style={{
            padding: '6px 12px', borderRadius: 6, background: 'transparent',
            border: '1px solid #475569', color: '#94a3b8', cursor: 'pointer', fontSize: 13
          }}>Sair</button>
        </div>
      </header>
      <main style={{ padding: 32 }}>
        <h2 style={{ color: '#22c55e', marginBottom: 8 }}>✅ Sistema Online</h2>
        <p style={{ color: '#94a3b8' }}>
          EPI Monitor V2 rodando com arquitetura de microserviços.
        </p>
        <p style={{ color: '#64748b', fontSize: 13, marginTop: 16 }}>
          Implementar páginas: Câmeras → Monitoramento → Treinamento → Regras → Validações → Dashboard
        </p>
      </main>
    </div>
  )
}

export default function App() {
  const { user, isAuthenticated, logout } = useAuth()

  if (!isAuthenticated || !user) {
    return <Login />
  }

  return <MainApp user={user} onLogout={logout} />
}
