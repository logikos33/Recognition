/**
 * Tela de Login — tema azul, estilo clean.
 * Tela dedicada: logout SEMPRE leva aqui.
 * Tabs: Entrar / Criar Conta
 */
import { useState, FormEvent } from 'react'
import { useAuth } from '../hooks/useAuth'

export function Login() {
  const { login, register } = useAuth()
  const [tab, setTab] = useState<'login' | 'register'>('login')
  const [form, setForm] = useState({ name: '', email: '', password: '', confirm: '' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm(f => ({ ...f, [k]: e.target.value }))

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    if (tab === 'register' && form.password !== form.confirm) {
      setError('As senhas não coincidem')
      return
    }
    setLoading(true)
    try {
      if (tab === 'login') await login(form.email, form.password)
      else await register(form.name, form.email, form.password)
    } catch (err: any) {
      setError(err.message || 'Erro ao autenticar')
    } finally {
      setLoading(false)
    }
  }

  const inp: React.CSSProperties = {
    width: '100%', padding: '12px 14px', borderRadius: 10,
    border: '1.5px solid #dbeafe', background: '#f0f7ff',
    fontSize: 15, color: '#1e3a5f', outline: 'none',
    boxSizing: 'border-box', fontFamily: 'inherit'
  }

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(160deg,#eff6ff,#dbeafe,#bfdbfe)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: "'Inter','Segoe UI',sans-serif", padding: 20
    }}>
      <div style={{ width: '100%', maxWidth: 400 }}>

        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <div style={{
            width: 72, height: 72, borderRadius: 20, margin: '0 auto 14px',
            background: 'linear-gradient(135deg,#2563eb,#1e40af)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 36, boxShadow: '0 8px 24px rgba(37,99,235,0.4)'
          }}>👁️</div>
          <h1 style={{ fontSize: 28, fontWeight: 800, color: '#1e3a5f', margin: 0 }}>
            EPI Monitor
          </h1>
          <p style={{ color: '#64748b', margin: '6px 0 0', fontSize: 14 }}>
            Monitoramento Inteligente de Baias
          </p>
        </div>

        {/* Card */}
        <div style={{
          background: '#fff', borderRadius: 20, padding: '28px 24px',
          boxShadow: '0 8px 40px rgba(37,99,235,0.12)', border: '1px solid #e0eaff'
        }}>
          {/* Tabs */}
          <div style={{
            display: 'flex', background: '#f0f7ff',
            borderRadius: 10, padding: 4, marginBottom: 24, gap: 4
          }}>
            {(['login', 'register'] as const).map(t => (
              <button key={t} onClick={() => { setTab(t); setError(null) }}
                style={{
                  flex: 1, padding: '9px 0', border: 'none', borderRadius: 8,
                  fontSize: 14, fontWeight: 600, cursor: 'pointer',
                  background: tab === t ? '#fff' : 'transparent',
                  color: tab === t ? '#2563eb' : '#94a3b8',
                  boxShadow: tab === t ? '0 2px 8px rgba(37,99,235,0.15)' : 'none'
                }}>
                {t === 'login' ? 'Entrar' : 'Criar Conta'}
              </button>
            ))}
          </div>

          {/* Form */}
          <form onSubmit={submit}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {tab === 'register' && (
                <input style={inp} placeholder="Nome completo" required
                  value={form.name} onChange={set('name')} />
              )}
              <input style={inp} type="email" placeholder="seu@email.com" required
                value={form.email} onChange={set('email')} />
              <input style={inp} type="password" placeholder="••••••••" required
                value={form.password} onChange={set('password')} />
              {tab === 'register' && (
                <input style={inp} type="password" placeholder="Confirmar senha" required
                  value={form.confirm} onChange={set('confirm')} />
              )}
              {error && (
                <div style={{
                  padding: '10px 14px', borderRadius: 8,
                  background: '#fef2f2', border: '1px solid #fecaca',
                  color: '#dc2626', fontSize: 13
                }}>⚠️ {error}</div>
              )}
              <button type="submit" disabled={loading} style={{
                padding: 13, borderRadius: 10, border: 'none',
                background: loading
                  ? '#93c5fd'
                  : 'linear-gradient(135deg,#2563eb,#1d4ed8)',
                color: '#fff', fontSize: 15, fontWeight: 700,
                cursor: loading ? 'not-allowed' : 'pointer',
                boxShadow: '0 4px 14px rgba(37,99,235,0.35)'
              }}>
                {loading ? 'Aguarde...' : tab === 'login' ? 'Entrar' : 'Criar Conta'}
              </button>
            </div>
          </form>

          {tab === 'login' && (
            <div style={{
              marginTop: 16, padding: '10px 12px', borderRadius: 8,
              background: '#f0f7ff', border: '1px dashed #93c5fd'
            }}>
              <p style={{ margin: 0, fontSize: 12, color: '#475569', fontWeight: 600 }}>
                🔑 Acesso padrão:
              </p>
              <p style={{ margin: '2px 0 0', fontSize: 12, color: '#64748b', fontFamily: 'monospace' }}>
                admin@epimonitor.com / EpiMonitor@2024!
              </p>
            </div>
          )}
        </div>

        <p style={{ textAlign: 'center', color: '#94a3b8', fontSize: 12, marginTop: 20 }}>
          © 2024 EPI Monitor ·{' '}
          <span style={{ color: '#2563eb', fontWeight: 600 }}>Logikos</span>
        </p>
      </div>
    </div>
  )
}
