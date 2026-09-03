/**
 * O que esta tela não pode errar:
 *
 *  · marcar um módulo tem de MANDAR O CONJUNTO NOVO. Um teste que só confere
 *    "chamou o PUT" passa com o conjunto antigo no corpo — por isso cada
 *    asserção olha `modules` de verdade, e `alternar()` é testada sozinha;
 *  · a ação em massa tem de ir num PUT SÓ com todas as câmeras marcadas. N
 *    requisições paralelas já estouraram o pool de conexões da API nas 28
 *    câmeras do RVB (o mesmo motivo que criou `/cameras/model-config`);
 *  · a câmera SEM MÓDULO tem de aparecer e ter saída. É o estado inicial de
 *    100% do parque no dia do deploy (a migration 134 não faz backfill) — se
 *    ela sumir ou não for resolvível, a tela inteira não serve para nada;
 *  · falha ao salvar tem de DESFAZER o otimismo. Uma tela que continua
 *    mostrando a marcação que o banco recusou é o defeito que ela veio
 *    consertar, só que na outra ponta;
 *  · nenhum `module_code` na tela — quem usa é o dono da fábrica.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const get = vi.fn()
const put = vi.fn()
vi.mock('../../services/api', () => ({
  api: {
    get: (...a: unknown[]) => get(...a),
    put: (...a: unknown[]) => put(...a),
  },
}))

const auth = vi.hoisted(() => ({
  can: ((_p: string) => true) as (p: string) => boolean,
  isSuperAdmin: false,
}))
vi.mock('../../hooks/useAuth', () => ({ useAuth: () => auth }))

const toastOk = vi.fn()
const toastErro = vi.fn()
vi.mock('../../components/ui/Toast/useToast', () => ({
  useToast: () => ({ success: toastOk, error: toastErro, warning: vi.fn(), info: vi.fn() }),
}))

import { CamerasPorModulo, alternar, semModulo } from './CamerasPorModulo'

// ── fixtures: o formato real de GET /api/cameras/modules ────────────────────

const camera = (id: string, name: string, modules: string[] = []) => ({
  id,
  name,
  location: null,
  is_active: true,
  modules,
})

const envelope = (cameras: unknown[], modules_enabled = ['epi', 'quality', 'counting']) => ({
  success: true,
  data: { cameras, modules_enabled },
})

/** O parque da RVB como ele nasce: tudo sem módulo declarado. */
const PARQUE = [
  camera('c1', 'Corredor Segurança do trabalho'),
  camera('c2', 'Qualidade 06'),
  camera('c3', 'Estacionamento Motos'),
]

beforeEach(() => {
  get.mockReset()
  put.mockReset()
  toastOk.mockReset()
  toastErro.mockReset()
  auth.can = () => true
  put.mockResolvedValue({ success: true, data: { assignments: {} } })
})

// ── conta pura ──────────────────────────────────────────────────────────────

describe('alternar', () => {
  it('acrescenta o que não estava e tira o que estava — N:N, não troca', () => {
    expect(alternar(['epi'], 'quality')).toEqual(['epi', 'quality'])
    expect(alternar(['epi', 'quality'], 'epi')).toEqual(['quality'])
    expect(alternar([], 'epi')).toEqual(['epi'])
  })

  it('desmarcar o último deixa lista vazia — "sem uso" é estado, não erro', () => {
    expect(alternar(['epi'], 'epi')).toEqual([])
  })
})

describe('semModulo', () => {
  it('só as que ninguém declarou', () => {
    const lista = [camera('a', 'A', ['epi']), camera('b', 'B')]
    expect(semModulo(lista).map((c) => c.name)).toEqual(['B'])
  })
})

// ── a tela ──────────────────────────────────────────────────────────────────

describe('CamerasPorModulo', () => {
  it('renderiza a lista de câmeras do tenant', async () => {
    get.mockResolvedValue(envelope(PARQUE))
    render(<CamerasPorModulo />)
    expect(await screen.findByText('Corredor Segurança do trabalho')).toBeTruthy()
    expect(screen.getByText('Qualidade 06')).toBeTruthy()
    expect(screen.getByText('Estacionamento Motos')).toBeTruthy()
    expect(get).toHaveBeenCalledWith('/cameras/modules')
  })

  it('fala português de gente — nenhum código de módulo na tela', async () => {
    get.mockResolvedValue(envelope([camera('c1', 'Guarita', ['counting'])]))
    const { container } = render(<CamerasPorModulo />)
    await screen.findByText('Guarita')
    const texto = container.textContent ?? ''
    expect(texto).not.toContain('module_code')
    expect(texto).not.toContain('counting')
    expect(texto).toContain('Carga')
  })

  it('marcar um módulo manda o CONJUNTO NOVO da câmera', async () => {
    get.mockResolvedValue(envelope([camera('c2', 'Qualidade 06')]))
    render(<CamerasPorModulo />)
    await screen.findByText('Qualidade 06')

    fireEvent.click(screen.getByLabelText('Qualidade em Qualidade 06'))

    await waitFor(() => expect(put).toHaveBeenCalledTimes(1))
    expect(put).toHaveBeenCalledWith('/cameras/modules', {
      camera_ids: ['c2'],
      modules: ['quality'],
    })
  })

  it('marcar um SEGUNDO módulo acumula — a câmera serve os dois (N:N)', async () => {
    get.mockResolvedValue(envelope([camera('c2', 'Qualidade 01 EPI', ['epi'])]))
    render(<CamerasPorModulo />)
    await screen.findByText('Qualidade 01 EPI')

    fireEvent.click(screen.getByLabelText('Qualidade em Qualidade 01 EPI'))

    await waitFor(() => expect(put).toHaveBeenCalled())
    expect(put.mock.calls[0][1]).toEqual({ camera_ids: ['c2'], modules: ['epi', 'quality'] })
  })

  it('desmarcar tira só aquele módulo e mantém o resto', async () => {
    get.mockResolvedValue(envelope([camera('c2', 'Qualidade 01 EPI', ['epi', 'quality'])]))
    render(<CamerasPorModulo />)
    await screen.findByText('Qualidade 01 EPI')

    fireEvent.click(screen.getByLabelText('EPI · Segurança em Qualidade 01 EPI'))

    await waitFor(() => expect(put).toHaveBeenCalled())
    expect(put.mock.calls[0][1]).toEqual({ camera_ids: ['c2'], modules: ['quality'] })
  })

  it('ação em massa aplica a VÁRIAS câmeras num PUT só', async () => {
    get.mockResolvedValue(envelope(PARQUE))
    render(<CamerasPorModulo />)
    await screen.findByText('Qualidade 06')

    fireEvent.click(screen.getByLabelText('Marcar todas as câmeras da lista'))
    fireEvent.click(screen.getByLabelText('EPI · Segurança para as câmeras marcadas'))
    fireEvent.click(screen.getByRole('button', { name: 'Aplicar a 3' }))

    await waitFor(() => expect(put).toHaveBeenCalledTimes(1))
    expect(put).toHaveBeenCalledWith('/cameras/modules', {
      camera_ids: ['c1', 'c2', 'c3'],
      modules: ['epi'],
    })
  })

  it('em massa com dois módulos marcados manda os dois', async () => {
    get.mockResolvedValue(envelope(PARQUE))
    render(<CamerasPorModulo />)
    await screen.findByText('Qualidade 06')

    fireEvent.click(screen.getByLabelText('Marcar Qualidade 06'))
    fireEvent.click(screen.getByLabelText('EPI · Segurança para as câmeras marcadas'))
    fireEvent.click(screen.getByLabelText('Qualidade para as câmeras marcadas'))
    fireEvent.click(screen.getByRole('button', { name: 'Aplicar a 1' }))

    await waitFor(() => expect(put).toHaveBeenCalled())
    expect(put.mock.calls[0][1]).toEqual({ camera_ids: ['c2'], modules: ['epi', 'quality'] })
  })

  // ── SEM BECO SEM SAÍDA ────────────────────────────────────────────────────

  it('conta e mostra as câmeras sem uso definido', async () => {
    get.mockResolvedValue(envelope([camera('c1', 'A', ['epi']), camera('c2', 'B'), camera('c3', 'C')]))
    render(<CamerasPorModulo />)
    await screen.findByText('A')
    expect(screen.getByText('2')).toBeTruthy()
    expect(screen.getAllByText('ainda sem uso definido')).toHaveLength(2)
  })

  it('"Resolver essas agora" seleciona as sem uso e a massa as resolve', async () => {
    get.mockResolvedValue(envelope([camera('c1', 'A', ['epi']), camera('c2', 'B'), camera('c3', 'C')]))
    render(<CamerasPorModulo />)
    await screen.findByText('A')

    fireEvent.click(screen.getByRole('button', { name: 'Resolver essas agora' }))
    // A que já tinha uso NÃO entra na seleção — só as pendentes.
    fireEvent.click(screen.getByLabelText('EPI · Segurança para as câmeras marcadas'))
    fireEvent.click(screen.getByRole('button', { name: 'Aplicar a 2' }))

    await waitFor(() => expect(put).toHaveBeenCalled())
    expect(put.mock.calls[0][1]).toEqual({ camera_ids: ['c2', 'c3'], modules: ['epi'] })
  })

  it('resolvida a última pendência, a lista filtrada oferece a volta', async () => {
    get.mockResolvedValue(envelope([camera('c1', 'A', ['epi'])]))
    render(<CamerasPorModulo />)
    await screen.findByText('A')

    fireEvent.click(screen.getByLabelText('Mostrar só as câmeras sem uso definido'))
    expect(screen.getByText(/Todas as câmeras já têm uso definido/)).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Ver todas' }))
    expect(screen.getByText('A')).toBeTruthy()
  })

  // ── estados que a tela encontra de verdade ────────────────────────────────

  it('nenhuma câmera cadastrada — vazio explicado, não tela branca', async () => {
    get.mockResolvedValue(envelope([]))
    render(<CamerasPorModulo />)
    expect(await screen.findByText('Nenhuma câmera cadastrada')).toBeTruthy()
  })

  it('falha no GET não vira "nenhuma câmera" — diz que não carregou, com retry', async () => {
    get.mockRejectedValue(new Error('timeout'))
    render(<CamerasPorModulo />)
    expect(await screen.findByText('Não deu para carregar as câmeras')).toBeTruthy()
    expect(screen.queryByText('Nenhuma câmera cadastrada')).toBeNull()

    get.mockResolvedValue(envelope(PARQUE))
    fireEvent.click(screen.getByRole('button', { name: 'Tentar novamente' }))
    expect(await screen.findByText('Qualidade 06')).toBeTruthy()
  })

  it('falha ao salvar DESFAZ a marcação e avisa — a tela não pode mentir', async () => {
    get.mockResolvedValue(envelope([camera('c2', 'Qualidade 06')]))
    put.mockRejectedValue(new Error('500'))
    render(<CamerasPorModulo />)
    await screen.findByText('Qualidade 06')

    const chip = screen.getByLabelText('Qualidade em Qualidade 06')
    fireEvent.click(chip)

    await waitFor(() => expect(toastErro).toHaveBeenCalled())
    expect(screen.getByLabelText('Qualidade em Qualidade 06').getAttribute('aria-pressed')).toBe('false')
    expect(screen.getByText('ainda sem uso definido')).toBeTruthy()
  })

  it('tenant sem área liberada explica em vez de mostrar linha vazia', async () => {
    get.mockResolvedValue(envelope(PARQUE, []))
    render(<CamerasPorModulo />)
    await screen.findByText('Qualidade 06')
    expect(screen.getByText(/não tem nenhuma área liberada/)).toBeTruthy()
  })

  it('módulo gravado que o tenant não tem mais continua visível e removível', async () => {
    get.mockResolvedValue(envelope([camera('c2', 'Qualidade 06', ['quality'])], ['epi']))
    render(<CamerasPorModulo />)
    await screen.findByText('Qualidade 06')

    const orfa = screen.getByLabelText('Qualidade em Qualidade 06 — área não contratada')
    expect(orfa.getAttribute('aria-pressed')).toBe('true')
    fireEvent.click(orfa)
    await waitFor(() => expect(put).toHaveBeenCalled())
    expect(put.mock.calls[0][1]).toEqual({ camera_ids: ['c2'], modules: [] })
  })

  it('sem permissão: lê, não escreve', async () => {
    auth.can = () => false
    get.mockResolvedValue(envelope([camera('c2', 'Qualidade 06')]))
    render(<CamerasPorModulo />)
    await screen.findByText('Qualidade 06')

    const chip = screen.getByLabelText('Qualidade em Qualidade 06') as HTMLButtonElement
    expect(chip.disabled).toBe(true)
    fireEvent.click(chip)
    expect(put).not.toHaveBeenCalled()
    expect(screen.getByText(/só pode ver esta tela/)).toBeTruthy()
  })

  it('não promete efeito que ainda não tem sobre a coleta', async () => {
    get.mockResolvedValue(envelope(PARQUE))
    render(<CamerasPorModulo />)
    await screen.findByText('Qualidade 06')
    const ressalva = screen.getByRole('note').textContent ?? ''
    expect(ressalva).toMatch(/coleta de imagens/)
    expect(ressalva).toMatch(/ainda\s*não/)
  })
})
