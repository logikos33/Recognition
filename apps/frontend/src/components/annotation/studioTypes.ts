/**
 * Tipos do Estúdio de Anotação (keyboard-first).
 *
 * A sequência de frames é CONGELADA na entrada (props) — o estúdio nunca
 * reconsulta o servidor durante a sessão: a coleta está ativa e a lista não
 * pode escorregar debaixo do usuário.
 */

/** Frame da sequência congelada (derivado do card da galeria). */
export interface StudioFrame {
  id: string
  /** Presigned R2 (ttl 1h) — fallback: `${apiBase}/api/training/frames/{id}/image`. */
  url: string | null
  filename: string
  cameraName?: string | null
  capturedAt?: string | null
  /** Estado inicial (galeria) — o estúdio atualiza localmente ao salvar. */
  annotated?: boolean
  /** id da câmera (public.cameras/ip_cameras) — usado como `camera_id` do
   * preflight/criação de job de propagação semeada ("buscar imagens
   * iguais"). `undefined`/`null` = busca indisponível pra este frame. */
  cameraId?: string | null
}

/**
 * Classe disponível na paleta — `classId` é o id devolvido pelo backend
 * (GET /modules/<code>/classes). Ids de classe do tenant já vêm namespaced
 * (100000+id): usar como veio, sem aritmética própria.
 */
export interface StudioClass {
  classId: number
  name: string
  color: string
  usageCount?: number
}

/**
 * Caixa em coordenadas YOLO normalizadas (0–1, centro + dimensões).
 *
 * `isProposal`/`confidence` (fila de aprovação de propostas — migration
 * 111): true quando a caixa veio de `pre_annotations` ainda não revisada
 * (GET .../annotations devolve `source: 'ai'` nesse caso — ver
 * AnnotationService.get_frame_annotations). Uma vez que o frame tem
 * QUALQUER linha em frame_annotations (humana OU pré-anotação já aceita),
 * o backend nunca mistura com `pre_annotations` de novo — então uma caixa
 * "proposta" só existe enquanto NENHUMA caixa do frame foi persistida
 * ainda. `undefined`/`false` = caixa humana normal (mesmo default de
 * sempre, campos novos não quebram nenhum caller existente).
 */
export interface Box {
  id: string
  classId: number
  xCenter: number
  yCenter: number
  width: number
  height: number
  isProposal?: boolean
  confidence?: number | null
}

/** Item cru do GET /training/frames/{id}/annotations. */
export interface RawAnnotation {
  id?: string | number
  class_id: number
  x_center: number
  y_center: number
  width: number
  height: number
  /** 'ai' = proposta pendente (pre_annotations, ainda não revisada). */
  source?: string
  confidence?: number | null
}

let localIdCounter = 0

/** Id local de caixa — único dentro da sessão do estúdio. */
export function nextBoxId(): string {
  return `box-${Date.now()}-${++localIdCounter}`
}

export function rawToBox(raw: RawAnnotation): Box {
  return {
    id: raw.id != null ? String(raw.id) : nextBoxId(),
    classId: Number(raw.class_id),
    xCenter: Number(raw.x_center),
    yCenter: Number(raw.y_center),
    width: Number(raw.width),
    height: Number(raw.height),
    isProposal: raw.source === 'ai',
    confidence: raw.confidence ?? null,
  }
}

export function boxToPayload(
  box: Box,
  className: string | undefined,
  moduleCode: string,
): Record<string, unknown> {
  return {
    class_id: box.classId,
    class_name: className,
    module_code: moduleCode,
    x_center: box.xCenter,
    y_center: box.yCenter,
    width: box.width,
    height: box.height,
  }
}
