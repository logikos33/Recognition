/**
 * A paleta é operada de teclado por gente que não larga o mouse por gosto, e
 * sim porque está com luva. O que se protege aqui é o contrato do handoff
 * ("abre por clique ou ⌘K/Ctrl+K; fecha com ESC") e o que ele não diz mas o
 * teclado exige:
 *
 *  · ⌘K no Mac e Ctrl+K no resto — não vale só um dos dois;
 *  · ↑ ↓ dão a volta nas pontas, senão a última linha vira um beco;
 *  · filtrar tem de puxar o destaque de volta ao topo, senão ↵ dispara um item
 *    que a busca já tirou da tela — a paleta age no lugar errado;
 *  · o foco VOLTA de onde veio ao fechar, senão quem entrou por teclado é
 *    devolvido ao começo da página;
 *  · lista vazia é estado, não exceção: ↓ e ↵ no vazio não podem quebrar.
 */
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { PaletaComandos, type GrupoPaleta } from './PaletaComandos'

/** Dados no formato real do handoff (RVB Isolantes — CAM-01/CAM-04). */
function montar(vazia = false) {
  const escolhido = vi.fn<(id: string) => void>()
  const item = (id: string, rotulo: string, extra: Partial<GrupoPaleta['itens'][number]> = {}) => ({
    id,
    rotulo,
    aoEscolher: () => escolhido(id),
    ...extra,
  })
  const grupos: GrupoPaleta[] = vazia
    ? []
    : [
        {
          id: 'cameras',
          titulo: 'Câmeras',
          itens: [
            item('c1', 'CAM-01 Doca Norte', { detalhe: '● online', atalho: '↵' }),
            item('c4', 'CAM-04 Expedição', { detalhe: '▲ instável' }),
          ],
        },
        {
          id: 'eventos',
          titulo: 'Eventos',
          itens: [item('e1', 'Sem capacete · CAM-04 Expedição', { detalhe: 'HOJE 14:32' })],
        },
        { id: 'telas', titulo: 'Telas', itens: [item('t1', 'Ir para: Ao Vivo', { atalho: 'G V' })] },
        { id: 'acoes', titulo: 'Ações', itens: [item('a1', 'Criar ação corretiva', { atalho: '⌘⇧A' })] },
      ]
  return { escolhido, ...render(<PaletaComandos grupos={grupos} />) }
}

const abrirComCmd = () => fireEvent.keyDown(document, { key: 'k', metaKey: true })
const tecla = (key: string) => fireEvent.keyDown(document, { key })
const destacado = () => screen.getByRole('option', { selected: true })
const campo = () => screen.getByRole('combobox')

describe('abrir e fechar', () => {
  it('nasce fechada', () => {
    montar()
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('⌘K abre (Mac)', () => {
    montar()
    abrirComCmd()
    expect(screen.getByRole('dialog')).toBeTruthy()
  })

  it('Ctrl+K abre (Windows/Linux) — não vale só o ⌘', () => {
    montar()
    fireEvent.keyDown(document, { key: 'k', ctrlKey: true })
    expect(screen.getByRole('dialog')).toBeTruthy()
  })

  it('Esc fecha', () => {
    montar()
    abrirComCmd()
    tecla('Escape')
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('abre com o foco no campo — quem chamou por teclado já pode digitar', () => {
    montar()
    abrirComCmd()
    expect(document.activeElement).toBe(campo())
  })

  it('é diálogo modal, e diz o item destacado ao leitor de tela', () => {
    montar()
    abrirComCmd()
    expect(screen.getByRole('dialog').getAttribute('aria-modal')).toBe('true')
    expect(campo().getAttribute('aria-activedescendant')).toBe(destacado().id)
  })
})

describe('navegação', () => {
  it('começa no primeiro item', () => {
    montar()
    abrirComCmd()
    expect(destacado().textContent).toContain('CAM-01 Doca Norte')
  })

  it('↓ desce, e atravessa a fronteira de grupo', () => {
    montar()
    abrirComCmd()
    tecla('ArrowDown')
    expect(destacado().textContent).toContain('CAM-04 Expedição')
    tecla('ArrowDown')
    // Último de Câmeras → primeiro de Eventos.
    expect(destacado().textContent).toContain('Sem capacete')
  })

  it('↑ no primeiro dá a volta para o último', () => {
    montar()
    abrirComCmd()
    tecla('ArrowUp')
    expect(destacado().textContent).toContain('Criar ação corretiva')
  })

  it('↓ no último dá a volta para o primeiro', () => {
    montar()
    abrirComCmd()
    tecla('ArrowUp')
    tecla('ArrowDown')
    expect(destacado().textContent).toContain('CAM-01 Doca Norte')
  })
})

describe('confirmar', () => {
  it('↵ dispara a ação do item destacado, e não a do primeiro', () => {
    const { escolhido } = montar()
    abrirComCmd()
    tecla('ArrowDown')
    tecla('Enter')
    expect(escolhido).toHaveBeenCalledExactlyOnceWith('c4')
  })

  it('↵ fecha a paleta depois de agir', () => {
    montar()
    abrirComCmd()
    tecla('Enter')
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('clique também escolhe', () => {
    const { escolhido } = montar()
    abrirComCmd()
    fireEvent.click(screen.getByText('Ir para: Ao Vivo'))
    expect(escolhido).toHaveBeenCalledExactlyOnceWith('t1')
  })
})

describe('busca', () => {
  it('filtra DENTRO dos grupos e some com os grupos que esvaziaram', () => {
    montar()
    abrirComCmd()
    fireEvent.change(campo(), { target: { value: 'expedi' } })
    expect(screen.getAllByRole('option')).toHaveLength(2)
    expect(screen.getByText('Câmeras')).toBeTruthy()
    expect(screen.getByText('Eventos')).toBeTruthy()
    expect(screen.queryByText('Telas')).toBeNull()
    expect(screen.queryByText('Ações')).toBeNull()
  })

  it('acha sem acento — "acao" encontra "ação"', () => {
    montar()
    abrirComCmd()
    fireEvent.change(campo(), { target: { value: 'acao corretiva' } })
    expect(destacado().textContent).toContain('Criar ação corretiva')
  })

  it('filtrar traz o destaque de volta ao primeiro resultado', () => {
    montar()
    abrirComCmd()
    tecla('ArrowDown')
    tecla('ArrowDown')
    expect(destacado().textContent).toContain('Sem capacete')
    fireEvent.change(campo(), { target: { value: 'cam-0' } })
    expect(destacado().textContent).toContain('CAM-01 Doca Norte')
  })

  it('reabrir não herda a busca anterior', () => {
    montar()
    abrirComCmd()
    fireEvent.change(campo(), { target: { value: 'expedi' } })
    tecla('Escape')
    abrirComCmd()
    expect((campo() as HTMLInputElement).value).toBe('')
    expect(screen.getAllByRole('option')).toHaveLength(5)
  })
})

describe('foco', () => {
  it('volta ao elemento anterior ao fechar', () => {
    const gatilho = document.createElement('button')
    document.body.appendChild(gatilho)
    gatilho.focus()

    montar()
    abrirComCmd()
    expect(document.activeElement).toBe(campo())

    tecla('Escape')
    expect(document.activeElement).toBe(gatilho)
    gatilho.remove()
  })
})

describe('lista vazia', () => {
  it('sem grupos mostra o estado vazio', () => {
    montar(true)
    abrirComCmd()
    expect(screen.getByText('Nada encontrado.')).toBeTruthy()
    expect(screen.queryAllByRole('option')).toHaveLength(0)
  })

  it('busca sem resultado mostra o estado vazio', () => {
    montar()
    abrirComCmd()
    fireEvent.change(campo(), { target: { value: 'zzz' } })
    expect(screen.getByText('Nada encontrado.')).toBeTruthy()
  })

  it('↓ e ↵ no vazio não quebram nem disparam nada', () => {
    const { escolhido } = montar(true)
    abrirComCmd()
    tecla('ArrowDown')
    tecla('ArrowUp')
    tecla('Enter')
    expect(escolhido).not.toHaveBeenCalled()
    // ↵ sem item não pode fechar: não houve escolha nenhuma.
    expect(screen.getByRole('dialog')).toBeTruthy()
    expect(campo().getAttribute('aria-activedescendant')).toBeNull()
  })
})

describe('atalhos exibidos', () => {
  it('mostra o atalho de quem tem, e não inventa para quem não tem', () => {
    montar()
    abrirComCmd()
    expect(screen.getByText('G V')).toBeTruthy()
    expect(screen.getByText('⌘⇧A')).toBeTruthy()
    // CAM-04 não tem atalho — o item existe, o chip não.
    const cam04 = screen.getByText('CAM-04 Expedição').closest('[role="option"]')
    expect(cam04?.textContent).toBe('CAM-04 Expedição▲ instável')
  })
})
