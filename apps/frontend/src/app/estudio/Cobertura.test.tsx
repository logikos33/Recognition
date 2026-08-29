/**
 * O que esta tela não pode errar: os saltos da matriz (anotar/classificar)
 * têm de virar navegação de rota certa — câmera e classe no lugar certo da
 * query string, sem perder o dado no caminho.
 */
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const navigateMock = vi.hoisted(() => vi.fn())
vi.mock('react-router-dom', async () => {
  const real = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...real, useNavigate: () => navigateMock }
})

interface PropsVistas {
  onAnnotateCamera: (cameraId: string) => void
  onClassifyCell: (cameraId: string, classId?: number) => void
}

const vistas = vi.hoisted(() => ({ matriz: null as PropsVistas | null }))
vi.mock('../../components/training/CoverageMatrix', () => ({
  CoverageMatrix: (props: PropsVistas) => {
    vistas.matriz = props
    return <div>matriz-cobertura</div>
  },
}))

import { Cobertura } from './Cobertura'

function monta() {
  return render(
    <MemoryRouter>
      <Cobertura />
    </MemoryRouter>,
  )
}

describe('Cobertura (matriz classe×câmera do Estúdio)', () => {
  beforeEach(() => {
    navigateMock.mockReset()
    vistas.matriz = null
  })

  it('título "Cobertura" e a matriz embrulhada', () => {
    monta()
    expect(screen.getByText('Cobertura')).toBeTruthy()
    expect(screen.getByText('matriz-cobertura')).toBeTruthy()
  })

  it('célula "anotar" navega para Dados focado na câmera', () => {
    monta()
    vistas.matriz?.onAnnotateCamera('cam-9')
    expect(navigateMock).toHaveBeenCalledWith('/novo/estudio/dados?camera=cam-9')
  })

  it('célula "classificar" com classe navega para Classificar com câmera e classe', () => {
    monta()
    vistas.matriz?.onClassifyCell('cam-9', 3)
    expect(navigateMock).toHaveBeenCalledWith('/novo/estudio/classificar?camera=cam-9&classe=3')
  })

  it('célula "classificar" sem classe (opcional) navega só com a câmera', () => {
    monta()
    vistas.matriz?.onClassifyCell('cam-9')
    expect(navigateMock).toHaveBeenCalledWith('/novo/estudio/classificar?camera=cam-9')
  })
})
