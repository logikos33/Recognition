/**
 * Guard-rail WS1 — proíbe cores fora da marca em src/**\/*.tsx.
 *
 * Falha quando encontra, fora da allowlist:
 *  - backgrounds claros hardcoded (#fff/white/#F9FAFB/#f5f5f5/#f8fafc)
 *  - azuis fora da marca (#2563eb/#3b82f6/#0070f3/#4f46e5/#1d4ed8)
 *  - violet legacy (#a78bfa/#7c3aed/#8b5cf6)
 *  - backdrops rgba(0,0,0,x) hand-rolled (usar vars.color.overlay/Modal do kit)
 *
 * Exceções:
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

const RULES: Array<{ name: string; re: RegExp }> = [
  {
    name: 'background claro hardcoded',
    re: /background(Color)?:\s*['"](#fff(fff)?|white|#f9fafb|#f5f5f5|#f8fafc)['"]/i,
  },
  {
    name: 'azul fora da marca',
    re: /#(2563eb|3b82f6|0070f3|4f46e5|1d4ed8)\b/i,
  },
  {
    name: 'violet legacy',
    re: /#(a78bfa|7c3aed|8b5cf6)\b/i,
  },
  {
    name: 'backdrop rgba(0,0,0,x) hand-rolled — usar vars.color.overlay / Modal do kit',
    re: /background:\s*['"]rgba\(0,\s*0,\s*0/,
  },
]

function walk(dir: string, acc: string[] = []): string[] {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      if (entry.name === 'node_modules' || entry.name === '__tests__') continue
      walk(full, acc)
    } else if (entry.name.endsWith('.tsx')) {
      acc.push(full)
    }
  }
  return acc
}

describe('guard-rail: cores fora da marca (WS1)', () => {
  it('src/**/*.tsx não contém cores proibidas fora da allowlist', () => {
    const files = walk(SRC)
    const violations: Violation[] = []

    for (const file of files) {
      const rel = path.relative(SRC, file).split(path.sep).join('/')
      if (ALLOWLIST.some((p) => rel.startsWith(p))) continue

      const lines = fs.readFileSync(file, 'utf-8').split('\n')
      lines.forEach((line, i) => {
        if (line.includes('allow:') || line.includes('TODO-WS1')) return
        for (const rule of RULES) {
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
