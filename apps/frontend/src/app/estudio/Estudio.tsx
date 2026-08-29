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
 * Só entra item cuja rota EXISTE — as demais áreas da prancha (Classes,
 * Ferramentas IA, Dataset, Treinos, Modelos) chegam nas próximas PRs da F5.
 * Item apontando para rota inexistente é tela inventada.
 */
import { Images } from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'

import { useAuth } from '../../hooks/useAuth'
import { SemPermissao } from '../shell/SemPermissao'
import * as s from './Estudio.css'

const ITENS = [{ rota: 'dados', rotulo: 'Dados', Icone: Images }]

export function Estudio() {
  const { can } = useAuth()

  if (!can('frames:annotate')) return <SemPermissao permissao="frames:annotate" />

  return (
    <div className={s.raiz}>
      <nav className={s.lateral} aria-label="Seções do Estúdio">
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
        <Outlet />
      </div>
    </div>
  )
}
