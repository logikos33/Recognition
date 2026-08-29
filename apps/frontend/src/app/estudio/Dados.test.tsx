/**
 * O que esta tela não pode errar:
 *
 *  · aceitar `?status=` inventado da URL (filtro inválido entra em silêncio);
 *  · abrir o estúdio sem congelar a fila / fechar sem recarregar a galeria;
 *  · perder o deep-link `?camera=` que a matriz de cobertura vai usar.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

interface Continuacao {
  buscarPagina: (pagina: number) => Promise<{ frames: { id: string }[]; temMais: boolean }>
  paginaInicial: number
  totalDoFiltro: number
}

interface PropsVistas {
  reloadKey?: number
  statusFilterRequest?: { filter: string; nonce: number } | null
  cameraFocusRequest?: { cameraId: string; nonce: number } | null
  onOpenStudio: (frames: { id: string }[], index: number, continuacao?: Continuacao) => void
}

const vistas = vi.hoisted(() => ({
  gallery: null as PropsVistas | null,
  continuacaoFake: undefined as Continuacao | undefined,
}))
vi.mock('../../components/training/TrainingGallery', () => ({
  TrainingGallery: (props: PropsVistas) => {
    vistas.gallery = props
    return (
      <>
        <button onClick={() => props.onOpenStudio([{ id: 'f1' }], 0, undefined)}>
          abrir-estudio
        </button>
        <button onClick={() => props.onOpenStudio([{ id: 'f1' }], 0, vistas.continuacaoFake)}>
          abrir-estudio-com-fila
        </button>
      </>
    )
  },
}))

const estudio = vi.hoisted(() => ({
  props: null as { frames: { id: string }[]; onExit: () => void; onNearEnd?: () => void } | null,
}))
vi.mock('../../components/annotation/AnnotationStudio', () => ({
  AnnotationStudio: (props: { frames: { id: string }[]; onExit: () => void; onNearEnd?: () => void }) => {
    estudio.props = props
    return (
      <div>
        estudio-aberto
        <button onClick={props.onExit}>sair-do-estudio</button>
        {props.onNearEnd && <button onClick={props.onNearEnd}>perto-do-fim</button>}
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
    vistas.continuacaoFake = undefined
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

  it('reabastecimento: dedup de página repetida e esgota após 2 secas seguidas', async () => {
    const buscarPagina = vi
      .fn<Continuacao['buscarPagina']>()
      // pagina 1: só repete o que já está na fila → seca 1 (mas temMais=true, não esgota)
      .mockResolvedValueOnce({ frames: [{ id: 'f1' }], temMais: true })
      // pagina 2: repete de novo, agora sem temMais → 2ª seca → esgota
      .mockResolvedValueOnce({ frames: [{ id: 'f1' }], temMais: false })
      // nunca deveria ser chamada: já esgotado
      .mockResolvedValueOnce({ frames: [{ id: 'f2' }], temMais: true })
    vistas.continuacaoFake = { buscarPagina, paginaInicial: 1, totalDoFiltro: 5 }

    monta()
    fireEvent.click(screen.getByText('abrir-estudio-com-fila'))
    expect(screen.getByText('estudio-aberto')).toBeTruthy()

    fireEvent.click(screen.getByText('perto-do-fim'))
    await waitFor(() => expect(buscarPagina).toHaveBeenCalledTimes(1))
    expect(buscarPagina).toHaveBeenNthCalledWith(1, 1)
    expect(estudio.props?.frames).toHaveLength(1) // dedup: f1 repetido não duplica

    fireEvent.click(screen.getByText('perto-do-fim'))
    await waitFor(() => expect(buscarPagina).toHaveBeenCalledTimes(2))
    expect(buscarPagina).toHaveBeenNthCalledWith(2, 2)

    // esgotado: a 3ª chamada não deve nem tentar buscar mais.
    fireEvent.click(screen.getByText('perto-do-fim'))
    await new Promise((r) => setTimeout(r, 0))
    expect(buscarPagina).toHaveBeenCalledTimes(2)
    expect(estudio.props?.frames).toHaveLength(1)
  })
})
