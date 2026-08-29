/**
 * O que esta tela não pode errar:
 *
 *  · aceitar `?status=` inventado da URL (filtro inválido entra em silêncio);
 *  · abrir o estúdio sem congelar a fila / fechar sem recarregar a galeria;
 *  · perder o deep-link `?camera=` que a matriz de cobertura vai usar.
 */
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

interface PropsVistas {
  reloadKey?: number
  statusFilterRequest?: { filter: string; nonce: number } | null
  cameraFocusRequest?: { cameraId: string; nonce: number } | null
  onOpenStudio: (frames: unknown[], index: number, continuacao?: unknown) => void
}

const vistas = vi.hoisted(() => ({ gallery: null as PropsVistas | null }))
vi.mock('../../components/training/TrainingGallery', () => ({
  TrainingGallery: (props: PropsVistas) => {
    vistas.gallery = props
    return (
      <button onClick={() => props.onOpenStudio([{ id: 'f1' }], 0, undefined)}>
        abrir-estudio
      </button>
    )
  },
}))

const estudio = vi.hoisted(() => ({ props: null as { onExit: () => void } | null }))
vi.mock('../../components/annotation/AnnotationStudio', () => ({
  AnnotationStudio: (props: { onExit: () => void }) => {
    estudio.props = props
    return (
      <div>
        estudio-aberto
        <button onClick={props.onExit}>sair-do-estudio</button>
      </div>
    )
  },
}))

vi.mock('../../components/annotation/PropagationStatusBar', () => ({
  PropagationStatusBar: () => <div>barra-propagacao</div>,
}))
vi.mock('../../components/annotation/propagationUi', () => ({
  dismissJob: vi.fn(),
  pickJobToResurface: vi.fn(() => null),
}))
vi.mock('../../services/propagationService', () => ({
  propagationService: { listJobs: vi.fn(async () => []) },
}))

import { Dados } from './Dados'

function monta(url = '/novo/estudio/dados') {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <Dados />
    </MemoryRouter>,
  )
}

describe('Dados (galeria do Estúdio)', () => {
  beforeEach(() => {
    vistas.gallery = null
    estudio.props = null
  })

  it('?camera= vira cameraFocusRequest para a galeria', () => {
    monta('/novo/estudio/dados?camera=cam-77')
    expect(vistas.gallery?.cameraFocusRequest?.cameraId).toBe('cam-77')
  })

  it('?status= válido vira statusFilterRequest', () => {
    monta('/novo/estudio/dados?status=proposta_pendente')
    expect(vistas.gallery?.statusFilterRequest?.filter).toBe('proposta_pendente')
  })

  it('?status= inventado NÃO vira filtro', () => {
    monta('/novo/estudio/dados?status=hackeado')
    expect(vistas.gallery?.statusFilterRequest).toBeNull()
  })

  it('?status= herdado de Object.prototype NÃO vira filtro (toString/valueOf)', () => {
    monta('/novo/estudio/dados?status=toString')
    expect(vistas.gallery?.statusFilterRequest).toBeNull()
  })

  it('abrir o estúdio troca a tela; sair recarrega a galeria (reloadKey)', () => {
    monta()
    expect(vistas.gallery?.reloadKey).toBe(0)
    fireEvent.click(screen.getByText('abrir-estudio'))
    expect(screen.getByText('estudio-aberto')).toBeTruthy()
    fireEvent.click(screen.getByText('sair-do-estudio'))
    expect(screen.queryByText('estudio-aberto')).toBeNull()
    expect(vistas.gallery?.reloadKey).toBe(1)
  })
})
