/**
 * Revisão Qualidade — fila (R1) e detalhe (R2) numa tela só.
 *
 * Desenho: `Revisão Qualidade.dc.html`. Backend: blueprint `quality_bp`,
 * prefixo `/api/v1/quality` (`services/api/app/api/v1/quality/routes.py`).
 * Tabela: `{tenant_schema}.quality_inspections` (migration 104).
 *
 * A tela antiga equivalente (`modules/quality/pages/QualityInspectionsPage`) é
 * 100% MOCK — zero chamada de API. Nada dela foi aproveitado.
 *
 * ─── A INVERSÃO QUE MORDE — leia antes de mexer nos botões ───────────────────
 *
 * `feedback_status` NÃO é o veredito sobre a peça, é o veredito sobre o ALARME:
 *
 *     'rejected'  = rejeitar o alarme da IA  →  a peça está **CONFORME**
 *     'confirmed' = confirmar o NOK da IA    →  a peça é **NÃO CONFORME**
 *
 * Quem implementar lendo o nome do status ("rejected? então reprovou a peça")
 * inverte o julgamento da fila inteira, em silêncio, e o dado de treino sai
 * espelhado. É a razão de `CONFORME` mandar `rejected` logo abaixo.
 *
 * ─── LACUNAS DO DESENHO — medidas no código, não supostas ────────────────────
 *
 * O que o desenho pede e o servidor NÃO tem. Cada uma aparece na tela como
 * controle desabilitado com o motivo no `title`, ou simplesmente não aparece —
 * nunca como número inventado.
 *
 *  · **Ponto de inspeção (P1..P8)** — não existe: nenhuma tabela, coluna ou
 *    rota. O mais próximo é `validation_type VARCHAR(10)` ('v1'|'v2'|'v3'), que
 *    são 3 valores sem nome legível. O filtro fica desabilitado.
 *  · **Estação** — a coluna `station` existe (migration 033) mas o worker que
 *    grava inspeções (`quality_inference.py:204`) nunca a preenche, e
 *    `GET /inspections` não aceita filtro por estação. Filtro desabilitado.
 *  · **Número da peça ('AN-24-0781')** — `piece_id` também não é preenchido
 *    pelo worker; o `piece_number` legível vive em `quality_pieces`, sem join
 *    em nenhuma rota de inspeção. Some da linha: UUID cru na tela é proibido, e
 *    NULL fingindo peça é pior.
 *  · **Chips 'SUSPEITA DE NC' / 'DÚVIDA'** — não há bucket de dúvida/baixa
 *    confiança no módulo qualidade. O que existe é `result` ('ok'|'nok'), e é
 *    isso que os chips mostram, com o nome certo.
 *  · **SLA de 45 min e 'idade máx'** — SLA não existe no backend. A idade sai
 *    de `created_at` no cliente; a MÁXIMA da fila só é verdadeira quando a fila
 *    inteira coube na página, e por isso só aparece nesse caso.
 *  · **'NC + CLASSE'** — `PATCH .../feedback` grava só
 *    `feedback_status/by/at/notes`. NENHUMA rota escreve `defect_class` a
 *    partir de revisão humana. O botão vira "NÃO CONFORME" (que é real) e a
 *    faixa de classes do desenho fica no lugar, desabilitada.
 *  · **'Foto inválida'** — `valid_statuses` é {confirmed, rejected,
 *    retrain_requested, false_negative}. Não há para onde mandar. Desabilitado.
 *  · **'A decisão vira anotação de treino automaticamente'** — falso. Feedback
 *    só cria `quality_retrain_suggestions` em retrain_requested/false_negative,
 *    e sugestão não é anotação: anotar exige `POST /prepare-annotation` (Celery)
 *    disparado à mão. O texto do rodapé diz o que acontece de verdade.
 *  · **Bbox sobre a foto e '1,3 s' de inferência** — `quality_inspections` não
 *    tem coluna de caixa nem de latência. Só `confidence`, que é o que a
 *    legenda mostra.
 *  · **Bloco MEDIÇÃO (OCR do paquímetro / WISER)** — inteiro sem lastro: o
 *    `OcrService` lê NÚMERO DE PEÇA, não medida, e não é exposto por rota
 *    nenhuma; a integração WISER só EXPORTA. Não renderiza nunca.
 *  · **HISTÓRICO DA PEÇA** — `GET /inspections` não aceita filtro `piece_id`, e
 *    `piece_id` é NULL. O painel fica, dizendo por quê.
 *
 * ─── DUAS ARMADILHAS DE ENVELOPE QUE JÁ DERRUBARAM TELA ─────────────────────
 *
 *  1. `GET /inspections/<id>` faz `return success(item)` — a inspeção vem
 *     DIRETO em `data`, não em `data.inspection`. A tela antiga lê
 *     `data.inspection`, recebe `undefined` e renderiza "não encontrada". Aqui
 *     o detalhe **reusa o item que a lista já trouxe** (mesmas colunas + o
 *     `camera_name` do JOIN): uma requisição a menos e a armadilha some.
 *  2. `PATCH .../feedback` devolve `{inspection_id, feedback_status}`, não
 *     `{inspection}`. Nada aqui lê a resposta além do sucesso HTTP.
 *
 * ─── RATE LIMIT DA EVIDÊNCIA (60 URLs/hora/usuário) ─────────────────────────
 *
 * `quality_video_security.py:23`: 60 URLs assinadas por usuário por HORA,
 * compartilhadas entre evidence-url, clip-url e frame url. O desenho mostra 7
 * miniaturas na fila — pedir uma por linha queima o teto em poucos refreshes e
 * devolve 429 justamente para quem está revisando. **A fila não busca imagem.**
 * A URL é pedida só quando um item é ABERTO, e fica em cache por id: voltar
 * para a fila e reabrir não gasta outra.
 *
 * ─── PERMISSÃO ──────────────────────────────────────────────────────────────
 *
 * Não existe chave `quality:*` no registry (`app/core/permissions.py`) — as
 * rotas de qualidade são protegidas por JWT + módulo, sem gate de permissão.
 * Usamos `verification:read`/`verification:write`, cujas descrições no registry
 * são literalmente esta tela ("fila de detecções pendentes de verificação
 * humana" / "aprovar, rejeitar ou corrigir detecções"). Inventar `quality:read`
 * esconderia a tela para todo mundo menos o superadmin — que é justamente quem
 * nunca veria o problema. Chave própria para qualidade fica registrada como
 * pedido ao backend.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AlertTriangle, Check, ChevronRight, ImageOff, Lock, X } from 'lucide-react'

import { useAuth } from '../../hooks/useAuth'
import { api } from '../../services/api'
import { useToast } from '../../components/ui/Toast/useToast'
import { LogikosLoader } from '../shell/LogikosLoader'
import * as s from './RevisaoQualidade.css'

/** Colunas reais de `quality_inspections` (migration 104) + o JOIN de câmera. */
export interface Inspecao {
  id: string
  camera_id?: string | null
  camera_name?: string | null
  result?: 'ok' | 'nok' | string | null
  /** ⚠️ é o NOME da classe do modelo (string), não um id numérico. */
  defect_class?: string | null
  defect_category?: string | null
  confidence?: number | null
  evidence_r2_key?: string | null
  production_order?: string | null
  product_type?: string | null
  shift?: string | null
  feedback_status?: string | null
  created_at?: string | null
}

interface Camera {
  id: string
  name?: string | null
}

/** `public.module_classes ∪ public.yolo_classes` do tenant. */
interface ClasseModulo {
  class_id?: string | number
  class_name?: string
  display_name?: string
}

interface Snapshot {
  id: string
  production_order?: string | null
  captured_at?: string | null
}

type Veredito = 'rejected' | 'confirmed'

/** Turnos reais do backend — derivados da hora UTC em `routes.py:68`. Não há
 *  "1º/2º turno" nem configuração de turno por tenant. */
const TURNOS: ReadonlyArray<[string, string]> = [
  ['morning', 'Manhã (06–14 UTC)'],
  ['afternoon', 'Tarde (14–22 UTC)'],
  ['night', 'Noite (22–06 UTC)'],
]

/** Teto do endpoint (`per_page` é clampado em 100). */
const POR_PAGINA = 100

/** Acima disto a idade fica âmbar — mesmo corte do desenho (30 min). */
const IDADE_ATENCAO_MIN = 30

export function minutosDesde(iso: string | null | undefined, agora = Date.now()): number | null {
  if (!iso) return null
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return null
  return Math.max(0, Math.floor((agora - t) / 60000))
}

export function formatarIdade(min: number | null): string {
  if (min === null) return '—'
  if (min < 60) return `${min} min`
  return `${Math.floor(min / 60)}h${String(min % 60).padStart(2, '0')}`
}

/**
 * Rótulo legível da classe.
 *
 * `defect_class` chega como o nome da classe do modelo ('defeito_visual'). O
 * catálogo do TENANT (`/api/modules/quality/classes`) traz `display_name` — é
 * ele que casa com a taxonomia real do cliente. `/api/v1/quality/classes` é
 * uma lista fixa genérica de 9 itens e não serve.
 *
 * Sem correspondência, devolve o nome cru: mostrar o que o banco tem é honesto;
 * inventar um rótulo bonito não é. Nota: a tela antiga comparava
 * `classes.find(c => c.id === inspection.defect_class)` — number contra string,
 * nunca casa, e o badge de defeito nunca aparecia.
 */
export function rotuloDaClasse(
  nome: string | null | undefined,
  catalogo: Record<string, string>,
): string | null {
  if (!nome) return null
  return catalogo[nome] ?? nome
}

export function RevisaoQualidade() {
  const { can } = useAuth()
  const toast = useToast()
  const podeLer = can('verification:read')
  const podeDecidir = can('verification:write')

  const [turno, setTurno] = useState('')
  const [cameraId, setCameraId] = useState('')
  const [fila, setFila] = useState<Inspecao[] | null>(null)
  const [total, setTotal] = useState(0)
  const [erro, setErro] = useState<string | null>(null)
  const [selId, setSelId] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)
  const [cameras, setCameras] = useState<Camera[]>([])
  const [catalogo, setCatalogo] = useState<Record<string, string>>({})
  const [classes, setClasses] = useState<string[]>([])
  const [evidencia, setEvidencia] = useState<{ url: string | null; motivo: string | null }>({
    url: null,
    motivo: null,
  })
  const [padrao, setPadrao] = useState<Snapshot | null>(null)

  /** Cache de URL assinada por inspeção — o teto é 60/hora (ver cabeçalho). */
  const cacheUrl = useRef(new Map<string, { url: string | null; motivo: string | null }>())
  /** Trava síncrona: `enviando` só vale no próximo render, e duas teclas no
   *  MESMO tick leem `false` nas duas — dois PATCH no mesmo item. */
  const enviandoRef = useRef(false)

  const rota = useMemo(() => {
    const q = new URLSearchParams({ feedback_status: 'pending', per_page: String(POR_PAGINA) })
    if (turno) q.set('shift', turno)
    if (cameraId) q.set('camera_id', cameraId)
    return `/v1/quality/inspections?${q.toString()}`
  }, [turno, cameraId])

  const carregar = useCallback(() => {
    setErro(null)
    setFila(null)
    api
      .get<{ data?: { inspections?: Inspecao[]; total?: number } }>(rota)
      .then((r) => {
        setFila(r.data?.inspections ?? [])
        setTotal(r.data?.total ?? r.data?.inspections?.length ?? 0)
      })
      .catch((e) => setErro(e instanceof Error ? e.message : 'Erro ao carregar a fila'))
  }, [rota])

  useEffect(() => {
    if (!podeLer) return
    carregar()
  }, [carregar, podeLer])

  // Câmeras: traduz camera_id (UUID) → nome e serve o filtro. Falha aqui não
  // derruba a fila — o filtro some, a revisão continua.
  useEffect(() => {
    if (!podeLer) return
    api
      .get<{ data?: { cameras?: Camera[] } }>('/v1/quality/cameras')
      .then((r) => setCameras(r.data?.cameras ?? []))
      .catch(() => undefined)
    // ⚠️ prefixo /api/modules — NÃO /api/v1/modules (modules/routes.py:19).
    api
      .get<{ data?: { classes?: ClasseModulo[] } }>('/modules/quality/classes')
      .then((r) => {
        const lista = r.data?.classes ?? []
        setCatalogo(
          Object.fromEntries(
            lista
              .filter((c) => c.class_name)
              .map((c) => [c.class_name as string, c.display_name ?? (c.class_name as string)]),
          ),
        )
        setClasses(lista.map((c) => c.display_name ?? c.class_name ?? '').filter(Boolean))
      })
      .catch(() => undefined)
  }, [podeLer])

  const selecionado = useMemo(
    () => (selId ? (fila ?? []).find((i) => i.id === selId) ?? null : null),
    [fila, selId],
  )

  // Evidência do item ABERTO — nunca da lista. Ver o rate limit no cabeçalho.
  useEffect(() => {
    if (!selecionado) {
      setEvidencia({ url: null, motivo: null })
      return
    }
    if (!selecionado.evidence_r2_key) {
      setEvidencia({ url: null, motivo: 'Esta inspeção não gravou foto de evidência.' })
      return
    }
    const cacheado = cacheUrl.current.get(selecionado.id)
    if (cacheado) {
      setEvidencia(cacheado)
      return
    }
    let vivo = true
    setEvidencia({ url: null, motivo: null })
    api
      .get<{ data?: { url?: string } }>(`/v1/quality/inspections/${selecionado.id}/evidence-url`)
      .then((r) => {
        const achado = { url: r.data?.url ?? null, motivo: r.data?.url ? null : 'Sem URL assinada.' }
        cacheUrl.current.set(selecionado.id, achado)
        if (vivo) setEvidencia(achado)
      })
      .catch((e) => {
        const msg = e instanceof Error ? e.message : ''
        const falha = {
          url: null,
          motivo: /429|limit/i.test(msg)
            ? 'Limite de 60 URLs assinadas por hora atingido — a evidência volta quando a janela renovar.'
            : `GET /api/v1/quality/inspections/${selecionado.id}/evidence-url · ${msg || 'falhou'}`,
        }
        cacheUrl.current.set(selecionado.id, falha)
        if (vivo) setEvidencia(falha)
      })
    return () => {
      vivo = false
    }
  }, [selecionado])

  // Snapshot de referência da CÂMERA (o mais perto que existe de "padrão").
  useEffect(() => {
    if (!selecionado?.camera_id) {
      setPadrao(null)
      return
    }
    let vivo = true
    setPadrao(null)
    // ⚠️ `return success(snapshots)` — a LISTA vem direto em `data`, não em
    // `data.snapshots`; e o campo é `captured_at`, não `created_at`.
    api
      .get<{ data?: Snapshot[] }>(`/v1/quality/reference-snapshots/${selecionado.camera_id}`)
      .then((r) => {
        if (vivo) setPadrao(Array.isArray(r.data) ? r.data[0] ?? null : null)
      })
      .catch(() => undefined)
    return () => {
      vivo = false
    }
  }, [selecionado])

  const decidir = useCallback(
    async (status: Veredito) => {
      if (!selecionado || !podeDecidir || enviandoRef.current) return
      enviandoRef.current = true
      setEnviando(true)
      try {
        // A resposta é {inspection_id, feedback_status} — NÃO {inspection}.
        await api.patch(`/v1/quality/inspections/${selecionado.id}/feedback`, { status })
        // O item sai da fila porque saiu do filtro `pending` no servidor:
        // mantê-lo apresentaria de novo o que já foi julgado.
        setFila((f) => (f ?? []).filter((i) => i.id !== selecionado.id))
        setTotal((t) => Math.max(0, t - 1))
        setSelId(null)
        toast.success(
          status === 'rejected' ? 'Peça marcada como conforme' : 'Não conformidade confirmada',
        )
      } catch (e) {
        toast.error(e instanceof Error ? e.message : 'Erro ao registrar a decisão')
      } finally {
        enviandoRef.current = false
        setEnviando(false)
      }
    },
    [podeDecidir, selecionado, toast],
  )

  // Deps completas de propósito: o listener acompanha o item corrente. Handler
  // preso a um render antigo carimba veredito no item que já saiu da tela.
  useEffect(() => {
    if (!selecionado) return
    const aoTeclar = (e: KeyboardEvent) => {
      const alvo = e.target as HTMLElement | null
      if (alvo && /^(INPUT|TEXTAREA|SELECT)$/.test(alvo.tagName)) return
      if (e.metaKey || e.ctrlKey || e.altKey) return
      const k = e.key.toLowerCase()
      if (k === 'a') void decidir('rejected')
      else if (k === 'n') void decidir('confirmed')
      else if (k === 'escape') setSelId(null)
      else return
      e.preventDefault()
    }
    window.addEventListener('keydown', aoTeclar)
    return () => window.removeEventListener('keydown', aoTeclar)
  }, [decidir, selecionado])

  if (!podeLer) {
    return (
      <div className={s.centro}>
        <Lock size={36} strokeWidth={1.5} aria-hidden="true" />
        <span className={s.centroTitulo}>Sem permissão</span>
        <span className={s.centroTexto}>
          A fila de revisão exige a permissão <code>verification:read</code>. Peça ao
          administrador do seu tenant.
        </span>
      </div>
    )
  }

  if (erro) {
    return (
      <div className={s.centro}>
        <AlertTriangle size={36} strokeWidth={1.5} aria-hidden="true" />
        <span className={s.centroTitulo}>Não foi possível carregar a fila</span>
        <span className={s.centroTecnico}>
          GET /api{rota} · {erro}
        </span>
        <button type="button" className={s.botaoPrimario} onClick={carregar}>
          Tentar novamente
        </button>
      </div>
    )
  }

  if (fila === null) {
    return <LogikosLoader estado="waiting" variante="fullscreen" rotulo="CARREGANDO FILA" />
  }

  const nok = fila.filter((i) => i.result === 'nok').length
  const ok = fila.filter((i) => i.result === 'ok').length
  const filaInteira = fila.length >= total
  const idades = fila.map((i) => minutosDesde(i.created_at)).filter((m): m is number => m !== null)
  const maisAntigo = idades.length ? Math.max(...idades) : null

  // ── R2 · DETALHE ──────────────────────────────────────────────────────────
  if (selecionado) {
    const eNok = selecionado.result === 'nok'
    const rotulo = rotuloDaClasse(selecionado.defect_class, catalogo)
    const idade = minutosDesde(selecionado.created_at)
    const meta = [
      selecionado.camera_name ?? null,
      selecionado.production_order ? `OP ${selecionado.production_order}` : null,
      selecionado.product_type,
      idade !== null ? `há ${formatarIdade(idade)}` : null,
    ].filter(Boolean)

    return (
      <div className={`${s.raiz} ${s.larguraDetalhe}`}>
        <div className={s.cabecalhoDetalhe}>
          <button type="button" className={s.voltar} onClick={() => setSelId(null)}>
            ← Fila ({fila.length})
          </button>
          <span className={eNok ? s.chipNc : s.chipOk}>
            {eNok ? (
              <AlertTriangle size={13} strokeWidth={2.2} aria-hidden="true" />
            ) : (
              <Check size={13} strokeWidth={2.6} aria-hidden="true" />
            )}
            {eNok ? 'IA APONTOU NOK' : 'IA APONTOU OK'}
          </span>
          <span className={s.tituloDetalhe}>{rotulo ?? 'Sem classe registrada'}</span>
          <span className={s.meta}>{meta.join(' · ')}</span>
        </div>

        <div className={s.painesDetalhe}>
          <div className={s.coluna}>
            <div className={eNok ? s.overlineNc : s.overline}>Encontrado — foto da inspeção</div>
            <div className={`${s.palco} ${eNok ? s.palcoNc : ''}`}>
              {evidencia.url ? (
                <img
                  className={s.imagem}
                  src={evidencia.url}
                  alt={`Evidência da inspeção ${rotulo ?? ''}`}
                  draggable={false}
                />
              ) : (
                <span className={s.semImagem}>
                  <ImageOff size={26} strokeWidth={1.5} aria-hidden="true" />
                  {evidencia.motivo ?? 'Carregando evidência…'}
                </span>
              )}
              {/* Sem bbox: `quality_inspections` não guarda coordenadas — só
                  `confidence` e o nome da classe. Sem latência: não há coluna
                  de tempo de inferência em lugar nenhum do módulo. */}
              <span className={s.legendaPalco}>
                {typeof selecionado.confidence === 'number'
                  ? `confiança ${Math.round(selecionado.confidence * 100)}%`
                  : 'sem confiança registrada'}
              </span>
            </div>
          </div>

          <div className={s.coluna}>
            <div className={s.overline}>Especificado — referência da câmera</div>
            <div className={s.palco}>
              <span className={s.semImagem}>
                <ImageOff size={26} strokeWidth={1.5} aria-hidden="true" />
                {padrao ? (
                  <>
                    Há uma referência desta câmera
                    {padrao.production_order ? ` (OP ${padrao.production_order})` : ''}
                    {padrao.captured_at
                      ? `, capturada em ${new Date(padrao.captured_at).toLocaleString('pt-BR')}`
                      : ''}
                    , mas não há como exibi-la:{' '}
                    <code>GET /reference-snapshots/&lt;camera_id&gt;</code> devolve a chave do
                    objeto (r2_key) e nenhuma rota assina essa URL.
                  </>
                ) : (
                  <>
                    Nenhuma referência capturada para esta câmera. O padrão é gravado no
                    primeiro OK do lote — e é por câmera e ordem de produção, não por ponto de
                    inspeção.
                  </>
                )}
              </span>
            </div>
          </div>

          <div className={s.colunaLateral}>
            <div className={s.overline}>Histórico da peça</div>
            <div className={s.cartaoLateral}>
              <span className={s.centroTexto}>
                Não há como montar o histórico: <code>GET /inspections</code> não aceita filtro
                por peça, e o worker que grava as inspeções não preenche <code>piece_id</code>.
                Registrado como pedido ao backend.
              </span>
              <div className={s.rodapeLateral}>
                Turno {selecionado.shift ?? '—'}
                <br />
                Estação não registrada pelo worker
              </div>
            </div>
          </div>
        </div>

        {/* A faixa de classes do desenho fica — e fica desabilitada. Esconder
            faria a lacuna sumir do radar de quem decide o roadmap; deixar
            clicável seria botão que não faz nada. */}
        <div className={s.faixaClasses}>
          <span className={s.nota}>Classe da NC:</span>
          {(classes.length ? classes : ['sem catálogo de classes']).slice(0, 8).map((c) => (
            <button
              key={c}
              type="button"
              className={s.chipClasse}
              disabled
              title="Nenhuma rota grava a classe da NC: PATCH /inspections/<id>/feedback escreve só feedback_status, feedback_by, feedback_at e feedback_notes."
            >
              {c}
            </button>
          ))}
        </div>

        <div className={s.barraDecisao}>
          <button
            type="button"
            className={s.conforme}
            onClick={() => void decidir('rejected')}
            disabled={!podeDecidir || enviando}
            title={podeDecidir ? undefined : 'Exige a permissão verification:write'}
          >
            <Check size={18} strokeWidth={2.6} aria-hidden="true" />
            CONFORME <span className={s.tecla}>A</span>
          </button>
          <button
            type="button"
            className={s.naoConforme}
            onClick={() => void decidir('confirmed')}
            disabled={!podeDecidir || enviando}
            title={podeDecidir ? undefined : 'Exige a permissão verification:write'}
          >
            <X size={18} strokeWidth={2.6} aria-hidden="true" />
            NÃO CONFORME <span className={s.tecla}>N</span>
          </button>
          <button
            type="button"
            className={s.acaoNeutra}
            disabled
            title="Sem status equivalente: o feedback aceita apenas confirmed, rejected, retrain_requested e false_negative — 'foto inválida' não é nenhum deles."
          >
            Foto inválida
          </button>
          <span className={s.nota}>
            A decisão grava só o veredito humano. Ela <strong>não</strong> vira anotação de
            treino: anotar exige preparar os frames em uma ação separada, que ainda não tem
            lugar nesta tela.
          </span>
        </div>
      </div>
    )
  }

  // ── R1 · FILA ─────────────────────────────────────────────────────────────
  return (
    <div className={`${s.raiz} ${s.larguraFila}`}>
      <div className={s.cabecalho}>
        <h1 className={s.titulo}>Fila de revisão</h1>
        <span className={s.contagem}>{total} itens</span>
        {nok > 0 && (
          <span className={s.pilulaNc}>
            <AlertTriangle size={13} strokeWidth={2.2} aria-hidden="true" />
            {nok} apontados NOK
          </span>
        )}
        {ok > 0 && (
          <span className={s.pilulaOk}>
            <Check size={13} strokeWidth={2.6} aria-hidden="true" />
            {ok} apontados OK
          </span>
        )}
        <span className={s.espacador} />
        {/* A idade máxima só é verdade quando a fila inteira veio: o endpoint
            ordena por created_at DESC e pagina, então com fila truncada o mais
            antigo REAL está numa página que não foi lida. */}
        {filaInteira && maisAntigo !== null && (
          <span className={s.nota}>
            mais antigo há <span className={s.dado}>{formatarIdade(maisAntigo)}</span>
          </span>
        )}
      </div>

      <div className={s.filtros}>
        <select
          className={s.seletor}
          disabled
          aria-label="Ponto de inspeção"
          title="Ponto de inspeção não existe no backend: nenhuma tabela, coluna ou rota. O mais próximo é validation_type ('v1'|'v2'|'v3'), sem nome legível e sem filtro."
        >
          <option>Todos os pontos</option>
        </select>
        <select
          className={s.seletor}
          disabled
          aria-label="Estação"
          title="A coluna station existe mas o worker que grava as inspeções nunca a preenche, e GET /inspections não aceita filtro por estação."
        >
          <option>Todas as estações</option>
        </select>
        <select
          className={s.seletor}
          value={turno}
          aria-label="Turno"
          onChange={(e) => setTurno(e.target.value)}
        >
          <option value="">Todos os turnos</option>
          {TURNOS.map(([valor, nome]) => (
            <option key={valor} value={valor}>
              {nome}
            </option>
          ))}
        </select>
        <select
          className={s.seletor}
          value={cameraId}
          aria-label="Câmera"
          onChange={(e) => setCameraId(e.target.value)}
        >
          <option value="">Todas as câmeras</option>
          {cameras.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name ?? c.id}
            </option>
          ))}
        </select>
      </div>

      {fila.length === 0 ? (
        <div className={s.centro}>
          <Check size={36} strokeWidth={1.5} aria-hidden="true" />
          <span className={s.centroTitulo}>Fila vazia</span>
          <span className={s.centroTexto}>
            Nada aguardando revisão{turno || cameraId ? ' com estes filtros' : ''}.
          </span>
        </div>
      ) : (
        <div className={s.lista}>
          {fila.map((i) => {
            const eNok = i.result === 'nok'
            const idade = minutosDesde(i.created_at)
            const rotulo = rotuloDaClasse(i.defect_class, catalogo)
            const meta = [
              i.camera_name ?? null,
              i.production_order ? `OP ${i.production_order}` : null,
              i.product_type,
            ].filter(Boolean)
            return (
              <button
                key={i.id}
                type="button"
                className={s.item}
                onClick={() => setSelId(i.id)}
              >
                {/* O quadro fica; a imagem não. Ver o rate limit no cabeçalho. */}
                <span
                  className={s.miniatura}
                  title="A miniatura não é carregada na fila: a URL da evidência é assinada e o limite é de 60 por hora por usuário, compartilhado com o clipe. A foto abre no detalhe."
                >
                  <ImageOff size={16} strokeWidth={1.5} aria-hidden="true" />
                  no detalhe
                </span>
                <span className={s.corpoItem}>
                  <span className={s.linhaTopo}>
                    <span className={eNok ? s.chipNc : s.chipOk}>
                      {eNok ? (
                        <AlertTriangle size={12} strokeWidth={2.2} aria-hidden="true" />
                      ) : (
                        <Check size={12} strokeWidth={2.6} aria-hidden="true" />
                      )}
                      {eNok ? 'IA APONTOU NOK' : 'IA APONTOU OK'}
                    </span>
                    <span className={s.classe}>{rotulo ?? 'Sem classe registrada'}</span>
                  </span>
                  <span className={s.meta}>{meta.join(' · ') || 'Sem câmera e sem ordem de produção'}</span>
                </span>
                <span
                  className={idade !== null && idade > IDADE_ATENCAO_MIN ? s.idadeVelha : s.idade}
                >
                  {formatarIdade(idade)}
                </span>
                <ChevronRight size={16} strokeWidth={2} className={s.seta} aria-hidden="true" />
              </button>
            )
          })}
        </div>
      )}

      <span className={s.notaMono}>
        atalhos no detalhe: A conforme · N não conforme · Esc volta
      </span>
      {!filaInteira && (
        <span className={s.nota}>
          Mostrando os {fila.length} mais recentes de {total}. O endpoint pagina por
          created_at DESC — os mais antigos estão nas páginas seguintes.
        </span>
      )}
    </div>
  )
}
