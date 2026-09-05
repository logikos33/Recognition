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

import { isValidElement, type ReactElement } from 'react'

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
    // `operator` anota — e enxerga as duas telas de câmera em modo
    // somente-leitura, que é o que elas já fazem hoje (ver teste abaixo).
    operator: ['Dados', 'Cobertura', 'Classificar', 'Modelos por câmera', 'Uso das câmeras'],
    // `trainer` treina; só não vê `Modelos` fora... ele vê tudo menos nada:
    // a única chave que lhe falta na lateral é nenhuma — `training:read` e
    // `training:write` ele tem, e as de câmera não gateiam mais.
    trainer: TODAS,
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

  /**
   * Regra desta lateral, e o pino que impede reapertá-la sem querer: o gate é
   * o que o backend recusa no CARREGAMENTO, não o que ele recusa num botão.
   *
   * As duas telas de câmera foram gateadas em `cameras:configure` na 1ª versão
   * desta PR. Elas carregam com JWT e têm modo somente-leitura PRÓPRIO — o
   * componente até escreve isso na tela. Escondê-las não consertava 403
   * nenhum: apagava leitura que funciona (e matava o link "O que a câmera
   * reconhece" de `epi/Cenario.tsx`, que hoje serve trainer e operator).
   */
  it('tela com modo somente-leitura próprio não pode ser escondida por permissão de escrita', () => {
    const raiz = join(__dirname, '..', '..')
    const escopo = readFileSync(join(raiz, 'components', 'training', 'CameraModelScope.tsx'), 'utf8')
    const porModulo = readFileSync(join(__dirname, 'CamerasPorModulo.tsx'), 'utf8')
    // A prova de que o modo existe vem do código da tela, não da minha palavra.
    expect(escopo, 'CameraModelScope perdeu o modo somente-leitura').toContain('somente leitura')
    expect(escopo).toContain("can('cameras:configure')")
    expect(porModulo, 'CamerasPorModulo perdeu o gate próprio').toContain("can('cameras:configure')")
    // Logo: a lateral não pode exigir a permissão de ESCRITA para deixar entrar.
    const gateadas = ITENS
      .filter((i) => ['modelos-por-camera', 'cameras-por-modulo'].includes(i.rota))
      .filter((i) => i.permissao !== null)
      .map((i) => `${i.rotulo} (${i.permissao})`)
    expect(gateadas, 'tela somente-leitura escondida atrás de permissão de escrita').toEqual([])
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

  // O gate só alcança seção que está em ITENS: sub-rota nova sem entrada aqui
  // nasce SEM gate nenhum e ninguém percebe. Guarda de drift — se a lista de
  // rotas e a lista de itens divergirem, esta é a linha que reclama.
  it('toda sub-rota do Estúdio tem entrada em ITENS (senão nasce sem gate)', async () => {
    const { ROTAS_NOVAS } = await import('../RotasNovas')
    const layout = ROTAS_NOVAS.find(
      (r) => (r.props as { path?: string }).path === 'estudio',
    ) as ReactElement
    const filhas = ([] as unknown[])
      .concat((layout.props as { children?: unknown }).children ?? [])
      .filter(isValidElement)
      .map((c) => (c.props as { path?: string }).path)
      .filter((p): p is string => typeof p === 'string') // index route não tem path
    const conhecidas = new Set(ITENS.map((i) => i.rota))
    expect(filhas.filter((p) => !conhecidas.has(p)), 'sub-rota sem gate').toEqual([])
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

  // O matcher do React Router é case-insensitive e compara o caminho com os
  // %-escapes decodificados: estas três URLs renderizam a MESMA `classes`.
  // Comparar o segmento cru no gate deixava as duas últimas passarem — o
  // "esconder não é autorizar" caía com um caps lock (achado do cético).
  it.each(['CLASSES', 'Classes', 'classe%73'])(
    'URL "%s" cai no mesmo gate que /classes',
    (variante) => {
      auth.can.mockImplementation(podeDo('operator'))
      monta(variante)
      expect(screen.queryByText('conteudo-classes'), 'conteúdo vazou por URL').toBeNull()
      expect(screen.getByText('Sem permissão')).toBeTruthy()
    },
  )

  it('seção liberada continua renderizando o Outlet', () => {
    auth.can.mockImplementation(podeDo('trainer'))
    monta('classes')
    expect(screen.getByText('conteudo-classes')).toBeTruthy()
    expect(screen.queryByText('Sem permissão')).toBeNull()
  })
})
