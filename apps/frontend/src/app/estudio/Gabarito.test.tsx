/**
 * O que esta tela não pode errar:
 *
 *  · PERDER RESPOSTA. É o defeito que a inutiliza: o dono toca SIM, a tela
 *    avança, e o veredito nunca existiu. Em rede móvel isso acontece calado —
 *    por isso os testes de rede caída/voltando são os mais longos daqui;
 *  · reduzir os três estados a dois. Sem "não sei" quem julga chuta, e o
 *    gabarito passa a medir o chute;
 *  · esquecer o atalho "não há pessoa": ele responde TODAS as classes de uma
 *    vez com 'nao' e carimba o motivo. Sem ele o dono gasta 3+ toques numa
 *    imagem que não decide nada;
 *  · inventar a ordem da fila. A ordem vem do backend e a tela obedece;
 *  · perder o lugar ao fechar e reabrir — em 246 quadros, recomeçar do zero é
 *    perder a sessão inteira;
 *  · virar editor de caixa. Nenhum canvas, nenhum retângulo: o gabarito do
 *    A/B é por IMAGEM (ab_ausencia.py), e caixa só serviria para treinar —
 *    coisa que estes quadros nunca farão (dataset_role='holdout').
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const get = vi.fn()
const put = vi.fn()
vi.mock('../../services/api', () => ({
  api: {
    get: (...a: unknown[]) => get(...a),
    put: (...a: unknown[]) => put(...a),
  },
  API_BASE: '/api',
}))

const auth = vi.hoisted(() => ({ can: ((_p: string) => true) as (p: string) => boolean }))
vi.mock('../../hooks/useAuth', () => ({ useAuth: () => auth }))

import { Gabarito } from './Gabarito'
import { aplicarResposta, pendentes, semear } from './filaGabarito'

/**
 * Storage de verdade em memória — mesmo padrão de `AoVivo.test.tsx`.
 *
 * Não é frescura de isolamento: a tela GRAVA e RELÊ (é o que faz a resposta
 * sobreviver à rede caída e ao fechar/reabrir), então um stub que só finge
 * gravar deixaria passar exatamente o defeito que estes testes existem para
 * pegar. Uma instância por teste = estado limpo entre casos, persistente
 * dentro do caso — que é o que "fechar e reabrir" precisa.
 */
class MemoriaStorage implements Storage {
  private mapa = new Map<string, string>()
  get length(): number { return this.mapa.size }
  clear(): void { this.mapa.clear() }
  getItem(k: string): string | null { return this.mapa.get(k) ?? null }
  key(i: number): string | null { return Array.from(this.mapa.keys())[i] ?? null }
  removeItem(k: string): void { this.mapa.delete(k) }
  setItem(k: string, v: string): void { this.mapa.set(k, String(v)) }
}

const CLASSES = [
  { class_id: 5, nome: 'Sem Luvas', foco: true },
  { class_id: 100009, nome: 'Sem mascara', foco: true },
  { class_id: 7, nome: 'Sem Óculos', foco: false },
]

const quadro = (id: string, extra: Record<string, unknown> = {}) => ({
  id,
  url: `https://r2.test/${id}.jpg`,
  camera_name: 'Entrada Preparação',
  captured_at: '2026-09-02T07:30:02+00:00',
  verdicts: {},
  reason: null,
  ...extra,
})

function filaDe(frames: unknown[]) {
  get.mockResolvedValue({ success: true, data: { classes: CLASSES, frames } })
}

/**
 * Sempre dentro de um Router — é como a rota real monta
 * (`ROTAS_NOVAS_SEM_SHELL`), e `SemPermissao` usa `<Link>`. Renderizar solto
 * passaria nos casos felizes e só quebraria no caminho de negação.
 */
const montar = () =>
  render(
    <MemoryRouter initialEntries={['/novo/estudio/gabarito']}>
      <Gabarito />
    </MemoryRouter>,
  )

const esperaCarregar = () => screen.findByRole('group', { name: 'Sem Luvas' })

describe('Gabarito — triagem por toque (mobile)', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', new MemoriaStorage())
    get.mockReset()
    put.mockReset()
    put.mockResolvedValue({ success: true })
    auth.can = () => true
  })

  it('mostra o quadro, a câmera e o contador de progresso', async () => {
    filaDe([quadro('f1'), quadro('f2'), quadro('f3')])
    montar()
    await esperaCarregar()

    expect(screen.getByText('1 de 3')).toBeTruthy()
    expect(screen.getByText('Entrada Preparação')).toBeTruthy()
    expect(get).toHaveBeenCalledWith('/training/gabarito/fila')
  })

  it('as duas classes de FOCO ficam à vista; as demais atrás de um toque', async () => {
    // A hierarquia é conteúdo: "Sem Luvas" e "Sem mascara" têm gabarito ZERO
    // e são o que trava o A/B. Cinco perguntas de peso igual esconderiam isso.
    filaDe([quadro('f1')])
    montar()
    await esperaCarregar()

    expect(screen.getByRole('group', { name: 'Sem mascara' })).toBeTruthy()
    expect(screen.queryByRole('group', { name: 'Sem Óculos' })).toBeNull()

    fireEvent.click(screen.getByText('Mais 1 classes'))
    expect(screen.getByRole('group', { name: 'Sem Óculos' })).toBeTruthy()
  })

  it('os TRÊS estados gravam — sim, não e não sei', async () => {
    filaDe([quadro('f1')])
    montar()
    await esperaCarregar()

    for (const [rotulo, esperado] of [
      ['Sem Luvas: Sim', 'sim'],
      ['Sem Luvas: Não', 'nao'],
      ['Sem Luvas: Não sei', 'nao_sei'],
    ] as const) {
      put.mockClear()
      fireEvent.click(screen.getByLabelText(rotulo))
      await waitFor(() =>
        expect(put).toHaveBeenCalledWith('/training/gabarito/frames/f1', {
          verdicts: { 5: esperado },
          reason: null,
        }),
      )
    }
  })

  it('o botão escolhido fica marcado (aria-pressed), não só colorido', async () => {
    filaDe([quadro('f1')])
    montar()
    await esperaCarregar()

    fireEvent.click(screen.getByLabelText('Sem Luvas: Não sei'))
    await waitFor(() =>
      expect(screen.getByLabelText('Sem Luvas: Não sei').getAttribute('aria-pressed')).toBe(
        'true',
      ),
    )
    expect(screen.getByLabelText('Sem Luvas: Sim').getAttribute('aria-pressed')).toBe('false')
  })

  it('"Não há pessoa": UM toque responde todas as classes e avança', async () => {
    filaDe([quadro('f1'), quadro('f2')])
    montar()
    await esperaCarregar()

    fireEvent.click(screen.getByText('Não há pessoa'))

    await waitFor(() =>
      expect(put).toHaveBeenCalledWith('/training/gabarito/frames/f1', {
        // Todas as classes, inclusive as secundárias que estavam recolhidas —
        // "não há pessoa" é afirmação sobre a imagem, não sobre o que está à
        // vista na tela.
        verdicts: { 5: 'nao', 100009: 'nao', 7: 'nao' },
        reason: 'sem_pessoa',
      }),
    )
    expect(screen.getByText('2 de 2')).toBeTruthy()
  })

  it('avança e volta sem pular quadro, e trava nas pontas', async () => {
    filaDe([quadro('f1'), quadro('f2')])
    montar()
    await esperaCarregar()

    expect(screen.getByText('Anterior').hasAttribute('disabled')).toBe(true)
    fireEvent.click(screen.getByText('Próxima'))
    expect(screen.getByText('2 de 2')).toBeTruthy()
    expect(screen.getByText('Próxima').hasAttribute('disabled')).toBe(true)
    fireEvent.click(screen.getByText('Anterior'))
    expect(screen.getByText('1 de 2')).toBeTruthy()
  })

  it('a ordem da fila é a do backend — a tela não reordena nada', async () => {
    // A fila já foi decidida (fila-gabarito-150.csv → priority_rank).
    // Reordenar aqui inventaria uma segunda fila.
    filaDe([quadro('z'), quadro('a'), quadro('m')])
    montar()
    await esperaCarregar()

    const vistos: string[] = []
    for (let i = 0; i < 3; i++) {
      vistos.push((screen.getByRole('img') as HTMLImageElement).src)
      if (i < 2) fireEvent.click(screen.getByText('Próxima'))
    }
    expect(vistos.map((u) => u.split('/').pop())).toEqual(['z.jpg', 'a.jpg', 'm.jpg'])
  })

  it('fechar e reabrir mantém a posição E as respostas', async () => {
    filaDe([quadro('f1'), quadro('f2'), quadro('f3')])
    const tela = montar()
    await esperaCarregar()

    fireEvent.click(screen.getByLabelText('Sem Luvas: Sim'))
    fireEvent.click(screen.getByText('Próxima'))
    await waitFor(() => expect(screen.getByText('2 de 3')).toBeTruthy())
    tela.unmount()

    montar()
    await esperaCarregar()
    expect(screen.getByText('2 de 3')).toBeTruthy()
    fireEvent.click(screen.getByText('Anterior'))
    expect(screen.getByLabelText('Sem Luvas: Sim').getAttribute('aria-pressed')).toBe('true')
  })

  it('o que o servidor já sabe reaparece ao abrir', async () => {
    filaDe([quadro('f1', { verdicts: { '5': 'nao' } })])
    montar()
    await esperaCarregar()
    await waitFor(() =>
      expect(screen.getByLabelText('Sem Luvas: Não').getAttribute('aria-pressed')).toBe('true'),
    )
  })

  it('sem permissão de anotar, a tela não abre nem chama a API', async () => {
    auth.can = () => false
    filaDe([quadro('f1')])
    montar()
    expect(get).not.toHaveBeenCalled()
  })

  it('não é editor de caixa: nenhum canvas na tela', async () => {
    filaDe([quadro('f1')])
    const { container } = montar()
    await esperaCarregar()
    expect(container.querySelector('canvas')).toBeNull()
  })
})

describe('Gabarito — rede caindo (o defeito que inutiliza a tela)', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', new MemoriaStorage())
    get.mockReset()
    put.mockReset()
    auth.can = () => true
  })

  it('resposta com a rede caída NÃO se perde: fica pendente e é reenviada', async () => {
    filaDe([quadro('f1')])
    put.mockRejectedValue(new Error('Network error'))
    montar()
    await esperaCarregar()

    fireEvent.click(screen.getByLabelText('Sem Luvas: Sim'))

    // A resposta continua na tela...
    await waitFor(() =>
      expect(screen.getByLabelText('Sem Luvas: Sim').getAttribute('aria-pressed')).toBe('true'),
    )
    // ...e o dono é avisado de que ela ainda não saiu do aparelho.
    await waitFor(() => expect(screen.getByText('1 a enviar')).toBeTruthy())
    // ...e sobreviveu ao storage: recarregar não a apaga.
    expect(pendentes(JSON.parse(localStorage.getItem('gabarito:respostas')!))).toEqual(['f1'])

    // Voltou a rede: reenviada sem o dono fazer nada.
    put.mockResolvedValue({ success: true })
    window.dispatchEvent(new Event('online'))
    await waitFor(() =>
      expect(put).toHaveBeenCalledWith('/training/gabarito/frames/f1', {
        verdicts: { 5: 'sim' },
        reason: null,
      }),
    )
    await waitFor(() => expect(screen.queryByText('1 a enviar')).toBeNull())
  })

  it('falha ao CARREGAR a fila diz o motivo em vez de mostrar tela vazia', async () => {
    get.mockRejectedValue(new Error('Network error'))
    montar()
    await waitFor(() =>
      expect(screen.getByText(/Não foi possível carregar a fila/)).toBeTruthy(),
    )
  })
})

describe('Gabarito — tela estreita (390px, telefone em pé)', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', new MemoriaStorage())
    get.mockReset()
    put.mockReset()
    put.mockResolvedValue({ success: true })
    auth.can = () => true
    // jsdom não faz layout; o que dá para afirmar é que NADA fica dependente
    // de largura para existir — a tela não tem variante "só no desktop".
    window.innerWidth = 390
    window.dispatchEvent(new Event('resize'))
  })

  it('a 390px todos os controles de decisão continuam presentes', async () => {
    filaDe([quadro('f1'), quadro('f2')])
    montar()
    await esperaCarregar()

    expect(screen.getByText('Não há pessoa')).toBeTruthy()
    for (const nome of ['Sem Luvas', 'Sem mascara']) {
      for (const v of ['Sim', 'Não', 'Não sei']) {
        expect(screen.getByLabelText(`${nome}: ${v}`)).toBeTruthy()
      }
    }
    expect(screen.getByText('Próxima')).toBeTruthy()
    expect(screen.getByText('1 de 2')).toBeTruthy()
  })
})

describe('filaGabarito — a memória local', () => {
  it('resposta nova nasce PENDENTE e mescla com a classe já respondida', () => {
    const um = aplicarResposta({}, 'f1', { 5: 'sim' })
    expect(um.f1).toEqual({ verdicts: { 5: 'sim' }, enviado: false })

    const dois = aplicarResposta(um, 'f1', { 7: 'nao' })
    // Mescla: responder a segunda classe não apaga a primeira.
    expect(dois.f1.verdicts).toEqual({ 5: 'sim', 7: 'nao' })
  })

  it('a resposta local PENDENTE vence a do servidor', () => {
    // É a única que existe em um lugar só — deixar o servidor sobrescrevê-la
    // perderia justamente o que a rede engoliu.
    const local = { f1: { verdicts: { 5: 'sim' as const }, enviado: false } }
    const depois = semear(local, { f1: { verdicts: { 5: 'nao' } } })
    expect(depois.f1.verdicts).toEqual({ 5: 'sim' })
    expect(depois.f1.enviado).toBe(false)
  })

  it('resposta já confirmada é substituída pela do servidor', () => {
    const local = { f1: { verdicts: { 5: 'sim' as const }, enviado: true } }
    const depois = semear(local, { f1: { verdicts: { 5: 'nao' } } })
    expect(depois.f1).toEqual({ verdicts: { 5: 'nao' }, enviado: true })
  })
})
