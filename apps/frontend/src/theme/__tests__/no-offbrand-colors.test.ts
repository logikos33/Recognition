/**
 * Guard-rail WS1 — proíbe cores fora da marca em src/**\/*.tsx (e, para a
 * regra de roxo, também em src/**\/*.css.ts).
 *
 * Falha quando encontra, fora da allowlist:
 *  - backgrounds claros hardcoded (#fff/white/#F9FAFB/#f5f5f5/#f8fafc)
 *  - azuis fora da marca (#2563eb/#3b82f6/#0070f3/#4f46e5/#1d4ed8)
 *  - violet legacy (#a78bfa/#7c3aed/#8b5cf6)
 *  - backdrops rgba(0,0,0,x) hand-rolled (usar vars.color.overlay/Modal do kit)
 *  - branco-alpha rgba(255,255,255,x) hand-rolled — classe do bug da task-063:
 *    invisível sob superfícies claras de white-label (usar tokens text/border/bg)
 *
 * ─── ESCOPO DE ARQUIVO (furo da rodada O2, issue #661) ─────────────────
 *
 * O `walk()` só andava por `*.tsx` — e praticamente TODO estilo deste front
 * mora em `*.css.ts` (vanilla-extract). Medido: 11 declarações de roxo
 * legado servidas ao cliente passavam pelo CI verde (`CameraGrid.css.ts` ×6,
 * `KPICard.css.ts` ×1, `KPIRow.tsx` ×2, `TrainingPage.css.ts` ×2).
 *
 * Segundo furo, na REGRA: `violet legacy` só casava a forma HEX
 * (`#8b5cf6`). Das 11 declarações reais, ZERO eram hex — todas eram
 * `rgba(139, 92, 246, α)`. A regra ganhou a forma rgb/rgba.
 *
 * Por que só a regra de roxo passou a ler `.css.ts`, e não as 5 outras:
 * MEDIDO — estender todas de uma vez acende 34 achados pré-existentes
 * (backdrops `rgba(0,0,0,x)`, branco-alpha e `#2563eb` de admin) em arquivos
 * de OUTRAS frentes, que este PR não tem mandato para reescrever. Ficam
 * registradas na issue aberta junto com este PR; a régua de roxo — a que
 * guarda a identidade da marca — fecha agora e por inteiro.
 *
 * Exceções:
 *  - linha de COMENTÁRIO (`//`, `/*`, `*`): documentação sobre a cor não é
 *    a cor servida — é o que permite explicar `#8b5cf6` no comentário que
 *    conta por que ele saiu (`themes/professional.css.ts`, `Shell.css.ts`)
 *  - linha com marcador `allow:` (justificativa inline obrigatória)
 *  - linha com `TODO-WS1` (baseline congelada — proíbe REGRESSÃO nova,
 *    conversão estrutural pendente documentada no PR do WS1)
 *  - arquivos/diretórios da ALLOWLIST abaixo (intencionais)
 */
import { describe, it, expect } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const SRC = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')

/** Prefixos (relativos a src/) intencionalmente fora do guard-rail. */
const ALLOWLIST: string[] = [
  // Kiosk tablet Quality — palette navy própria, decisão de produto
  'modules/quality/tablet/',
  // TV Andon chão de fábrica — display escuro próprio
  'modules/quality/pages/QualityAndonDisplay.tsx',
  // Overlays funcionais sobre vídeo/canvas (legendas, réguas, ROI)
  'components/scenario/DrawingCanvas.tsx',
  'components/scenario/CountingLineCanvas.tsx',
  'components/training/canvas/',
  'components/monitoring/DetectionOverlay.tsx',
  'modules/quality/components/AnnotationCanvas.tsx',
  // Sandbox de branding — hexes são CONTEÚDO de demonstração, não estilo
  'modules/admin/pages/AdminBrandingSandboxPage.tsx',
  // Fixtures de teste
  'test/',
]

interface Violation {
  file: string
  line: number
  text: string
  rule: string
}

/** `.tsx` para todas; `.css.ts` só para a regra de roxo (ver ESCOPO acima). */
const SO_TSX = ['.tsx']
const TSX_E_ESTILO = ['.tsx', '.css.ts']

const RULES: Array<{ name: string; re: RegExp; extensoes: string[] }> = [
  {
    extensoes: SO_TSX,
    name: 'background claro hardcoded',
    re: /background(Color)?:\s*['"](#fff(fff)?|white|#f9fafb|#f5f5f5|#f8fafc)['"]/i,
  },
  {
    extensoes: SO_TSX,
    name: 'azul fora da marca',
    re: /#(2563eb|3b82f6|0070f3|4f46e5|1d4ed8)\b/i,
  },
  {
    extensoes: TSX_E_ESTILO,
    name: 'violet legacy (hex)',
    re: /#(a78bfa|7c3aed|8b5cf6)\b/i,
  },
  {
    extensoes: TSX_E_ESTILO,
    // Forma rgb/rgba dos MESMOS três roxos — era o furo real: as 11
    // declarações servidas (issue #661) eram todas `rgba(139, 92, 246, α)`,
    // nenhuma hex. Substituto: os tokens `vars.color.primary*`, que já leem
    // as CSS vars de white-label com o ciano da marca como default.
    name: 'violet legacy (rgb) — use vars.color.primary/primaryLight/primaryAlpha',
    re: /rgba?\(\s*(139\s*,\s*92\s*,\s*246|167\s*,\s*139\s*,\s*250|124\s*,\s*58\s*,\s*237)\s*[,)]/i,
  },
  {
    extensoes: SO_TSX,
    name: 'backdrop rgba(0,0,0,x) hand-rolled — usar vars.color.overlay / Modal do kit',
    re: /background:\s*['"]rgba\(0,\s*0,\s*0/,
  },
  {
    extensoes: SO_TSX,
    name: 'branco-alpha rgba(255,255,255,x) hand-rolled — quebra sob white-label claro (task-063); usar tokens text*/border*/bg*',
    re: /rgba\(\s*255\s*,\s*255\s*,\s*255/i,
  },
]

function walk(dir: string, acc: string[] = []): string[] {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      if (entry.name === 'node_modules' || entry.name === '__tests__') continue
      walk(full, acc)
    } else if (entry.name.endsWith('.tsx') || entry.name.endsWith('.css.ts')) {
      acc.push(full)
    }
  }
  return acc
}

/** Comentário não é estilo servido — ver "Exceções" no topo. */
function ehComentario(linha: string): boolean {
  return /^\s*(\/\/|\/\*|\*)/.test(linha)
}

describe('guard-rail: cores fora da marca (WS1)', () => {
  it('src/**/*.{tsx,css.ts} não contém cores proibidas fora da allowlist', () => {
    const files = walk(SRC)
    const violations: Violation[] = []

    for (const file of files) {
      const rel = path.relative(SRC, file).split(path.sep).join('/')
      if (ALLOWLIST.some((p) => rel.startsWith(p))) continue

      const ext = file.endsWith('.css.ts') ? '.css.ts' : '.tsx'
      const lines = fs.readFileSync(file, 'utf-8').split('\n')
      lines.forEach((line, i) => {
        if (line.includes('allow:') || line.includes('TODO-WS1') || ehComentario(line)) return
        for (const rule of RULES) {
          if (!rule.extensoes.includes(ext)) continue
          if (rule.re.test(line)) {
            violations.push({ file: rel, line: i + 1, text: line.trim().slice(0, 120), rule: rule.name })
          }
        }
      })
    }

    const report = violations
      .map((v) => `${v.file}:${v.line} [${v.rule}]\n    ${v.text}`)
      .join('\n')
    expect(violations, `Cores fora da marca encontradas:\n${report}`).toEqual([])
  })
})

/**
 * Prova por MUTAÇÃO: reinstala como fixture as linhas EXATAS que estavam
 * servidas antes deste PR (issue #661) e mostra a régua pegando cada uma.
 * Sem isto, "o guard-rail agora cobre `.css.ts`" seria só afirmação — foi
 * exatamente o CI verde sobre 11 declarações de roxo que criou a issue.
 */
describe('prova por mutação: as 11 linhas reais que passavam verdes', () => {
  const regraRoxa = RULES.filter((r) => r.name.startsWith('violet legacy'))

  const LINHAS_ANTES = [
    "  boxShadow: `inset 0 0 20px rgba(139, 92, 246, 0.15)`,",      // CameraGrid.css.ts:63
    "    borderColor: 'rgba(139, 92, 246, 0.4)',",                   // CameraGrid.css.ts:173
    "    background: 'rgba(139, 92, 246, 0.05)',",                   // CameraGrid.css.ts:174
    "    color: 'rgba(139, 92, 246, 0.6)',",                         // CameraGrid.css.ts:175
    "    background: 'rgba(139, 92, 246, 0.1)',",                    // CameraGrid.css.ts:502
    "    background: 'rgba(139, 92, 246, 0.3)',",                    // CameraGrid.css.ts:566
    "    boxShadow: '0 0 12px rgba(139, 92, 246, 0.1)',",            // KPICard.css.ts:19
    '          icon={<Brain size={20} color={"#a78bfa"} />}',        // KPIRow.tsx:138
    '          iconBg="rgba(139, 92, 246, 0.15)"',                   // KPIRow.tsx:139
    "    background: 'rgba(139, 92, 246, 0.03)',",                   // TrainingPage.css.ts:183
    "  background: 'rgba(139, 92, 246, 0.06)',",                     // TrainingPage.css.ts:189
  ]

  it('as 11 linhas de antes disparam a regra de roxo', () => {
    const passam = LINHAS_ANTES.filter((l) => !regraRoxa.some((r) => r.re.test(l)))
    expect(passam, `linhas de roxo que ESCAPARIAM da régua:\n${passam.join('\n')}`).toEqual([])
  })

  it('as 11 substituições de hoje NÃO disparam (sem falso positivo)', () => {
    const DEPOIS = [
      '  boxShadow: `inset 0 0 20px ${vars.color.primaryAlpha}`,',
      '    borderColor: vars.color.primary,',
      '    background: vars.color.primaryAlpha,',
      '    color: vars.color.primaryLight,',
      '    background: vars.color.primaryDark,',
      '  background: `0 0 12px ${vars.color.primaryAlpha}`,',
      '          icon={<Brain size={20} color={vars.color.primaryLight} />}',
      '          iconBg={vars.color.primaryAlpha}',
    ]
    const batem = DEPOIS.filter((l) => RULES.some((r) => r.re.test(l)))
    expect(batem, `falso positivo nas linhas novas:\n${batem.join('\n')}`).toEqual([])
  })

  it('a régua de roxo lê `.css.ts` — onde mora o estilo deste front', () => {
    expect(regraRoxa.every((r) => r.extensoes.includes('.css.ts'))).toBe(true)
    expect(walk(SRC).some((f) => f.endsWith('.css.ts'))).toBe(true)
  })
})
