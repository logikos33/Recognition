/**
 * O papel padrão que quebra.
 *
 * As TRÊS telas que criam usuário nasciam com `role = 'operator'`. "Operador" é
 * a palavra certa para quem está no chão de fábrica e a errada para o sistema:
 * `operator` não tem `training:write`, então quem for criado assim e entrar no
 * Estúdio toma 403 em curadoria, classes, gabarito e treino
 * (`services/api/app/api/v1/training/routes.py` + `core/auth.py`).
 *
 * Aceitar o padrão era a coisa mais fácil de fazer e a mais fácil de errar.
 * Estes testes travam o contrário: nenhuma tela nasce com papel escolhido, e
 * nenhuma deixa criar sem escolha explícita.
 *
 * O último bloco NÃO renderiza — lê o código das telas. É o guarda do PADRÃO:
 * qualquer tela nova que chame `adminService.createUser` cai aqui, mesmo que
 * ninguém lembre de escrever teste para ela.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { getUsers, getTenants, createUser, getTenant } = vi.hoisted(() => ({
  getUsers: vi.fn(), getTenants: vi.fn(), createUser: vi.fn(), getTenant: vi.fn(),
}))
// As três telas puxam métodos diferentes do mesmo serviço (a de tenant sozinha
// chama meia dúzia). Enumerar todos aqui só criaria manutenção: o que estes
// testes olham é o seletor de papel. Proxy devolve promessa vazia para o resto.
vi.mock('./services/adminService', () => ({
  adminService: new Proxy(
    {
      getUsers, getTenants, createUser, getTenant,
    } as Record<string, unknown>,
    { get: (alvo, chave: string) => alvo[chave] ?? (() => Promise.resolve([])) },
  ),
}))

import { Usuarios } from '../../app/admin/Usuarios'
import { CreateUserWizard } from './components/CreateUserWizard'
import { AdminTenantDetailPage } from './pages/AdminTenantDetailPage'

const TENANTS = [{ id: 't-rvb', name: 'RVB Isolantes', slug: 'rvb' }]
const TENANT_DETALHE = {
  id: 't-rvb', name: 'RVB Isolantes', slug: 'rvb', plan: 'pro', is_active: true,
  users: [], modules: [], camera_count: 0, user_count: 0,
}

beforeEach(() => {
  getUsers.mockReset().mockResolvedValue({ items: [], total: 0 })
  getTenants.mockReset().mockResolvedValue(TENANTS)
  getTenant.mockReset().mockResolvedValue(TENANT_DETALHE)
  createUser.mockReset()
})

function seletorPapel(): HTMLSelectElement {
  return screen.getByLabelText(/papel|role de sistema/i) as HTMLSelectElement
}

describe('nenhuma tela de criação nasce com papel escolhido', () => {
  it('Usuarios (front novo, /novo/admin/usuarios)', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter><Usuarios /></MemoryRouter>
      </QueryClientProvider>,
    )
    fireEvent.click(await screen.findByRole('button', { name: 'Convidar usuário' }))

    expect(seletorPapel().value).toBe('')
    // ...e o botão não deixa passar batido: e-mail e tenant preenchidos,
    // papel em branco → continua bloqueado.
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'novo@rvb.com.br' } })
    fireEvent.change(screen.getByLabelText('Tenant'), { target: { value: 't-rvb' } })
    const criar = screen.getByRole('button', { name: 'Criar usuário' }) as HTMLButtonElement
    expect(criar.disabled).toBe(true)
    fireEvent.click(criar)
    expect(createUser).not.toHaveBeenCalled()
  })

  it('CreateUserWizard (front antigo, /admin/users)', async () => {
    render(<MemoryRouter><CreateUserWizard open onClose={() => {}} onCreated={() => {}} /></MemoryRouter>)
    await screen.findByLabelText(/role de sistema/i)

    expect(seletorPapel().value).toBe('')
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'novo@rvb.com.br' } })
    fireEvent.change(screen.getByLabelText('Selecionar tenant'), { target: { value: 't-rvb' } })
    const avancar = screen.getByRole('button', { name: 'Avançar' }) as HTMLButtonElement
    expect(avancar.disabled).toBe(true)
  })

  it('AdminTenantDetailPage → aba Usuários (front antigo, /admin/tenants/:id)', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/tenants/t-rvb']}>
        <Routes>
          <Route path="/admin/tenants/:id" element={<AdminTenantDetailPage />} />
        </Routes>
      </MemoryRouter>,
    )
    fireEvent.click(await screen.findByText('Usuários'))
    fireEvent.click(screen.getByText('Adicionar usuário'))

    expect(seletorPapel().value).toBe('')
    fireEvent.change(screen.getByPlaceholderText('email@empresa.com'), {
      target: { value: 'novo@rvb.com.br' },
    })
    const criar = screen.getByRole('button', { name: 'Criar' }) as HTMLButtonElement
    expect(criar.disabled).toBe(true)
    fireEvent.click(criar)
    expect(createUser).not.toHaveBeenCalled()
  })

  it('a escolha diz o que o papel NÃO alcança, não só o que ele faz', async () => {
    render(<MemoryRouter><CreateUserWizard open onClose={() => {}} onCreated={() => {}} /></MemoryRouter>)
    await screen.findByLabelText(/role de sistema/i)

    fireEvent.change(seletorPapel(), { target: { value: 'operator' } })
    expect(screen.getByText(/curar frames.*403|403/i)).toBeTruthy()
  })
})

describe('guarda do padrão — vale para as telas que ainda nem existem', () => {
  const RAIZ = join(__dirname, '..', '..')

  const arquivos = (dir: string): string[] =>
    readdirSync(dir).flatMap((nome) => {
      const caminho = join(dir, nome)
      if (nome === 'node_modules') return []
      if (statSync(caminho).isDirectory()) return arquivos(caminho)
      return /\.tsx?$/.test(nome) && !/\.test\.tsx?$/.test(nome) ? [caminho] : []
    })

  const telasQueCriam = arquivos(RAIZ)
    .map((c) => [c, readFileSync(c, 'utf8')] as const)
    .filter(([, src]) => src.includes('adminService.createUser('))

  it('as três telas conhecidas continuam sendo as que criam usuário', () => {
    expect(telasQueCriam.map(([c]) => c.slice(RAIZ.length + 1)).sort()).toEqual([
      'app/admin/Usuarios.tsx',
      'modules/admin/components/CreateUserWizard.tsx',
      'modules/admin/pages/AdminTenantDetailPage.tsx',
    ])
  })

  it('nenhuma delas semeia um papel — todas usam o vocabulário único', () => {
    for (const [caminho, src] of telasQueCriam) {
      const rel = caminho.slice(RAIZ.length + 1)
      expect(src, `${rel} ainda tem papel literal pré-selecionado`).not.toMatch(/'operator'/)
      expect(src, `${rel} não usa modules/admin/papeis`).toMatch(/PAPEIS_ATRIBUIVEIS/)
      expect(src, `${rel} não parte de SEM_PAPEL`).toMatch(/SEM_PAPEL/)
    }
  })
})
