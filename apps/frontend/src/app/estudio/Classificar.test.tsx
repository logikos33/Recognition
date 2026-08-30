/**
 * O que esta tela não pode errar:
 *
 *  · perder o deep-link `?camera=`/`?classe=` da matriz de Cobertura;
 *  · aceitar `?classe=` inventado (não-numérico) como se fosse válido;
 *  · "Ajustar" abrir um canvas próprio em vez do `AnnotationStudio` já
 *    existente (mesma conexão que `TrainingPage` usa).
 */
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const navigateMock = vi.hoisted(() => vi.fn())
vi.mock('react-router-dom', async () => {
  const real = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...real, useNavigate: () => navigateMock }
})

interface PropsVistas {
  initialCameraId?: string | null
  initialClassId?: number | null
  onOpenAdjust: (frames: unknown[], index: number) => void
}

const vistas = vi.hoisted(() => ({ classificador: null as PropsVistas | null }))
vi.mock('../../components/annotation/CropClassifier', () => ({
  CropClassifier: (props: PropsVistas) => {
    vistas.classificador = props
    return (
      <button onClick={() => props.onOpenAdjust([{ id: 'f1' }], 0)}>ajustar</button>
    )
  },
}))

interface PropsEstudio {
  onExit: () => void
  onExitToProposals?: () => void
}

const estudio = vi.hoisted(() => ({ props: null as PropsEstudio | null }))
vi.mock('../../components/annotation/AnnotationStudio', () => ({
  AnnotationStudio: (props: PropsEstudio) => {
    estudio.props = props
    return (
      <div>
        estudio-aberto
        <button onClick={props.onExit}>sair-do-estudio</button>
        <button onClick={props.onExitToProposals}>sair-para-propostas</button>
      </div>
    )
  },
}))

import { Classificar } from './Classificar'

function monta(url = '/novo/estudio/classificar') {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <Classificar />
    </MemoryRouter>,
  )
}

describe('Classificar (recorte a recorte do Estúdio)', () => {
  beforeEach(() => {
    vistas.classificador = null
    estudio.props = null
    navigateMock.mockReset()
  })

  it('sem query string: foco vazio (nenhum deep-link herdado por engano)', () => {
    monta()
    expect(vistas.classificador?.initialCameraId).toBeNull()
    expect(vistas.classificador?.initialClassId).toBeNull()
  })

  it('?camera= vira initialCameraId', () => {
    monta('/novo/estudio/classificar?camera=cam-9')
    expect(vistas.classificador?.initialCameraId).toBe('cam-9')
  })

  it('?camera=&classe= viram foco completo', () => {
    monta('/novo/estudio/classificar?camera=cam-9&classe=3')
    expect(vistas.classificador?.initialCameraId).toBe('cam-9')
    expect(vistas.classificador?.initialClassId).toBe(3)
  })

  it('?classe= inventado (não-numérico) NÃO vira classe', () => {
    monta('/novo/estudio/classificar?camera=cam-9&classe=hackeado')
    expect(vistas.classificador?.initialClassId).toBeNull()
  })

  it('"Ajustar" abre o AnnotationStudio já existente; sair volta ao classificador', () => {
    monta()
    fireEvent.click(screen.getByText('ajustar'))
    expect(screen.getByText('estudio-aberto')).toBeTruthy()
    fireEvent.click(screen.getByText('sair-do-estudio'))
    expect(screen.queryByText('estudio-aberto')).toBeNull()
    expect(screen.getByText('ajustar')).toBeTruthy()
  })

  it('"Ajustar" → sair para propostas navega para /estudio/dados?status=proposta_pendente', () => {
    monta()
    fireEvent.click(screen.getByText('ajustar'))
    fireEvent.click(screen.getByText('sair-para-propostas'))
    expect(navigateMock).toHaveBeenCalledWith('/estudio/dados?status=proposta_pendente')
  })
})
