/**
 * CropClassifier — aba "Classificar": EVOLUÇÃO de SearchFindingsPanel.tsx
 * pra classificação rápida de EPI (~3s/recorte). O humano vê UM recorte por
 * vez e marca um ESTADO por tipo de EPI (radio dentro do tipo, multilabel
 * entre tipos), em vez de desenhar caixa (~20s) — a lógica pura de mapeamento
 * estado→classe vive em cropClassifierLogic.ts (testada isolada).
 *
 * Reuso deliberado (⛔ isto NÃO é uma segunda UI de anotação):
 * - `cropStyle(bbox)` — mesmo truque de recorte por CSS de
 *   SearchFindingsPanel.tsx (copiado abaixo). Ver nota de limitação: ainda
 *   não existe um detector de "pessoa" dedicado no backend, então o bbox
 *   usado hoje é o frame inteiro [0,0,1,1] — cropStyle fica pronto pro dia
 *   em que um bbox de pessoa real alimentar este componente.
 * - carga de classes — mesmo endpoint/formato de AnnotationStudio.tsx e
 *   SearchFindingsPanel.tsx (GET /modules/epi/classes).
 * - "Ajustar caixa" abre o AnnotationStudio JÁ EXISTENTE (setStudio do pai,
 *   TrainingPage.tsx) — nenhum canvas novo.
 * - "Não sei" / "Reprovar·Recorte ruim" reusam POST /training/frames/
 *   curation (duvida/excluida) — o MESMO endpoint da curadoria em lote de
 *   TrainingGallery.tsx ("Marcar em dúvida"/"Excluir da coleta").
 * - "Aprovar" reusa POST /training/frames/{id}/annotations (replace-all,
 *   mesmo contrato usado por AnnotationStudio) — por isso busca as
 *   anotações existentes do frame ANTES de aprovar e preserva as humanas
 *   (source !== 'ai'); nunca promove proposta de IA a anotação por engano.
 *
 * 401-safety (requisito crítico): api.ts redireciona a PÁGINA INTEIRA pro
 * /login em qualquer 401 (window.location.href) — o estado do React some
 * junto. Por isso `pendingApprovals`/contadores da sessão/lista "classe a
 * criar"/rascunho do recorte aberto são persistidos no localStorage ANTES
 * de cada POST, não depois — e replayed automaticamente no próximo mount
 * (pós-login). Ver useEffect de persistência e replayPending() abaixo.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AlertTriangle, CheckCircle2, ImageOff } from 'lucide-react'
import { api, ApiError } from '../../services/api'
import { cameraService } from '../../services/cameraService'
import { useToast } from '../ui/Toast/useToast'
import { Skeleton } from '../ui/Skeleton/Skeleton'
import { Button } from '../ui/Button/Button'
import { Badge } from '../ui/Badge/Badge'
import { EmptyState } from '../ui/EmptyState/EmptyState'
import type { ApiResponse, Camera } from '../../types'
import type { RawAnnotation, StudioFrame } from './studioTypes'
import { useStudioKeyboard } from './useStudioKeyboard'
import { CameraFilterSelector, type CameraFilterOption } from '../training/CameraFilterSelector'
import {
  EPI_TYPES,
  GLOBAL_KEYS,
  KEY_BINDINGS,
  buildApprovalPayload,
  resolveClassId,
  setVerdictState,
  deveAutoAvancar,
  anexarLote,
  devePrefetch,
  ordenarPorCarencia,
  corteSeguro,
  tiposVisiveis,
  lacunasDosTipos,
  nomesDeClasseDosTipos,
  TIPOS_PRIORITARIOS,
  stateForKey,
  type LacunaCobertura,
  confiancaDasPropostas,
  medirAceitacao,
  mensagemClassesNaoResolvidas,
  suggestedPresenceStates,
  vereditoInicialDaProposta,
  intercalar,
  numeroDoBloco,
  reordenarCaudaIntercalada,
  cadenciaValida,
  CADENCIA_PADRAO,
  type Cadencia,
  type MissingClass,
  type RuntimeClass,
  type Verdict,
} from './cropClassifierLogic'
import * as s from './CropClassifier.css'

const STORAGE_KEY = 'epi_crop_classifier_session_v1'
const FULL_FRAME_BBOX: [number, number, number, number] = [0, 0, 1, 1]
const MODULE_CODE = 'epi'
/** Presets do seletor de cadência (D5). Valor do <select> = "N/M"; '' = desligado.
 * Só N, M ≥ 1: um lado em 0 não intercala nada (cadenciaValida devolve null). */
const CADENCIAS: readonly Cadencia[] = [
  { normais: 3, propostas: 1 },
  CADENCIA_PADRAO,
  { normais: 10, propostas: 5 },
]
const cadenciaKey = (c: Cadencia | null): string => (c ? `${c.normais}/${c.propostas}` : '')

/** Estilo absoluto do crop: mesmo truque de SearchFindingsPanel.tsx —
 * porcentagens de left/top/width/height de um filho `position:absolute` são
 * relativas ao container, então funciona sem precisar da resolução real do
 * frame. Não usado hoje (bbox = frame inteiro cai no branch cropImgContain,
 * sem distorcer proporção) — fica pronto pro bbox de pessoa real. */
function cropStyle(bbox: readonly [number, number, number, number]): React.CSSProperties {
  const [x, y, w, h] = bbox
  const safeW = Math.max(w, 0.02)
  const safeH = Math.max(h, 0.02)
  return {
    left: `${-(x / safeW) * 100}%`,
    top: `${-(y / safeH) * 100}%`,
    width: `${(1 / safeW) * 100}%`,
    height: `${(1 / safeH) * 100}%`,
  }
}

function isFullFrame(bbox: readonly [number, number, number, number]): boolean {
  return bbox[0] === 0 && bbox[1] === 0 && bbox[2] === 1 && bbox[3] === 1
}

interface ClassResponseItem {
  class_id: number
  class_name: string
  display_name?: string | null
  is_active?: boolean
  archived_at?: string | null
}

interface QueueFrame {
  id: string
  url: string | null
  filename: string
  camera_id: string | null
  created_at: string
  /** Propostas de IA pendentes neste recorte (servidor, mesmo campo que o card
   * da galeria usa) e os nomes de classe delas (lower/trim). Entra no braço
   * "propostas" da intercalação só se alguma for de PRESENÇA de tipo na tela
   * (temProposta) — sem os nomes (API antiga), pela contagem. */
  pending_proposals_count?: number | null
  pending_proposal_classes?: readonly string[] | null
}

interface MissingCropEntry {
  frameId: string
  filename: string
  missing: MissingClass[]
}

/** Mesmo shape de cropClassifierLogic.AnnotationBoxPayload — class_name e
 * module_code são OBRIGATÓRIOS no POST (annotation_service._validate_class
 * rejeita o batch inteiro com 400 sem eles). Fica persistido assim no
 * localStorage, então o replay de uma aprovação pendente também os leva. */
interface AnnotationBoxPayload {
  class_id: number
  class_name: string
  module_code: string
  x_center: number
  y_center: number
  width: number
  height: number
}

interface PendingApproval {
  frameId: string
  annotations: AnnotationBoxPayload[]
}

type LastAction =
  | { type: 'skip'; frameId: string }
  | { type: 'duvida'; frameId: string }
  | { type: 'excluida'; frameId: string }
  | { type: 'approve'; frameId: string; snapshotBefore: RawAnnotation[]; addedClassIds: number[] }

interface PersistedSession {
  cameraIds: string[]
  classFocus: number | null
  approvedCounts: Record<string, number>
  missingCrops: MissingCropEntry[]
  pendingApprovals: PendingApproval[]
  currentDraft: { frameId: string; verdict: Verdict } | null
  autoAvanco: boolean
  /** Filtro por classe: tipos de EPI escolhidos. Vazio = todos (sucessor do
   * antigo booleano `modoEstreito` — payload velho cai em "todos" sozinho,
   * sem migração, porque loadPersisted espalha sobre EMPTY_SESSION). */
  tiposSelecionados: string[]
  cadencia: Cadencia | null
}

const EMPTY_SESSION: PersistedSession = {
  cameraIds: [],
  classFocus: null,
  approvedCounts: {},
  missingCrops: [],
  pendingApprovals: [],
  currentDraft: null,
  autoAvanco: true,
  tiposSelecionados: [],
  // ⛔ Opt-in (decisão do dono): ninguém vê a fila intercalar sem escolher.
  cadencia: null,
}

function loadPersisted(): PersistedSession {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return EMPTY_SESSION
    return { ...EMPTY_SESSION, ...(JSON.parse(raw) as Partial<PersistedSession>) }
  } catch {
    return EMPTY_SESSION
  }
}

export interface CropClassifierProps {
  /** Deep-link da matriz de cobertura (CoverageMatrix "classificar →") —
   * vence a câmera persistida de uma sessão anterior quando informado. */
  initialCameraId?: string | null
  initialClassId?: number | null
  /** Abre o AnnotationStudio JÁ EXISTENTE (mesmo `setStudio` que TrainingPage
   * usa pra Imagens) — "Ajustar caixa" nunca constrói um canvas novo. */
  onOpenAdjust: (frames: StudioFrame[], index: number) => void
}

export function CropClassifier({ initialCameraId, initialClassId, onOpenAdjust }: CropClassifierProps) {
  const toast = useToast()
  const apiBase = import.meta.env.VITE_API_URL || ''

  const persistedRef = useRef<PersistedSession>(loadPersisted())
  const restoredDraftRef = useRef(persistedRef.current.currentDraft)

  // ── classes runtime (mesmo endpoint/formato de AnnotationStudio) ─────────
  const [classes, setClasses] = useState<RuntimeClass[]>([])
  const [classesLoading, setClassesLoading] = useState(true)

  // ── câmeras do tenant + filtro (reuso de CameraFilterSelector) ───────────
  const [allCameras, setAllCameras] = useState<Camera[]>([])
  const [cameraIds, setCameraIds] = useState<Set<string>>(
    () => new Set(initialCameraId ? [initialCameraId] : persistedRef.current.cameraIds),
  )
  const [classFocus] = useState<number | null>(initialClassId ?? persistedRef.current.classFocus)

  // ── fila de recortes (frame inteiro = "recorte" nesta v1) ────────────────
  const [queue, setQueue] = useState<QueueFrame[]>([])
  const [index, setIndex] = useState(0)
  const [loadingQueue, setLoadingQueue] = useState(true)
  const [imgFallback, setImgFallback] = useState<Record<string, 'fallback' | 'broken'>>({})

  // ── veredito do recorte corrente + anotações já existentes do frame ──────
  const [verdict, setVerdict] = useState<Verdict>({})
  const [existingAnnotations, setExistingAnnotations] = useState<RawAnnotation[] | null>(null)
  const [shownAt, setShownAt] = useState<number | null>(null)
  const [timings, setTimings] = useState<number[]>([])

  // ── sessão (persistida — ver 401-safety no topo do arquivo) ──────────────
  const [approvedCounts, setApprovedCounts] = useState<Record<string, number>>(persistedRef.current.approvedCounts)
  const [missingCrops, setMissingCrops] = useState<MissingCropEntry[]>(persistedRef.current.missingCrops)
  const [pendingApprovals, setPendingApprovals] = useState<PendingApproval[]>(persistedRef.current.pendingApprovals)
  const [syncing, setSyncing] = useState(false)
  /** Causa REAL da última falha de sincronização — antes o erro era engolido
   * num catch vazio e o banner só sabia dizer "pendente". */
  const [syncError, setSyncError] = useState<string | null>(null)
  /** Catálogo estável para o reparo de aprovações pendentes antigas, sem
   * re-criar replayPending a cada carga de classes. */
  const classesRef = useRef<RuntimeClass[]>([])
  classesRef.current = classes
  const [lastAction, setLastAction] = useState<LastAction | null>(null)
  // Ligado por padrão: com classe em foco, é o ganho principal da tela.
  const [autoAvanco, setAutoAvanco] = useState(persistedRef.current.autoAvanco ?? true)
  const [lacunas, setLacunas] = useState<LacunaCobertura[]>([])
  // Fila infinita: o lote de 40 acabava e a tela parava — o anotador tinha
  // que FECHAR e reabrir para continuar. Agora pagina e se realimenta.
  // Cursor (keyset) do servidor: o ID do ÚLTIMO item entregue no lote
  // anterior. Substitui a paginação por OFFSET — a fila ENCOLHE enquanto é
  // percorrida (cada veredito tira o frame do conjunto) e cresce por cima (a
  // coleta do NVR entra com created_at mais novo), então `OFFSET n*40`
  // escorregava sobre um conjunto de outro tamanho e o que ficava entre um
  // lote e o seguinte ⛔ NUNCA era mostrado.
  //
  // É só o id: o servidor lê o (created_at, id) exato da linha. Mandar o
  // created_at ecoado da resposta perdia subsegundo (Flask serializa em RFC
  // 822) e recriava o mesmo pulo silencioso, por dentro do conserto.
  const cursorRef = useRef<string | null>(null)
  const [buscandoMais, setBuscandoMais] = useState(false)
  const [esgotado, setEsgotado] = useState(false)
  const [vereditosNaSessao, setVereditosNaSessao] = useState(0)
  // Aceitação por classe: {classe: [aceitas, total]} — decide a fase C.
  const [aceitacao, setAceitacao] = useState<Record<string, [number, number]>>({})
  const jaVistosRef = useRef<Set<string>>(new Set())
  const currentFrameRef = useRef<string | null>(null)
  // Filtro por classe: quais tipos de EPI ficam na tela. Filtra a TELA, a
  // FILA (só recorte com proposta pendente dessas classes — ver
  // `proposalClasses`) e o PESO da carência. Nunca o banco — as demais
  // classes seguem existindo e anotáveis desmarcando o filtro. Vazio = todos.
  const [tiposSel, setTiposSel] = useState<Set<string>>(
    () => new Set(persistedRef.current.tiposSelecionados),
  )
  const tiposNaTela = useMemo(() => tiposVisiveis(tiposSel), [tiposSel])
  // Param `?proposal_classes=` da fila: string estável (CSV) para entrar nas
  // deps de loadQueue/buscarMais sem recriar closure a cada render.
  const proposalClasses = useMemo(() => nomesDeClasseDosTipos(tiposSel).join(','), [tiposSel])
  // Intercalação (D5): blocos normais/propostas na cauda da fila. Ref para os
  // callbacks de fila (mesma razão de lacunasRef: reordenar, ⛔ nunca resetar).
  // Saneada na entrada: payload velho/corrompido do localStorage vira null
  // (desligada), nunca um `{}` que chega ao intercalar.
  const [cadencia, setCadencia] = useState<Cadencia | null>(
    () => cadenciaValida(persistedRef.current.cadencia),
  )
  const cadenciaRef = useRef<Cadencia | null>(cadencia)
  cadenciaRef.current = cadencia
  // Tipos na tela também decidem quem é "com proposta" na intercalação —
  // mesmo motivo do ref acima (os callbacks de fila não podem reiniciar).
  const tiposNaTelaRef = useRef(tiposNaTela)
  tiposNaTelaRef.current = tiposNaTela
  // Aceitação por lote: {nº do bloco de propostas: [aceitas, total]}.
  const [aceitacaoPorBloco, setAceitacaoPorBloco] = useState<Record<number, [number, number]>>({})

  // A carência REORDENA, ⛔ não RESETA — e reordena SÓ O QUE AINDA NÃO FOI VISTO.
  //
  // Duas travas, de dois defeitos diferentes:
  //
  // 1. `lacunas` NÃO entra nas dependências de `loadQueue`. A matriz de
  //    cobertura chega assíncrona; quando entrava nas deps, `loadQueue`
  //    re-executava e com ela vinham `paginaRef.current = 1` e `setIndex(0)`.
  //    Reset é ato de TROCA DE FILTRO (câmera), e só — por isso a matriz é
  //    lida por REF aqui, nunca por dependência.
  //
  // 2. `queue` JÁ É a ordem de apresentação: não existe mais uma fila
  //    ordenada DERIVADA. Reordenar a fila INTEIRA a cada mudança (era um
  //    useMemo sobre `queue` cheio) fazia lote novo de carência alta entrar
  //    ANTES do cursor e empurrar para trás o que já teve veredito — o
  //    anotador recebia de volta recorte já excluído ou marcado dúvida.
  //    `index` é POSICIONAL: nem o que ficou atrás dele, nem o recorte que
  //    está na tela agora, podem se mover.
  //    Ver `reordenarCauda`.
  //
  // 3. A carência olha SÓ as classes dos tipos escolhidos (`lacunasDosTipos`).
  //    Sem isto o filtro mudava o painel mas não a ORDEM: "só luvas" seguia
  //    recebendo primeiro a câmera carente de outra coisa. Ref (e não só
  //    efeito) porque `loadQueue` e o prefetch ordenam o lote novo por ele.
  const lacunasFiltradas = useMemo(() => lacunasDosTipos(lacunas, tiposSel), [lacunas, tiposSel])
  const lacunasRef = useRef<readonly LacunaCobertura[]>([])
  lacunasRef.current = lacunasFiltradas
  const indexRef = useRef(0)
  indexRef.current = index

  const currentFrame = queue[index] ?? null
  currentFrameRef.current = currentFrame?.id ?? null

  // A matriz chegou (ou mudou) / a cadência mudou: reordena a CAUDA ainda não
  // vista. Não toca em posição, página nem fim-de-fila — isto é reordenação,
  // ⛔ nunca reset.
  useEffect(() => {
    if (lacunasFiltradas.length === 0 && cadencia == null) return
    setQueue(fila =>
      reordenarCaudaIntercalada(
        fila, corteSeguro(fila, indexRef.current, jaVistosRef.current), lacunasFiltradas, cadencia,
        tiposNaTela,
      ),
    )
  }, [lacunasFiltradas, cadencia, tiposNaTela])

  useEffect(() => {
    let cancelled = false
    void cameraService
      .list()
      .then(list => { if (!cancelled) setAllCameras(list) })
      .catch(() => { /* seletor fica vazio — filtro por câmera some, resto funciona */ })
    return () => { cancelled = true }
  }, [])

  const cameraOptions = useMemo<CameraFilterOption[]>(
    () => allCameras.map(c => ({ cameraId: c.id, channel: c.channel, name: c.name || null, count: 0 })),
    [allCameras],
  )
  const cameraLabel = useCallback(
    (id: string | null | undefined): string | null => (id ? allCameras.find(c => c.id === id)?.name ?? 'Câmera' : null),
    [allCameras],
  )

  const loadClasses = useCallback(async () => {
    setClassesLoading(true)
    try {
      const res = await api.get<ApiResponse<{ classes: ClassResponseItem[] }>>(`/modules/${MODULE_CODE}/classes`)
      const raw = res?.data?.classes ?? []
      setClasses(
        raw
          .filter(c => c.is_active !== false && !c.archived_at)
          .map(c => ({ classId: Number(c.class_id), name: c.display_name || c.class_name })),
      )
    } catch {
      toast.error('Erro ao carregar classes')
    } finally {
      setClassesLoading(false)
    }
  }, [toast])
  useEffect(() => { void loadClasses() }, [loadClasses])

  // Matriz de cobertura: alimenta a ordenação por carência. Falha aqui não
  // trava a fila — só a deixa na ordem do servidor (mais recente primeiro).
  useEffect(() => {
    let cancelado = false
    api.get<ApiResponse<{ gaps: LacunaCobertura[] }>>('/training/coverage-matrix')
      .then(res => { if (!cancelado) setLacunas(res?.data?.gaps ?? []) })
      .catch(() => { /* fila sem priorização é pior, não quebrada */ })
    return () => { cancelado = true }
  }, [])

  // Fila: reusa GET /training/images (mesma origem de dados da galeria,
  // filtrado a não-anotado/ativo) — um crop aprovado ganha annotation_count
  // > 0 no servidor e some sozinho de um recarregamento futuro; nenhuma
  // paginação/posição de fila precisa ser persistida por causa disso.
  const TAMANHO_LOTE = 40

  const loadQueue = useCallback(async () => {
    setLoadingQueue(true)
    try {
      const params = new URLSearchParams({
        page: '1',
        page_size: String(TAMANHO_LOTE),
        is_annotated: 'false',
        curation_status: 'active',
        // Só recorte de pessoa: o acervo mistura recorte e frame inteiro na
        // mesma tabela, e "esta pessoa está de máscara?" não tem resposta
        // sobre a cena inteira. Filtro é do servidor porque a fila é paginada
        // lá — filtrar aqui daria contagem e paginação erradas.
        only_crops: 'true',
      })
      if (cameraIds.size > 0) params.set('camera_ids', Array.from(cameraIds).join(','))
      // Filtro por classe É do servidor (a fila é paginada lá — filtrar aqui
      // daria contagem e paginação erradas): só recorte com proposta PENDENTE
      // de classe dos tipos escolhidos.
      if (proposalClasses) params.set('proposal_classes', proposalClasses)
      const res = await api.get<ApiResponse<{ frames: QueueFrame[] }>>(`/training/images?${params}`)
      // Carência primeiro: sem isto a primeira hora de anotação acelerada
      // é gasta em recorte de classe já farta.
      const primeiro = res?.data?.frames ?? []
      // Cursor semeado com o ÚLTIMO item do lote, na ordem do servidor.
      cursorRef.current = primeiro[primeiro.length - 1]?.id ?? null
      setEsgotado(primeiro.length < TAMANHO_LOTE)
      // Matriz por REF: ordena com a carência já conhecida sem que `lacunas`
      // vire dependência — era isso que resetava a fila no meio da sessão.
      //
      // Cinto de segurança: recorte que JÁ teve veredito nesta sessão nunca
      // volta, nem se o servidor o devolver (escrita da curadoria em voo,
      // "Recarregar fila", troca de filtro). `buscarMais` já filtrava por
      // `jaVistos` via anexarLote; este caminho não filtrava nada.
      // `esgotado` segue medido no lote CRU — quem diz "acabou" é o servidor.
      const inedito = primeiro.filter(f => !jaVistosRef.current.has(f.id))
      setQueue(intercalar(
        ordenarPorCarencia(inedito, lacunasRef.current), cadenciaRef.current, [], tiposNaTelaRef.current,
      ))
      setIndex(0)
    } catch {
      toast.error('Erro ao carregar fila de recortes')
    } finally {
      setLoadingQueue(false)
    }
  }, [cameraIds, proposalClasses, toast])
  // Próximo lote, em segundo plano. O anotador NUNCA vê a fila acabar nem
  // espera fetch: dispara quando ainda restam ~10 na frente dele.
  const buscarMais = useCallback(async () => {
    setBuscandoMais(true)
    try {
      const params = new URLSearchParams({
        page_size: String(TAMANHO_LOTE),
        is_annotated: 'false',
        curation_status: 'active',
        only_crops: 'true',
      })
      // Cursor keyset: pede o que vem DEPOIS do último item já entregue.
      const cur = cursorRef.current
      if (cur) params.set('before_id', cur)
      if (cameraIds.size > 0) params.set('camera_ids', Array.from(cameraIds).join(','))
      if (proposalClasses) params.set('proposal_classes', proposalClasses)
      const res = await api.get<ApiResponse<{ frames: QueueFrame[] }>>(`/training/images?${params}`)
      const lote = res?.data?.frames ?? []
      cursorRef.current = lote[lote.length - 1]?.id ?? cursorRef.current
      // "Acabou" é o SERVIDOR dizendo zero, não a fila local esvaziando.
      if (lote.length < TAMANHO_LOTE) setEsgotado(true)
      // Anexa no fim e reordena só a cauda ainda não vista: o lote novo pode
      // ter carência maior, mas ⛔ não pode passar na frente do cursor e empurrar
      // para trás o que já teve veredito.
      setQueue(fila => {
        const juntada = anexarLote(fila, lote, jaVistosRef.current)
        const corte = corteSeguro(juntada, indexRef.current, jaVistosRef.current)
        return reordenarCaudaIntercalada(
          juntada, corte, lacunasRef.current, cadenciaRef.current, tiposNaTelaRef.current,
        )
      })
    } catch (err) {
      // 410 = o frame que servia de cursor sumiu (vídeo pai apagado por
      // alguém da equipe — o pool é compartilhado). Recarrega a fila: o
      // `loadQueue` já filtra `jaVistos`, então nada que já teve veredito
      // volta, e o servidor deixa de ser lido como "fila concluída".
      if (err instanceof ApiError && err.status === 410) {
        cursorRef.current = null
        // Recuperação silenciosa NO LOG, ⛔ não na tela: no instante do 410 o
        // prefetch corre à frente, então o recorte visível ainda não teve
        // veredito — não está em `jaVistos` — e o `loadQueue` volta pra
        // página 1 com `setIndex(0)`. Quem estava 200 recortes adentro vê o
        // recorte trocar sozinho e perde o rascunho. Toast de ERRO seria
        // mentira (a recuperação funcionou); silêncio transforma
        // "recuperado" em "a tela bugou". Uma linha de info é o que é verdade.
        toast.info('A fila foi recarregada — um recorte foi removido por outra pessoa')
        void loadQueue()
        return
      }
      // Silencioso de propósito: falhar o prefetch não pode interromper quem
      // está anotando. Tenta de novo no próximo veredito.
    } finally {
      setBuscandoMais(false)
    }
  }, [cameraIds, proposalClasses, loadQueue, toast])

  useEffect(() => {
    if (devePrefetch(queue.length - index, buscandoMais, esgotado)) void buscarMais()
  }, [queue.length, index, buscandoMais, esgotado, buscarMais])

  useEffect(() => { void loadQueue() }, [loadQueue])

  // Anotações existentes do frame corrente: alimenta a sugestão (bloco 3) E
  // a base preservada ao aprovar (POST é replace-all — ver approve()).
  useEffect(() => {
    if (!currentFrame) { setExistingAnnotations(null); return }
    setShownAt(Date.now())
    setExistingAnnotations(null)
    let cancelled = false
    api
      .get<{ success: boolean; annotations: RawAnnotation[] }>(`/training/frames/${currentFrame.id}/annotations`)
      .then(res => { if (!cancelled) setExistingAnnotations(res?.annotations ?? []) })
      .catch(() => { if (!cancelled) setExistingAnnotations([]) })
    return () => { cancelled = true }
  }, [currentFrame])

  // Retoma o rascunho persistido se o recorte corrente for o mesmo que
  // estava aberto quando a sessão foi salva (401-safety) — senão, começa
  // vazio (nada decidido ainda bloqueia o Aprovar, ver buildApprovalPayload).
  useEffect(() => {
    if (!currentFrame) { setVerdict({}); return }
    const draft = restoredDraftRef.current
    setVerdict(draft && draft.frameId === currentFrame.id ? draft.verdict : {})
  }, [currentFrame])

  const suggested = useMemo(() => {
    const proposalClassIds = (existingAnnotations ?? []).filter(a => a.source === 'ai').map(a => a.class_id)
    if (proposalClassIds.length === 0) return new Set<string>()
    return suggestedPresenceStates(proposalClassIds, classes)
  }, [existingAnnotations, classes])

  // `tipo:estado` sugerido → maior confiança da proposta (null = sem
  // confiança, ex.: DINO legado). Só alimenta o % visível no botão.
  const suggestedConfidence = useMemo(
    () => confiancaDasPropostas((existingAnnotations ?? []).filter(a => a.source === 'ai'), classes),
    [existingAnnotations, classes],
  )

  // Fase A do propor-confirmar: a proposta do modelo entra PRÉ-SELECIONADA.
  // Enter confirma (barato), tecla corrige (barato) — e o que grava é sempre
  // `humana`: as anotações `ai` são descartadas no approve(), nunca promovidas.
  //
  // Só roda com o veredito ainda vazio: se o humano já mexeu neste recorte, a
  // proposta NÃO sobrescreve o que ele decidiu.
  //
  // ⛔ Só tipos NA TELA: proposta de tipo escondido pelo filtro não é
  // pré-selecionada — o humano não a vê, e Enter a gravaria às cegas.
  useEffect(() => {
    if (suggested.size === 0) return
    setVerdict(v => (Object.keys(v).length === 0 ? vereditoInicialDaProposta(suggested, tiposNaTela) : v))
  }, [suggested, tiposNaTela])

  const avgSeconds = timings.length > 0 ? timings.reduce((a, b) => a + b, 0) / timings.length : null

  // "Classe em foco" do deep-link da matriz de cobertura — só destaque
  // visual do tipo dono daquela classe (requisito 7), nunca filtra/trava
  // os demais tipos (a fila em si é por câmera, não por classe — o
  // endpoint de imagens não tem esse filtro pra reusar).
  const emphasizedTypeKey = useMemo(() => {
    if (classFocus == null || classes.length === 0) return null
    for (const type of EPI_TYPES) {
      for (const state of type.states) {
        if (resolveClassId(state.classNameCandidates, classes) === classFocus) return type.key
      }
    }
    return null
  }, [classFocus, classes])

  // Deep-link "classificar →" da matriz: o tipo dono da classe ENTRA no filtro
  // (adiciona, não substitui — filtro vazio já mostra tudo, fica como está).
  // Sem isto, um filtro persistido "só máscara" escondia justamente o tipo
  // que a matriz mandou classificar.
  useEffect(() => {
    if (initialClassId == null || emphasizedTypeKey == null) return
    setTiposSel(prev =>
      prev.size === 0 || prev.has(emphasizedTypeKey) ? prev : new Set([...prev, emphasizedTypeKey]),
    )
  }, [initialClassId, emphasizedTypeKey])

  // Persistência (401-safety): tudo que NÃO dá pra recuperar de volta do
  // servidor num remount — contadores da sessão, lista "classe a criar",
  // aprovações ainda não confirmadas e o rascunho do recorte aberto.
  useEffect(() => {
    const payload: PersistedSession = {
      cameraIds: Array.from(cameraIds),
      classFocus,
      approvedCounts,
      missingCrops,
      pendingApprovals,
      currentDraft: currentFrame ? { frameId: currentFrame.id, verdict } : null,
      autoAvanco,
      tiposSelecionados: Array.from(tiposSel),
      cadencia,
    }
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(payload))
    } catch {
      /* quota/modo privado — sessão só não sobrevive a um crash, não trava o fluxo */
    }
  }, [cameraIds, classFocus, approvedCounts, missingCrops, pendingApprovals, verdict, currentFrame, autoAvanco, tiposSel, cadencia])

  // Aprovação gravada por uma versão que ainda omitia class_name/module_code
  // fica presa para sempre: o backend responde 400 e nenhum retry resolve.
  // Repara com o catálogo em memória antes de reenviar — o trabalho do humano
  // é recuperável, o payload é que estava incompleto.
  const repairPending = useCallback(
    (entry: PendingApproval): PendingApproval => ({
      ...entry,
      annotations: entry.annotations.map(a => ({
        ...a,
        class_name: a.class_name || classesRef.current.find(c => c.classId === a.class_id)?.name || '',
        module_code: a.module_code || MODULE_CODE,
      })),
    }),
    [],
  )

  const replayPending = useCallback(async (items: PendingApproval[]) => {
    if (items.length === 0) return
    setSyncing(true)
    setSyncError(null)
    for (const entry of items) {
      const repaired = repairPending(entry)
      // Só erro transitório merece nova tentativa; 4xx é permanente e some
      // do banner com a causa REAL, em vez de girar em silêncio para sempre.
      let lastErr: unknown = null
      for (let attempt = 0; attempt < 3; attempt++) {
        try {
          await api.post(`/training/frames/${repaired.frameId}/annotations`, {
            annotations: repaired.annotations,
          })
          setPendingApprovals(prev => prev.filter(p => p.frameId !== repaired.frameId))
          lastErr = null
          break
        } catch (err) {
          lastErr = err
          const status = (err as { status?: number })?.status
          if (status != null && status >= 400 && status < 500) break
          await new Promise(r => setTimeout(r, 500 * 2 ** attempt))
        }
      }
      if (lastErr != null) {
        const msg = (lastErr as { message?: string })?.message ?? String(lastErr)
        setSyncError(msg)
        console.error('crop_classifier_sync_failed', { frameId: repaired.frameId, error: lastErr })
      }
    }
    setSyncing(false)
  }, [repairPending])

  // Replay automático uma vez no mount (ex.: acabou de logar de novo depois
  // do 401 ter interrompido no meio de um Aprovar). Espera o catálogo de
  // classes carregar — sem ele o reparo acima não teria como achar o nome.
  const didReplayRef = useRef(false)
  useEffect(() => {
    if (didReplayRef.current || classesLoading) return
    didReplayRef.current = true
    if (persistedRef.current.pendingApprovals.length > 0) void replayPending(persistedRef.current.pendingApprovals)
  }, [replayPending, classesLoading])

  const advance = useCallback(() => {
    if (currentFrameRef.current) jaVistosRef.current.add(currentFrameRef.current)
    setVereditosNaSessao(n => n + 1)
    setIndex(i => Math.min(i + 1, queue.length))
  }, [queue.length])
  const goBack = useCallback(() => setIndex(i => Math.max(i - 1, 0)), [])

  // Bloco de propostas em que o recorte da tela cai (0 = recorte normal).
  const blocoAtual = useMemo(() => numeroDoBloco(queue, index, tiposNaTela), [queue, index, tiposNaTela])

  // `verdictOverride`: no auto-avanço a tecla e a aprovação acontecem no mesmo
  // evento, e o `verdict` do closure ainda é o ANTERIOR (setState é assíncrono).
  // Passar o veredito já calculado evita aprovar o recorte sem a última tecla.
  const approve = useCallback(async (verdictOverride?: Verdict) => {
    if (!currentFrame) return
    const frame = currentFrame
    const vereditoFinal = verdictOverride ?? verdict

    // Mede a aceitação ANTES de gravar: proposta × o que o humano deixou —
    // só dos tipos na tela (tipo escondido não foi julgado por ninguém).
    if (suggested.size > 0) {
      const medida = medirAceitacao(suggested, vereditoFinal, tiposNaTela)
      setAceitacao(prev => {
        const proximo = { ...prev }
        for (const { classe, aceita } of medida) {
          const [a, tot] = proximo[classe] ?? [0, 0]
          proximo[classe] = [a + (aceita ? 1 : 0), tot + 1]
        }
        return proximo
      })
      // Mesma medida, agregada por lote (bloco de propostas da intercalação).
      if (blocoAtual > 0) {
        const aceitas = medida.filter(m => m.aceita).length
        setAceitacaoPorBloco(prev => {
          const [a, tot] = prev[blocoAtual] ?? [0, 0]
          return { ...prev, [blocoAtual]: [a + aceitas, tot + medida.length] }
        })
      }
    }
    // ⛔ `tiposNaTela`: só tipo VISÍVEL vira anotação. O veredito pode trazer
    // chave de tipo escondido (rascunho restaurado, tecla, filtro estreitado
    // depois da pré-seleção) — nenhuma delas pode virar anotação humana.
    const { payload, missing } = buildApprovalPayload(
      vereditoFinal, FULL_FRAME_BBOX, classes, MODULE_CODE, tiposNaTela,
    )
    const elapsedSec = shownAt != null ? (Date.now() - shownAt) / 1000 : null

    if (missing.length > 0) {
      setMissingCrops(prev => [
        ...prev.filter(m => m.frameId !== frame.id),
        { frameId: frame.id, filename: frame.filename, missing },
      ])
      toast.warning(mensagemClassesNaoResolvidas(missing, classes))
    }

    if (payload.length > 0) {
      // Replace-all: preserva anotações humanas já existentes (nunca
      // promove proposta 'ai' pendente a manual por engano — ela continua
      // esperando seu próprio fluxo de revisão).
      // class_name/module_code viajam junto aqui também: o backend valida
      // TODO o batch, então uma anotação preservada sem nome derruba o save
      // inteiro — inclusive as novas (annotation_service._validate_class).
      const preserved: AnnotationBoxPayload[] = (existingAnnotations ?? [])
        .filter(a => a.source !== 'ai')
        .map(a => ({
          class_id: a.class_id,
          // Valores que o próprio servidor devolveu no GET; o catálogo em
          // memória é só o fallback (classe arquivada some da lista mas a
          // anotação antiga continua válida e não pode ser perdida).
          class_name: a.class_name ?? classes.find(c => c.classId === a.class_id)?.name ?? '',
          module_code: a.module_code ?? MODULE_CODE,
          x_center: a.x_center, y_center: a.y_center, width: a.width, height: a.height,
        }))
      const fullSet = [...preserved, ...payload]

      // Persiste ANTES do POST — se a rede cair ou o 401 global redirecionar
      // a página inteira, o trabalho já está gravado (replay no próximo mount).
      setPendingApprovals(prev => [...prev.filter(p => p.frameId !== frame.id), { frameId: frame.id, annotations: fullSet }])
      setApprovedCounts(prev => {
        const next = { ...prev }
        for (const box of payload) {
          const name = classes.find(c => c.classId === box.class_id)?.name ?? `#${box.class_id}`
          next[name] = (next[name] ?? 0) + 1
        }
        return next
      })
      if (elapsedSec != null) setTimings(prev => [...prev.slice(-49), elapsedSec])
      setLastAction({
        type: 'approve',
        frameId: frame.id,
        snapshotBefore: existingAnnotations ?? [],
        addedClassIds: payload.map(p => p.class_id),
      })

      try {
        await api.post(`/training/frames/${frame.id}/annotations`, { annotations: fullSet })
        setPendingApprovals(prev => prev.filter(p => p.frameId !== frame.id))
      } catch {
        toast.error('Erro ao sincronizar — a aprovação ficou pendente, nada foi perdido')
      }
    }

    advance()
  }, [currentFrame, verdict, classes, existingAnnotations, shownAt, toast, advance, suggested, blocoAtual,
      tiposNaTela])

  const markCuration = useCallback(
    async (status: 'duvida' | 'excluida', label: string) => {
      if (!currentFrame) return
      const frameId = currentFrame.id
      setLastAction({ type: status, frameId })
      advance()
      try {
        await api.post('/training/frames/curation', { frame_ids: [frameId], status })
      } catch {
        toast.error(`Erro ao marcar ${label} — tente de novo pela galeria`)
      }
    },
    [currentFrame, advance, toast],
  )
  const markNaoSei = useCallback(() => void markCuration('duvida', '"não sei"'), [markCuration])
  const markReprovar = useCallback(() => void markCuration('excluida', 'como reprovado'), [markCuration])

  // Pular (defer): sem chamada ao backend — o frame segue "não anotado" e
  // reaparece numa fila futura (curation_status=active continua servindo-o).
  const skip = useCallback(() => {
    if (!currentFrame) return
    setLastAction({ type: 'skip', frameId: currentFrame.id })
    advance()
  }, [currentFrame, advance])

  // Desfazer (U) — reverte só a ÚLTIMA ação (aprovar/não-sei/reprovar/pular).
  const undo = useCallback(async () => {
    const action = lastAction
    if (!action) return
    setLastAction(null)
    const idxInQueue = queue.findIndex(f => f.id === action.frameId)
    if (idxInQueue >= 0) setIndex(idxInQueue)
    if (action.type === 'skip') return
    if (action.type === 'duvida' || action.type === 'excluida') {
      try {
        await api.post('/training/frames/curation', { frame_ids: [action.frameId], status: 'active' })
      } catch {
        toast.error('Erro ao desfazer')
      }
      return
    }
    // Mesmo motivo do `preserved` em approve(): sem class_name/module_code o
    // backend recusa o batch e o desfazer não desfaria nada.
    const revertSet: AnnotationBoxPayload[] = action.snapshotBefore
      .filter(a => a.source !== 'ai')
      .map(a => ({
        class_id: a.class_id,
        class_name: a.class_name ?? classes.find(c => c.classId === a.class_id)?.name ?? '',
        module_code: a.module_code ?? MODULE_CODE,
        x_center: a.x_center, y_center: a.y_center, width: a.width, height: a.height,
      }))
    setPendingApprovals(prev => prev.filter(p => p.frameId !== action.frameId))
    setApprovedCounts(prev => {
      const next = { ...prev }
      for (const classId of action.addedClassIds) {
        const name = classes.find(c => c.classId === classId)?.name ?? `#${classId}`
        next[name] = Math.max(0, (next[name] ?? 1) - 1)
      }
      return next
    })
    try {
      await api.post(`/training/frames/${action.frameId}/annotations`, { annotations: revertSet })
    } catch {
      toast.error('Erro ao desfazer aprovação')
    }
  }, [lastAction, queue, classes, toast])

  const openAdjust = useCallback(() => {
    if (!currentFrame) return
    const frame: StudioFrame = {
      id: currentFrame.id,
      url: currentFrame.url,
      filename: currentFrame.filename,
      cameraName: cameraLabel(currentFrame.camera_id),
      capturedAt: currentFrame.created_at,
      cameraId: currentFrame.camera_id,
    }
    onOpenAdjust([frame], 0)
  }, [currentFrame, onOpenAdjust, cameraLabel])

  // Teclado: reusa useStudioKeyboard (mesmo guard "ignora enquanto o foco
  // está num input" do AnnotationStudio).
  useStudioKeyboard(
    useCallback(
      (event: KeyboardEvent) => {
        if (event.ctrlKey || event.metaKey || event.altKey) return
        const key = event.key
        if (key === 'Enter') { event.preventDefault(); void approve(); return }
        if (key === 'Backspace') { event.preventDefault(); goBack(); return }
        if (key === GLOBAL_KEYS.undo) { event.preventDefault(); void undo(); return }
        if (key === GLOBAL_KEYS.skip) { event.preventDefault(); skip(); return }
        if (key === GLOBAL_KEYS.naoSei) { event.preventDefault(); markNaoSei(); return }
        if (key === GLOBAL_KEYS.reprovar) { event.preventDefault(); markReprovar(); return }
        const binding = stateForKey(key)
        // Tecla de tipo ESCONDIDO pelo filtro não grava nada: veredito que o
        // humano não pode ver na tela é dado errado em silêncio.
        if (binding && tiposNaTela.some(t => t.key === binding.typeKey)) {
          event.preventDefault()
          const proximo = setVerdictState(verdict, binding.typeKey, binding.stateKey)
          setVerdict(proximo)
          if (deveAutoAvancar(binding, emphasizedTypeKey, autoAvanco)) void approve(proximo)
        }
      },
      [approve, goBack, undo, skip, markNaoSei, markReprovar, verdict, emphasizedTypeKey, autoAvanco,
       tiposNaTela],
    ),
  )

  const frameSrc = useCallback(
    (frame: QueueFrame): string =>
      imgFallback[frame.id] === 'fallback' || !frame.url
        ? `${apiBase}/api/training/frames/${frame.id}/image`
        : frame.url,
    [imgFallback, apiBase],
  )

  const frameBroken = currentFrame ? imgFallback[currentFrame.id] === 'broken' : false

  return (
    <div className={s.root}>
      <div className={s.sessionBar}>
        <CameraFilterSelector cameras={cameraOptions} selected={cameraIds} onChange={setCameraIds} />
        <span className={s.sessionStat}>
          {/* "Acabou" é o SERVIDOR dizendo zero, não a fila local esvaziando —
              antes o lote de 40 terminava e o anotador tinha que fechar a tela
              e reabrir. Enquanto houver mais, o próximo lote já vem vindo. */}
          {esgotado && queue.length - index === 0 ? (
            <>
              fila concluída — <span className={s.sessionStatStrong}>{vereditosNaSessao}</span>{' '}
              recorte(s) nesta sessão
            </>
          ) : (
            <>
              <span className={s.sessionStatStrong}>{Math.max(queue.length - index, 0)}</span>{' '}
              restante(s) na fila{!esgotado && '+'}
            </>
          )}
        </span>
        {/* Aceitação da pré-anotação, por classe: é o número que decide se a
            fase C (propor também ausência, ou propor sem confirmação) tem base.
            Só aparece quando o modelo propôs algo nesta sessão. */}
        {Object.keys(aceitacao).length > 0 && (
          <span className={s.sessionStat}>
            proposta aceita:{' '}
            {Object.entries(aceitacao)
              .map(([classe, [a, tot]]) => `${classe.split(':')[0]} ${a}/${tot}`)
              .join(' · ')}
          </span>
        )}
        {/* A mesma aceitação, por lote (bloco de propostas da intercalação) —
            últimos 3 blocos; a tendência aparece sem precisar de gráfico. */}
        {Object.keys(aceitacaoPorBloco).length > 0 && (
          <span className={s.sessionStat}>
            por lote:{' '}
            {Object.entries(aceitacaoPorBloco)
              .slice(-3)
              .map(([bloco, [a, tot]]) => `#${bloco} ${a}/${tot}`)
              .join(' · ')}
          </span>
        )}
        {/* Cadência da intercalação (D5, opt-in — desligada por padrão): N
            normais, depois M com proposta pré-selecionada. Ligar ou desligar
            muda só a ORDEM da cauda ainda não vista (reordenação estável);
            ⛔ nunca reseta a fila nem volta a um estado "anterior". */}
        <label
          className={s.sessionStat}
          title="Desligado = fila só por carência. Ligar/desligar reordena só o que você ainda não viu — não reseta a fila."
        >
          intercalar{' '}
          <select
            aria-label="cadência da intercalação"
            value={cadenciaKey(cadencia)}
            onChange={e => {
              const [n, m] = e.target.value.split('/').map(Number)
              setCadencia(cadenciaValida({ normais: n, propostas: m }))
            }}
          >
            <option value="">desligado (só carência)</option>
            {CADENCIAS.map(c => (
              <option key={cadenciaKey(c)} value={cadenciaKey(c)}>
                {c.normais} normais / {c.propostas} propostas
              </option>
            ))}
          </select>
        </label>
        {avgSeconds != null && (
          <span className={s.sessionStat}>
            ~<span className={s.sessionStatStrong}>{avgSeconds.toFixed(1)}s</span>/recorte
          </span>
        )}
        {/* Filtro por classe: marca o que vai ser anotado nesta rajada. Tudo
            marcado = sem filtro (persiste vazio, não lista redundante). */}
        <span className={s.sessionStat}>anotar:</span>
        {EPI_TYPES.map(t => (
          <label key={t.key} className={s.sessionStat}>
            <input
              type="checkbox"
              checked={tiposSel.size === 0 || tiposSel.has(t.key)}
              onChange={() =>
                setTiposSel(prev => {
                  const base = prev.size === 0 ? new Set(EPI_TYPES.map(x => x.key)) : new Set(prev)
                  if (base.has(t.key)) base.delete(t.key)
                  else base.add(t.key)
                  return base.size === EPI_TYPES.length ? new Set<string>() : base
                })
              }
            />{' '}
            {t.label}
          </label>
        ))}
        <button
          type="button"
          className={s.stateButton}
          onClick={() => setTiposSel(new Set(TIPOS_PRIORITARIOS))}
        >
          só prioritárias
        </button>
        {/* Só aparece com classe em foco: sem foco o auto-avanço não age (o
            recorte pode precisar de veredito para vários tipos), e um controle
            que não faz nada é pior que controle nenhum. */}
        {emphasizedTypeKey != null && (
          <label className={s.sessionStat}>
            <input
              type="checkbox"
              checked={autoAvanco}
              onChange={e => setAutoAvanco(e.target.checked)}
            />{' '}
            avanço automático
          </label>
        )}
        <div className={s.countBadges}>
          {Object.entries(approvedCounts).map(([name, count]) => (
            <Badge key={name} variant="success">{name}: {count}</Badge>
          ))}
          {missingCrops.length > 0 && (
            <Badge variant="warning">{missingCrops.length} aguardando classe</Badge>
          )}
        </div>
      </div>

      {pendingApprovals.length > 0 && (
        <div className={s.pendingBanner} role="alert">
          <AlertTriangle size={14} />
          {pendingApprovals.length} aprovaç{pendingApprovals.length === 1 ? 'ão' : 'ões'} ainda não
          sincronizada(s) com o servidor — guardada(s) neste navegador, sobrevive(m) a recarregar.
          {syncError && <span className={s.pendingReason}> Motivo: {syncError}</span>}
          <button className={s.retryButton} onClick={() => void replayPending(pendingApprovals)} disabled={syncing}>
            {syncing ? 'sincronizando…' : 'tentar de novo'}
          </button>
        </div>
      )}

      {loadingQueue || (classesLoading && classes.length === 0) ? (
        <Skeleton variant="rect" width="100%" height={480} />
      ) : !currentFrame ? (
        <EmptyState
          icon={<CheckCircle2 size={32} />}
          title={queue.length === 0 ? 'Nada para classificar com esse filtro' : 'Fila concluída nesta sessão'}
          description={
            tiposSel.size > 0
              ? 'Só recortes com proposta pendente das classes marcadas em "anotar" entram na fila — desmarque o filtro, troque a câmera ou recarregue.'
              : 'Troque a câmera ou recarregue para buscar mais recortes não anotados.'
          }
          action={<Button size="sm" variant="secondary" onClick={() => void loadQueue()}>Recarregar fila</Button>}
        />
      ) : (
        <div className={s.main}>
          <div className={s.stage}>
            {frameBroken ? (
              <div className={s.imageBroken}>
                <ImageOff size={32} />
                <span>Este recorte não carregou.</span>
                <div style={{ display: 'flex', gap: 8 }}>
                  <Button size="sm" variant="secondary" onClick={skip}>Pular</Button>
                  <Button size="sm" variant="danger" onClick={markReprovar}>Recorte ruim</Button>
                </div>
              </div>
            ) : isFullFrame(FULL_FRAME_BBOX) ? (
              <img
                className={s.cropImgContain}
                src={frameSrc(currentFrame)}
                alt={currentFrame.filename}
                onError={() =>
                  setImgFallback(prev => ({
                    ...prev,
                    [currentFrame.id]:
                      prev[currentFrame.id] === 'fallback' || !currentFrame.url ? 'broken' : 'fallback',
                  }))
                }
              />
            ) : (
              <div className={s.cropTile}>
                <img
                  className={s.cropImg}
                  src={frameSrc(currentFrame)}
                  style={cropStyle(FULL_FRAME_BBOX)}
                  alt={currentFrame.filename}
                  onError={() =>
                    setImgFallback(prev => ({
                      ...prev,
                      [currentFrame.id]:
                        prev[currentFrame.id] === 'fallback' || !currentFrame.url ? 'broken' : 'fallback',
                    }))
                  }
                />
              </div>
            )}
          </div>

          <div className={s.panel}>
            {tiposNaTela.map(type => (
              <div
                key={type.key}
                data-type={type.key}
                className={`${s.typeGroup}${type.key === emphasizedTypeKey ? ` ${s.typeGroupEmphasized}` : ''}`}
              >
                <span className={s.typeLabel}>{type.label}</span>
                <div className={s.stateRow}>
                  {type.states.map(state => {
                    const active = verdict[type.key] === state.key
                    const binding = KEY_BINDINGS.find(b => b.typeKey === type.key && b.stateKey === state.key)
                    const isSuggested = suggested.has(`${type.key}:${state.key}`)
                    const conf = suggestedConfidence.get(`${type.key}:${state.key}`)
                    const pct = typeof conf === 'number' ? Math.round(conf * 100) : null
                    const activeClass = !active
                      ? ''
                      : state.kind === 'presente'
                        ? s.stateButtonActivePresente
                        : state.kind === 'ausente'
                          ? s.stateButtonActiveAusente
                          : s.stateButtonActiveNeutral
                    return (
                      <button
                        key={state.key}
                        type="button"
                        className={`${s.stateButton}${activeClass ? ` ${activeClass}` : ''}`}
                        onClick={() => setVerdict(v => setVerdictState(v, type.key, state.key))}
                        title={isSuggested
                          ? `Sugerido por proposta de IA pendente${pct != null ? ` (${pct}% de confiança)` : ''}`
                          : undefined}
                      >
                        {binding && <span className={s.keyBadge}>{binding.key.toUpperCase()}</span>}
                        {state.label}
                        {pct != null && <span className={s.confBadge}>{pct}%</span>}
                        {isSuggested && !active && <span className={s.suggestedDot} />}
                      </button>
                    )
                  })}
                </div>
              </div>
            ))}

            {/* Recorte com proposta pré-selecionada: diz o que o Enter vai fazer.
                Gate em `suggested`, não em pending_proposals_count — proposta só
                de ausência nunca é pré-selecionada, e aí o aviso mentiria. */}
            {suggested.size > 0 && (
              <Badge variant="warning">
                proposta da IA pré-selecionada{blocoAtual > 0 ? ` · lote #${blocoAtual}` : ''} — Enter confirma, tecla corrige
              </Badge>
            )}

            <div className={s.actions}>
              <Button variant="primary" onClick={() => void approve()}>Aprovar</Button>
              <Button variant="secondary" onClick={skip}>Pular</Button>
              <Button variant="secondary" onClick={markNaoSei}>Não sei</Button>
              <Button variant="danger" onClick={markReprovar}>Recorte ruim / Reprovar</Button>
              <Button variant="secondary" onClick={openAdjust}>Ajustar caixa</Button>
            </div>

            <div className={s.legend}>
              <span className={s.kbd}>Enter</span> aprovar · <span className={s.kbd}>Backspace</span> anterior ·{' '}
              <span className={s.kbd}>U</span> desfazer · <span className={s.kbd}>Shift+S</span> pular ·{' '}
              <span className={s.kbd}>N</span> não sei · <span className={s.kbd}>Shift+R</span> reprovar
            </div>

            {missingCrops.length > 0 && (
              <div className={s.missingList}>
                <strong>Aguardando criação de classe:</strong>
                {missingCrops.slice(0, 5).map(m => (
                  <span key={m.frameId}>
                    {m.filename}: {m.missing.map(x => `${x.typeLabel} → ${x.stateLabel}`).join(', ')}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
