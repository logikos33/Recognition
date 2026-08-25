/**
 * O motivo do veredito chega ao backend.
 *
 * A rota `POST /verification/:id/review` e o `VerificationService` SEMPRE
 * aceitaram `reason`. A tela é que não coletava — `darVeredito` mandava só
 * `{ verdict }`, e a coluna `verification_reason` ficava NULL em 100% dos
 * vereditos humanos.
 *
 * Por que importa: um `reject` sozinho é AMBÍGUO. "A pessoa estava de
 * máscara", "a caixa pegou a pessoa errada" e "não dava para ver" levam a
 * ações OPOSTAS — recalibrar limiar, corrigir a caixa, abster. Sem o motivo, o
 * falso positivo não ensina nada além de "erramos", e é justamente esse campo
 * que alimenta a recalibração e o classificador de recorte.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'

// `vi.hoisted`: o `vi.mock` é ICADO acima das constantes do módulo, então um
// `const` normal não existe ainda quando a fábrica roda.
const { post, get } = vi.hoisted(() => ({
  post: vi.fn(),
  get: vi.fn(),
}))

const ALERTA = {
  id: 'a1', camera_id: 'c1', camera_name: 'Entrada',
  timestamp: '2026-08-25T10:00:00Z',
  violations: [{ class: 'Sem mascara', confidence: 0.7 }],
  confidence: 0.7, acknowledged: false, evidence_url: null,
  verification_verdict: null, verified_by: null,
}

vi.mock('../../services/api', () => ({ api: { get, post, put: vi.fn(), patch: vi.fn() } }))
vi.mock('react-router-dom', async () => {
  const real = await vi.importActual<Record<string, unknown>>('react-router-dom')
  return { ...real, useParams: () => ({ alertId: 'a1' }), useNavigate: () => vi.fn() }
})

import { MemoryRouter } from 'react-router-dom'

import AlertDetailPage from '../../pages/epi/AlertDetailPage'

function montar() {
  return render(
    <MemoryRouter>
      <AlertDetailPage />
    </MemoryRouter>,
  )
}

describe('motivo do veredito', () => {
  beforeEach(() => {
    post.mockReset().mockResolvedValue({ data: {} })
    get.mockReset().mockResolvedValue({ data: { alert: ALERTA } })
  })

  it('o campo de motivo existe na tela', async () => {
    montar()
    expect(await screen.findByLabelText('Motivo do veredito')).toBeTruthy()
  })

  it('o motivo digitado vai junto do veredito', async () => {
    montar()
    const campo = await screen.findByLabelText('Motivo do veredito')
    fireEvent.change(campo, { target: { value: 'a caixa pegou a luva do outro' } })
    fireEvent.click(screen.getByRole('button', { name: /Errado/i }))

    await waitFor(() => expect(post).toHaveBeenCalled())
    const [rota, corpo] = post.mock.calls[0]
    expect(rota).toContain('/verification/a1/review')
    expect(corpo).toEqual({
      verdict: 'reject',
      reason: 'a caixa pegou a luva do outro',
    })
  })

  it('motivo vazio NÃO manda a chave — não grava string vazia', async () => {
    montar()
    await screen.findByLabelText('Motivo do veredito')
    fireEvent.click(screen.getByRole('button', { name: /Confirmar/i }))

    await waitFor(() => expect(post).toHaveBeenCalled())
    const corpo = post.mock.calls[0][1] as Record<string, unknown>
    expect(corpo).toEqual({ verdict: 'approve' })
    expect('reason' in corpo).toBe(false)
  })

  it('só espaço em branco também não vira motivo', async () => {
    montar()
    const campo = await screen.findByLabelText('Motivo do veredito')
    fireEvent.change(campo, { target: { value: '    ' } })
    fireEvent.click(screen.getByRole('button', { name: /Confirmar/i }))

    await waitFor(() => expect(post).toHaveBeenCalled())
    expect('reason' in (post.mock.calls[0][1] as object)).toBe(false)
  })
})
