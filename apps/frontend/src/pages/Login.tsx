/**
 * Tela de Login — tema azul, estilo clean.
 * Tela dedicada: logout SEMPRE leva aqui.
 * Tabs: Entrar / Criar Conta
 */
import { useState, FormEvent } from 'react'
import { useAuth } from '../hooks/useAuth'
import * as s from './Login.css'

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
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Erro ao autenticar')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={s.page}>
      <div className={s.container}>

        {/* Logo */}
        <div className={s.logoWrap}>
          <div className={s.logoIcon}>◈</div>
          <h1 className={s.logoTitle}>Recognition</h1>
          <p className={s.logoSub}>Visão computacional industrial para sua fábrica</p>
        </div>

        {/* Card */}
        <div className={s.card}>
          {/* Tabs */}
          <div className={s.tabs}>
            {(['login', 'register'] as const).map(t => (
              <button
                key={t}
                onClick={() => { setTab(t); setError(null) }}
                className={`${s.tabBtn}${tab === t ? ` ${s.tabBtnActive}` : ''}`}
              >
                {t === 'login' ? 'Entrar' : 'Criar Conta'}
              </button>
            ))}
          </div>

          {/* Form */}
          <form onSubmit={submit}>
            <div className={s.formStack}>
              {tab === 'register' && (
                <input className={s.input} placeholder="Nome completo" required
                  value={form.name} onChange={set('name')} />
              )}
              <input className={s.input} type="email" placeholder="seu@email.com" required
                value={form.email} onChange={set('email')} />
              <input className={s.input} type="password" placeholder="••••••••" required
                value={form.password} onChange={set('password')} />
              {tab === 'register' && (
                <input className={s.input} type="password" placeholder="Confirmar senha" required
                  value={form.confirm} onChange={set('confirm')} />
              )}
              {error && (
                <div className={s.errorBox}>⚠️ {error}</div>
              )}
              <button
                type="submit"
                disabled={loading}
                className={`${s.submitBtn}${loading ? ` ${s.submitBtnLoading}` : ''}`}
              >
                {loading ? 'Aguarde...' : tab === 'login' ? 'Entrar' : 'Criar Conta'}
              </button>
            </div>
          </form>

          {tab === 'login' && (
            <div className={s.credHint}>
              <p className={s.credHintLabel}>🔑 Acesso padrão:</p>
              <p className={s.credHintValue}>admin@epimonitor.com / EpiMonitor@2024!</p>
            </div>
          )}
        </div>

        <p className={s.footer}>
          © 2026 Recognition ·{' '}
          <span className={s.footerBrand}>Logikos</span>
        </p>
      </div>
    </div>
  )
}
