/**
 * Tela de "Esqueci minha senha" — solicita link de reset por e-mail.
 * Pré-auth, acessível sem login (ADR-0042 Fase 2).
 */
import { useState, FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../services/api'
import { recognitionDarkTheme } from '../theme/tokens/recognition-dark.css'
import * as s from './Login.css'

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sent, setSent] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await api.post('/auth/forgot-password', { email })
      // Backend sempre retorna sucesso (evita enumeração de contas).
      setSent(true)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Erro ao solicitar redefinição')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={`${recognitionDarkTheme} ${s.page}`}>
      <div className={s.container}>
        <div className={s.logoWrap}>
          <div className={s.logoIcon}>◈</div>
          <h1 className={s.logoTitle}>Recognition</h1>
          <p className={s.logoSub}>Recuperação de senha</p>
        </div>
        <div className={s.card}>
          {sent ? (
            <div className={s.formStack}>
              <div className={s.successBox}>
                Se o e-mail existir em nossa base, você receberá um link de
                redefinição em instantes. Confira também a caixa de spam.
              </div>
              <Link to="/" className={s.linkBtn}>Voltar para o login</Link>
            </div>
          ) : (
            <form onSubmit={submit}>
              <div className={s.formStack}>
                <input className={s.input} type="email" placeholder="seu@email.com" required
                  value={email} onChange={e => setEmail(e.target.value)} />
                {error && <div className={s.errorBox}>⚠️ {error}</div>}
                <button type="submit" disabled={loading}
                  className={`${s.submitBtn}${loading ? ` ${s.submitBtnLoading}` : ''}`}>
                  {loading ? 'Aguarde...' : 'Enviar link de redefinição'}
                </button>
                <Link to="/" className={s.linkBtn}>Voltar para o login</Link>
              </div>
            </form>
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
