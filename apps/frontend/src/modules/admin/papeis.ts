/**
 * Vocabulário de papéis atribuíveis — fonte única das TRÊS telas que criam
 * usuário (`app/admin/Usuarios.tsx`, `components/CreateUserWizard.tsx`,
 * `pages/AdminTenantDetailPage.tsx`).
 *
 * Por que existe: as três telas vinham com **"Operador" pré-selecionado**. É a
 * palavra natural para quem está no chão de fábrica, e é a errada para quem vai
 * trabalhar no Estúdio: `operator` NÃO tem `training:write`, então curadoria de
 * frames (`POST /api/training/frames/curation`), classes, gabarito e treino
 * devolvem 403 — `services/api/app/core/auth.py:require_training_role`. Um
 * padrão que o usuário aceita sem ler e que quebra depois não é conveniência,
 * é armadilha. Aqui **não há padrão**: quem cria escolhe, vendo o que a escolha
 * concede e o que ela NEGA.
 *
 * Por que `concede`/`nega` são listas de chave e não só prosa: prosa não tem
 * teste. Cada frase declara as chaves que promete e as que exclui, e
 * `papeis.test.ts` confere as duas contra `test/e2e/matriz-papeis.json` — que é
 * gerada do registry real (`services/api/app/core/permissions.py`). Se alguém
 * mexer no registry e a frase virar mentira, o teste fica vermelho ANTES de a
 * tela mentir para o Vitor.
 *
 * `superadmin` não está aqui de propósito: as telas nunca o ofereceram e o
 * backend só o aceita de outro superadmin (`admin/routes.py:@require_superadmin`).
 */
import type { UserRole } from './types/admin'

export interface PapelAtribuivel {
  valor: UserRole
  rotulo: string
  /** O que o papel FAZ. As chaves em `concede` são a prova desta frase. */
  resumo: string
  concede: string[]
  /** O que o papel NÃO alcança. As chaves em `nega` são a prova desta frase. */
  alerta: string
  nega: string[]
}

export const PAPEIS_ATRIBUIVEIS: PapelAtribuivel[] = [
  {
    valor: 'admin',
    rotulo: 'Admin',
    resumo: 'Administra o cliente: usuários, câmeras, alertas e o Estúdio inteiro.',
    concede: ['admin:users', 'cameras:write', 'alerts:read', 'training:write'],
    alerta: 'Não abre o painel da plataforma (só superadmin).',
    nega: ['admin:panel'],
  },
  {
    valor: 'operator',
    rotulo: 'Operador',
    resumo: 'Opera câmeras, trata alertas, verifica detecções e anota frames.',
    concede: ['cameras:control', 'alerts:feedback', 'verification:write', 'frames:annotate'],
    alerta: 'No Estúdio só anota: curar frames, classes, gabarito e treino recusam (403).',
    nega: ['training:read', 'training:write'],
  },
  {
    valor: 'analyst',
    rotulo: 'Analista',
    resumo: 'Acompanha alertas, verificação e relatórios; exporta os dados.',
    concede: ['alerts:read', 'verification:read', 'reports:export'],
    alerta: 'Não opera câmeras e não entra no Estúdio.',
    nega: ['cameras:control', 'frames:annotate'],
  },
  {
    valor: 'trainer',
    rotulo: 'Treinador',
    resumo: 'Dono do Estúdio: anota, cura frames, cria classes e dispara treino.',
    concede: ['frames:annotate', 'training:read', 'training:write'],
    alerta: 'Não opera câmeras ao vivo e não trata alertas.',
    nega: ['cameras:control', 'alerts:read'],
  },
  {
    valor: 'viewer',
    rotulo: 'Visualizador',
    resumo: 'Somente leitura: painéis, alertas e relatórios.',
    concede: ['alerts:read', 'reports:read'],
    alerta: 'Não altera nada e não entra no Estúdio.',
    nega: ['frames:annotate', 'verification:write'],
  },
]

/** Rótulo pt-BR de QUALQUER papel — inclui `superadmin`, que aparece em lista/filtro. */
export const PAPEL_LABEL: Record<UserRole, string> = {
  superadmin: 'Superadmin',
  admin: 'Admin',
  operator: 'Operador',
  analyst: 'Analista',
  trainer: 'Treinador',
  viewer: 'Visualizador',
}

/**
 * Valor inicial do seletor de papel nas telas de criação. String vazia de
 * propósito — ver cabeçalho. Não troque por um papel "sensato": o papel
 * sensato pelo nome (`operator`) é justamente o que quebra no Estúdio.
 */
export const SEM_PAPEL = '' as const

/** Texto da opção neutra do seletor. */
export const ROTULO_SEM_PAPEL = 'Selecione um papel'
