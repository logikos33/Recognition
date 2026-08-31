/**
 * TrainingGallery — vazio honesto da fila de propostas (contrato A2).
 *
 * Causa provada no navegador (05-propostas-pendentes-passo3c-origem-
 * residual.png): trocar o chip de status NUNCA reseta câmera/origem. Com
 * "Propostas pendentes" + "Origem: Upload" ativos ao mesmo tempo, a busca
 * fica sempre 0 — proposta de IA nasce de nvr/auto, nunca de upload manual
 * (_PENDING_PROPOSAL_CONDITION, backend) — e a tela antiga mentia "fila
 * vazia" sem revelar o filtro escondido que zerou tudo.
 *
 * Cobre: (1) vazio com filtro ativo revela QUAIS filtros e oferece "Limpar
 * filtros"; (2) limpar restaura o resultado; (3) chip "Propostas pendentes"
 * ganha contador (get_facets, aditivo); (4) combinação impossível avisada
 * sem bloquear a escolha.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { TrainingGallery } from './TrainingGallery'

const mocks = vi.hoisted(() => ({ get: vi.fn(), listCameras: vi.fn(), listJobs: vi.fn() }))

vi.mock('../../services/api', () => ({ api: { get: mocks.get, post: vi.fn() } }))
vi.mock('../../services/cameraService', () => ({ cameraService: { list: mocks.listCameras } }))
vi.mock('../../services/searchService', () => ({
  searchService: { listJobs: mocks.listJobs },
}))

const FRAME = {
  id: 'f1',
  video_id: null,
  frame_number: 1,
  filename: 'frame1.jpg',
  is_annotated: false,
  created_at: '2026-08-20T10:00:00Z',
  url: 'https://r2.example/f1.jpg',
  camera_id: null,
  curation_status: 'active' as const,
  provenance: 'proposta' as const,
  annotation_count: 0,
  pending_proposals_count: 2,
  source: 'nvr',
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.listCameras.mockResolvedValue([])
  mocks.listJobs.mockResolvedValue([])
  mocks.get.mockImplementation(async (path: string) => {
    const params = new URLSearchParams(path.split('?')[1] ?? '')
    if (path.startsWith('/training/images/facets')) {
      return {
        data: {
          cameras: [],
          status: { nao_anotado: 0, anotado: 0, duvida: 0, excluida: 0, proposta_pendente: 281 },
        },
      }
    }
    if (path.startsWith('/training/images')) {
      // A ÚNICA combinação que o servidor real devolve 0: pending_review
      // (proposta de IA) + source=upload (nasce de nvr/auto, nunca upload).
      const impossivel = params.get('pending_review') === 'true' && params.get('source') === 'upload'
      if (impossivel) {
        return { data: { frames: [], total: 0, total_pending_proposals: 0, page: 1, page_size: 60, total_pages: 1 } }
      }
      return {
        data: {
          frames: [FRAME],
          total: 281,
          total_pending_proposals: params.get('pending_review') === 'true' ? 349 : 0,
          page: 1,
          page_size: 60,
          total_pages: 5,
        },
      }
    }
    throw new Error(`GET inesperado: ${path}`)
  })
})

describe('TrainingGallery — fila de propostas pendentes', () => {
  it('chip "Propostas pendentes" mostra o contador (facet aditiva, get_facets)', async () => {
    render(<TrainingGallery onOpenStudio={vi.fn()} />)
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Propostas pendentes/ }).textContent).toContain('281'),
    )
  })

  it('filtro residual de Origem esvazia a fila — o vazio revela os filtros e oferece limpar; limpar restaura', async () => {
    render(<TrainingGallery onOpenStudio={vi.fn()} />)
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Propostas pendentes/ }).textContent).toContain('281'),
    )

    // Passo 1: abre a fila de propostas — 281 imagens, como no navegador real.
    fireEvent.click(screen.getByRole('button', { name: /Propostas pendentes/ }))
    await waitFor(() => expect(screen.getByText(/281 imagens/)).toBeDefined())

    // Passo 2: troca Origem para Upload (resíduo de uma seleção anterior,
    // sem trocar de status) — combinação estruturalmente vazia.
    fireEvent.click(screen.getByRole('button', { name: 'Upload' }))

    // Aviso de combinação impossível — não bloqueia, só explica em linguagem
    // de gente por que a fila nunca vai encher assim.
    await waitFor(() =>
      expect(screen.getByText(/nunca de upload manual/)).toBeDefined(),
    )

    // ⛔ Nunca "fila vazia" sozinho — revela EXATAMENTE quais filtros zeraram
    // o resultado e oferece 1 clique pra sair deles.
    await waitFor(() =>
      expect(
        screen.getByText(/Nenhuma imagem com estes filtros: Propostas pendentes \+ Origem: Upload/),
      ).toBeDefined(),
    )
    expect(screen.queryByText(/Fila de aprovação vazia/)).toBeNull()

    // Passo 3: limpar filtros restaura as 281 imagens.
    fireEvent.click(screen.getByRole('button', { name: 'Limpar filtros' }))
    await waitFor(() => expect(screen.getByText('281 imagens')).toBeDefined())
    expect(screen.queryByText(/nunca de upload manual/)).toBeNull()
  })

  it('vazio sem NENHUM filtro ativo continua a mensagem neutra de coleção vazia (não há filtro pra revelar)', async () => {
    mocks.get.mockImplementation(async (path: string) => {
      if (path.startsWith('/training/images/facets')) {
        return { data: { cameras: [], status: { nao_anotado: 0, anotado: 0, duvida: 0, excluida: 0, proposta_pendente: 0 } } }
      }
      return { data: { frames: [], total: 0, total_pending_proposals: 0, page: 1, page_size: 60, total_pages: 1 } }
    })
    render(<TrainingGallery onOpenStudio={vi.fn()} />)
    await waitFor(() =>
      expect(screen.getByText(/Nenhuma imagem ainda\. Faça upload ou colete frames/)).toBeDefined(),
    )
    expect(screen.queryByText(/Limpar filtros/)).toBeNull()
  })
})
