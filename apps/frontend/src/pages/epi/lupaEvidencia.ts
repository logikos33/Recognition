/**
 * Matemática da lupa da evidência — PURA, sem DOM, sem React.
 *
 * O transform aplicado é `translate(x px, y px) scale(escala)` com
 * `transform-origin: center`. Toda âncora (cursor, ponto médio da pinça) é
 * medida RELATIVA AO CENTRO do palco. Trocar a origem para `0 0` quebra a
 * âncora em silêncio — não troque.
 *
 * Em escala 1 o conteúdo cobre o palco exatamente (a <img> é width:100% do
 * palco), então o limite de pan fecha em fórmula: |x| <= largura*(s-1)/2.
 * Em s=1 isso dá 0 — o pan volta ao centro sozinho, sem caso especial.
 */
import { clamp } from '../../components/annotation/boxGeometry'

export const ESCALA_MIN = 1
export const ESCALA_MAX = 8

export interface EstadoLupa { escala: number; x: number; y: number }
export interface Palco { largura: number; altura: number }
export interface Ponto { x: number; y: number }

export type EventoLupa =
  | { tipo: 'zoom'; fator: number; ancoraX: number; ancoraY: number }
  | { tipo: 'arrastar'; dx: number; dy: number }
  | { tipo: 'reset' }

export const LUPA_INICIAL: EstadoLupa = { escala: ESCALA_MIN, x: 0, y: 0 }

/** Deslocamento máximo antes de abrir faixa vazia (= antes de a imagem sumir). */
export function limitePan(escala: number, tamanhoPalco: number): number {
  return Math.max(0, (tamanhoPalco * (escala - ESCALA_MIN)) / 2)
}

/** Distância entre os dois primeiros ponteiros — fator da pinça. */
export function distanciaEntre([a, b]: Ponto[]): number {
  if (!a || !b) return 0
  return Math.hypot(b.x - a.x, b.y - a.y)
}

export function proximoEstado(estado: EstadoLupa, evento: EventoLupa, palco: Palco): EstadoLupa {
  if (evento.tipo === 'reset') return LUPA_INICIAL

  let { escala, x, y } = estado
  if (evento.tipo === 'zoom') {
    const nova = clamp(escala * evento.fator, ESCALA_MIN, ESCALA_MAX)
    // Sem mudança de escala = mesmo objeto: React não re-renderiza à toa.
    if (nova === escala) return estado
    // Mantém sob o cursor o MESMO pixel do frame.
    const razao = nova / escala
    x = evento.ancoraX - razao * (evento.ancoraX - x)
    y = evento.ancoraY - razao * (evento.ancoraY - y)
    escala = nova
  } else {
    x += evento.dx
    y += evento.dy
  }

  // Ao APROXIMAR este clamp nunca morde (o limite pós-zoom é exatamente
  // W(s'-1)/2). Ao AFASTAR ele morde e reenquadra: o limite VENCE a âncora,
  // senão abriria faixa vazia. Medido: 0/23491 aproximações vs 11710/23657
  // afastamentos em 50k eventos aleatórios.
  const limX = limitePan(escala, palco.largura)
  const limY = limitePan(escala, palco.altura)
  // `+ 0` normaliza -0 (vem de `-limX` com limite zero): React usa Object.is
  // para desistir do re-render, e -0 !== 0 ali dentro renderizaria à toa.
  return { escala, x: clamp(x, -limX, limX) + 0, y: clamp(y, -limY, limY) + 0 }
}
