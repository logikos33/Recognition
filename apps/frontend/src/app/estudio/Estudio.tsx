/**
 * Estúdio — layout e gate. `Estúdio.dc.html` (bundle canônico F5).
 *
 * O trainer VIVE aqui: `frames:annotate` é exatamente a união de quem anota
 * (superadmin, admin, operator, trainer — `matriz-papeis.json`, gerada do
 * registry real). O desenho gateia com "estudio:acesso", chave que NÃO existe
 * no registry — usá-la faria o `can()` negar para todo mundo menos o
 * superadmin, em silêncio. Divergência registrada na Fase 0 da F5.
 *
 * A lateral é PRÓPRIA (220px, desenho); a do Shell some via SEM_BARRA_LATERAL.
 * Só entra item cuja rota EXISTE — as áreas restantes da prancha (Ferramentas
 * IA, Dataset) chegam nas próximas PRs da F5.
 * Item apontando para rota inexistente é tela inventada.
 *
 * F5-LEVE (item 2): a lateral própria SUBSTITUI a nav principal do Shell —
 * quem entra aqui perde o menu do EPI/Admin de vista, e o logo do topbar
 * (F5-LEVE item 1) é pequeno demais para contar como o caminho de volta que
 * a pessoa vai procurar. Por isso "Voltar" no topo da lateral, explícito, não
 * dependente do logo. Vai para o Dashboard EPI — é de lá que a nav do Shell
 * leva ao Estúdio, e é para lá que faz sentido devolver quem entrou pelo
 * menu (`/modules` daria um passo a mais: tenant de módulo único, como a
 * RVB, cairia de novo no dashboard EPI de qualquer jeito).
 */
import { Suspense } from 'react'
import {
  Activity, ArrowLeft, Box, Cctv, Grid3x3, Images, SlidersHorizontal,
  Smartphone, SquareMousePointer, Tags,
} from 'lucide-react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'

import { useAuth } from '../../hooks/useAuth'
import { rotaNova } from '../RotasNovas'
import { SemPermissao } from '../shell/SemPermissao'
import * as s from './Estudio.css'

/**
 * A lateral é filtrada por PERMISSÃO. Item que o papel não pode usar não
 * aparece — e não é alcançável por URL direta: o guard antes do `<Outlet />`
 * repete a checagem, porque menu escondido não é autorização.
 *
 * `permissao` foi MEDIDA endpoint a endpoint (issue #688) contra
 * `services/api/app/api/v1/training/routes.py` e `app/api/v1/cameras/*`:
 *
 *   Dados         GET  /api/training/images                   só JWT  (anotar = frames:annotate)
 *   Cobertura     GET  /api/training/coverage-matrix          só JWT
 *   Classificar   POST /api/training/frames/<id>/annotations  frames:annotate
 *   Gabarito      GET  /api/training/gabarito/fila            training:write ← morria na ABERTURA
 *   Classes       POST/PUT/PATCH/DELETE /api/classes          training:write
 *   Treinos       POST /api/training/jobs · .../stop          training:write
 *   Modelos       training:read — o registry define a chave como "acompanhar
 *                 jobs de treinamento, datasets e modelos do tenant"
 *                 (`core/permissions.py`); a rota GET é frouxa, a intenção não.
 *   Mod. p/ câm.  POST /api/cameras/<id>/model-config         cameras:configure
 *   Uso das câm.  PUT  /api/cameras/modules                   cameras:configure
 *
 * `null` = quem passou pela porta do Estúdio (`frames:annotate`) já pode usar.
 *
 * ⚠️ A resposta ao 403 é ESCONDER o que o papel não pode, nunca ampliar a
 * permissão de ninguém — `operator` anota, e é só isso que ele vê aqui.
 */
export const ITENS: {
  rota: string
  rotulo: string
  Icone: typeof Images
  permissao: string | null
}[] = [
  { rota: 'dados', rotulo: 'Dados', Icone: Images, permissao: null },
  { rota: 'cobertura', rotulo: 'Cobertura', Icone: Grid3x3, permissao: null },
  { rota: 'classificar', rotulo: 'Classificar', Icone: SquareMousePointer, permissao: null },
  // Vive FORA deste layout (rota em ROTAS_NOVAS_SEM_SHELL — tela de celular,
  // onde lateral de 220px não cabe), mas o caminho é filho daqui, então o
  // NavLink relativo alcança. Entra na lateral porque é por aqui que o dono
  // acha a tela — rota sem porta de entrada é rota que ninguém usa.
  { rota: 'gabarito', rotulo: 'Gabarito (celular)', Icone: Smartphone, permissao: 'training:write' },
  { rota: 'classes', rotulo: 'Classes', Icone: Tags, permissao: 'training:write' },
  { rota: 'treino', rotulo: 'Treinos', Icone: Activity, permissao: 'training:write' },
  { rota: 'modelo', rotulo: 'Modelos', Icone: Box, permissao: 'training:read' },
  {
    rota: 'modelos-por-camera',
    rotulo: 'Modelos por câmera',
    Icone: Cctv,
    permissao: 'cameras:configure',
  },
  // Fica ao lado de "Modelos por câmera" porque as duas respondem sobre a
  // MESMA câmera — lá "qual modelo responde", aqui "para que ela serve".
  {
    rota: 'cameras-por-modulo',
    rotulo: 'Uso das câmeras',
    Icone: SlidersHorizontal,
    permissao: 'cameras:configure',
  },
]

/**
 * Seção que a URL está pedindo, NORMALIZADA como o React Router normaliza.
 *
 * O matcher do router é case-insensitive e enxerga o caminho com os
 * %-escapes já decodificados: `/novo/estudio/CLASSES` e
 * `/novo/estudio/classe%73` renderizam a MESMA tela que `/classes`.
 * Comparar o segmento cru deixava as duas passarem pelo gate abaixo —
 * bypass real, achado do cético desta PR e coberto por teste.
 *
 * `decodeURIComponent` estoura em %-escape malformado (`%ZZ`): cai no cru,
 * que também não casa rota nenhuma, então nada renderiza de qualquer jeito.
 */
function secaoDaUrl(pathname: string): string {
  const bruto = pathname.replace(/\/+$/, '').split('/').pop() ?? ''
  try {
    return decodeURIComponent(bruto).toLowerCase()
  } catch {
    return bruto.toLowerCase()
  }
}

export function Estudio() {
  const { can } = useAuth()
  const { pathname } = useLocation()

  if (!can('frames:annotate')) return <SemPermissao permissao="frames:annotate" />

  const visiveis = ITENS.filter((i) => i.permissao === null || can(i.permissao))
  // Esconder do menu não é autorizar: quem digita a URL da seção cai no MESMO
  // gate. A lateral continua desenhada — sem ela a pessoa fica sem saída.
  const atual = ITENS.find((i) => i.rota === secaoDaUrl(pathname))
  const bloqueada = atual && atual.permissao !== null && !can(atual.permissao)
    ? atual.permissao
    : null

  return (
    <div className={s.raiz}>
      <nav className={s.lateral} aria-label="Seções do Estúdio">
        <Link to={rotaNova('/epi/dashboard')} className={s.voltar}>
          <ArrowLeft size={16} strokeWidth={1.7} aria-hidden="true" />
          Voltar
        </Link>
        <span className={s.lateralTitulo}>Estúdio</span>
        {visiveis.map(({ rota, rotulo, Icone }) => (
          <NavLink
            key={rota}
            to={rota}
            className={({ isActive }) => (isActive ? `${s.item} ${s.itemAtivo}` : s.item)}
          >
            <Icone size={16} strokeWidth={1.7} aria-hidden="true" />
            {rotulo}
          </NavLink>
        ))}
      </nav>
      <div className={s.conteudo}>
        {bloqueada ? (
          <SemPermissao permissao={bloqueada} />
        ) : (
          /* Boundary local: sem ele, layout e sub-rota (ambos lazy) suspendem em
             sequência no fallback do Shell e a tela pisca duas vezes. */
          <Suspense fallback={null}>
            <Outlet />
          </Suspense>
        )}
      </div>
    </div>
  )
}
