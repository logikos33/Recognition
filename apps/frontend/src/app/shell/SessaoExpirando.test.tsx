/**
 * O que se protege aqui não é layout — é o comportamento que, quebrado, ou
 * derruba o app ou desloga alguém no meio do turno:
 *
 *  · o aviso é de 5 MINUTOS, não "perto do fim" — antes disso não aparece;
 *  · o contador anda de segundo em segundo, em mm:ss com zero à esquerda;
 *  · `onExpirou` sai UMA vez. Em loop, viraria cascata de logout;
 *  · desmontar mata o intervalo. Timer órfão em SPA de turno de 8h vaza;
 *  · **"Renovar" renova de verdade** (issue #667): chama a troca de token e o
 *    cartão some com o prazo NOVO. Enquanto isso era `location.reload()`, o
 *    botão voltava com o mesmo `exp` e o aviso reaparecia em segundos.
 */
import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { SessaoExpirando } from './SessaoExpirando'

const MIN = 60_000

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-08-27T12:00:00Z'))
})
afterEach(() => vi.useRealTimers())

/** Avança o relógio deixando o React reagir a cada batida. */
const avancar = (ms: number) => act(() => void vi.advanceTimersByTime(ms))

/**
 * `renovar` SEMPRE injetado: o default do componente é o `renovarSessao` real,
 * que faria fetch. Teste que sai na rede não é teste.
 */
const montar = (restanteMs: number, props: Partial<Parameters<typeof SessaoExpirando>[0]> = {}) =>
  render(
    <SessaoExpirando
      expiraEm={Date.now() + restanteMs}
      onEntrarDeNovo={props.onEntrarDeNovo ?? vi.fn()}
      onExpirou={props.onExpirou}
      renovar={props.renovar ?? vi.fn().mockResolvedValue(Date.now() + 24 * 60 * MIN)}
    />,
  )

const botao = (nome: RegExp) => screen.getByRole('button', { name: nome })

describe('quando aparece', () => {
  it('fica calado com mais de 5 min restantes', () => {
    montar(5 * MIN + 1000)
    expect(screen.queryByRole('alertdialog')).toBeNull()
  })

  it('aparece exatamente em 5 min', () => {
    montar(5 * MIN)
    expect(screen.getByRole('alertdialog')).toBeTruthy()
    expect(screen.getByText('05:00')).toBeTruthy()
  })

  it('aparece sozinho quando o relógio cruza os 5 min', () => {
    montar(5 * MIN + 2000)
    expect(screen.queryByRole('alertdialog')).toBeNull()
    avancar(3000)
    expect(screen.getByRole('alertdialog')).toBeTruthy()
  })
})

describe('contador', () => {
  it('desce de segundo em segundo', () => {
    montar(5 * MIN)
    avancar(1000)
    expect(screen.getByText('04:59')).toBeTruthy()
    avancar(1000)
    expect(screen.getByText('04:58')).toBeTruthy()
  })

  it('formata mm:ss com zero à esquerda', () => {
    montar(9000)
    expect(screen.getByText('00:09')).toBeTruthy()
    avancar(1000)
    expect(screen.getByText('00:08')).toBeTruthy()
  })

  it('some ao zerar — não fica um 00:00 pendurado', () => {
    montar(2000)
    avancar(2000)
    expect(screen.queryByText('00:00')).toBeNull()
    expect(screen.getByRole('alertdialog')).toBeTruthy()
  })

  it('é polite, não assertive — leitor de tela não pode ser atropelado 300 vezes', () => {
    const { container } = montar(5 * MIN)
    expect(container.querySelector('[aria-live]')?.getAttribute('aria-live')).toBe('polite')
  })
})

describe('expiração', () => {
  it('chama onExpirou UMA vez, mesmo passando muito tempo depois', () => {
    const aoExpirar = vi.fn()
    montar(3000, { onExpirou: aoExpirar })
    avancar(2999)
    expect(aoExpirar).not.toHaveBeenCalled()
    avancar(1)
    expect(aoExpirar).toHaveBeenCalledTimes(1)
    avancar(10 * MIN)
    expect(aoExpirar).toHaveBeenCalledTimes(1)
  })

  it('para de contar depois de zerar', () => {
    montar(1000, { onExpirou: vi.fn() })
    avancar(1000)
    expect(vi.getTimerCount()).toBe(0)
  })
})

describe('renovar — o botão faz o que promete (issue #667)', () => {
  it('oferece "Renovar sessão" enquanto ainda dá tempo', () => {
    montar(2 * MIN)
    expect(botao(/renovar sessão/i)).toBeTruthy()
  })

  it('clicar chama a renovação de verdade — não recarrega a página', async () => {
    const renovar = vi.fn().mockResolvedValue(Date.now() + 24 * 60 * MIN)
    montar(2 * MIN, { renovar })
    await act(async () => void fireEvent.click(botao(/renovar sessão/i)))
    expect(renovar).toHaveBeenCalledTimes(1)
  })

  it('renovou → o cartão some NA HORA, com o prazo novo', async () => {
    // Sem adotar o prazo devolvido, o cartão ficaria até 1 min contando o `exp`
    // VELHO (o Shell só relê o token de minuto em minuto) e a pessoa clicaria
    // de novo achando que não funcionou.
    montar(2 * MIN, { renovar: vi.fn().mockResolvedValue(Date.now() + 24 * 60 * MIN) })
    expect(screen.getByRole('alertdialog')).toBeTruthy()
    await act(async () => void fireEvent.click(botao(/renovar sessão/i)))
    expect(screen.queryByRole('alertdialog')).toBeNull()
  })

  it('clique duplo não dispara duas renovações', async () => {
    // Dois refresh em voo emitem dois tokens; com `single_session` ligado o
    // segundo REVOGA o primeiro e a sessão morre por excesso de zelo.
    let resolver: (v: number) => void = () => {}
    const renovar = vi.fn(() => new Promise<number>((r) => { resolver = r }))
    montar(2 * MIN, { renovar })
    // O MESMO nó, clicado duas vezes: buscar pelo nome de novo não serviria,
    // porque o rótulo já virou "Renovando…" — o que também é parte da defesa.
    const alvo = botao(/renovar sessão/i)
    fireEvent.click(alvo)
    fireEvent.click(alvo)
    expect(renovar).toHaveBeenCalledTimes(1)
    expect(alvo).toHaveProperty('disabled', true)
    await act(async () => void resolver(Date.now() + 24 * 60 * MIN))
  })

  it('falhou → diz o motivo e revela a saída, sem tela branca', async () => {
    const renovar = vi.fn().mockRejectedValue(new Error('Sessão não pode ser renovada.'))
    montar(2 * MIN, { renovar })
    await act(async () => void fireEvent.click(botao(/renovar sessão/i)))

    expect(screen.getByRole('alertdialog')).toBeTruthy()
    expect(screen.getByText(/não pode ser renovada/i)).toBeTruthy()
    expect(botao(/entrar de novo/i)).toBeTruthy()
    // E dá para tentar de novo: pode ter sido a rede, não a sessão.
    expect(botao(/renovar sessão/i)).toBeTruthy()
  })

  it('falhou com código HTTP cru → mostra frase de gente, não "HTTP 401"', async () => {
    // Caminho REAL e não hipotético: os erros de JWT (token expirado por
    // relógio adiantado, revogado por single_session, conta desativada)
    // respondem noutro envelope, o `api.ts` não acha mensagem e devolve
    // "HTTP 401". Jogar isso na cara do operador é o jargão que a onda 1
    // passou a semana tirando das telas.
    const renovar = vi.fn().mockRejectedValue(new Error('HTTP 401'))
    montar(2 * MIN, { renovar })
    await act(async () => void fireEvent.click(botao(/renovar sessão/i)))

    expect(screen.queryByText(/HTTP 401/)).toBeNull()
    expect(screen.getByText(/não foi possível renovar a sessão/i)).toBeTruthy()
    // E a saída continua aparecendo — a falha não pode virar beco sem saída.
    expect(botao(/entrar de novo/i)).toBeTruthy()
  })

  it('falhou → "Entrar de novo" leva ao login', async () => {
    const entrarDeNovo = vi.fn()
    montar(2 * MIN, {
      onEntrarDeNovo: entrarDeNovo,
      renovar: vi.fn().mockRejectedValue(new Error('falhou')),
    })
    await act(async () => void fireEvent.click(botao(/renovar sessão/i)))
    fireEvent.click(botao(/entrar de novo/i))
    expect(entrarDeNovo).toHaveBeenCalledTimes(1)
  })

  it('enquanto NÃO falhou, não há botão destrutivo ao lado do que resolve', () => {
    montar(2 * MIN)
    expect(screen.queryByRole('button', { name: /entrar de novo/i })).toBeNull()
  })

  it('depois de expirar não oferece renovar — o backend recusa token morto', () => {
    montar(1000)
    avancar(1000)
    expect(screen.queryByRole('button', { name: /renovar/i })).toBeNull()
    expect(botao(/entrar de novo/i)).toBeTruthy()
  })
})

describe('ações', () => {
  it('"Agora não" some com o cartão — dá para terminar e salvar', () => {
    montar(2 * MIN)
    fireEvent.click(botao(/agora não/i))
    expect(screen.queryByRole('alertdialog')).toBeNull()
  })

  it('depois de expirar o cartão volta, mesmo dispensado, e sem "Agora não"', () => {
    // Dispensado + sessão morta é o pior estado possível: a tela parece viva e
    // toda chamada já vai levar 401. O aviso volta e sobra uma ação só.
    montar(2000)
    fireEvent.click(botao(/agora não/i))
    expect(screen.queryByRole('alertdialog')).toBeNull()
    avancar(2000)
    expect(screen.getByRole('alertdialog')).toBeTruthy()
    expect(screen.getByText(/sua sessão expirou/i)).toBeTruthy()
    expect(screen.queryByRole('button', { name: /agora não/i })).toBeNull()
  })

  it('o foco cai em "Renovar sessão" — o primário deixou de ser destrutivo', () => {
    // Enquanto o primário era "Entrar de novo", focá-lo transformava um Enter
    // distraído em trabalho perdido. "Renovar" não custa nada se clicado sem
    // querer, então volta a ser o alvo natural do teclado.
    montar(2 * MIN)
    expect(document.activeElement).toBe(botao(/renovar sessão/i))
  })
})

describe('desmonte', () => {
  it('não deixa timer vivo', () => {
    const aoExpirar = vi.fn()
    const { unmount } = montar(2 * MIN, { onExpirou: aoExpirar })
    // Delta, não contagem absoluta: o `focus()` do jsdom também agenda um
    // timer, e travar num número exato seria testar o jsdom, não o componente.
    const antes = vi.getTimerCount()
    unmount()
    expect(vi.getTimerCount()).toBe(antes - 1)
    avancar(10 * MIN)
    expect(aoExpirar).not.toHaveBeenCalled()
  })
})

/**
 * "Agora não" dispensa ESTA sessão, não o aviso para sempre.
 *
 * O `Shell` relê o `exp` do token de minuto em minuto, porque o token TROCA
 * sem desmontar o shell (renovação do contexto assumido, login em outra aba).
 * Como o cartão não desmonta entre um token e outro, um `dispensado` que nunca
 * volta atrás silencia o aviso do token NOVO: o operador perderia o único
 * heads-up de 5 minutos e descobriria a expiração ao ver a tela parar de
 * responder. O estado é por prazo — muda o prazo, volta o aviso.
 */
describe('o "Agora não" vale por sessão, não para sempre', () => {
  it('some com o cartão enquanto ainda dá tempo', () => {
    montar(4 * MIN)
    fireEvent.click(screen.getByRole('button', { name: /agora não/i }))
    expect(screen.queryByRole('alertdialog')).toBeNull()
  })

  it('o cartão volta quando o token é trocado por um com outro prazo', () => {
    const tela = render(
      <SessaoExpirando expiraEm={Date.now() + 4 * MIN} onEntrarDeNovo={vi.fn()} />,
    )
    fireEvent.click(screen.getByRole('button', { name: /agora não/i }))
    expect(screen.queryByRole('alertdialog')).toBeNull()

    // Token novo (outro `exp`), já perto do fim — o aviso é devido de novo.
    tela.rerender(
      <SessaoExpirando expiraEm={Date.now() + 3 * MIN} onEntrarDeNovo={vi.fn()} />,
    )
    expect(screen.getByRole('alertdialog')).toBeTruthy()
  })

  it('mesmo dispensado, o cartão volta ao expirar — não se esconde uma sessão morta', () => {
    montar(4 * MIN)
    fireEvent.click(screen.getByRole('button', { name: /agora não/i }))
    avancar(4 * MIN)
    expect(screen.getByRole('alertdialog')).toBeTruthy()
    expect(screen.getByRole('button', { name: /entrar de novo/i })).toBeTruthy()
  })
})
