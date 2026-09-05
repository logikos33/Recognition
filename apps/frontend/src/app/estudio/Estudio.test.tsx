/**
 * O gate é o que não pode falhar aqui: o Estúdio é a casa do trainer e a
 * fronteira do jargão de ML — analyst e viewer não entram.
 *
 * E, para quem entra, a LATERAL não pode oferecer tela que o backend recusa
 * (issue #688): o cruzamento item×papel é feito contra a matriz REAL do
 * backend (`matriz-papeis.json`, gerada do registry), não contra uma cópia.
 */
import { readFileSync } from 'node:fs'
import { join } from 'node:path'

import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const auth = vi.hoisted(() => ({ can: vi.fn((_p: string) => true) }))
vi.mock('../../hooks/useAuth', () => ({ useAuth: () => auth }))

import { Estudio, ITENS } from './Estudio'

/** Papéis reais do backend (`core/permissions.py:ROLE_ORDER`). */
const PAPEIS = ['superadmin', 'admin', 'operator', 'analyst', 'trainer', 'viewer'] as const

const MATRIZ: Record<string, string[]> = JSON.parse(
  readFileSync(join(__dirname, '..', '..', 'test', 'e2e', 'matriz-papeis.json'), 'utf8'),
)

/** Mesma regra do `useAuth().can`: superadmin pode tudo. */
const podeDo = (papel: string) => (p: string) =>
  papel === 'superadmin' || (MATRIZ[papel] ?? []).includes(p)

function monta(secao = 'dados') {
  return render(
    <MemoryRouter initialEntries={[`/novo/estudio/${secao}`]}>
      <Routes>
        <Route path="/novo/estudio" element={<Estudio />}>
          <Route path="dados" element={<div>conteudo-dados</div>} />
          <Route path="classes" element={<div>conteudo-classes</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}

/** Rótulos da lateral efetivamente renderizados (o "Voltar" não é seção). */
function secoesNaTela(): string[] {
  const lateral = screen.queryByRole('navigation', { name: 'Seções do Estúdio' })
  if (!lateral) return []
  return [...lateral.querySelectorAll('a')]
    .map((a) => a.textContent?.trim() ?? '')
    .filter((t) => t !== 'Voltar')
}

describe('Estudio (layout + gate)', () => {
  beforeEach(() => {
    auth.can.mockReset()
    auth.can.mockReturnValue(true)
  })

  it('sem frames:annotate → Sem permissão, e NADA do conteúdo vaza', () => {
    auth.can.mockImplementation((p: string) => p !== 'frames:annotate')
    monta()
    expect(screen.getByText('Sem permissão')).toBeTruthy()
    expect(screen.getByText('frames:annotate')).toBeTruthy()
    expect(screen.queryByText('conteudo-dados')).toBeNull()
    expect(screen.queryByRole('navigation')).toBeNull()
  })

  it('com frames:annotate → lateral própria com Dados e a sub-rota no Outlet', () => {
    monta()
    expect(auth.can).toHaveBeenCalledWith('frames:annotate')
    const lateral = screen.getByRole('navigation', { name: 'Seções do Estúdio' })
    expect(lateral).toBeTruthy()
    expect(screen.getByRole('link', { name: /dados/i })).toBeTruthy()
    expect(screen.getByText('conteudo-dados')).toBeTruthy()
  })

  it('"Voltar" é o primeiro link da lateral e leva ao Dashboard EPI', () => {
    // A lateral do Estúdio SUBSTITUI a nav principal do Shell — sem este
    // link, quem entra aqui não tem caminho de volta nenhum (regra global,
    // ver app/shell/becoSemSaida.test.tsx).
    monta()
    const primeiro = screen.getAllByRole('link')[0]
    expect(primeiro.textContent?.trim()).toBe('Voltar')
    expect(primeiro.getAttribute('href')).toBe('/novo/epi/dashboard')
  })
})

describe('lateral do Estúdio × o que o backend permite (issue #688)', () => {
  beforeEach(() => auth.can.mockReset())

  /**
   * Tabela ESCRITA À MÃO de propósito: se ela fosse derivada de `ITENS` o
   * teste só provaria que o filtro filtra. Aqui ela é o contrato — mudou o
   * gate de um item sem querer, o teste diz qual papel ganhou ou perdeu tela.
   *
   * `analyst` e `viewer` não têm `frames:annotate` → nem entram no Estúdio.
   */
  const TODAS = ITENS.map((i) => i.rotulo)
  const ESPERADO: Record<string, string[]> = {
    superadmin: TODAS,
    admin: TODAS,
    // `operator` anota, e é só: sem training:write nem cameras:configure.
    operator: ['Dados', 'Cobertura', 'Classificar'],
    // `trainer` treina, mas não configura câmera (cameras:configure é
    // superadmin/admin no registry).
    trainer: [
      'Dados', 'Cobertura', 'Classificar', 'Gabarito (celular)',
      'Classes', 'Treinos', 'Modelos',
    ],
    analyst: [],
    viewer: [],
  }

  it.each(PAPEIS)('%s vê exatamente as seções que pode usar', (papel) => {
    auth.can.mockImplementation(podeDo(papel))
    monta()
    expect(secoesNaTela()).toEqual(ESPERADO[papel])
  })

  it.each(PAPEIS)('nenhuma seção visível para %s exige permissão que ele não tem', (papel) => {
    const pode = podeDo(papel)
    auth.can.mockImplementation(pode)
    monta()
    const visiveis = new Set(secoesNaTela())
    // Cruza com a matriz REAL: item na tela cuja permissão o papel não possui
    // é exatamente o 403 da issue #688 voltando.
    const mentirosos = ITENS
      .filter((i) => visiveis.has(i.rotulo) && i.permissao !== null && !pode(i.permissao))
      .map((i) => `${i.rotulo} (${i.permissao})`)
    expect(mentirosos, 'item oferecido que o backend recusa').toEqual([])
    // E o contrário: item escondido que o papel PODERIA usar é tela sonegada.
    const sonegados = ITENS
      .filter((i) => !visiveis.has(i.rotulo) && (i.permissao === null || pode(i.permissao)))
      .map((i) => i.rotulo)
    if (pode('frames:annotate')) expect(sonegados, 'tela sonegada').toEqual([])
  })

  it('toda permissão citada na lateral EXISTE no registry do backend', () => {
    const py = readFileSync(
      join(__dirname, '..', '..', '..', '..', '..',
        'services', 'api', 'app', 'core', 'permissions.py'), 'utf8',
    )
    const reais = new Set([...py.matchAll(/"([a-z_]+:[a-z_]+)":\s*_entry/g)].map((m) => m[1]))
    expect(reais.size, 'não consegui ler o registry').toBeGreaterThan(20)
    const inventadas = ITENS
      .map((i) => i.permissao)
      .filter((p): p is string => p !== null)
      .filter((p) => !reais.has(p))
    expect(inventadas, 'chave inexistente some para todo mundo, em silêncio').toEqual([])
  })

  it('esconder não é autorizar: URL direta da seção cai no mesmo gate', () => {
    auth.can.mockImplementation(podeDo('operator'))
    monta('classes')
    expect(screen.queryByText('conteudo-classes'), 'conteúdo vazou por URL direta').toBeNull()
    expect(screen.getByText('Sem permissão')).toBeTruthy()
    expect(screen.getByText('training:write')).toBeTruthy()
    // A lateral fica de pé — bloquear não pode virar beco sem saída.
    expect(screen.getByRole('navigation', { name: 'Seções do Estúdio' })).toBeTruthy()
  })

  it('seção liberada continua renderizando o Outlet', () => {
    auth.can.mockImplementation(podeDo('trainer'))
    monta('classes')
    expect(screen.getByText('conteudo-classes')).toBeTruthy()
    expect(screen.queryByText('Sem permissão')).toBeNull()
  })
})
