/**
 * Issue #428 — Excluir câmera apagava em CASCATA.
 *
 * `DELETE /cameras/<id>` leva junto frames, anotações e detecções: acervo de
 * treinamento, trabalho humano de anotação que não se recupera. A UI oferecia
 * isso como um botão numa tabela.
 *
 * Estes testes fixam as duas metades da correção: a UI arquiva (reversível), e
 * o caminho de DELETE **não existe** na camada de serviço do frontend.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { api } from '../../services/api'
import { cameraService } from '../../services/cameraService'

vi.mock('../../services/api')

beforeEach(() => {
  vi.resetAllMocks()
})

const CAM = { id: 'cam-1', name: 'Portaria', is_active: false }

describe('cameraService — arquivar em vez de excluir', () => {
  it('archive() chama POST /cameras/<id>/archive e devolve a câmera', async () => {
    vi.mocked(api.post).mockResolvedValue({ status: 'success', data: { camera: CAM } })

    const result = await cameraService.archive('cam-1')

    expect(api.post).toHaveBeenCalledWith('/cameras/cam-1/archive')
    expect(result.is_active).toBe(false)
  })

  it('restore() chama POST /cameras/<id>/restore', async () => {
    vi.mocked(api.post).mockResolvedValue({
      status: 'success',
      data: { camera: { ...CAM, is_active: true } },
    })

    const result = await cameraService.restore('cam-1')

    expect(api.post).toHaveBeenCalledWith('/cameras/cam-1/restore')
    expect(result.is_active).toBe(true)
  })

  it('⛔ não existe delete() — o caminho de DELETE saiu da UI', () => {
    expect('delete' in cameraService).toBe(false)
  })
})
