/**
 * Piso de contraste da cor de marca — DECISÃO v2 item 3.
 *
 * O contrato: o cliente troca **só a cor de marca**; as superfícies do shell
 * escuro são intocáveis. E a cor escolhida tem de ter **≥4,5:1** contra elas —
 * cor reprovada sofre **clamp de luminância automático**.
 *
 * POR QUE ISSO EXISTE, e não é zelo abstrato: `--color-primary` vem do cadastro
 * do tenant, e o cadastro não faz pergunta nenhuma sobre fundo. Um cliente com
 * marca azul-marinho escolhe azul-marinho, e o texto/ícone dele desaparece
 * sobre `#0A0A0F`. Quem paga é o operador que não enxerga o botão.
 *
 * O clamp CLAREIA (nunca escurece): o shell é escuro, então a saída é sempre na
 * direção da luz. E preserva matiz e saturação — a marca do cliente continua
 * reconhecível, só sobe até passar do piso.
 *
 * ⚠️ Isto NÃO substitui o aviso no admin, que a decisão também pede: o cliente
 * tem de SABER que a cor dele foi ajustada. Esse aviso é tela de admin, e está
 * registrado como pendência — aqui só garantimos que ninguém fique sem enxergar.
 */

import { VALORES } from './lk.css'

/** As superfícies contra as quais a marca precisa se destacar (tokens fixos). */
export const SUPERFICIES = [VALORES.preto, VALORES.grafite] as const

/** Piso do contrato. WCAG AA para texto normal. */
export const PISO_CONTRASTE = 4.5

function paraRgb(hex: string): [number, number, number] | null {
  const h = hex.trim().replace('#', '')
  const completo = h.length === 3 ? h.split('').map((c) => c + c).join('') : h
  if (!/^[0-9a-fA-F]{6}$/.test(completo)) return null
  return [0, 2, 4].map((i) => Number.parseInt(completo.slice(i, i + 2), 16)) as [number, number, number]
}

const paraHex = (rgb: [number, number, number]) =>
  '#' + rgb.map((v) => Math.round(Math.min(255, Math.max(0, v))).toString(16).padStart(2, '0')).join('')

/** Luminância relativa (WCAG 2.x). */
export function luminancia(hex: string): number | null {
  const rgb = paraRgb(hex)
  if (!rgb) return null
  const [r, g, b] = rgb.map((v) => {
    const c = v / 255
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

/** Razão de contraste entre duas cores. */
export function contraste(a: string, b: string): number | null {
  const la = luminancia(a)
  const lb = luminancia(b)
  if (la === null || lb === null) return null
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05)
}

/** O pior caso entre todas as superfícies — é ele que tem de passar. */
export function piorContraste(cor: string): number | null {
  const razoes = SUPERFICIES.map((s) => contraste(cor, s)).filter((r): r is number => r !== null)
  return razoes.length ? Math.min(...razoes) : null
}

export interface ResultadoClamp {
  /** A cor que deve ser usada — igual à original quando ela já passa. */
  cor: string
  /** Precisou clarear? O admin tem de avisar o cliente quando sim. */
  ajustada: boolean
  /** Contraste final contra a pior superfície. */
  contraste: number | null
}

/**
 * Devolve a cor de marca utilizável.
 *
 * Clareia em passos pequenos até passar do piso, preservando matiz: multiplica
 * o canal na direção do branco. Se nem o branco puro passar (impossível contra
 * estas superfícies, mas a função não presume), devolve o melhor que alcançou —
 * nunca `null`, porque uma topbar sem cor de acento é pior que uma imperfeita.
 */
export function corDeMarcaUsavel(cor: string | null | undefined): ResultadoClamp {
  const base = (cor ?? '').trim()
  const rgb = paraRgb(base)
  if (!rgb) return { cor: VALORES.cianoVisao, ajustada: false, contraste: piorContraste(VALORES.cianoVisao) }

  const inicial = piorContraste(base)
  if (inicial !== null && inicial >= PISO_CONTRASTE) {
    return { cor: paraHex(rgb), ajustada: false, contraste: inicial }
  }

  let atual = rgb
  for (let passo = 0; passo < 40; passo += 1) {
    // 6% do que falta para o branco, por passo: sobe rápido no começo e
    // desacelera perto do topo, o que preserva melhor a percepção do matiz.
    atual = atual.map((v) => v + (255 - v) * 0.06) as [number, number, number]
    const hex = paraHex(atual)
    const r = piorContraste(hex)
    if (r !== null && r >= PISO_CONTRASTE) return { cor: hex, ajustada: true, contraste: r }
  }
  const hex = paraHex(atual)
  return { cor: hex, ajustada: true, contraste: piorContraste(hex) }
}
