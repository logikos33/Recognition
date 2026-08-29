/**
 * Em qual cliente eu estou — e como trocar, sem sair do front novo.
 *
 * POR QUE ISTO EXISTE
 *
 * Um superadmin nasce no tenant DELE. No DEV isso é `dev`, que tem 0 alertas;
 * os 423 do RVB estão a um "assumir contexto" de distância. O resultado é a
 * tela de Eventos abrindo vazia e parecendo quebrada — foi o relato de
 * "alertas da RVB vazios".
 *
 * O que existia não cobria:
 *
 *  · `useAutoAssumeTenantContext` desiste quando há mais de um tenant
 *    (`tenants.length !== 1`) — e o DEV tem três. Correto: a plataforma não
 *    deve adivinhar em qual cliente entrar. Mas então alguém precisa perguntar.
 *  · esse hook mora dentro de `CrossTenantCameraBanner`, componente do front
 *    ANTIGO, que o shell novo não monta.
 *  · o `TenantContextBanner` global só aparece DEPOIS de já se ter um contexto
 *    — ele mostra a saída, nunca a entrada.
 *
 * Então o front novo não tinha entrada nenhuma: dava para ver que não havia
 * dado, e não dava para fazer nada a respeito.
 *
 * Só aparece para superadmin, e só quando NÃO há contexto assumido — com
 * contexto, quem manda é o banner global, e dois controles dizendo a mesma
 * coisa seria pior que nenhum.
 */
import { useCallback, useEffect, useState } from 'react'
import { Building2, ChevronDown } from 'lucide-react'

import { useAuth } from '../../hooks/useAuth'
import {
  assumeTenantContext,
  isInTenantContext,
  listAvailableTenants,
  type AvailableTenant,
} from '../../services/tenantContext'
import * as s from './SeletorTenant.css'

export function SeletorTenant() {
  const { isSuperAdmin } = useAuth()
  const [tenants, setTenants] = useState<AvailableTenant[]>([])
  const [aberto, setAberto] = useState(false)
  const [entrando, setEntrando] = useState<string | null>(null)
  const [erro, setErro] = useState<string | null>(null)

  const emContexto = isInTenantContext()
  const mostrar = isSuperAdmin && !emContexto

  useEffect(() => {
    if (!mostrar) return
    let vivo = true
    listAvailableTenants()
      .then((lista) => vivo && setTenants(lista))
      // Falhar aqui não pode derrubar a topbar: sem lista, o controle não
      // aparece e o caminho antigo (tela de admin) continua de pé.
      .catch(() => vivo && setTenants([]))
    return () => {
      vivo = false
    }
  }, [mostrar])

  const entrar = useCallback(async (t: AvailableTenant) => {
    setEntrando(t.id)
    setErro(null)
    try {
      // `assumeTenantContext` recarrega a página no sucesso — é ela quem troca
      // o token. Não duplicar isso aqui: dois donos do token foi o que já
      // custou caro no congelamento do live view.
      // Volta para a MESMA tela: quem escolheu o cliente estava tentando ver
      // algo aqui, e o padrão do serviço (`/`) devolve no front antigo.
      await assumeTenantContext(t.id, window.location.pathname + window.location.search)
    } catch (e) {
      setEntrando(null)
      setErro(e instanceof Error ? e.message : 'Não foi possível entrar neste cliente')
    }
  }, [])

  if (!mostrar || tenants.length === 0) return null

  return (
    <div className={s.raiz}>
      <button
        className={s.gatilho}
        onClick={() => setAberto((v) => !v)}
        aria-expanded={aberto}
        aria-haspopup="menu"
      >
        <Building2 size={16} strokeWidth={1.7} />
        <span>Escolher cliente</span>
        <ChevronDown size={15} strokeWidth={1.7} />
      </button>

      {aberto && (
        <div className={s.menu} role="menu">
          <p className={s.titulo}>Você está fora de qualquer cliente</p>
          <p className={s.explicacao}>
            Sem escolher um, as telas mostram os dados do seu próprio tenant — que
            costuma estar vazio.
          </p>
          {tenants.map((t) => (
            <button
              key={t.id}
              className={s.item}
              role="menuitem"
              onClick={() => void entrar(t)}
              disabled={entrando !== null}
            >
              <span className={s.nome}>{t.name}</span>
              <span className={s.slug}>{t.slug}</span>
            </button>
          ))}
          {erro && <p className={s.erro}>{erro}</p>}
        </div>
      )}
    </div>
  )
}
