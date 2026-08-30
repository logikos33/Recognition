/**
 * Admin — layout e gate do painel da plataforma (`/novo/admin`).
 *
 * Desenho: `Admin Plataforma.dc.html`. Visão geral (PR-1), Dispositivos e
 * Auditoria (PR-3), Tenants (com white-label) e Usuários (PR-2) — resta só
 * "Links compartilhados", que aguarda backend (pedido registrado).
 * Item apontando para rota inexistente é tela inventada.
 *
 * Gate: `admin:panel` é SUPERADMIN-ONLY (`permissions.py:205-208`, confirmado
 * em `matriz-papeis.json` — nenhum outro papel, nem `admin`, tem esta chave).
 *
 * Banner "você está vendo como" / contexto assumido: NÃO entra aqui. Já é
 * `GlobalBanners`, montado em `App.tsx` fora de qualquer rota — duplicá-lo
 * criaria dois banners e uma segunda fonte de verdade (mesmo raciocínio do
 * `Shell.tsx`).
 *
 * Lateral própria (220px), padrão EXATO de `app/estudio/Estudio.tsx`; a do
 * Shell some via `SEM_BARRA_LATERAL`.
 */
import { Suspense } from 'react'
import { Building2, HardDrive, LayoutDashboard, ScrollText, Users } from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'

import { useAuth } from '../../hooks/useAuth'
import { SemPermissao } from '../shell/SemPermissao'
import * as s from './Admin.css'

const ITENS = [
  { rota: '', rotulo: 'Visão geral', Icone: LayoutDashboard },
  { rota: 'tenants', rotulo: 'Tenants', Icone: Building2 },
  { rota: 'usuarios', rotulo: 'Usuários', Icone: Users },
  { rota: 'dispositivos', rotulo: 'Dispositivos', Icone: HardDrive },
  { rota: 'auditoria', rotulo: 'Auditoria', Icone: ScrollText },
]

export function Admin() {
  const { can } = useAuth()

  if (!can('admin:panel')) return <SemPermissao permissao="admin:panel" />

  return (
    <div className={s.raiz}>
      <nav className={s.lateral} aria-label="Seções do Admin">
        <span className={s.lateralTitulo}>Plataforma · Admin</span>
        {ITENS.map(({ rota, rotulo, Icone }) => (
          <NavLink
            key={rotulo}
            to={rota}
            end={rota === ''}
            className={({ isActive }) => (isActive ? `${s.item} ${s.itemAtivo}` : s.item)}
          >
            <Icone size={16} strokeWidth={1.7} aria-hidden="true" />
            {rotulo}
          </NavLink>
        ))}
      </nav>
      <div className={s.conteudo}>
        {/* Boundary local: mesmo raciocínio do Estúdio — sem ele, layout e
            sub-rota (ambos lazy) suspendem em sequência no fallback do Shell. */}
        <Suspense fallback={null}>
          <Outlet />
        </Suspense>
      </div>
    </div>
  )
}
