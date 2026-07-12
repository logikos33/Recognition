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
  useAuth: () => ({ isAdmin: mocks.isAdmin }),
}))

beforeEach(() => {
  vi.clearAllMocks()
  mocks.isAdmin = true
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
})
