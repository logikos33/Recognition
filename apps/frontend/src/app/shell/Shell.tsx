/**
 * Shell Logikos Vision — F1 da migração.
 *
 * TopBar (56) · sidebar (236/64) · ⌘K · loader · aviso de sessão. Medidas do
 * README do handoff, todas por token.
 *
 * ⚠️ COEXISTE com o `AppLayout` atual, de propósito (decisão do Vitor, 27/08):
 * as rotas novas montam este shell, as antigas seguem no antigo, e nada é
 * removido até a migração inteira estar feita. Quem controla o que pode sair
 * depois é o `docs/migration/MANIFESTO-FRONT-ANTIGO.md`.
 *
 * O que este shell NÃO faz, de propósito:
 *
 * · **Banner de contexto assumido.** Já existe, montado em `App.tsx` FORA das
 *   rotas (`GlobalBanners`), com TTL de 30min, renovação proativa, expiração e
 *   "Reassumir" — três arquivos de teste. Reconstruí-lo aqui renderizaria DOIS
 *   banners e criaria uma segunda fonte de verdade sobre quem estou vendo. A
 *   topbar só desce o que ele ocupa, via `--global-banner-offset`.
 *   O visual novo (42px + faixa âmbar de 2px) entra quando o front antigo sair
 *   — restilizá-lo agora mudaria o front antigo junto, que tem de seguir de pé.
 *
 * · **Expiração da sessão.** `getSessionTokenExpMs()` lê o claim `exp` do JWT
 *   corrente. Decodificar token aqui de novo divergiria no primeiro refresh.
 */
import { Suspense, useCallback, useEffect, useLayoutEffect, useMemo, useState } from 'react'
import { Menu, Search } from 'lucide-react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '../../hooks/useAuth'
import { getSessionTokenExpMs } from '../../services/tenantContext'
import { LogikosLoader } from './LogikosLoader'
import { PaletaComandos, type GrupoPaleta } from './PaletaComandos'
import { SeletorTenant } from './SeletorTenant'
import { SessaoExpirando } from './SessaoExpirando'
import { PREFIXO_NOVO, rotaHomeDoUsuario } from '../RotasNovas'
import { useMarcaDoTenant } from '../tokens/MarcaDoTenant'
import { NAV_ADMIN, NAV_EPI, NAV_ESTUDIO, navVisivel } from './navPorPerfil'
import * as s from './Shell.css'

/**
 * Marca: monograma + wordmark, link para a home do usuário (F5-LEVE item 1).
 * Geometria do monograma é canônica — nunca distorcer.
 */
function Marca({ para }: { para: string }) {
  return (
    <Link to={para} className={s.marca}>
      <svg width="22" height="22" viewBox="0 0 100 100" aria-hidden="true">
        <path d="M40 55.3 A20 20 0 1 1 60 55.3 L67 88 L33 88 Z" fill="currentColor" />
      </svg>
      <span>LOGIKOS</span>
    </Link>
  )
}

export interface ShellProps {
  /** Cobre o conteúdo com o loader — usado enquanto a sessão carrega. */
  carregando?: boolean
}

/**
 * Módulos que trazem a PRÓPRIA navegação e por isso não recebem a barra lateral.
 *
 * Não é economia de espaço: os desenhos de Qualidade e Carga importam só o
 * `EPI Topbar`, nunca o `EPI Sidebar` — a navegação deles é a barra de abas
 * dentro da tela. Impor o menu do EPI ali mostra "Eventos" e "Verificação" para
 * quem está inspecionando peça, e some com a navegação que a tela realmente tem.
 */
export const SEM_BARRA_LATERAL = [
  `${PREFIXO_NOVO}/quality`,
  `${PREFIXO_NOVO}/carga`,
  `${PREFIXO_NOVO}/estudio`,
  `${PREFIXO_NOVO}/admin`,
]

export function Shell({ carregando }: ShellProps) {
  const { can, isSuperAdmin } = useAuth()
  const { pathname } = useLocation()
  const comBarraLateral = !SEM_BARRA_LATERAL.some((r) => pathname.startsWith(r))
  // Publica --lk-marca clampada; os tokens leem dela. Ver DECISÃO v2 item 3.
  useMarcaDoTenant()
  // F5-LEVE (identidade, rodada 2): estende o remap de `Shell.css.ts` até o
  // que Radix portaliza pra `document.body` (Modal, Popover, Tooltip) e até
  // o `ToastProvider` (irmão de `<App/>`, fora de `.raiz`) — nenhum dos dois
  // é descendente da raiz do shell, então só um marcador no documentElement
  // alcança os dois (ver comentário em `Shell.css.ts` e em `AppShell.tsx`,
  // mesma técnica pro tema legado). `useLayoutEffect`: aplica antes do
  // primeiro paint, sem flash de roxo caso algo portalize de cara.
  useLayoutEffect(() => {
    const el = document.documentElement
    el.setAttribute('data-lk-shell', '1')
    return () => el.removeAttribute('data-lk-shell')
  }, [])
  const navegar = useNavigate()
  const [colapsada, setColapsada] = useState(false)
  const [paletaAberta, setPaletaAberta] = useState(false)

  const grupos = useMemo(() => navVisivel([...NAV_EPI, ...NAV_ESTUDIO, ...NAV_ADMIN], can), [can])

  /**
   * `navPorPerfil` guarda o endereço FINAL de cada tela (`/epi/eventos`), que é
   * o do desenho. Enquanto os dois fronts convivem, o front novo mora sob o
   * prefixo — então o prefixo entra aqui, na hora de navegar, e não na tabela.
   * Assim o tombamento é apagar `PREFIXO_NOVO` daqui, e a tabela já está certa.
   *
   * Sem isto o menu do front NOVO levaria para as telas do front ANTIGO, em
   * silêncio: `/epi/dashboard` é rota válida nos dois.
   */

  /**
   * Telas na paleta = as MESMAS que a navegação mostra. Derivar das duas
   * fontes separadamente faria a paleta oferecer atalho para tela que o perfil
   * não pode abrir — o ⌘K viraria um caminho lateral em volta da permissão.
   */
  const gruposPaleta = useMemo<GrupoPaleta[]>(
    () => [
      {
        id: 'telas',
        titulo: 'Telas',
        itens: grupos.flatMap((g) =>
          g.itens.map((i) => ({
            id: i.rota,
            rotulo: i.rotulo,
            detalhe: g.titulo,
            aoEscolher: () => navegar(PREFIXO_NOVO + i.rota),
          })),
        ),
      },
    ],
    [grupos, navegar],
  )

  // Quando a sessão morre. null = token ilegível; sem prazo não há o que avisar.
  const [expiraEm, setExpiraEm] = useState<number | null>(() => getSessionTokenExpMs())
  useEffect(() => {
    // O token troca sem desmontar o shell (renovação de contexto, refresh).
    // Relê de minuto em minuto para o aviso seguir o token vigente.
    const id = setInterval(() => setExpiraEm(getSessionTokenExpMs()), 60_000)
    return () => clearInterval(id)
  }, [])

  const aoRenovar = useCallback(() => window.location.reload(), [])
  const aoSair = useCallback(() => navegar('/login'), [navegar])

  return (
    <div className={s.raiz}>
      <header className={s.topbar}>
        {comBarraLateral && (
          <button
            className={s.botaoIcone}
            onClick={() => setColapsada((v) => !v)}
            aria-label={colapsada ? 'Expandir menu' : 'Recolher menu'}
            aria-expanded={!colapsada}
          >
            <Menu size={18} strokeWidth={1.7} />
          </button>
        )}
        <Marca para={rotaHomeDoUsuario(isSuperAdmin)} />
        <span className={s.espacador} />
        <SeletorTenant />
        <button
          className={s.botaoIcone}
          onClick={() => setPaletaAberta(true)}
          aria-label="Buscar (Command K)"
        >
          <Search size={18} strokeWidth={1.7} />
        </button>
        <span className={s.dicaAtalho}>⌘K</span>
      </header>

      <div className={s.corpo}>
        {comBarraLateral && (
        <nav
          className={colapsada ? `${s.sidebar} ${s.sidebarColapsada}` : s.sidebar}
          aria-label="Navegação principal"
        >
          {grupos.map((g) => (
            <div key={g.titulo}>
              {!colapsada && <p className={s.grupoTitulo}>{g.titulo}</p>}
              {g.itens.map((i) => {
                const Icone = i.icone
                return (
                  <NavLink
                    key={i.rota}
                    to={PREFIXO_NOVO + i.rota}
                    className={({ isActive }) =>
                      isActive ? `${s.item} ${s.itemAtivo}` : s.item
                    }
                    title={colapsada ? i.rotulo : undefined}
                  >
                    <Icone size={18} strokeWidth={1.7} />
                    <span className={colapsada ? s.rotuloColapsado : undefined}>
                      {i.rotulo}
                    </span>
                  </NavLink>
                )
              })}
            </div>
          ))}
        </nav>
        )}

        <main className={s.conteudo}>
          <div className={s.conteudoInterno}>
            {carregando ? (
              <LogikosLoader estado="waiting" variante="fullscreen" rotulo="CARREGANDO" />
            ) : (
              // As telas vêm por lazy(): entre o clique e o pedaço chegar há um
              // vão. Sem Suspense o React estoura; com um spinner qualquer, o
              // vão fica com a cara de outro produto.
              <Suspense
                fallback={
                  <LogikosLoader estado="entering" variante="fullscreen" rotulo="ABRINDO" />
                }
              >
                <Outlet />
              </Suspense>
            )}
          </div>
        </main>
      </div>

      <PaletaComandos
        grupos={gruposPaleta}
        aberta={paletaAberta}
        onAbertaChange={setPaletaAberta}
      />
      {expiraEm !== null && (
        <SessaoExpirando expiraEm={expiraEm} onRenovar={aoRenovar} onSair={aoSair} />
      )}
    </div>
  )
}
