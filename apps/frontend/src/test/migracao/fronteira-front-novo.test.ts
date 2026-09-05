/**
 * A fronteira de import do front NOVO (`src/app/**`) — a regra que sobrou
 * depois da triagem, não a que a contagem sugeria.
 *
 * ── O QUE FOI MEDIDO E O QUE ELE QUER DIZER ────────────────────────────────
 *
 * A varredura acusou "11 telas do front novo renderizam componente do front
 * antigo". A contagem está certa; a conclusão não. Ela soma três coisas de
 * naturezas diferentes:
 *
 *  1. **Primitiva de UI** — `EmptyState` (24 importadores), `ConfirmDialog`
 *     (9), `Tooltip`, `InfoTooltip`. Isso é o design system da casa morando
 *     em `components/ui/`. Compartilhar primitiva não é dívida, é o motivo
 *     de ela existir. Duplicar em `app/ui/` daria DOIS `EmptyState` que
 *     divergem no primeiro ajuste de espaçamento.
 *
 *  2. **Componente de domínio compartilhado** — `CameraPlayer`,
 *     `CameraOnboardingWizard`, `CameraWizard`, `CameraModelScope`. Todos
 *     têm consumidor no front ANTIGO também (`CamerasPage`, `CameraCell`,
 *     `ScenarioEditor`, `FuelingPage`, `CameraTriagePage`, `GridPanel`,
 *     `TrainingPage`). MOVER qualquer um para `app/` quebra o front antigo,
 *     que ainda serve rota viva. Reuso é a resposta certa aqui, não a
 *     mudança — e é o que `AoVivo.tsx` e `Cameras.tsx` documentam no topo.
 *
 *  3. **TELA do front antigo** — o único caso que seria dívida de verdade.
 *     Casos hoje: ZERO.
 *
 * O manifesto (`docs/migration/MANIFESTO-FRONT-ANTIGO.md`, gerado) já separa
 * (1)+(2) de (3): tudo que o front novo importa hoje está classificado
 * `INFRA` ("não é tela") ou é módulo de lógica pura mal alojado sob `pages/`
 * (`lupaEvidencia`) e `modules/` (`adminService`, `useTabletWebSocket`).
 *
 * ── A REGRA QUE ESTE TESTE TRAVA ───────────────────────────────────────────
 *
 * PERMITIDO   `app/**` importar infra compartilhada do front antigo
 *             (`components/`, `hooks/`, `services/`, `utils/`, `types/`).
 *
 * PROIBIDO 1  `app/**` importar arquivo `MIGRADO`. `MIGRADO` é exatamente o
 *             que a Fase 3 tem licença para APAGAR — e se a tela nova depende
 *             dele, a demolição derruba o front novo em produção. Nenhum caso
 *             hoje; a trava é para o dia em que alguém marcar `@migrado-para`
 *             num arquivo que a tela nova ainda usa.
 *
 * PROIBIDO 2  `app/**` importar uma TELA do front antigo — componente
 *             (`.tsx`) sob `pages/` ou `modules/` — em qualquer status. Tela
 *             nova que renderiza tela velha é a migração andando para trás.
 *             O recorte é a árvore, não o sufixo do nome: `Login.tsx`,
 *             `AdminLayout.tsx` e `SiteMonitor.tsx` são rota viva e nenhuma
 *             se chama `*Page.tsx`.
 *
 * Note o que a regra NÃO faz: não proíbe `app/**` de importar de fora de
 * `app/`. Proibir isso reprovaria as 19 ocorrências acima, das quais 19 são
 * compartilhamento legítimo — e o conserto seria duplicar o design system.
 */
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs'
import { dirname, join, relative, resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

const RAIZ = join(__dirname, '..', '..', '..')
const SRC = join(RAIZ, 'src')
const APP = join(SRC, 'app')
const MANIFESTO = join(RAIZ, '..', '..', 'docs', 'migration', 'MANIFESTO-FRONT-ANTIGO.md')

/** `| \`src/x/y.tsx\` | \`STATUS\` | ... |` → { 'src/x/y.tsx': 'STATUS' } */
function lerManifesto(): Map<string, string> {
  const mapa = new Map<string, string>()
  for (const linha of readFileSync(MANIFESTO, 'utf8').split('\n')) {
    const m = /^\|\s*`(src\/[^`]+)`\s*\|\s*`([A-Z-]+)`\s*\|/.exec(linha)
    if (m) mapa.set(m[1], m[2])
  }
  return mapa
}

function arquivosDe(dir: string, saida: string[] = []): string[] {
  for (const nome of readdirSync(dir)) {
    const caminho = join(dir, nome)
    if (statSync(caminho).isDirectory()) arquivosDe(caminho, saida)
    else if (/\.tsx?$/.test(nome) && !/\.css\.ts$/.test(nome)) saida.push(caminho)
  }
  return saida
}

/** `from '...'` e `import('...')` — só os relativos e os do alias `@/`. */
function importsDe(fonte: string): string[] {
  const specs: string[] = []
  const re = /(?:from|import)\s*\(?\s*['"]([^'"]+)['"]/g
  for (let m = re.exec(fonte); m; m = re.exec(fonte)) {
    if (m[1].startsWith('.') || m[1].startsWith('@/')) specs.push(m[1])
  }
  return specs
}

/** Especificador → caminho `src/...` do arquivo real, ou null se não resolver. */
function resolver(deOArquivo: string, spec: string): string | null {
  const base = spec.startsWith('@/')
    ? join(SRC, spec.slice(2))
    : resolve(dirname(deOArquivo), spec)
  for (const sufixo of ['', '.ts', '.tsx', '/index.ts', '/index.tsx']) {
    const tentativa = base + sufixo
    if (existsSync(tentativa) && statSync(tentativa).isFile()) {
      return relative(RAIZ, tentativa)
    }
  }
  return null
}

/**
 * Tela do front antigo: componente (`.tsx`) morando na ÁRVORE DE TELAS
 * (`pages/` ou `modules/`) — a mesma árvore que o gerador do manifesto usa
 * para dizer que um arquivo não é infra.
 *
 * Convenção de nome NÃO serve como recorte, e isso foi medido: o primeiro
 * corte era `*Page.tsx` + `modules/*\/pages/*`, e com ele `app/**` podia
 * importar `src/pages/Login.tsx` (o login do front antigo),
 * `src/modules/admin/AdminLayout.tsx` (que tem um `<Routes>` inteiro dentro)
 * e `src/pages/monitoring/SiteMonitor.tsx` (o /monitoring) com o teste VERDE.
 * Rota viva, nenhuma terminando em `Page.tsx`.
 *
 * A extensão é o que separa tela de lógica: os módulos de lógica pura mal
 * alojados nessa árvore são `.ts` (`adminService.ts`, `lupaEvidencia.ts`,
 * `gate.ts`, `useTabletWebSocket.ts`) e seguem permitidos.
 */
function ehTela(caminho: string): boolean {
  return /(^|\/)(pages|modules)\/.*\.tsx$/.test(caminho)
}

interface Cruzamento {
  tela: string
  alvo: string
  status: string
}

/** Todo import de `app/**` que aterrissa num arquivo do front ANTIGO. */
function cruzamentos(): Cruzamento[] {
  const manifesto = lerManifesto()
  const achados: Cruzamento[] = []
  for (const arquivo of arquivosDe(APP)) {
    for (const spec of importsDe(readFileSync(arquivo, 'utf8'))) {
      const alvo = resolver(arquivo, spec)
      // Fora do manifesto = front novo ou node_modules. O manifesto lista
      // exatamente o front antigo — é ele que define a fronteira, não um
      // segundo registro que envelheceria em paralelo.
      if (!alvo || !manifesto.has(alvo)) continue
      achados.push({ tela: relative(RAIZ, arquivo), alvo, status: manifesto.get(alvo)! })
    }
  }
  return achados
}

const CRUZAMENTOS = cruzamentos()

describe('fronteira de import do front novo', () => {
  it('a varredura enxerga alguma coisa (senão o teste é decorativo)', () => {
    // Sem isto, um regex quebrado deixaria as duas travas abaixo passarem por
    // não encontrar NADA — verde por cegueira, o pior verde que existe.
    expect(CRUZAMENTOS.length).toBeGreaterThan(10)
  })

  it('não importa nada que a Fase 3 tem licença para APAGAR (`MIGRADO`)', () => {
    const proibidos = CRUZAMENTOS.filter((c) => c.status === 'MIGRADO')
    expect(
      proibidos.map((c) => `${c.tela} → ${c.alvo} [MIGRADO]`),
      'a demolição do front antigo apaga `MIGRADO` e levaria a tela nova junto',
    ).toEqual([])
  })

  it('não renderiza TELA do front antigo por dentro', () => {
    const proibidos = CRUZAMENTOS.filter((c) => ehTela(c.alvo))
    expect(
      proibidos.map((c) => `${c.tela} → ${c.alvo} [${c.status}]`),
      'tela nova importando tela velha é a migração andando para trás',
    ).toEqual([])
  })

  it('`ehTela` pega rota viva que não se chama `*Page.tsx`', () => {
    // Regressão medida: com o recorte por sufixo, estes três passavam verde
    // importados dentro de `app/**`. São o login, o layout do admin e o
    // /monitoring — rota viva do front antigo, os três.
    const telas = [
      'src/pages/Login.tsx',
      'src/modules/admin/AdminLayout.tsx',
      'src/modules/quality/QualityLayout.tsx',
      'src/pages/monitoring/SiteMonitor.tsx',
    ]
    const manifesto = lerManifesto()
    // Se alguém renomear um destes, falha aqui em vez de testar um fantasma.
    expect(telas.filter((f) => !manifesto.has(f))).toEqual([])
    expect(telas.filter((f) => !ehTela(f))).toEqual([])

    // E o outro lado do recorte: lógica pura mal alojada na mesma árvore
    // continua permitida — senão o "conserto" seria mudar 16 imports que
    // estão certos.
    const logica = [
      'src/modules/admin/services/adminService.ts',
      'src/modules/admin/types/admin.ts',
      'src/pages/epi/lupaEvidencia.ts',
      'src/modules/quality/tablet/useTabletWebSocket.ts',
      'src/modules/quality/types/gate.ts',
    ]
    expect(logica.filter(ehTela)).toEqual([])
  })

  it('o reuso decidido em Ao Vivo e Câmeras se apoia em `INFRA`, não em tela', () => {
    // O veredito da triagem, em forma executável. Se alguém reclassificar um
    // destes, este teste diz QUAL tela nova depende dele antes do estrago.
    const reusados = [
      'src/components/monitoring/CameraPlayer.tsx', // AoVivo.tsx:73
      'src/components/cameras/CameraOnboardingWizard.tsx', // Cameras.tsx:92
      'src/components/cameras/CameraWizard.tsx', // Cameras.tsx:93
      'src/components/ui/ConfirmDialog/ConfirmDialog.tsx', // Cameras.tsx:91
    ]
    const manifesto = lerManifesto()
    expect(reusados.map((f) => `${f} ${manifesto.get(f)}`)).toEqual(
      reusados.map((f) => `${f} INFRA`),
    )
  })
})
