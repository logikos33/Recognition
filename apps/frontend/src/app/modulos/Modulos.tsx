/**
 * `/modules` — a porta de entrada de quem tem mais de um módulo.
 *
 * Spec: `design/Módulos.dc.html`. Recriada em React com tokens; os estilos
 * inline do arquivo são a medida, não o código.
 *
 * ─── O QUE O BACKEND SERVE, E O QUE O DESENHO SUPÕE ─────────────────────────
 *
 * `GET /api/modules/` devolve, por módulo do tenant: `module_code`, `enabled`,
 * `alerts_today`, `cameras_count`, `activated_at`, `expires_at`, `config`.
 *
 * O desenho supõe três coisas que NÃO vêm de lá:
 *
 *  1. **Nome e descrição** — o backend só dá `module_code`. Ficam no mapa
 *     abaixo, no front, porque são rótulo de produto e não dado de tenant.
 *  2. **Pendência por módulo** ("3 NOK aguardam revisão", "2 divergências a
 *     validar"). Só existe `alerts_today`, e só ele é mostrado — quando é > 0.
 *     Inventar as outras seria dado mocado em tela de produto.
 *  3. **"Última visita · ontem 17:42"** — não há endpoint. Guardamos no
 *     navegador de quem usa: é o SEU último acesso, dado verdadeiro sobre você,
 *     só que local. Sem registro, o selo não aparece.
 *
 * E os códigos reais divergem do desenho: são `epi`, `counting`, `quality`,
 * `basic`, `analytics` — não existe `carga` (é `counting`) nem `estudio`.
 * `basic` e `analytics` não têm tela em lugar nenhum do produto, então não
 * viram cartão: cartão que não leva a lugar nenhum é pior que ausência.
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Boxes, PencilRuler, ScanSearch, ShieldCheck } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { useAuth } from '../../hooks/useAuth'
import { api } from '../../services/api'
import { LogikosLoader } from '../shell/LogikosLoader'
import { PREFIXO_NOVO } from '../RotasNovas'
import { useMarcaDoTenant } from '../tokens/MarcaDoTenant'
import { lk } from '../tokens/lk.css'
import { ROTULO_MODULO } from './rotulos'
import * as s from './Modulos.css'

interface ModuloDaApi {
  module_code: string
  enabled?: boolean
  alerts_today?: number
  cameras_count?: number
}

/**
 * Rótulo, ícone e destino por código REAL do backend.
 *
 * Os TRÊS destinos são rotas do front NOVO. Até 05/09 dois deles não eram:
 * Qualidade apontava para `/quality` e Contagem para `/epi/counting`, com um
 * `externo: true` que saltava de página inteira (`window.location`) para o
 * front ANTIGO. O comentário chamava isso de "deliberado, esses módulos ainda
 * não foram migrados" — e estava desatualizado: `RotasNovas.tsx` registra
 * `quality` (mais gestão/revisão/configuração) e `carga` desde F4, e o
 * `MANIFESTO-FRONT-ANTIGO.md` marca `pages/CountingPage.tsx` como SUBSTITUIDA
 * por `app/carga/Carga.tsx`. O de-para é o do `DELTA-PRE-MIGRACAO.md:99`
 * (`/epi/counting` · `/fueling/*` → `/carga/*`).
 *
 * Se um dia um módulo REALMENTE não tiver tela nova, ele não entra aqui:
 * cartão que não leva a lugar nenhum é pior que ausência (é a regra que já
 * mantém `basic` e `analytics` fora).
 */
const CATALOGO: Record<
  string,
  { nome: string; desc: string; icone: typeof ShieldCheck; destino: string }
> = {
  epi: {
    // `nome` vem de `./rotulos` — mesma palavra que a tela de atribuição de
    // câmeras usa para este módulo. `desc` continua sendo desta tela: aqui ela
    // vende o módulo, lá ela explica o que acontece com a imagem da câmera.
    nome: ROTULO_MODULO.epi,
    desc: 'Conformidade de EPI em zonas monitoradas',
    icone: ShieldCheck,
    destino: `${PREFIXO_NOVO}/epi/dashboard`,
  },
  quality: {
    nome: ROTULO_MODULO.quality,
    desc: 'Inspeção por ponto, gate e retrabalho',
    icone: ScanSearch,
    destino: `${PREFIXO_NOVO}/quality`,
  },
  counting: {
    nome: ROTULO_MODULO.counting,
    desc: 'Contagem e validação de expedição',
    icone: Boxes,
    destino: `${PREFIXO_NOVO}/carga`,
  },
}

/** Onde o navegador guarda o último módulo aberto por esta pessoa. */
const CHAVE_ULTIMO = 'lk-ultimo-modulo'

export function registrarVisita(codigo: string) {
  try {
    localStorage.setItem(CHAVE_ULTIMO, JSON.stringify({ codigo, em: Date.now() }))
  } catch {
    // Navegador sem armazenamento (janela privada, política): o selo apenas
    // não aparece. Nunca derruba a tela por causa de um enfeite.
  }
}

function ultimaVisita(): { codigo: string; em: number } | null {
  try {
    const cru = localStorage.getItem(CHAVE_ULTIMO)
    return cru ? (JSON.parse(cru) as { codigo: string; em: number }) : null
  } catch {
    return null
  }
}

/** "ONTEM 17:42" · "HOJE 09:12" · "25/08 14:03" — o formato do desenho. */
function quando(em: number): string {
  const d = new Date(em)
  const hora = d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
  const hoje = new Date()
  const dia = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime()
  const diff = (dia(hoje) - dia(d)) / 86_400_000
  if (diff === 0) return `HOJE ${hora}`
  if (diff === 1) return `ONTEM ${hora}`
  return `${d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })} ${hora}`
}

export function Modulos() {
  const { user, isSuperAdmin } = useAuth()
  // Esta tela fica FORA do Shell, então liga o clamp por conta própria.
  useMarcaDoTenant()
  const navegar = useNavigate()
  const [modulos, setModulos] = useState<ModuloDaApi[] | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const ultimo = useMemo(ultimaVisita, [])

  const carregar = useCallback(() => {
    setErro(null)
    api
      .get<{ data?: { modules?: ModuloDaApi[] } }>('/modules/')
      .then((r) => setModulos(r.data?.modules ?? []))
      .catch((e) => setErro(e instanceof Error ? e.message : 'Erro ao carregar os módulos'))
  }, [])

  useEffect(carregar, [carregar])

  /** Só os módulos habilitados que têm tela. Ordem estável: a do catálogo. */
  const cartoes = useMemo(() => {
    const codigos = new Set((modulos ?? []).filter((m) => m.enabled !== false).map((m) => m.module_code))
    return Object.keys(CATALOGO)
      .filter((c) => codigos.has(c))
      .map((codigo) => {
        const api_ = (modulos ?? []).find((m) => m.module_code === codigo)
        return { codigo, ...CATALOGO[codigo], alertasHoje: api_?.alerts_today ?? 0 }
      })
  }, [modulos])

  const abrir = useCallback(
    (c: (typeof cartoes)[number]) => {
      registrarVisita(c.codigo)
      navegar(c.destino)
    },
    [navegar],
  )

  /**
   * Entrada direta quando só há um módulo — regra escrita no rodapé do próprio
   * desenho. Fazer a pessoa escolher entre uma opção só é pedir um clique que
   * não decide nada. (No RVB hoje é exatamente este o caso: só EPI.)
   */
  useEffect(() => {
    if (cartoes.length === 1) {
      const unico = cartoes[0]
      registrarVisita(unico.codigo)
      navegar(unico.destino, { replace: true })
    }
  }, [cartoes, navegar])

  // Teclas 1..N abrem o módigo na posição — o desenho anuncia o atalho, então
  // ele tem de existir. Re-registrado quando a lista muda: um handler preso ao
  // primeiro render abriria o módulo errado depois que a lista chegasse.
  useEffect(() => {
    const aoTeclar = (e: KeyboardEvent) => {
      const i = Number.parseInt(e.key, 10)
      if (!i || i < 1 || i > cartoes.length) return
      abrir(cartoes[i - 1])
    }
    window.addEventListener('keydown', aoTeclar)
    return () => window.removeEventListener('keydown', aoTeclar)
  }, [cartoes, abrir])

  return (
    <div className={s.raiz}>
      <header className={s.topo}>
        <svg viewBox="0 0 100 100" width="30" height="30" aria-hidden="true">
          <defs>
            <mask id="lk-monograma">
              <rect width="100" height="100" fill="white" />
              <g transform="translate(24,22.4) scale(0.52)">
                <path d="M40 55.3 A20 20 0 1 1 60 55.3 L67 88 L33 88 Z" fill="black" />
              </g>
            </mask>
          </defs>
          <circle cx="50" cy="50" r="44" fill={lk.cor.brancoSinal} mask="url(#lk-monograma)" />
        </svg>
        <span className={s.marca}>LOGIKOS</span>
        <span className={s.divisor} />
        {user?.name && <span className={s.tenant}>{user.name}</span>}
        <span className={s.espacador} />
        <div className={s.identidade}>
          <span className={s.avatar}>
            {(user?.name ?? '?')
              .split(' ')
              .slice(0, 2)
              .map((p) => p[0])
              .join('')
              .toUpperCase()}
          </span>
          <div>
            <p className={s.nome}>{user?.name}</p>
            <p className={s.papel}>{user?.role}</p>
          </div>
        </div>
        <a className={s.sair} href="/login">
          Sair
        </a>
      </header>

      <main className={s.centro}>
        {modulos === null && !erro && (
          <LogikosLoader estado="waiting" variante="fullscreen" rotulo="CARREGANDO MÓDULOS" />
        )}

        {erro && (
          <div className={s.vazio}>
            <AlertTriangle size={26} strokeWidth={1.6} color={lk.estado.nc} aria-hidden="true" />
            <h1 className={s.titulo}>Não deu para carregar seus módulos</h1>
            <p className={s.subtitulo}>{erro}</p>
            <button className={s.admin} onClick={carregar}>
              Tentar novamente
            </button>
          </div>
        )}

        {modulos !== null && !erro && cartoes.length === 0 && (
          <div className={s.vazio}>
            <PencilRuler size={26} strokeWidth={1.6} color={lk.cor.cinzaNevoa} aria-hidden="true" />
            <h1 className={s.titulo}>Nenhum módulo liberado</h1>
            <p className={s.subtitulo}>
              Sua conta não tem módulo habilitado neste cliente. Quem administra o tenant
              pode liberar.
            </p>
          </div>
        )}

        {cartoes.length > 1 && (
          <>
            <div className={s.cabecalho}>
              <h1 className={s.titulo}>Onde você vai trabalhar agora?</h1>
              <p className={s.subtitulo}>
                Tecle o número ou clique. Troque a qualquer momento pelo topo do sistema.
              </p>
            </div>

            <div className={s.grade}>
              {cartoes.map((c, i) => {
                const Icone = c.icone
                const eUltimo = ultimo?.codigo === c.codigo
                return (
                  <button
                    key={c.codigo}
                    className={eUltimo ? `${s.cartao} ${s.cartaoUltimo}` : s.cartao}
                    onClick={() => abrir(c)}
                  >
                    {eUltimo && ultimo && (
                      <span className={s.selo}>ÚLTIMA VISITA · {quando(ultimo.em)}</span>
                    )}
                    <span className={s.linhaIcone}>
                      <Icone size={22} strokeWidth={1.7} aria-hidden="true" />
                      <span className={s.tecla}>{i + 1}</span>
                    </span>
                    <span className={s.textos}>
                      <span className={s.nomeModulo}>{c.nome}</span>
                      <span className={s.descricao}>{c.desc}</span>
                    </span>
                    <span className={s.rodapeCartao}>
                      {/* Estado por cor + palavra: o ponto sozinho não diz nada
                          para quem não distingue as cores. */}
                      <span
                        className={s.ponto}
                        style={{ background: c.alertasHoje > 0 ? lk.estado.nc : lk.estado.ok }}
                      />
                      <span
                        className={s.pendencia}
                        style={{ color: c.alertasHoje > 0 ? lk.estado.nc : lk.cor.cinzaNevoa }}
                      >
                        {c.alertasHoje > 0
                          ? `${c.alertasHoje} ${c.alertasHoje === 1 ? 'alerta hoje' : 'alertas hoje'}`
                          : 'sem alertas hoje'}
                      </span>
                    </span>
                  </button>
                )
              })}
            </div>

            {isSuperAdmin && (
              // Sem equivalente no front novo (C1) — honesto sobre o destino em vez
              // de teleportar calado: só superadmin vê, e o texto avisa que é a
              // área técnica antiga. Ver EXCECOES em coexistencia.test.tsx.
              <a
                className={s.admin}
                href="/admin/observability"
                title="Abre a área técnica do front antigo — sem equivalente novo ainda"
              >
                <ShieldCheck size={15} strokeWidth={1.8} aria-hidden="true" />
                Painel Admin — plataforma (área técnica antiga)
              </a>
            )}

            <p className={s.nota}>
              Quem tem um módulo só não vê esta tela — entra direto nele.
            </p>
          </>
        )}
      </main>
    </div>
  )
}
