/**
 * Tela de Login — tema azul, estilo clean.
 * Tela dedicada: logout SEMPRE leva aqui.
 *
 * SEM aba "Criar Conta" (bloco 4 / armadilhas da entrada): o auto-registro
 * criava conta com role='operator' e SEM tenant_id, e o próprio login depois
 * recusava essa conta ("Usuário sem tenant atribuído", ADR-0017) — o usuário
 * ficava travado sem entender por quê. Contas são criadas pelo administrador
 * em /admin/users; a rota POST /api/auth/register está fechada por padrão
 * (ALLOW_PUBLIC_REGISTRATION).
 */
import { useState, FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { recognitionDarkTheme } from '../theme/tokens/recognition-dark.css'
import * as s from './Login.css'

export function Login() {
  const { login } = useAuth()
  const [form, setForm] = useState({ email: '', password: '' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm(f => ({ ...f, [k]: e.target.value }))

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await login(form.email, form.password)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Erro ao autenticar')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={`${recognitionDarkTheme} ${s.page}`}>
      <div className={s.container}>

        {/* Logo */}
        <div className={s.logoWrap}>
          <div className={s.logoIcon}>◈</div>
          <h1 className={s.logoTitle}>Recognition</h1>
          <p className={s.logoSub}>Visão computacional industrial para sua fábrica</p>
        </div>

        {/* Card */}
        <div className={s.card}>
          <form onSubmit={submit}>
            <div className={s.formStack}>
              <input className={s.input} type="email" placeholder="seu@email.com" required
                value={form.email} onChange={set('email')} />
              <input className={s.input} type="password" placeholder="••••••••" required
                value={form.password} onChange={set('password')} />
              <Link to="/forgot-password" className={s.linkBtn}>Esqueci minha senha</Link>
              {error && (
                <div className={s.errorBox}>⚠️ {error}</div>
              )}
              <button
                type="submit"
                disabled={loading}
                className={`${s.submitBtn}${loading ? ` ${s.submitBtnLoading}` : ''}`}
              >
                {loading ? 'Aguarde...' : 'Entrar'}
              </button>
            </div>
          </form>
        </div>

        <p className={s.footer}>
          © 2026 Recognition ·{' '}
          <span className={s.footerBrand}>Logikos</span>
        </p>
      </div>
    </div>
  )
}
