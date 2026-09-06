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
 *
 * SENHA TEMPORÁRIA (issue #819): desde que o /login passou a COBRAR
 * `force_password_reset` (403 `password_change_required`), esta tela é o
 * único lugar por onde uma pessoa sai desse 403 — e todo caminho que ARMA a
 * flag é de admin (criar tenant, criar usuário pelo painel, resetar senha).
 * Sem o formulário abaixo, quem recebesse a senha no papel ficaria parada
 * aqui para sempre, com uma instrução que só um `curl` cumpre. Por isso a
 * troca acontece na PRÓPRIA tela: o 403 não é um beco, é o primeiro passo.
 */
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle } from 'lucide-react'

import { useAuth } from '../../hooks/useAuth'
import { api, ApiError } from '../../services/api'
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
  // Modo "definir nova senha": ligado SÓ pelo 403 password_change_required.
  const [trocaExigida, setTrocaExigida] = useState(false)
  const [novaSenha, setNovaSenha] = useState('')
  const [confirmacao, setConfirmacao] = useState('')

  const enviar = async (e: FormEvent) => {
    e.preventDefault()
    setErro(null)
    setLoading(true)
    try {
      // Pós-login do fluxo NOVO leva ao front novo (decisão registrada na
      // missão F5 SR2) — o Login antigo continua indo para '/' (default).
      await login(email, senha, rotaNova('/'))
    } catch (err: unknown) {
      // A credencial CONFERE; o que falta é trocar a senha temporária. Trocar
      // a tela em vez de mostrar erro: é a única saída que existe hoje.
      if (err instanceof ApiError && err.code === 'password_change_required') {
        setTrocaExigida(true)
        setLoading(false)
        return
      }
      setErro(err instanceof Error ? err.message : 'Erro ao autenticar')
      setLoading(false)
    }
  }

  const trocarSenha = async (e: FormEvent) => {
    e.preventDefault()
    setErro(null)
    // Conferência aqui e não só no backend: sem ela o erro de digitação vira
    // uma senha que ninguém sabe — e a conta volta a precisar do admin.
    if (novaSenha !== confirmacao) {
      setErro('As duas senhas não são iguais.')
      return
    }
    setLoading(true)
    try {
      await api.post('/auth/change-password', {
        email,
        current_password: senha,
        new_password: novaSenha,
      })
    } catch (err: unknown) {
      setErro(err instanceof Error ? err.message : 'Não foi possível trocar a senha')
      setLoading(false)
      return
    }
    // Daqui para frente a senha temporária NÃO VALE MAIS. Se o login logo
    // depois falhar (rede), insistir neste formulário mandaria a senha velha
    // como "senha atual" e devolveria 401 para sempre — o jeito de sair é
    // voltar ao login com a senha nova, não repetir a troca.
    try {
      // Entra já com a senha nova — a pessoa não digita credencial duas vezes.
      await login(email, novaSenha, rotaNova('/'))
    } catch {
      setTrocaExigida(false)
      setSenha('')
      setErro('Senha alterada. Entre com a sua senha nova.')
      setLoading(false)
    }
  }

  return (
    <div className={s.pagina}>
      <div className={s.coluna}>
        <Marca />
        <div className={s.cartao}>
          <h1 className={s.tituloTela}>{trocaExigida ? 'Definir nova senha' : 'Entrar'}</h1>
          {trocaExigida ? (
            <form onSubmit={trocarSenha}>
              <div className={s.formStack}>
                <p className={s.erroTexto}>
                  A senha que você recebeu é temporária. Escolha uma senha sua
                  para continuar.
                </p>
                <div className={s.campo}>
                  <label htmlFor="entrar-nova-senha" className={s.rotulo}>Nova senha</label>
                  <input
                    id="entrar-nova-senha"
                    className={s.input}
                    type="password"
                    placeholder="mínimo 6 caracteres"
                    required
                    minLength={6}
                    autoComplete="new-password"
                    value={novaSenha}
                    onChange={(e) => setNovaSenha(e.target.value)}
                  />
                </div>
                <div className={s.campo}>
                  <label htmlFor="entrar-confirma-senha" className={s.rotulo}>Repita a nova senha</label>
                  <input
                    id="entrar-confirma-senha"
                    className={s.input}
                    type="password"
                    placeholder="repita a nova senha"
                    required
                    minLength={6}
                    autoComplete="new-password"
                    value={confirmacao}
                    onChange={(e) => setConfirmacao(e.target.value)}
                  />
                </div>
                {erro && (
                  <div className={s.erroBox} role="alert">
                    <AlertTriangle size={14} strokeWidth={2} color={lk.estado.nc} aria-hidden="true" />
                    <span className={s.erroTexto}>{erro}</span>
                  </div>
                )}
                <button type="submit" className={s.botao} disabled={loading}>
                  Salvar e entrar
                </button>
              </div>
            </form>
          ) : (
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
          )}
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
