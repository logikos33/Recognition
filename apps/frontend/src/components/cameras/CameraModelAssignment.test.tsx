/**
 * CameraModelAssignment (Task 045 — fix de segurança) — gate de role no UI.
 *
 * Backend PUT /api/cameras/<id>/models agora é admin/superadmin only; este
 * teste garante que o componente espelha o gate: operator/viewer veem os
 * selects desabilitados (somente leitura) e não conseguem disparar o PUT.
 */
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { CameraModelAssignment } from './CameraModelAssignment'

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------
const mocks = vi.hoisted(() => ({
  getCameraModels: vi.fn(),
  setCameraModel: vi.fn(),
  listModels: vi.fn(),
  isAdmin: true as boolean,
  // Default true preserva os testes de badge já existentes abaixo (fluxo de
  // engenharia) — os testes de anti-vazamento ligam false.
  isSuperAdmin: true as boolean,
}))

vi.mock('../../services/countingService', () => ({
  countingService: {
    getCameraModels: mocks.getCameraModels,
    setCameraModel: mocks.setCameraModel,
  },
}))

vi.mock('../../services/trainingService', () => ({
  trainingService: {
    listModels: mocks.listModels,
  },
}))

vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({ isAdmin: mocks.isAdmin, isSuperAdmin: mocks.isSuperAdmin }),
}))

beforeEach(() => {
  vi.clearAllMocks()
  mocks.isAdmin = true
  mocks.isSuperAdmin = true
  mocks.getCameraModels.mockResolvedValue({
    status: 'success',
    data: { camera_id: 'cam-1', models: { epi: null, quality: null, counting: null } },
  })
  mocks.listModels.mockResolvedValue({
    status: 'success',
    data: { models: [{ id: 'model-1', name: 'best_v1', map50: 0.8 }] },
  })
  mocks.setCameraModel.mockResolvedValue({
    status: 'success',
    data: { camera_id: 'cam-1', models: { epi: 'model-1', quality: null, counting: null } },
  })
})

describe('CameraModelAssignment', () => {
  it('admin vê os selects habilitados e consegue atribuir um modelo', async () => {
    render(<CameraModelAssignment cameraId="cam-1" />)

    await waitFor(() => {
      expect(mocks.getCameraModels).toHaveBeenCalledWith('cam-1')
    })

    const epiSelect = screen.getByLabelText('Modelo do módulo EPI') as HTMLSelectElement
    expect(epiSelect.disabled).toBe(false)
    expect(screen.queryByText(/somente leitura/i)).toBeNull()

    fireEvent.change(epiSelect, { target: { value: 'model-1' } })

    await waitFor(() => {
      expect(mocks.setCameraModel).toHaveBeenCalledWith('cam-1', 'epi', 'model-1')
    })
  })

  it('operator vê os selects desabilitados (somente leitura) e não consegue submeter', async () => {
    mocks.isAdmin = false
    render(<CameraModelAssignment cameraId="cam-1" />)

    await waitFor(() => {
      expect(mocks.getCameraModels).toHaveBeenCalledWith('cam-1')
    })

    expect(screen.getByText(/somente leitura/i)).toBeDefined()

    const epiSelect = screen.getByLabelText('Modelo do módulo EPI') as HTMLSelectElement
    const qualitySelect = screen.getByLabelText('Modelo do módulo Qualidade') as HTMLSelectElement
    const countingSelect = screen.getByLabelText('Modelo do módulo Contagem') as HTMLSelectElement
    expect(epiSelect.disabled).toBe(true)
    expect(qualitySelect.disabled).toBe(true)
    expect(countingSelect.disabled).toBe(true)

    fireEvent.change(epiSelect, { target: { value: 'model-1' } })
    expect(mocks.setCameraModel).not.toHaveBeenCalled()
  })

  it('viewer também vê os selects desabilitados', async () => {
    mocks.isAdmin = false
    render(<CameraModelAssignment cameraId="cam-1" />)

    await waitFor(() => {
      expect(screen.getByText(/somente leitura/i)).toBeDefined()
    })
    const epiSelect = screen.getByLabelText('Modelo do módulo EPI') as HTMLSelectElement
    expect(epiSelect.disabled).toBe(true)
  })

  // task-083: backend efetivo (RF-DETR/YOLOX) por câmera precisa aparecer na UI.
  it('mostra o badge do backend efetivo (RF-DETR) quando a câmera tem modelo atribuído', async () => {
    mocks.getCameraModels.mockResolvedValue({
      status: 'success',
      data: { camera_id: 'cam-1', models: { epi: 'model-1', quality: null, counting: null } },
    })
    mocks.listModels.mockResolvedValue({
      status: 'success',
      data: { models: [{ id: 'model-1', name: 'best_v1', map50: 0.8, framework: 'rfdetr' }] },
    })

    render(<CameraModelAssignment cameraId="cam-1" />)

    await waitFor(() => {
      expect(screen.getByLabelText('Modelo do módulo EPI')).toBeDefined()
    })
    expect(screen.getByText('RF-DETR')).toBeDefined()
  })

  it('não mostra badge quando a câmera usa o modelo padrão (sem atribuição)', async () => {
    mocks.listModels.mockResolvedValue({
      status: 'success',
      data: { models: [{ id: 'model-1', name: 'best_v1', map50: 0.8, framework: 'yolox' }] },
    })

    render(<CameraModelAssignment cameraId="cam-1" />)

    await waitFor(() => {
      expect(screen.getByLabelText('Modelo do módulo EPI')).toBeDefined()
    })
    expect(screen.queryByText('YOLOX')).toBeNull()
  })

  it('troca o badge sem restart quando o admin reatribui de YOLOX para RF-DETR', async () => {
    mocks.getCameraModels.mockResolvedValue({
      status: 'success',
      data: { camera_id: 'cam-1', models: { epi: 'model-yolox', quality: null, counting: null } },
    })
    mocks.listModels.mockResolvedValue({
      status: 'success',
      data: {
        models: [
          { id: 'model-yolox', name: 'yolox_v1', framework: 'yolox' },
          { id: 'model-rfdetr', name: 'rfdetr_v1', framework: 'rfdetr' },
        ],
      },
    })
    mocks.setCameraModel.mockResolvedValue({
      status: 'success',
      data: { camera_id: 'cam-1', models: { epi: 'model-rfdetr', quality: null, counting: null } },
    })

    render(<CameraModelAssignment cameraId="cam-1" />)

    await waitFor(() => expect(screen.getByText('YOLOX')).toBeDefined())

    const epiSelect = screen.getByLabelText('Modelo do módulo EPI') as HTMLSelectElement
    fireEvent.change(epiSelect, { target: { value: 'model-rfdetr' } })

    await waitFor(() => {
      expect(screen.getByText('RF-DETR')).toBeDefined()
    })
    expect(screen.queryByText('YOLOX')).toBeNull()
  })

  describe('gate Funcional/Parcial/Não avaliado (modelo-por-câmera)', () => {
    it('modelo Parcial aparece desabilitado no seletor, com o motivo visível', async () => {
      mocks.listModels.mockResolvedValue({
        status: 'success',
        data: {
          models: [{
            id: 'model-1', name: 'best_v1',
            eval_status: 'parcial',
            eval_motivo: 'Avaliado, mas sem imagens de validação suficientes para: oculos.',
          }],
        },
      })

      render(<CameraModelAssignment cameraId="cam-1" />)
      const epiSelect = await screen.findByLabelText('Modelo do módulo EPI') as HTMLSelectElement
      const opt = Array.from(epiSelect.options).find(o => o.value === 'model-1')!
      expect(opt.disabled).toBe(true)
      expect(opt.title).toMatch(/oculos/)
      expect(opt.textContent).toMatch(/Parcial/)
    })

    it('modelo Não avaliado também aparece desabilitado', async () => {
      mocks.listModels.mockResolvedValue({
        status: 'success',
        data: {
          models: [{
            id: 'model-1', name: 'best_v1',
            eval_status: 'nao_avaliado',
            eval_motivo: 'Este modelo nunca foi avaliado.',
          }],
        },
      })

      render(<CameraModelAssignment cameraId="cam-1" />)
      const epiSelect = await screen.findByLabelText('Modelo do módulo EPI') as HTMLSelectElement
      const opt = Array.from(epiSelect.options).find(o => o.value === 'model-1')!
      expect(opt.disabled).toBe(true)
      expect(opt.textContent).toMatch(/Não avaliado/)
      // mAP@50 nunca medido — "—", nunca "0%" fingido (LEI DA CASA).
      expect(opt.textContent).not.toMatch(/mAP50/)
    })

    it('modelo Funcional aparece habilitado, com o mAP@50 real e o n ao lado', async () => {
      mocks.listModels.mockResolvedValue({
        status: 'success',
        data: {
          models: [{
            id: 'model-1', name: 'best_v1',
            eval_status: 'funcional', eval_map50: 0.762, eval_images_evaluated: 232,
          }],
        },
      })

      render(<CameraModelAssignment cameraId="cam-1" />)
      const epiSelect = await screen.findByLabelText('Modelo do módulo EPI') as HTMLSelectElement
      const opt = Array.from(epiSelect.options).find(o => o.value === 'model-1')!
      expect(opt.disabled).toBe(false)
      expect(opt.textContent).toBe('best_v1 (mAP50 76.2% (n=232))')
    })
  })

  describe('anti-vazamento de stack interno (política F5-LEVE)', () => {
    // Forma real de um modelo "não rebatizado": name/framework internos,
    // display_name ainda NULL (ninguém atribuiu na tela de rebranding).
    const MODELO_INTERNO = {
      id: 'model-1', name: 'YOLO26 yolo26n - Job abc12345', framework: 'yolox',
      map50: 0.8, display_name: null as string | null,
    }

    it('não-superadmin: nome interno e framework NUNCA aparecem — cai em "Logikos"', async () => {
      mocks.isSuperAdmin = false
      mocks.getCameraModels.mockResolvedValue({
        status: 'success',
        data: { camera_id: 'cam-1', models: { epi: 'model-1', quality: null, counting: null } },
      })
      mocks.listModels.mockResolvedValue({ status: 'success', data: { models: [MODELO_INTERNO] } })

      render(<CameraModelAssignment cameraId="cam-1" />)

      const epiSelect = await screen.findByLabelText('Modelo do módulo EPI') as HTMLSelectElement
      const opt = Array.from(epiSelect.options).find(o => o.value === 'model-1')!
      expect(opt.textContent).toBe('Logikos (mAP50 80%)')
      expect(document.body.innerHTML).not.toMatch(/yolo|rf-?detr|onnx/i)
    })

    it('não-superadmin com display_name atribuído: mostra o nome escolhido para o cliente', async () => {
      mocks.isSuperAdmin = false
      mocks.listModels.mockResolvedValue({
        status: 'success',
        data: { models: [{ ...MODELO_INTERNO, display_name: 'Logikos V1' }] },
      })

      render(<CameraModelAssignment cameraId="cam-1" />)

      const epiSelect = await screen.findByLabelText('Modelo do módulo EPI') as HTMLSelectElement
      const opt = Array.from(epiSelect.options).find(o => o.value === 'model-1')!
      expect(opt.textContent).toBe('Logikos V1 (mAP50 80%)')
    })

    it('superadmin: continua vendo nome e framework internos — não regressão da engenharia', async () => {
      mocks.isSuperAdmin = true
      mocks.getCameraModels.mockResolvedValue({
        status: 'success',
        data: { camera_id: 'cam-1', models: { epi: 'model-1', quality: null, counting: null } },
      })
      mocks.listModels.mockResolvedValue({ status: 'success', data: { models: [MODELO_INTERNO] } })

      render(<CameraModelAssignment cameraId="cam-1" />)

      const epiSelect = await screen.findByLabelText('Modelo do módulo EPI') as HTMLSelectElement
      const opt = Array.from(epiSelect.options).find(o => o.value === 'model-1')!
      expect(opt.textContent).toBe(`${MODELO_INTERNO.name} (mAP50 80%)`)
      expect(screen.getByText('YOLOX')).toBeDefined()
    })
  })
})
