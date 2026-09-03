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
  SquareMousePointer, Tags,
} from 'lucide-react'
import { Link, NavLink, Outlet } from 'react-router-dom'

import { useAuth } from '../../hooks/useAuth'
import { rotaNova } from '../RotasNovas'
import { SemPermissao } from '../shell/SemPermissao'
import * as s from './Estudio.css'

const ITENS = [
  { rota: 'dados', rotulo: 'Dados', Icone: Images },
  { rota: 'cobertura', rotulo: 'Cobertura', Icone: Grid3x3 },
  { rota: 'classificar', rotulo: 'Classificar', Icone: SquareMousePointer },
  { rota: 'classes', rotulo: 'Classes', Icone: Tags },
  { rota: 'treino', rotulo: 'Treinos', Icone: Activity },
  { rota: 'modelo', rotulo: 'Modelos', Icone: Box },
  { rota: 'modelos-por-camera', rotulo: 'Modelos por câmera', Icone: Cctv },
  // Fica ao lado de "Modelos por câmera" porque as duas respondem sobre a
  // MESMA câmera — lá "qual modelo responde", aqui "para que ela serve".
  { rota: 'cameras-por-modulo', rotulo: 'Uso das câmeras', Icone: SlidersHorizontal },
]

export function Estudio() {
  const { can } = useAuth()

  if (!can('frames:annotate')) return <SemPermissao permissao="frames:annotate" />

  return (
    <div className={s.raiz}>
      <nav className={s.lateral} aria-label="Seções do Estúdio">
        <Link to={rotaNova('/epi/dashboard')} className={s.voltar}>
          <ArrowLeft size={16} strokeWidth={1.7} aria-hidden="true" />
          Voltar
        </Link>
        <span className={s.lateralTitulo}>Estúdio</span>
        {ITENS.map(({ rota, rotulo, Icone }) => (
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
        {/* Boundary local: sem ele, layout e sub-rota (ambos lazy) suspendem em
            sequência no fallback do Shell e a tela pisca duas vezes. */}
        <Suspense fallback={null}>
          <Outlet />
        </Suspense>
      </div>
    </div>
  )
}
