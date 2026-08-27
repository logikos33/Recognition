/**
 * O que esta tela não pode perder ao mudar de front.
 *
 * Três coisas medidas em produção morreram uma vez por serem "detalhe visual"
 * e voltaram como defeito de segurança operacional. Cada uma tem um caso aqui,
 * e cada caso FALHA se a migração as deixar pelo caminho:
 *
 *  · **Procedência** — o evento não pode PARECER ao vivo sem ser. O shadow
 *    roda sobre frames já coletados; a distância entre captura e gravação é o
 *    único dado que separa uma coisa da outra.
 *  · **Veredito humano ≠ veredito da IA** — a task Celery grava o MESMO
 *    'approve'/'reject' com `verified_by='claude-haiku'`. Ler o verdict sem
 *    olhar quem julgou apresenta decisão de máquina como julgamento de gente.
 *    E o MOTIVO que a pessoa escreveu tem de aparecer: é ele que ensina.
 *  · **Polaridade em TRÊS estados** — `is_violation` é NULLABLE e NULL é
 *    "ninguém decidiu", não "conformidade". Como `event_kind='violation'`
 *    colapsa TRUE e NULL no mesmo balde, quem desempata é o catálogo.
 *
 * Mais a paginação: `page`/`per_page`, o mesmo mecanismo do front atual e do
 * backend (`offset = (page-1)*per_page`). Trocar por offset cru ou cursor
 * nesta família já custou metade das linhas de uma página.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { beforeEach, describe, expect, it, vi } from 'vitest'

/** `vi.mock` é içado acima das constantes do módulo — daí o `vi.hoisted`. */
const h = vi.hoisted(() => ({
  permissoes: ['alerts:read', 'alerts:feedback', 'alerts:export'] as string[],
  gets: [] as string[],
  posts: [] as string[],
  pagina: {
    alerts: [] as unknown[],
    total: 0,
    page: 1,
    per_page: 20,
    pages: 1,
  },
  falhar: false,
  /** Espelha o `ApiError` real: a tela lê `.status` para dizer o que falhou. */
  ApiErroFalso: class ApiErroFalso extends Error {
    status: number
    constructor(status: number) {
      super(`HTTP ${status}`)
      this.status = status
    }
  },
}))

vi.mock('../../services/api', () => ({
  ApiError: h.ApiErroFalso,
  getToken: () => 't',
  api: {
    get: vi.fn((p: string) => {
      h.gets.push(p)
      if (h.falhar) return Promise.reject(new h.ApiErroFalso(500))
      return Promise.resolve({ success: true, data: h.pagina })
    }),
    post: vi.fn((p: string) => {
      h.posts.push(p)
      return Promise.resolve({ success: true })
    }),
    downloadBlob: vi.fn(() => Promise.resolve(new Blob(['a']))),
  },
}))

vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({ can: (p: string) => h.permissoes.includes(p) }),
}))

/** Catálogo REAL do módulo (GET /api/modules/epi/classes) — com polaridade. */
const CATALOGO = [
  { class_name: 'no_helmet', display_name: 'Sem capacete', polaridade: 'violacao' },
  { class_name: 'helmet', display_name: 'Capacete', polaridade: 'conformidade' },
  { class_name: 'no_earplug', display_name: 'Sem protetor de ouvido', polaridade: 'indefinida' },
]

vi.mock('../../hooks/useModuleClasses', () => ({
  useModuleClasses: () => ({
    classes: CATALOGO,
    loading: false,
    classLabel: (c: string) =>
      CATALOGO.find((k) => k.class_name === c)?.display_name ?? c,
  }),
}))

vi.mock('../../services/cameraService', () => ({
  cameraService: {
    list: () =>
      Promise.resolve([
        { id: 'cam-4', name: 'CAM-04', location: 'Expedição' },
        { id: 'cam-1', name: 'CAM-01', location: 'Doca Norte' },
      ]),
  },
}))

import { Eventos } from './Eventos'

/** Formato real do backend (RVB Isolantes — CAM-01/04/07). */
const EVENTOS = [
  {
    id: 'e1',
    camera_id: 'cam-4',
    camera_name: 'CAM-04 Expedição',
    violations: [{ class: 'no_helmet', confidence: 0.87 }],
    acknowledged: false,
    created_at: '2026-08-20T14:32:00',
    timestamp: '2026-08-20T14:32:00',
    event_kind: 'violation' as const,
    verification_verdict: null,
    verified_by: null,
  },
  {
    id: 'e2',
    camera_id: 'cam-1',
    camera_name: 'CAM-01 Doca Norte',
    violations: [{ class: 'helmet', confidence: 0.92 }],
    acknowledged: true,
    created_at: '2026-08-20T14:07:00',
    timestamp: '2026-08-20T14:07:00',
    event_kind: 'compliance' as const,
    // A IA gravou 'reject' — NÃO é veredito humano.
    verification_verdict: 'reject',
    verified_by: 'claude-haiku',
  },
  {
    id: 'e3',
    camera_id: 'cam-7',
    camera_name: 'CAM-07 Linha 2',
    violations: [{ class: 'no_earplug', confidence: 0.51 }],
    acknowledged: false,
    // 12 min entre captura e gravação → coleta retroativa, não ao vivo.
    created_at: '2026-08-20T14:32:00',
    timestamp: '2026-08-20T14:20:00',
    event_kind: 'violation' as const,
    verification_verdict: 'approve',
    verified_by: 'user:u-1',
    verification_reason: 'A caixa pegou a luva do outro operador',
  },
  {
    id: 'e4',
    camera_id: 'cam-4',
    camera_name: 'CAM-04 Doca Sul',
    violations: [{ class: 'classe_sem_catalogo', confidence: 0.4 }],
    acknowledged: false,
    created_at: '2026-08-20T13:44:00',
    timestamp: '2026-08-20T13:44:00',
    event_kind: 'violation' as const,
    verification_verdict: null,
    verified_by: null,
  },
]

function montar(rota = '/epi/eventos') {
  return render(
    <MemoryRouter initialEntries={[rota]}>
      <Routes>
        <Route path="/epi/eventos" element={<Eventos />} />
      </Routes>
    </MemoryRouter>,
  )
}

const linhaDe = (texto: string) => screen.getByText(texto).closest('tr') as HTMLTableRowElement

/** O SELO da coluna VEREDITO — o que a tela AFIRMA, não o que ela oferece. */
const seloVeredito = (texto: string) =>
  linhaDe(texto).cells[5].querySelector('span')!.textContent ?? ''

beforeEach(() => {
  h.permissoes = ['alerts:read', 'alerts:feedback', 'alerts:export']
  h.gets.length = 0
  h.posts.length = 0
  h.falhar = false
  h.pagina = { alerts: EVENTOS, total: 4, page: 1, per_page: 20, pages: 1 }
})

describe('procedência — o evento não pode parecer ao vivo sem ser', () => {
  it('carimba "coleta retroativa" quando a gravação atrasa da captura', async () => {
    montar()
    await screen.findByText('CAM-07 Linha 2')
    expect(linhaDe('CAM-07 Linha 2').textContent).toContain('coleta retroativa')
  })

  it('não carimba nada quando captura e gravação são contemporâneas', async () => {
    montar()
    await screen.findByText('CAM-04 Expedição')
    // Ausência de selo = ausência de afirmação. Não existe carimbo "AO VIVO".
    expect(linhaDe('CAM-04 Expedição').textContent).not.toContain('retroativa')
    expect(screen.queryByText(/ao vivo/i)).toBeNull()
  })
})

describe('veredito humano ≠ veredito da IA', () => {
  it('verdict escrito pela IA aparece como "Não revisado"', async () => {
    montar()
    await screen.findByText('CAM-01 Doca Norte')
    // FALHA se a tela ler verification_verdict sem olhar verified_by. O selo é
    // o que a tela AFIRMA; o botão "Falso positivo" ao lado é oferta de ação.
    expect(seloVeredito('CAM-01 Doca Norte')).toContain('Não revisado')
    expect(seloVeredito('CAM-01 Doca Norte')).not.toContain('Falso positivo')
  })

  it('verdict de gente ("user:") aparece com o MOTIVO que a pessoa deu', async () => {
    montar()
    await screen.findByText('CAM-07 Linha 2')
    expect(seloVeredito('CAM-07 Linha 2')).toContain('Procedente')
    expect(linhaDe('CAM-07 Linha 2').textContent).toContain(
      'A caixa pegou a luva do outro operador',
    )
  })

  it('julgar é clique explícito e vai SEM motivo — o motivo é da tela de detalhe', async () => {
    montar()
    await screen.findByText('CAM-04 Expedição')
    const botoes = [...linhaDe('CAM-04 Expedição').querySelectorAll('button')]
    fireEvent.click(botoes.find((b) => b.textContent === 'Procedente')!)
    await waitFor(() => expect(h.posts).toContain('/verification/e1/review'))
  })
})

describe('polaridade em três estados', () => {
  it('conformidade vem do backend e vale sozinha', async () => {
    montar()
    await screen.findByText('CAM-01 Doca Norte')
    expect(linhaDe('CAM-01 Doca Norte').textContent).toContain('Conformidade')
  })

  it('violação só é afirmada quando o catálogo diz que a classe é violação', async () => {
    montar()
    await screen.findByText('CAM-04 Expedição')
    expect(linhaDe('CAM-04 Expedição').textContent).toContain('Violação')
  })

  it('classe com is_violation NULL é "Não definida" — nunca violação', async () => {
    montar()
    await screen.findByText('CAM-07 Linha 2')
    const linha = linhaDe('CAM-07 Linha 2')
    // FALHA se a tela usar event_kind cru: o backend colapsa NULL em 'violation'.
    expect(linha.textContent).toContain('Não definida')
    expect(linha.textContent).not.toContain('Violação')
  })

  it('classe fora do catálogo não recebe selo nenhum — sem afirmação', async () => {
    montar()
    await screen.findByText('CAM-04 Doca Sul')
    const linha = linhaDe('CAM-04 Doca Sul')
    for (const palavra of ['Violação', 'Conformidade', 'Não definida']) {
      expect(linha.textContent).not.toContain(palavra)
    }
  })

  it('paleta do veredito é disjunta da paleta da polaridade', () => {
    // Se "falso positivo" virar vermelho, veredito e violação viram a mesma
    // cor na mesma linha e o operador perde a diferença entre os dois eixos.
    const css = fs.readFileSync(
      path.join(path.dirname(fileURLToPath(import.meta.url)), 'Eventos.css.ts'),
      'utf-8',
    )
    const bloco = (nome: string) => {
      const i = css.indexOf(`export const ${nome} = styleVariants({`)
      return css.slice(i, css.indexOf('})', i))
    }
    expect(bloco('corVeredito')).not.toContain('lk.estado.nc')
    expect(bloco('corVeredito')).not.toContain('lk.estado.ok')
    expect(bloco('corPolaridade')).toContain('lk.estado.nc')
    expect(bloco('corPolaridade')).toContain('lk.estado.ok')
  })
})

describe('paginação — page/per_page, como o backend calcula o offset', () => {
  it('pede a primeira página com per_page, nunca offset', async () => {
    montar()
    await screen.findByText('CAM-04 Expedição')
    expect(h.gets[0]).toContain('page=1')
    expect(h.gets[0]).toContain('per_page=20')
    expect(h.gets[0]).not.toContain('offset')
    expect(h.gets[0]).not.toContain('cursor')
  })

  it('avançar troca a PÁGINA e mantém o recorte', async () => {
    h.pagina = { ...h.pagina, pages: 3 }
    montar()
    await screen.findByText('CAM-04 Expedição')
    fireEvent.click(screen.getByLabelText('Próxima página'))
    await waitFor(() => expect(h.gets.at(-1)).toContain('page=2'))
    expect(h.gets.at(-1)).toContain('per_page=20')
    expect(h.gets.at(-1)).toContain('kind=violation')
  })

  it('trocar filtro volta para a página 1 — paginar sobre outro recorte pula linha', async () => {
    h.pagina = { ...h.pagina, pages: 3 }
    montar()
    await screen.findByText('CAM-04 Expedição')
    fireEvent.click(screen.getByLabelText('Próxima página'))
    await waitFor(() => expect(h.gets.at(-1)).toContain('page=2'))
    fireEvent.change(screen.getByLabelText('Status'), { target: { value: 'false' } })
    await waitFor(() => expect(h.gets.at(-1)).toContain('acknowledged=false'))
    expect(h.gets.at(-1)).toContain('page=1')
  })
})

describe('reconhecer é ato explícito', () => {
  it('o clique no botão manda o acknowledge daquele evento', async () => {
    montar()
    await screen.findByText('CAM-04 Expedição')
    const botoes = [...linhaDe('CAM-04 Expedição').querySelectorAll('button')]
    fireEvent.click(botoes.find((b) => b.textContent === 'Reconhecer')!)
    await waitFor(() => expect(h.posts).toContain('/alerts/e1/acknowledge'))
  })

  it('passar o mouse na linha NÃO reconhece', async () => {
    montar()
    await screen.findByText('CAM-04 Expedição')
    fireEvent.mouseOver(linhaDe('CAM-04 Expedição'))
    fireEvent.mouseEnter(linhaDe('CAM-04 Expedição'))
    expect(h.posts).toEqual([])
  })

  it('evento já reconhecido não oferece o botão', async () => {
    montar()
    await screen.findByText('CAM-01 Doca Norte')
    const botoes = [...linhaDe('CAM-01 Doca Norte').querySelectorAll('button')]
    expect(botoes.some((b) => b.textContent === 'Reconhecer')).toBe(false)
  })
})

describe('permissão', () => {
  it('sem alerts:read a tela não busca nada e diz o porquê', async () => {
    h.permissoes = []
    montar()
    expect(await screen.findByText('Sem permissão')).toBeTruthy()
    expect(h.gets).toEqual([])
  })

  it('sem alerts:feedback não há BOTÃO de veredito (o selo continua)', async () => {
    h.permissoes = ['alerts:read']
    montar()
    await screen.findByText('CAM-04 Expedição')
    expect(screen.queryAllByRole('button', { name: 'Procedente' })).toHaveLength(0)
    expect(screen.queryAllByRole('button', { name: 'Falso positivo' })).toHaveLength(0)
    // O veredito já registrado segue LEGÍVEL — esconder o julgamento de gente
    // por falta de permissão de julgar seria apagar prova, não proteger.
    expect(linhaDe('CAM-07 Linha 2').textContent).toContain('Procedente')
  })

  it('sem alerts:export não há exportação', async () => {
    h.permissoes = ['alerts:read']
    montar()
    await screen.findByText('CAM-04 Expedição')
    expect(screen.queryByText(/Exportar CSV/)).toBeNull()
  })
})

describe('estados da rota', () => {
  it('vazio é vazio honesto, não linha inventada', async () => {
    h.pagina = { alerts: [], total: 0, page: 1, per_page: 20, pages: 1 }
    montar()
    expect(await screen.findByText('Nenhum evento no período')).toBeTruthy()
    // Sem tabela: nada de linha de exemplo para "não ficar vazio".
    expect(screen.queryByRole('table')).toBeNull()
  })

  it('erro diz o que falhou e deixa tentar de novo', async () => {
    h.falhar = true
    montar()
    expect(await screen.findByText('Não foi possível carregar')).toBeTruthy()
    expect(screen.getByText(/GET \/api\/alerts/)).toBeTruthy()
    h.falhar = false
    fireEvent.click(screen.getByText('Tentar novamente'))
    expect(await screen.findByText('CAM-04 Expedição')).toBeTruthy()
  })
})

describe('deep-link do sino continua valendo', () => {
  it('camera_id e kind da URL entram como filtro da primeira busca', async () => {
    montar('/epi/eventos?camera_id=cam-4&kind=compliance&acknowledged=false')
    await waitFor(() => expect(h.gets.length).toBeGreaterThan(0))
    expect(h.gets[0]).toContain('camera_id=cam-4')
    expect(h.gets[0]).toContain('kind=compliance')
    expect(h.gets[0]).toContain('acknowledged=false')
  })
})
