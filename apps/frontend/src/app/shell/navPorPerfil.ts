/**
 * Navegação por perfil — derivada de PERMISSÃO, não de nome de papel.
 *
 * ⚠️ Divergência do contrato do design, registrada na Fase 0: o handoff assume
 * uma matriz de **4 perfis**; o backend tem **SEIS** (`permissions.py:35`):
 * superadmin, admin, operator, analyst, trainer, viewer.
 *
 * Resolver por nome de papel exigiria escolher quais dois ficam de fora, e
 * qualquer escolha estaria errada para alguém. Resolver por PERMISSÃO não
 * exige escolha nenhuma: a nav mostra o que a pessoa pode fazer, e quando o
 * backend acrescentar um papel a nav já sabe o que fazer com ele.
 *
 * É também o que impede a nav de mentir: item visível que leva a 403 é pior
 * que item ausente — o usuário clica, toma a porta na cara e perde a confiança
 * na tela inteira.
 */
import type { LucideIcon } from 'lucide-react'
import {
  Activity, AlertTriangle, BarChart3, Camera, CheckSquare,
  FlaskConical, LayoutDashboard, Radio, Shield,
} from 'lucide-react'

export interface ItemNav {
  rota: string
  rotulo: string
  icone: LucideIcon
  /**
   * Permissão exigida. `null` = todo mundo autenticado vê.
   * Os nomes vêm do registry real (`services/api/app/core/permissions.py`).
   */
  permissao: string | null
  /** Aparece no ⌘K com este atalho, quando tem. */
  atalho?: string
}

export interface GrupoNav {
  titulo: string
  itens: ItemNav[]
}

/**
 * Jornada-mestra do handoff: DETECTAR → TRIAR → AGIR → PROVAR. A ordem dos
 * itens é essa de propósito — a nav ensina o fluxo, não é lista alfabética.
 */
export const NAV_EPI: GrupoNav[] = [
  {
    titulo: 'EPI',
    itens: [
      { rota: '/epi/dashboard', rotulo: 'Dashboard', icone: LayoutDashboard, permissao: null },
      { rota: '/epi/live', rotulo: 'Ao Vivo', icone: Radio, permissao: 'cameras:read' },
      { rota: '/epi/eventos', rotulo: 'Eventos', icone: AlertTriangle, permissao: 'alerts:read' },
      { rota: '/epi/verificacao', rotulo: 'Verificação', icone: CheckSquare, permissao: 'verification:read' },
      // ⚠️ Não existe permissão `actions:*` no registry. Ações nasce de evento,
      // então quem lê evento vê as ações. Registrado para o design/backend.
      { rota: '/epi/acoes', rotulo: 'Ações', icone: Activity, permissao: 'alerts:read' },
      { rota: '/epi/cameras', rotulo: 'Câmeras', icone: Camera, permissao: 'cameras:read' },
      { rota: '/epi/relatorios', rotulo: 'Relatórios', icone: BarChart3, permissao: 'reports:read' },
    ],
  },
]

/**
 * Estúdio — grupo PRÓPRIO, não item do EPI: treinar modelo é transversal aos
 * módulos, e o trainer (que só tem 4 permissões) vive aqui. `frames:annotate`
 * é a união exata de quem anota: superadmin, admin, operator, trainer
 * (`matriz-papeis.json`). O desenho pedia "estudio:acesso" — chave que não
 * existe no registry; divergência registrada (F5 PR-A).
 */
export const NAV_ESTUDIO: GrupoNav[] = [
  {
    titulo: 'Estúdio',
    itens: [
      { rota: '/estudio', rotulo: 'Estúdio', icone: FlaskConical, permissao: 'frames:annotate' },
    ],
  },
]

/**
 * Admin — grupo PRÓPRIO, com um único item de entrada para o painel da
 * plataforma (`Admin.tsx` tem a lateral própria das sub-seções, como o
 * Estúdio). `admin:panel` é SUPERADMIN-ONLY (`permissions.py:205-208`) —
 * nenhum outro papel, nem `admin` do tenant, tem esta chave
 * (`matriz-papeis.json`), então este grupo só aparece para o superadmin.
 */
export const NAV_ADMIN: GrupoNav[] = [
  {
    titulo: 'Administração',
    itens: [
      { rota: '/admin', rotulo: 'Administração', icone: Shield, permissao: 'admin:panel' },
    ],
  },
]

/**
 * Filtra a nav pelo que a pessoa PODE. `pode` vem do `useAuth().can`, que já
 * trata superadmin como podendo tudo.
 */
export function navVisivel(
  grupos: GrupoNav[],
  pode: (permissao: string) => boolean,
): GrupoNav[] {
  return grupos
    .map((g) => ({ ...g, itens: g.itens.filter((i) => i.permissao === null || pode(i.permissao)) }))
    .filter((g) => g.itens.length > 0)
}
