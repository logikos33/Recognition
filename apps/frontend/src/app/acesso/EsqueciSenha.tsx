/**
 * `/novo/esqueci-senha` — recuperação de senha do front novo (F5 SR2).
 * Aditiva: convive com `src/pages/ForgotPasswordPage.tsx` (intocado).
 *
 * Spec visual: `docs/design/handoff-f5/Acesso Logikos.dc.html` (tela "esqueci").
 *
 * TTL de 30 minutos CONFIRMADO no backend (não é só a prancha): o token vive
 * em Redis com `_TOKEN_TTL_SECONDS = 1800` — 30 min — em
 * `services/api/app/domain/services/password_reset_service.py:33`, e o
 * e-mail de reset repete o mesmo prazo (linhas 74 e 119 do mesmo arquivo).
 */
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { CheckCircle2 } from 'lucide-react'

import { api } from '../../services/api'
import { rotaNova } from '../RotasNovas'
import { lk } from '../tokens/lk.css'
import { Marca } from './Marca'
import * as s from './Acesso.css'

export function EsqueciSenha() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [enviado, setEnviado] = useState(false)

  const enviar = async (e: FormEvent) => {
    e.preventDefault()
    setErro(null)
    setLoading(true)
    try {
      await api.post('/auth/forgot-password', { email })
      // Backend sempre retorna sucesso (evita enumeração de contas) — o
      // mesmo comportamento do ForgotPasswordPage antigo.
      setEnviado(true)
    } catch (err: unknown) {
      setErro(err instanceof Error ? err.message : 'Erro ao solicitar redefinição')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={s.pagina}>
      <div className={s.coluna}>
        <Marca />
        <div className={s.cartao}>
          <h1 className={s.tituloTela}>Recuperar acesso</h1>

          {enviado ? (
            <div className={s.sucessoWrap}>
              <CheckCircle2 size={30} strokeWidth={2} color={lk.estado.ok} aria-hidden="true" />
              <span className={s.sucessoTitulo}>Verifique seu e-mail</span>
              <span className={s.sucessoTexto}>
                Se o endereço existir, o link chega em instantes. Vale por 30 minutos.
              </span>
              <Link to={rotaNova('/entrar')} className={s.linkVoltar}>
                ← Voltar ao login
              </Link>
            </div>
          ) : (
            <form onSubmit={enviar}>
              <div className={s.formStack}>
                <span className={s.textoApoio}>
                  Informe seu e-mail. Se ele existir na plataforma, enviamos um link de
                  redefinição válido por 30 minutos.
                </span>
                <div className={s.campo}>
                  <label htmlFor="esqueci-email" className={s.rotulo}>E-mail</label>
                  <input
                    id="esqueci-email"
                    className={s.input}
                    type="email"
                    placeholder="voce@empresa.com.br"
                    required
                    autoComplete="username"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </div>
                {erro && (
                  <div className={s.erroBox} role="alert">
                    <span className={s.erroTexto}>{erro}</span>
                  </div>
                )}
                <button type="submit" className={s.botao} disabled={loading}>
                  {loading ? 'Enviando...' : 'Enviar link'}
                </button>
                <Link to={rotaNova('/entrar')} className={s.linkVoltar}>
                  ← Voltar ao login
                </Link>
              </div>
            </form>
          )}
        </div>
        <span className={s.rodape}>ACESSO REGISTRADO NA AUDITORIA · SUPORTE@LOGIKOS.COM.BR</span>
      </div>
    </div>
  )
}
