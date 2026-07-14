/**
 * Tela de redefinição de senha — lê o token da URL (?token=...) e define
 * a nova senha. Pré-auth, acessível sem login (ADR-0042 Fase 2).
 */
import { useState, FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../services/api'
import { recognitionDarkTheme } from '../theme/tokens/recognition-dark.css'
import * as s from './Login.css'

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') || ''
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    if (password !== confirm) {
      setError('As senhas não coincidem')
      return
    }
    setLoading(true)
    try {
      await api.post('/auth/reset-password', { token, password })
      setDone(true)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Erro ao redefinir senha')
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
          <p className={s.logoSub}>Definir nova senha</p>
        </div>
        <div className={s.card}>
          {!token ? (
            <div className={s.formStack}>
              <div className={s.errorBox}>⚠️ Link inválido — token ausente.</div>
              <Link to="/forgot-password" className={s.linkBtn}>Solicitar novo link</Link>
            </div>
          ) : done ? (
            <div className={s.formStack}>
              <div className={s.successBox}>
                Senha redefinida com sucesso. Faça login com a nova senha.
              </div>
              <Link to="/" className={s.linkBtn}>Ir para o login</Link>
            </div>
          ) : (
            <form onSubmit={submit}>
              <div className={s.formStack}>
                <input className={s.input} type="password" placeholder="Nova senha" required
                  value={password} onChange={e => setPassword(e.target.value)} />
                <input className={s.input} type="password" placeholder="Confirmar nova senha" required
                  value={confirm} onChange={e => setConfirm(e.target.value)} />
                {error && <div className={s.errorBox}>⚠️ {error}</div>}
                <button type="submit" disabled={loading}
                  className={`${s.submitBtn}${loading ? ` ${s.submitBtnLoading}` : ''}`}>
                  {loading ? 'Aguarde...' : 'Redefinir senha'}
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
