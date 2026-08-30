/**
 * O que esta tela não pode errar:
 *
 *  · ativar pela rota ERRADA (`/training/models/<id>/activate` — alias legado
 *    que não passa pelo gate campeão×desafiante). Só `/v1/models/<id>/activate`
 *    é aceitável;
 *  · duplicar o toast do 409 `eval_rejected` — o `api.ts` (mockado fora daqui)
 *    já mostra a mensagem legível do backend; o componente só não pode
 *    disparar um SEGUNDO toast de erro genérico por cima;
 *  · esconder o modelo ativo ou misturar suas métricas com as de outro.
 */
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const get = vi.fn()
const post = vi.fn()
vi.mock('../../services/api', () => ({
  api: { get: (...a: unknown[]) => get(...a), post: (...a: unknown[]) => post(...a) },
}))

const toast = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }))
vi.mock('../../components/ui/Toast/useToast', () => ({ useToast: () => toast }))

const wizard = vi.hoisted(() => ({
  props: null as { modelId: string; modelName: string; onClose: () => void; onSaved?: () => void } | null,
}))
vi.mock('../../components/scenario/ModelScenarioWizard', () => ({
  ModelScenarioWizard: (props: typeof wizard.props) => {
    wizard.props = props
    return <div>wizard-aberto:{props?.modelId}</div>
  },
}))

import { Modelo } from './Modelo'

/** Forma REAL de `trained_models` que `GET /training/models` devolve (envelope
 * `{success,message,data}` — `.data` já é o array, sem array na raiz). */
const modelo = (extra: Record<string, unknown> = {}) => ({
  id: 'm-1',
  name: 'yolo26n-epi-v11',
  model_path: '/models/m-1.onnx',
  map50: 0.842,
  precision: 0.9,
  recall: 0.77,
  is_active: false,
  created_at: '2026-07-28T10:00:00Z',
  origin: 'vast_ai',
  ...extra,
})

const classe = (extra: Record<string, unknown> = {}) => ({
  id: 1,
  name: 'Capacete',
  color: '#22d3ee',
  ...extra,
})

const responde = (modelos: unknown[], classes: unknown[] = []) =>
  get.mockImplementation((rota: string) => {
    const r = String(rota)
    if (r.includes('/training/models')) return Promise.resolve({ data: modelos })
    if (r.includes('/classes')) return Promise.resolve({ data: classes })
    return Promise.reject(new Error(`rota não mockada: ${r}`))
  })

function monta() {
  return render(
    <MemoryRouter>
      <Modelo />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  get.mockReset()
  post.mockReset()
  toast.success.mockReset()
  toast.error.mockReset()
  wizard.props = null
})

describe('Modelo — estados', () => {
  it('carregando: mostra o loader antes da resposta chegar', () => {
    get.mockReturnValue(new Promise(() => {})) // nunca resolve
    monta()
    expect(screen.getByRole('status')).toBeTruthy()
  })

  it('erro: mostra a rota e o retry refaz a chamada', async () => {
    get.mockRejectedValue(new Error('timeout'))
    monta()
    expect(await screen.findByText(/GET \/api\/training\/models/)).toBeTruthy()
    responde([modelo()])
    fireEvent.click(screen.getByRole('button', { name: /tentar novamente/i }))
    expect(await screen.findByText(/LGKV26n-epi-v11/)).toBeTruthy()
  })

  it('vazio: sem modelo treinado, mostra o EmptyState honesto (sem mock de dado)', async () => {
    responde([])
    monta()
    expect(await screen.findByText(/nenhum modelo treinado ainda/i)).toBeTruthy()
  })
})

describe('Modelo — lista e destaque do ativo', () => {
  it('lista os modelos que o servidor devolve, com apelido LGKV26', async () => {
    responde([modelo(), modelo({ id: 'm-2', name: 'yolo26s-epi-v10' })])
    monta()
    expect(await screen.findByText('LGKV26n-epi-v11')).toBeTruthy()
    expect(screen.getByText('LGKV26s-epi-v10')).toBeTruthy()
  })

  it('modelo ativo aparece destacado, com mAP@50/precisão/cobertura', async () => {
    responde([modelo({ id: 'm-2', is_active: true, map50: 0.9, precision: 0.95, recall: 0.8 })])
    monta()
    expect(await screen.findByText('Modelo ativo')).toBeTruthy()
    // A métrica do ativo some no card de destaque E se repete no card da
    // lista — as duas leituras precisam bater com o MESMO modelo.
    expect(screen.getAllByText('90.0%').length).toBeGreaterThan(0)
    expect(screen.getAllByText('95.0%').length).toBeGreaterThan(0)
    expect(screen.getAllByText('80.0%').length).toBeGreaterThan(0)
    expect(screen.getAllByText(/ativo/i).length).toBeGreaterThan(0)
  })

  it('sem modelo ativo, diz isso em vez de inventar um destaque', async () => {
    responde([modelo({ is_active: false })])
    monta()
    expect(await screen.findByText(/nenhum modelo ativo/i)).toBeTruthy()
  })

  it('lista as classes do tenant com a cor gravada', async () => {
    responde([modelo()], [classe(), classe({ id: 2, name: 'Luva', color: null })])
    monta()
    expect(await screen.findByText('Capacete')).toBeTruthy()
    expect(screen.getByText('Luva')).toBeTruthy()
  })

  it('origem do treino aparece como rótulo pt-BR (não o código cru)', async () => {
    responde([modelo({ origin: 'vast_ai' })])
    monta()
    expect(await screen.findByText('Origem: GPU Vast.ai')).toBeTruthy()
  })

  it('modelo simulado (metrics.simulated=true) mostra o selo de simulação no destaque E no card', async () => {
    responde([modelo({ id: 'm-sim', is_active: true, metrics: { simulated: true } })])
    monta()
    // Selo aparece 2x: no card de destaque "Modelo ativo" e no card da lista
    // (mesmo modelo, is_active=true) — as duas leituras não podem esconder a
    // simulação em nenhuma delas.
    expect((await screen.findAllByText(/SIMULAÇÃO — não é treino real/i)).length).toBe(2)
  })

  it('modelo NÃO simulado não mostra o selo (mutação: remover o guard de isSimulatedArtifact quebra este teste)', async () => {
    responde([modelo({ origin: 'vast_ai', metrics: {} })])
    monta()
    await screen.findByText('LGKV26n-epi-v11')
    expect(screen.queryByText(/SIMULAÇÃO/i)).toBeNull()
  })

  it('dono do modelo aparece com o nome', async () => {
    responde([modelo({ owner_name: 'Vitor Emanuel', owner_email: 'vitor@logikosvision.com.br' })])
    monta()
    expect(await screen.findByText('Dono: Vitor Emanuel')).toBeTruthy()
  })
})

describe('Modelo — ativar', () => {
  it('ativar chama POST /v1/models/<id>/activate — NUNCA o alias /training/models', async () => {
    responde([modelo({ id: 'm-9' })])
    post.mockResolvedValue({ success: true })
    monta()
    fireEvent.click(await screen.findByRole('button', { name: /^ativar$/i }))
    expect(post).toHaveBeenCalledWith('/v1/models/m-9/activate', {})
    expect(post).not.toHaveBeenCalledWith(expect.stringContaining('/training/models'), expect.anything())
    await screen.findByText('LGKV26n-epi-v11') // ainda de pé após o toast de sucesso
    expect(toast.success).toHaveBeenCalledWith('Modelo ativado')
  })

  it('modelo ativo não mostra botão Ativar — já é o corrente', async () => {
    responde([modelo({ is_active: true })])
    monta()
    // Ancora na ação do card (inequívoca) em vez do nome — nome + badge
    // "ativo" dividem o mesmo <span>, e várias ancestrais casam por
    // substring (erro clássico do RTL: "multiple elements").
    await screen.findByRole('button', { name: /configurar cenário/i })
    expect(screen.queryByRole('button', { name: /^ativar$/i })).toBeNull()
  })

  it('409 eval_rejected: NÃO duplica toast — o api.ts global já mostrou a mensagem', async () => {
    responde([modelo({ id: 'm-9' })])
    const erro409 = Object.assign(new Error('Este modelo foi reprovado na avaliação'), { status: 409 })
    post.mockRejectedValue(erro409)
    monta()
    fireEvent.click(await screen.findByRole('button', { name: /^ativar$/i }))
    await new Promise((r) => setTimeout(r, 0))
    expect(toast.error).not.toHaveBeenCalled()
  })

  it('erro diferente de 409 mostra o próprio toast (api.ts não cobre esse caso)', async () => {
    responde([modelo({ id: 'm-9' })])
    post.mockRejectedValue(Object.assign(new Error('falha de rede'), { status: 500 }))
    monta()
    fireEvent.click(await screen.findByRole('button', { name: /^ativar$/i }))
    await new Promise((r) => setTimeout(r, 0))
    expect(toast.error).toHaveBeenCalledWith('falha de rede')
  })
})

describe('Modelo — cenário e link de classes', () => {
  it('Configurar cenário abre o ModelScenarioWizard com o modelo certo', async () => {
    responde([modelo({ id: 'm-7', name: 'yolo26m-epi-v12' })])
    monta()
    fireEvent.click(await screen.findByRole('button', { name: /configurar cenário/i }))
    expect(await screen.findByText('wizard-aberto:m-7')).toBeTruthy()
    expect(wizard.props?.modelName).toBe('LGKV26m-epi-v12')
  })

  it('link "Configurar Classes" vai para /estudio/classes (rotaNova)', async () => {
    responde([modelo()])
    monta()
    const link = (await screen.findByRole('link', { name: /configurar classes/i })) as HTMLAnchorElement
    expect(link.getAttribute('href')).toBe('/estudio/classes')
  })
})
