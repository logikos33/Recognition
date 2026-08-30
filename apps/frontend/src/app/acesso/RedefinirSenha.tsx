/**
 * `/novo/redefinir-senha` — define a nova senha a partir do token de e-mail
 * (F5 SR2). Aditiva: convive com `src/pages/ResetPasswordPage.tsx` (intocado).
 *
 * Spec visual: `docs/design/handoff-f5/Acesso Logikos.dc.html` (tela "troca").
 *
 * DIVERGÊNCIA PRANCHA × BACKEND: a prancha pede 3 critérios — "mínimo de 10
 * caracteres", "letras e números" e "diferente da senha temporária" (essa
 * última nem se aplica aqui: é da tela de troca obrigatória por senha
 * temporária, fora do escopo desta SR2). O backend real, em
 * `services/api/app/domain/services/password_reset_service.py:83-84`, só
 * verifica `len(new_password) < 6` — SEM regra de letras+números. A régua
 * abaixo mostra os 2 critérios REAIS (tamanho mínimo real + confirmação
 * igual); inventar "letras e números" seria reprovar uma senha que o backend
 * aceitaria.
 */
import { useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { CheckCircle2 } from 'lucide-react'

import { api } from '../../services/api'
import { rotaNova } from '../RotasNovas'
import { lk } from '../tokens/lk.css'
import { Marca } from './Marca'
import * as s from './Acesso.css'

/** Fonte real: password_reset_service.py:83-84 (`len(new_password) < 6`). */
const SENHA_MINIMA = 6

export function RedefinirSenha() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') || ''
  const [senha, setSenha] = useState('')
  const [confirmar, setConfirmar] = useState('')
  const [loading, setLoading] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [concluido, setConcluido] = useState(false)

  const tamanhoOk = senha.length >= SENHA_MINIMA
  const confirmacaoOk = senha.length > 0 && senha === confirmar
  const formValido = tamanhoOk && confirmacaoOk

  const requisitos = [
    { texto: `Mínimo de ${SENHA_MINIMA} caracteres`, ok: tamanhoOk },
    { texto: 'Senha e confirmação coincidem', ok: confirmacaoOk },
  ]

  const enviar = async (e: FormEvent) => {
    e.preventDefault()
    setErro(null)
    if (!formValido) {
      setErro('Revise os critérios de senha abaixo')
      return
    }
    setLoading(true)
    try {
      await api.post('/auth/reset-password', { token, password: senha })
      setConcluido(true)
    } catch (err: unknown) {
      setErro(err instanceof Error ? err.message : 'Erro ao redefinir senha')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={s.pagina}>
      <div className={s.coluna}>
        <Marca />
        <div className={s.cartao}>
          {!token ? (
            <>
              <h1 className={s.tituloTela}>Link inválido</h1>
              <div className={s.erroBox} role="alert">
                <span className={s.erroTexto}>Link inválido — token ausente.</span>
              </div>
              <Link to={rotaNova('/esqueci-senha')} className={s.linkVoltar}>
                Solicitar novo link
              </Link>
            </>
          ) : concluido ? (
            <div className={s.sucessoWrap}>
              <CheckCircle2 size={30} strokeWidth={2} color={lk.estado.ok} aria-hidden="true" />
              <span className={s.sucessoTitulo}>Senha redefinida com sucesso</span>
              <span className={s.sucessoTexto}>Faça login com a nova senha.</span>
              <Link to={rotaNova('/entrar')} className={s.linkVoltar}>
                Ir para o login
              </Link>
            </div>
          ) : (
            <>
              <h1 className={s.tituloTela}>Defina sua nova senha</h1>
              <form onSubmit={enviar}>
                <div className={s.formStack}>
                  <div className={s.campo}>
                    <label htmlFor="redefinir-senha" className={s.rotulo}>Nova senha</label>
                    <input
                      id="redefinir-senha"
                      className={s.input}
                      type="password"
                      placeholder={`mínimo ${SENHA_MINIMA} caracteres`}
                      required
                      autoComplete="new-password"
                      value={senha}
                      onChange={(e) => setSenha(e.target.value)}
                    />
                  </div>
                  <div className={s.campo}>
                    <label htmlFor="redefinir-confirmar" className={s.rotulo}>Confirmar nova senha</label>
                    <input
                      id="redefinir-confirmar"
                      className={s.input}
                      type="password"
                      required
                      autoComplete="new-password"
                      value={confirmar}
                      onChange={(e) => setConfirmar(e.target.value)}
                    />
                  </div>
                  <div className={s.requisitos}>
                    {requisitos.map((r) => (
                      <span key={r.texto} className={s.requisitoItem} style={{ color: r.ok ? lk.estado.ok : lk.cor.cinzaNevoa }}>
                        <span className={s.requisitoMarcador}>{r.ok ? '✓' : '·'}</span>
                        {r.texto}
                      </span>
                    ))}
                  </div>
                  {erro && (
                    <div className={s.erroBox} role="alert">
                      <span className={s.erroTexto}>{erro}</span>
                    </div>
                  )}
                  <button type="submit" className={s.botao} disabled={loading || !formValido}>
                    {loading ? 'Salvando...' : 'Salvar e entrar'}
                  </button>
                </div>
              </form>
            </>
          )}
        </div>
        <span className={s.rodape}>ACESSO REGISTRADO NA AUDITORIA · SUPORTE@LOGIKOS.COM.BR</span>
      </div>
    </div>
  )
}
