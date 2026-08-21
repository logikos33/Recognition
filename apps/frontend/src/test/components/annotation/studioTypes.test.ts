/**
 * Tests: rawToBox — fila de aprovação de propostas (migration 111).
 *
 * `source: 'ai'` (AnnotationService.get_frame_annotations, caminho de
 * fallback pra pre_annotations ainda não revisada) precisa virar
 * `isProposal: true` no Box do estúdio, senão AnnotationStudio não sabe
 * distinguir uma caixa proposta de uma anotação humana normal (nem pra
 * estilo, nem pros atalhos V/X).
 */
import { describe, expect, it } from 'vitest'
import { proposalLabelSuffix, rawToBox } from '../../../components/annotation/studioTypes'

describe('proposalLabelSuffix', () => {
  it('mostra a confiança em % (ela prevê a aceitação — o revisor precisa vê-la)', () => {
    expect(proposalLabelSuffix(0.78)).toBe(' · IA 78%')
    expect(proposalLabelSuffix(0.005)).toBe(' · IA 1%') // arredonda, não trunca
    expect(proposalLabelSuffix(1)).toBe(' · IA 100%')
  })

  it('sem confiança (DINO legado) degrada pro rótulo antigo, nunca "NaN%"', () => {
    expect(proposalLabelSuffix(null)).toBe(' · proposta IA')
    expect(proposalLabelSuffix(undefined)).toBe(' · proposta IA')
  })
})

describe('rawToBox', () => {
  it('source=ai vira isProposal=true e preserva confidence', () => {
    const box = rawToBox({
      id: 'pre-0',
      class_id: 1,
      x_center: 0.5,
      y_center: 0.5,
      width: 0.2,
      height: 0.2,
      source: 'ai',
      confidence: 0.87,
    })
    expect(box.isProposal).toBe(true)
    expect(box.confidence).toBe(0.87)
  })

  it('anotação humana (sem source, ou source=manual) vira isProposal=false', () => {
    const human = rawToBox({
      id: 'abc',
      class_id: 1,
      x_center: 0.5,
      y_center: 0.5,
      width: 0.2,
      height: 0.2,
    })
    expect(human.isProposal).toBe(false)
    expect(human.confidence).toBeNull()

    const manual = rawToBox({
      id: 'def',
      class_id: 1,
      x_center: 0.5,
      y_center: 0.5,
      width: 0.2,
      height: 0.2,
      source: 'manual',
    })
    expect(manual.isProposal).toBe(false)
  })

  it('proposta aceita (source=pre_annotation, já em frame_annotations) NÃO é isProposal', () => {
    // Diferença crítica: 'pre_annotation' é o source da LINHA JÁ GRAVADA em
    // frame_annotations (accept-suggestions/accept_pre_annotations) — não
    // é mais uma proposta pendente, é anotação revisada e aceita. Só
    // 'ai' (fallback de pre_annotations JSONB cru) é proposta pendente.
    const accepted = rawToBox({
      id: 'ghi',
      class_id: 1,
      x_center: 0.5,
      y_center: 0.5,
      width: 0.2,
      height: 0.2,
      source: 'pre_annotation',
    })
    expect(accepted.isProposal).toBe(false)
  })
})
