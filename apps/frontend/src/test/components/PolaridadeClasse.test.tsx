/**
 * Polaridade (o que o evento É) nunca pode virar a mesma coisa que Veredito
 * (o que a PESSOA julgou). Palavras disjuntas, paletas disjuntas.
 *
 * E três estados, não dois: `yolo_classes.is_violation` é NULLABLE e NULL
 * significa "ninguém decidiu", que a ADR-0065 proíbe tratar como presença.
 */
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import {
  SeletorPolaridade,
  PolaridadeBadge,
  VARIANTE_POLARIDADE,
  ROTULO_POLARIDADE,
} from '../../components/shared/PolaridadeClasse'
import { VARIANTE_VEREDITO } from '../../components/shared/VereditoHumano'

describe('paleta disjunta', () => {
  it('nenhum estado DECIDIDO compartilha cor com o veredito humano', () => {
    // `neutral` é compartilhado de propósito: "não definida" (polaridade) e
    // "não revisado" (veredito) são os dois a MESMA ideia — ausência de
    // informação — e cinza nos dois não confunde ninguém. O que não pode
    // colidir são os estados em que alguém (ou algo) DECIDIU: se violação e
    // falso-positivo virarem a mesma cor na mesma linha, a tela passa a dizer
    // duas coisas diferentes com o mesmo sinal.
    const decididasPolaridade = [
      VARIANTE_POLARIDADE.violacao,
      VARIANTE_POLARIDADE.conformidade,
    ]
    const decididasVeredito = [
      VARIANTE_VEREDITO.procedente,
      VARIANTE_VEREDITO['falso-positivo'],
    ]
    const colisao = decididasPolaridade.filter(v => decididasVeredito.includes(v))
    expect(colisao).toEqual([])
  })

  it('o cinza compartilhado é SÓ o de ausência de decisão', () => {
    expect(VARIANTE_POLARIDADE.indefinida).toBe('neutral')
    expect(VARIANTE_VEREDITO['nao-revisado']).toBe('neutral')
  })

  it('violação é danger e conformidade é success', () => {
    expect(VARIANTE_POLARIDADE.violacao).toBe('danger')
    expect(VARIANTE_POLARIDADE.conformidade).toBe('success')
  })

  it('as palavras também são disjuntas', () => {
    const polaridade = Object.values(ROTULO_POLARIDADE).map(s => s.toLowerCase())
    for (const p of polaridade) {
      expect(p).not.toContain('procedente')
      expect(p).not.toContain('falso')
    }
  })
})

describe('três estados', () => {
  it('não definida não aparece como conformidade', () => {
    render(<PolaridadeBadge polaridade="indefinida" />)
    expect(screen.getByText('Não definida')).toBeTruthy()
    expect(screen.queryByText('Conformidade')).toBeNull()
  })

  it('com polaridade indefinida NENHUM dos dois botões fica marcado', () => {
    render(
      <SeletorPolaridade polaridade="indefinida" editavel onChange={() => {}} />,
    )
    const violacao = screen.getByRole('button', { name: 'Violação' })
    const conformidade = screen.getByRole('button', { name: 'Conformidade' })
    expect(violacao.getAttribute('aria-pressed')).toBe('false')
    expect(conformidade.getAttribute('aria-pressed')).toBe('false')
    expect(screen.getByText('não definida')).toBeTruthy()
  })

  it('marca o botão certo quando há decisão', () => {
    render(<SeletorPolaridade polaridade="violacao" editavel onChange={() => {}} />)
    expect(
      screen.getByRole('button', { name: 'Violação' }).getAttribute('aria-pressed'),
    ).toBe('true')
    expect(
      screen.getByRole('button', { name: 'Conformidade' }).getAttribute('aria-pressed'),
    ).toBe('false')
  })
})

describe('edição', () => {
  it('clicar em Violação emite a mudança', () => {
    const onChange = vi.fn()
    render(<SeletorPolaridade polaridade="conformidade" editavel onChange={onChange} />)
    fireEvent.click(screen.getByRole('button', { name: 'Violação' }))
    expect(onChange).toHaveBeenCalledWith('violacao')
  })

  it('catálogo global NÃO é editável — a polaridade vale para todos os tenants', () => {
    render(
      <SeletorPolaridade
        polaridade="violacao"
        editavel={false}
        onChange={() => {}}
      />,
    )
    expect(screen.queryByRole('button', { name: 'Violação' })).toBeNull()
    expect(screen.getByText('catálogo')).toBeTruthy()
    expect(screen.getByText('Violação')).toBeTruthy()
  })
})
