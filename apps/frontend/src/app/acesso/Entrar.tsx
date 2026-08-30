/**
 * `/novo/entrar` — login do front novo (F5 SR2). Aditiva: convive com o Login
 * antigo (`src/pages/Login.tsx`), que segue intocado e continua sendo o
 * catch-all deslogado.
 *
 * Spec visual: `docs/design/handoff-f5/Acesso Logikos.dc.html` (tela "login").
 *
 * DIVERGÊNCIA PRANCHA × BACKEND: o desenho mostra "E-mail ou senha
 * incorretos. 3 tentativas restantes." — o backend NÃO devolve contagem de
 * tentativas (só a mensagem da exceção, ex. "Credenciais inválidas" em
 * `services/api/app/domain/services/auth_service.py:71,74`, ou o 429 de
 * `login_account_limiter` em `routes.py:120-124`). Mostramos a mensagem REAL
 * do backend — inventar "N tentativas restantes" seria mentir um dado que
 * não existe.
 */
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle } from 'lucide-react'

import { useAuth } from '../../hooks/useAuth'
import { LogikosLoader } from '../shell/LogikosLoader'
import { rotaNova } from '../RotasNovas'
import { lk } from '../tokens/lk.css'
import { Marca } from './Marca'
import * as s from './Acesso.css'

export function Entrar() {
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [senha, setSenha] = useState('')
  const [loading, setLoading] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  const enviar = async (e: FormEvent) => {
    e.preventDefault()
    setErro(null)
    setLoading(true)
    try {
      // Pós-login do fluxo NOVO leva ao front novo (decisão registrada na
      // missão F5 SR2) — o Login antigo continua indo para '/' (default).
      await login(email, senha, rotaNova('/'))
    } catch (err: unknown) {
      setErro(err instanceof Error ? err.message : 'Erro ao autenticar')
      setLoading(false)
    }
  }

  return (
    <div className={s.pagina}>
      <div className={s.coluna}>
        <Marca />
        <div className={s.cartao}>
          <h1 className={s.tituloTela}>Entrar</h1>
          <form onSubmit={enviar}>
            <div className={s.formStack}>
              <div className={s.campo}>
                <label htmlFor="entrar-email" className={s.rotulo}>E-mail</label>
                <input
                  id="entrar-email"
                  className={s.input}
                  type="email"
                  placeholder="voce@empresa.com.br"
                  required
                  autoComplete="username"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              <div className={s.campo}>
                <div className={s.linhaRotulo}>
                  <label htmlFor="entrar-senha" className={s.rotulo}>Senha</label>
                  <Link to={rotaNova('/esqueci-senha')} className={s.linkCanto}>
                    Esqueci minha senha
                  </Link>
                </div>
                <input
                  id="entrar-senha"
                  className={s.input}
                  type="password"
                  placeholder="••••••••"
                  required
                  autoComplete="current-password"
                  value={senha}
                  onChange={(e) => setSenha(e.target.value)}
                />
              </div>
              {erro && (
                <div className={s.erroBox} role="alert">
                  <AlertTriangle size={14} strokeWidth={2} color={lk.estado.nc} aria-hidden="true" />
                  <span className={s.erroTexto}>{erro}</span>
                </div>
              )}
              <button type="submit" className={s.botao} disabled={loading}>
                Entrar
              </button>
            </div>
          </form>
        </div>
        <span className={s.rodape}>ACESSO REGISTRADO NA AUDITORIA · SUPORTE@LOGIKOS.COM.BR</span>
      </div>

      {loading && (
        <div className={s.overlayCarregando}>
          <LogikosLoader estado="waiting" variante="fullscreen" rotulo="ABRINDO LOGIKOS VISION" />
        </div>
      )}
    </div>
  )
}
