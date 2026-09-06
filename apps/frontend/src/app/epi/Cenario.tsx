/**
 * Cenário & Operações — `/epi/cameras/:cameraId/cenario` (F5-LEVE).
 *
 * Fonte única: `docs/design/handoff-f5/Cenário e Operações.dc.html`. Das 6
 * "abas" da prancha só DUAS viram tela — "Regras da câmera" (lista) e
 * "Editor" (3 passos) — as outras quatro são documentação da prancha
 * (catálogo de estados, mapa de conexões, pedidos ao backend, microcopy).
 *
 * ─── CONTRATO REAL (medido no código, não suposto) ──────────────────────────
 *
 * EXISTE: `GET/POST /cameras/<id>/operations`, `PUT /operations/<id>` (só
 * `name`+`config`), `DELETE /operations/<id>`, `POST /operations/<id>/test`,
 * `GET /modules/<code>/classes`, `GET /cameras/<id>/snapshot`.
 *
 * EM VOO nesta mesma rodada (outra branch — pode não estar mergeada ainda no
 * momento do PR): `template_id`, pausar/retomar, último disparo. PR #608 (o
 * backend desta rodada) fechou os três: `POST /cameras/<id>/operations`
 * aceita `template_id` e o ecoa; `GET .../operations` devolve `template_id` +
 * `last_event_at` por item; `POST /operations/<id>/pause` e
 * `POST /operations/<id>/resume` existem de verdade (resposta
 * `data.operation.status`). A tela manda `template_id` sempre; ao LER, se
 * faltar, infere pelo `type_id` real — os 5 `type_id` abaixo são os das
 * classes canônicas (`epi_zone.py`, `position.py`, `counting_line.py`,
 * `dwell_zone.py`, `overlap_dynamic.py`), não invenção. Guarda de
 * compatibilidade: se o PR do backend mergear DEPOIS deste (pause/resume
 * ainda 404/405), a tela para de tentar e o botão vira selo de dependência
 * — sem fingir que pausou.
 *
 * NÃO EXISTE (controle desenhado, com selo, zero ação falsa): avaliação
 * OK/NOK (B2 — sem tabela, sem rota), simular sobre a cena (B6 — o único
 * candidato real, `POST /operations/<id>/test`, avalia detecções que o
 * CALLER fornece contra uma operação JÁ SALVA; não roda a config em
 * rascunho contra os últimos minutos gravados, que é o que o botão promete —
 * não serve, então fica com o selo), confirmação de que o box aplicou (B9).
 *
 * ACHADO fora do script original: a prancha lista "sentido da linha
 * (entra/sai)" como NÃO EXISTE (B7). Falso — medido em
 * `counting_line.py`: `direction` é campo obrigatório do schema e É
 * respeitado em `evaluate()` (linhas 227-229 filtram por 'in'/'out'). A
 * tela implementa o controle de verdade, sem selo.
 *
 * `overlap_dynamic` (aproximação) não tem campo de geometria no schema real
 * — é sobreposição entre DUAS CLASSES em qualquer lugar do quadro, não uma
 * zona. A prancha desenha uma zona para esse template mesmo assim (para a
 * UX ficar igual às outras 4); a tela mantém o desenho como REFERÊNCIA
 * VISUAL declarada — nunca como recorte espacial que não existe. Isso é
 * pedido **B11 — geometria para aproximação** (motor passar a respeitar
 * `zone_points` em `overlap_dynamic`; aditivo, pequeno-médio). Até lá, um
 * aviso (`AVISO_APROXIMACAO_SEM_ZONA`) aparece no painel do passo 3 E no
 * preview "O QUE VAI ACONTECER", e a frase natural nunca cita o lugar
 * desenhado para este template — só "vale para toda a imagem desta câmera".
 *
 * ⛔ Esta tela nunca cria classe (isso é do Estúdio) e nunca mostra JSON cru
 * para quem não é superadmin.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ArrowRightLeft,
  Clock,
  Frame,
  HardHat,
  LayoutGrid,
  Plus,
  Radar,
  ShieldAlert,
  TriangleAlert,
  type LucideIcon,
} from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import { moduloDaCamera } from '../../components/training/CameraModelScope'
import { useAuth } from '../../hooks/useAuth'
import { useCameraSnapshot } from '../../hooks/useCameraSnapshot'
import { api, ApiError } from '../../services/api'
import type { ApiResponse, Camera } from '../../types'
import { LogikosLoader } from '../shell/LogikosLoader'
import { rotaNova } from '../RotasNovas'
import { lk } from '../tokens/lk.css'
import { SemPermissao } from '../shell/SemPermissao'
import * as s from './Cenario.css'

// ── contrato ─────────────────────────────────────────────────────────────────

/** Campos reais de `operations` (operation_repository.py) + os "em voo"
 * desta rodada — todos opcionais: a tela nunca assume que chegaram. */
interface Operacao {
  id: number
  camera_id: string
  module_id: string
  type_id: string
  name: string
  config?: Record<string, unknown> | null
  /** `active`/`inactive` — é o que `pause`/`resume` (PR #608) escrevem. */
  status?: string | null
  /** Em voo (B3). Quando ausente, infere pelo `type_id`. */
  template_id?: string | null
  /** Em voo (B10). Ausente = o cartão omite a linha, nunca inventa hora. */
  last_event_at?: string | null
  created_at?: string
}

interface ClasseCatalogo {
  class_name: string
  display_name: string
}

type Forma = 'area' | 'linha'
type TemplateKey = 'epi' | 'restrita' | 'linha' | 'tempo' | 'aproximacao'

interface Condicao {
  chave: string
  titulo: string
  sub: string
}

interface TemplateDef {
  key: TemplateKey
  /** `type_id` real das classes canônicas (`OperationTypeRegistry`). */
  typeId: string
  nome: string
  desc: string
  exemplo: string
  Icone: LucideIcon
  forma: Forma
  minClasses: number
  condicoes: [Condicao, Condicao]
  segundosPadrao: number
  temSensibilidade: boolean
}

/** As 5 zonas de risco previstas hoje no motor (`registry.py`). Copy
 * verbatim da prancha — nada aqui é frase inventada na implementação. */
const TEMPLATES: TemplateDef[] = [
  {
    key: 'epi', typeId: 'epi_zone', Icone: HardHat, forma: 'area', minClasses: 1, segundosPadrao: 3,
    temSensibilidade: false,
    nome: 'Zona de EPI obrigatório',
    desc: 'Um lugar onde só se entra com o equipamento certo. Avisamos quem entrar sem.',
    exemplo: '"avise se entrar na doca sem capacete"',
    condicoes: [
      { chave: 'entrada', titulo: 'Avisar assim que alguém entrar sem o equipamento', sub: 'O aviso sai na hora — bom para doca e corredor de passagem.' },
      { chave: 'permanencia', titulo: 'Só avisar se ficar um tempo dentro', sub: 'Evita aviso de quem só passou reto.' },
    ],
  },
  {
    key: 'restrita', typeId: 'position', Icone: ShieldAlert, forma: 'area', minClasses: 1, segundosPadrao: 2,
    temSensibilidade: false,
    nome: 'Área restrita',
    desc: 'Um lugar onde ninguém deveria estar. Avisamos qualquer presença.',
    exemplo: '"avise se alguém entrar atrás da prensa"',
    condicoes: [
      { chave: 'entrada', titulo: 'Avisar em qualquer presença', sub: 'Zona de risco: qualquer segundo dentro já vale aviso.' },
      { chave: 'permanencia', titulo: 'Só avisar se ficar um tempo dentro', sub: 'Para áreas onde a passagem rápida é normal.' },
    ],
  },
  {
    key: 'linha', typeId: 'counting_line', Icone: ArrowRightLeft, forma: 'linha', minClasses: 1, segundosPadrao: 0,
    temSensibilidade: false,
    nome: 'Linha de contagem',
    desc: 'Uma linha atravessando o caminho. Contamos cada vez que alguém ou algo cruza.',
    exemplo: '"conte os pallets que saem pela doca"',
    condicoes: [
      { chave: 'cruzamento', titulo: 'Contar cada cruzamento', sub: 'Vira número no painel, não alerta.' },
      { chave: 'sentido', titulo: 'Contar só num sentido', sub: 'Conta saída e ignora quem volta.' },
    ],
  },
  {
    key: 'tempo', typeId: 'dwell_zone', Icone: Clock, forma: 'area', minClasses: 1, segundosPadrao: 20,
    temSensibilidade: false,
    nome: 'Tempo de permanência',
    desc: 'Quanto tempo algo fica parado num lugar. Vira número e vira aviso se passar do limite.',
    exemplo: '"meça quanto a empilhadeira fica na doca"',
    condicoes: [
      { chave: 'permanencia', titulo: 'Avisar se passar do tempo', sub: 'Também guarda a média do turno para o relatório.' },
      { chave: 'medir', titulo: 'Só medir, sem avisar', sub: 'Para entender o gargalo antes de criar alerta.' },
    ],
  },
  {
    key: 'aproximacao', typeId: 'overlap_dynamic', Icone: Radar, forma: 'area', minClasses: 2, segundosPadrao: 2,
    temSensibilidade: true,
    nome: 'Aproximação perigosa',
    desc: 'Duas coisas que não deveriam chegar perto uma da outra. Avisamos quando isso acontece.',
    exemplo: '"avise se pessoa e empilhadeira se aproximarem"',
    condicoes: [
      { chave: 'entrada', titulo: 'Avisar na hora da aproximação', sub: 'Segurança: quanto mais rápido o aviso, melhor.' },
      { chave: 'permanencia', titulo: 'Só avisar se durar alguns segundos', sub: 'Reduz aviso de cruzamento rápido e normal.' },
    ],
  },
]

const TIPO_PARA_TEMPLATE: Record<string, TemplateDef> = Object.fromEntries(TEMPLATES.map((t) => [t.typeId, t]))
const TEMPLATE_ROTULO: Record<TemplateKey, string> = {
  epi: 'ZONA DE EPI OBRIGATÓRIO', restrita: 'ÁREA RESTRITA', linha: 'LINHA DE CONTAGEM',
  tempo: 'TEMPO DE PERMANÊNCIA', aproximacao: 'APROXIMAÇÃO PERIGOSA',
}
/** 'Bem perto'/'Perto'/'Na mesma área' → % de sobreposição real do schema
 * (`iou_threshold`, 0–100). A prancha assumia fração 0–1; o schema medido é
 * percentual — os números seguem o schema, não a prancha. */
const SENSIBILIDADE_PCT: Record<string, number> = { alta: 30, media: 10, baixa: 3 }
const SENSIBILIDADE_FRASE: Record<string, string> = { alta: 'quase se tocando', media: 'a um passo de distância', baixa: 'no mesmo canto da cena' }

const PONTOS_AREA_PADRAO: [number, number][] = [[0.22, 0.34], [0.7, 0.32], [0.74, 0.76], [0.18, 0.8]]
const PONTOS_LINHA_PADRAO: [number, number][] = [[0.62, 0.18], [0.66, 0.84]]

function pontosPadrao(forma: Forma): [number, number][] {
  return forma === 'linha' ? PONTOS_LINHA_PADRAO : PONTOS_AREA_PADRAO
}

function clamp01(v: number): number {
  return Math.max(0, Math.min(1, v))
}

// ── ler uma operação existente de volta para os termos do template ─────────

function templateDoOp(op: Operacao): TemplateDef | undefined {
  const chave = op.template_id
  if (chave) return TEMPLATES.find((t) => t.key === chave)
  return TIPO_PARA_TEMPLATE[op.type_id]
}

function pontosDoOp(op: Operacao, tpl: TemplateDef): [number, number][] {
  const c = op.config ?? {}
  const campo = tpl.key === 'linha' ? c.line_points : tpl.key === 'restrita' ? c.roi_points : c.zone_points
  return Array.isArray(campo) ? (campo as [number, number][]) : pontosPadrao(tpl.forma)
}

function classesDoOp(op: Operacao, tpl: TemplateDef): string[] {
  const c = op.config ?? {}
  if (tpl.key === 'epi') return Array.isArray(c.watch_classes) ? (c.watch_classes as string[]) : []
  if (tpl.key === 'aproximacao') return [c.class_a, c.class_b].filter((x): x is string => typeof x === 'string')
  return typeof c.target_class === 'string' ? [c.target_class] : []
}

/** Segundos de "quando avisar" — só `dwell_zone` tem campo nativo
 * (`max_dwell_seconds`); os demais usam `persistence_s` (extra, sem
 * aplicação no motor hoje — mesmo gap do pedido B8). */
function segundosDoOp(op: Operacao, tpl: TemplateDef): number {
  const c = op.config ?? {}
  if (tpl.key === 'tempo') return typeof c.max_dwell_seconds === 'number' ? c.max_dwell_seconds : tpl.segundosPadrao
  return typeof c.persistence_s === 'number' ? c.persistence_s : tpl.segundosPadrao
}

function condicaoDoOp(op: Operacao, tpl: TemplateDef): string {
  const c = op.config ?? {}
  if (tpl.key === 'linha') return c.direction && c.direction !== 'both' ? 'sentido' : 'cruzamento'
  if (tpl.key === 'tempo') return 'permanencia'
  return typeof c.persistence_s === 'number' && c.persistence_s > 0 ? 'permanencia' : tpl.condicoes[0].chave
}

// ── config a enviar por template (campos REAIS do schema de cada tipo) ─────

interface Rascunho {
  pontos: [number, number][]
  classes: string[]
  cond: string
  seg: number
  sens: string
}

function construirConfig(tpl: TemplateDef, r: Rascunho): Record<string, unknown> {
  const comPersistencia = r.cond === 'permanencia' ? { persistence_s: r.seg } : {}
  switch (tpl.key) {
    case 'epi':
      return { zone_points: r.pontos, watch_classes: r.classes, ...comPersistencia }
    case 'restrita':
      return { roi_points: r.pontos, target_class: r.classes[0] ?? '', metric: 'state', ...comPersistencia }
    case 'linha':
      return {
        line_points: r.pontos,
        target_class: r.classes[0] ?? '',
        direction: r.cond === 'sentido' ? 'out' : 'both',
      }
    case 'tempo':
      return { zone_points: r.pontos, target_class: r.classes[0] ?? '', max_dwell_seconds: r.seg }
    case 'aproximacao':
      // zone_points aqui é EXTRA: overlap_dynamic.py não tem campo de
      // geometria (é sobreposição de classe A × classe B em qualquer lugar
      // do quadro). Mantido pela consistência visual do editor com as
      // outras 4 regras; o motor ainda não lê esta chave.
      return {
        class_a: r.classes[0] ?? '', class_b: r.classes[1] ?? '', metric: 'iou_percent',
        iou_threshold: SENSIBILIDADE_PCT[r.sens] ?? SENSIBILIDADE_PCT.media,
        zone_points: r.pontos,
        ...comPersistencia,
      }
  }
}

/**
 * `overlap_dynamic` não recebe zone_points (pedido B11 — geometria para
 * aproximação, ainda não existe no motor). A tela mantém o desenho como
 * REFERÊNCIA VISUAL — nunca finge um recorte espacial que não existe: nem
 * na frase, nem calada. Mesmo texto no aviso do painel e no preview.
 */
const AVISO_APROXIMACAO_SEM_ZONA =
  'Nesta regra o aviso vale para toda a imagem — a marcação serve só de referência para quem for olhar depois.'

// ── frase em linguagem natural (porte fiel da prancha) ──────────────────────

function frase(tpl: TemplateDef, nomeLugar: string, classesDisplay: string[], cond: string, seg: number): string {
  const lugar = nomeLugar.trim() || 'este lugar'
  const cls = classesDisplay.length ? classesDisplay.map((c) => c.toLowerCase()).join(' ou ') : '…'
  switch (tpl.key) {
    case 'epi':
      return cond === 'permanencia'
        ? `Você verá um evento quando alguém ficar mais de ${seg} segundos em "${lugar}" sem ${cls}.`
        : `Você verá um evento quando alguém entrar em "${lugar}" sem ${cls}.`
    case 'restrita':
      return cond === 'permanencia'
        ? `Você verá um evento quando ${cls} ficar mais de ${seg} segundos dentro de "${lugar}".`
        : `Você verá um evento assim que ${cls} aparecer dentro de "${lugar}".`
    case 'linha':
      return cond === 'sentido'
        ? `Cada ${cls} que cruzar a linha "${lugar}" no sentido da seta soma 1 na contagem. Quem voltar não conta.`
        : `Cada ${cls} que cruzar a linha "${lugar}" soma 1 na contagem do turno.`
    case 'tempo':
      return cond === 'medir'
        ? `Vamos medir quanto tempo ${cls} fica em "${lugar}" e mostrar a média do turno no painel. Nenhum aviso será enviado.`
        : `Você verá um evento quando ${cls} ficar mais de ${seg} segundos em "${lugar}" — e a média do turno aparece no painel.`
    case 'aproximacao':
      // Sem geometria real no motor (B11) — a frase NUNCA cita o lugar
      // desenhado, senão prometeria um recorte espacial que não existe.
      return cond === 'permanencia'
        ? `Você verá um evento quando ${cls} ficarem próximos por mais de ${seg} segundos — vale para toda a imagem desta câmera.`
        : `Você verá um evento quando ${cls} se aproximarem — vale para toda a imagem desta câmera.`
  }
}

function ultimoAvisoTexto(op: Operacao): string | null {
  if (!op.last_event_at) return null
  const d = new Date(op.last_event_at)
  if (Number.isNaN(d.getTime())) return null
  return `ÚLTIMO AVISO ${d.toLocaleString('pt-BR', { hour: '2-digit', minute: '2-digit' })}`
}

function opEstaAtiva(op: Operacao): boolean {
  const st = (op.status ?? '').toLowerCase()
  return st !== 'inactive' && st !== 'paused'
}

// ── tela ─────────────────────────────────────────────────────────────────────

type CapacidadePausa = 'desconhecida' | 'ok' | 'indisponivel'
type Passo = 'lista' | 'template' | 'editando'

export function Cenario() {
  const { cameraId = '' } = useParams<{ cameraId: string }>()
  const { can, isSuperAdmin } = useAuth()
  const podeConfigurar = can('cameras:configure')

  const [situacao, setSituacao] = useState<'carregando' | 'erro' | 'pronto'>('carregando')
  const [erro, setErro] = useState<string | null>(null)
  const [camera, setCamera] = useState<Camera | null>(null)
  const [ops, setOps] = useState<Operacao[] | null>(null)
  const [classes, setClasses] = useState<ClasseCatalogo[]>([])
  const [moduleIdPorCodigo, setModuleIdPorCodigo] = useState<Record<string, string>>({})

  const [capacidadePausa, setCapacidadePausa] = useState<CapacidadePausa>('desconhecida')
  const [alternando, setAlternando] = useState<number | null>(null)

  const [passo, setPasso] = useState<Passo>('lista')
  const [editId, setEditId] = useState<number | null>(null)
  const [tpl, setTpl] = useState<TemplateDef | null>(null)
  const [nome, setNome] = useState('')
  const [classesSel, setClassesSel] = useState<string[]>([])
  const [cond, setCond] = useState<string | null>(null)
  const [seg, setSeg] = useState(5)
  const [sens, setSens] = useState('media')
  const [pontos, setPontos] = useState<[number, number][]>([])
  const [desenhando, setDesenhando] = useState(false)
  const [avancadoAberto, setAvancadoAberto] = useState(false)
  const [salvando, setSalvando] = useState(false)
  const [erroSalvar, setErroSalvar] = useState<string | null>(null)
  const [arrastando, setArrastando] = useState<number | null>(null)

  const cenaRef = useRef<HTMLDivElement>(null)

  const carregar = useCallback(() => {
    setSituacao('carregando')
    setErro(null)
    Promise.all([
      api.get<ApiResponse<{ operations?: Operacao[] }>>(`/cameras/${cameraId}/operations`),
      // Nome da câmera é enfeite: se falhar, o título cai para o id.
      api.get<ApiResponse<Camera & { camera?: Camera }>>(`/cameras/${cameraId}`).catch(() => null),
      api.get<ApiResponse<{ modules?: Array<{ id: string; module_code: string }> }>>('/modules/').catch(() => null),
    ])
      .then(([opsRes, camRes, modRes]) => {
        setOps(opsRes.data?.operations ?? [])
        const cam = camRes?.data?.camera ?? camRes?.data ?? null
        setCamera(cam && 'id' in cam ? (cam as Camera) : null)
        setModuleIdPorCodigo(
          Object.fromEntries((modRes?.data?.modules ?? []).map((m) => [m.module_code, m.id])),
        )
        const moduloAlvo = moduloDaCamera({ active_module: cam?.active_module })
        return api
          .get<ApiResponse<{ classes?: ClasseCatalogo[] }>>(`/modules/${moduloAlvo}/classes`)
          .then((r) => setClasses(r.data?.classes ?? []))
          .catch(() => undefined)
      })
      .then(() => setSituacao('pronto'))
      .catch((e) => {
        setErro(e instanceof Error ? e.message : 'Erro ao carregar')
        setSituacao('erro')
      })
  }, [cameraId])

  useEffect(carregar, [carregar])

  const nomeClasse = useCallback(
    (classeName: string) => classes.find((c) => c.class_name === classeName)?.display_name ?? classeName,
    [classes],
  )

  const snapshot = useCameraSnapshot(cameraId, passo !== 'lista')

  // ── zonas de outras regras (fundo tracejado do editor) ────────────────────
  const zonasSalvas = useMemo(() => {
    if (!ops) return []
    return ops
      .filter((o) => o.id !== editId)
      .map((o) => {
        const t = templateDoOp(o)
        if (!t) return null
        return { nome: o.name, forma: t.forma, pontos: pontosDoOp(o, t) }
      })
      .filter((z): z is { nome: string; forma: Forma; pontos: [number, number][] } => z !== null)
  }, [ops, editId])

  // ── ações da lista ─────────────────────────────────────────────────────────

  function abrirNovaRegra() {
    setEditId(null)
    setTpl(null)
    setNome('')
    setClassesSel([])
    setCond(null)
    setSeg(5)
    setSens('media')
    setPontos([])
    setDesenhando(false)
    setAvancadoAberto(false)
    setErroSalvar(null)
    setPasso('template')
  }

  function escolherTemplate(t: TemplateDef) {
    setTpl(t)
    setClassesSel([])
    setCond(t.condicoes[0].chave)
    setSeg(t.segundosPadrao || 5)
    setPontos(pontosPadrao(t.forma))
    setNome('')
    setPasso('editando')
  }

  function abrirEdicao(op: Operacao) {
    const t = templateDoOp(op)
    if (!t) return
    setEditId(op.id)
    setTpl(t)
    setNome(op.name)
    setClassesSel(classesDoOp(op, t))
    setCond(condicaoDoOp(op, t))
    setSeg(segundosDoOp(op, t))
    setSens('media')
    setPontos(pontosDoOp(op, t))
    setDesenhando(false)
    setAvancadoAberto(false)
    setErroSalvar(null)
    setPasso('editando')
  }

  async function alternarPausa(op: Operacao) {
    if (capacidadePausa === 'indisponivel') return
    setAlternando(op.id)
    const ativa = opEstaAtiva(op)
    const acao = ativa ? 'pause' : 'resume'
    try {
      const res = await api.post<ApiResponse<{ operation: Operacao }>>(`/operations/${op.id}/${acao}`)
      setCapacidadePausa('ok')
      const atualizado = res.data?.operation
      setOps((prev) =>
        (prev ?? []).map((o) => (o.id === op.id ? (atualizado ?? { ...o, status: ativa ? 'inactive' : 'active' }) : o)),
      )
    } catch (err) {
      // Guarda de compatibilidade (PR #608 pode mergear depois deste): rota
      // ainda ausente vira selo de dependência, nunca finge que pausou.
      if (err instanceof ApiError && (err.status === 404 || err.status === 405)) {
        setCapacidadePausa('indisponivel')
      }
    } finally {
      setAlternando(null)
    }
  }

  // ── ações do editor ─────────────────────────────────────────────────────────

  function moverPara(clientX: number, clientY: number): [number, number] | null {
    const rect = cenaRef.current?.getBoundingClientRect()
    if (!rect || rect.width === 0 || rect.height === 0) return null
    return [clamp01((clientX - rect.left) / rect.width), clamp01((clientY - rect.top) / rect.height)]
  }

  function aoClicarCena(e: React.MouseEvent<HTMLDivElement>) {
    if (!desenhando) return
    const p = moverPara(e.clientX, e.clientY)
    if (!p) return
    setPontos((prev) => [...prev, p])
  }

  function aoIniciarArraste(i: number) {
    return (e: React.PointerEvent<HTMLButtonElement>) => {
      e.stopPropagation()
      e.currentTarget.setPointerCapture(e.pointerId)
      setArrastando(i)
    }
  }

  function aoMoverHandle(e: React.PointerEvent<HTMLButtonElement>) {
    if (arrastando === null) return
    const p = moverPara(e.clientX, e.clientY)
    if (!p) return
    setPontos((prev) => prev.map((pt, idx) => (idx === arrastando ? p : pt)))
  }

  function aoSoltarHandle(e: React.PointerEvent<HTMLButtonElement>) {
    if (e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId)
    setArrastando(null)
  }

  const faltaNome = !nome.trim()
  const faltaClasse = tpl ? classesSel.length < tpl.minClasses : true
  const faltaCond = !cond
  const completo = !!tpl && !faltaNome && !faltaClasse && !faltaCond

  async function salvar() {
    if (!tpl || !completo || !cond) return
    setSalvando(true)
    setErroSalvar(null)
    try {
      const config = construirConfig(tpl, { pontos, classes: classesSel, cond, seg, sens })
      if (editId !== null) {
        const res = await api.put<ApiResponse<{ operation: Operacao }>>(`/operations/${editId}`, { name: nome.trim(), config })
        const atualizado = res.data?.operation
        if (atualizado) setOps((prev) => (prev ?? []).map((o) => (o.id === editId ? atualizado : o)))
      } else {
        const moduloCodigo = moduloDaCamera({ active_module: camera?.active_module })
        const moduleId = moduleIdPorCodigo[moduloCodigo]
        if (!moduleId) throw new Error(`Módulo "${moduloCodigo}" não encontrado para esta câmera`)
        const res = await api.post<ApiResponse<{ operation: Operacao }>>(`/cameras/${cameraId}/operations`, {
          module_id: moduleId, type_id: tpl.typeId, template_id: tpl.key, name: nome.trim(), config,
        })
        const criado = res.data?.operation
        if (criado) setOps((prev) => [...(prev ?? []), criado])
      }
      setPasso('lista')
    } catch (err) {
      setErroSalvar(err instanceof Error ? err.message : 'Erro ao salvar a regra')
    } finally {
      setSalvando(false)
    }
  }

  async function excluir() {
    if (editId === null) return
    const digitado = window.prompt(`Para excluir "${nome}", digite o nome exato da regra.`)
    if (digitado === null || digitado !== nome) return
    try {
      await api.delete(`/operations/${editId}?confirm_name=${encodeURIComponent(nome)}`)
      setOps((prev) => (prev ?? []).filter((o) => o.id !== editId))
      setPasso('lista')
    } catch (err) {
      setErroSalvar(err instanceof Error ? err.message : 'Erro ao excluir a regra')
    }
  }

  // ── estados de tela cheia ────────────────────────────────────────────────

  if (situacao === 'carregando') {
    return <LogikosLoader variante="fullscreen" estado="waiting" rotulo="ABRINDO O CENÁRIO" />
  }

  if (situacao === 'erro') {
    return (
      <div className={s.centro}>
        <TriangleAlert size={32} strokeWidth={1.5} color={lk.estado.nc} aria-hidden="true" />
        <span className={s.centroTitulo}>Não conseguimos abrir o cenário</span>
        <span className={s.centroTexto}>
          As regras que já estão valendo continuam funcionando — só a edição está indisponível agora.
        </span>
        <span className={s.centroTecnico}>{erro}</span>
        <button className={s.botaoPrimario} onClick={carregar}>Tentar de novo</button>
      </div>
    )
  }

  if (passo !== 'lista' && !podeConfigurar) {
    return <SemPermissao permissao="cameras:configure" />
  }

  const titulo = camera?.name ?? cameraId
  const listaOps = ops ?? []
  const ativas = listaOps.filter(opEstaAtiva).length

  // ── passo template ───────────────────────────────────────────────────────

  if (passo === 'template') {
    return (
      <div className={s.pagina}>
        <div className={s.editorTopo}>
          <button className={s.voltar} onClick={() => setPasso('lista')}>← Regras da câmera</button>
          <h2 className={s.tituloEditor}>O que você quer que esta câmera faça?</h2>
        </div>
        <span className={s.introTemplate}>Comece pelo que você quer que a câmera faça. A gente cuida do resto por baixo.</span>
        <div className={s.gradeTemplates}>
          {TEMPLATES.map((t) => (
            <button key={t.key} className={s.templateCard} onClick={() => escolherTemplate(t)}>
              <div className={s.templateTopo}>
                <t.Icone size={20} strokeWidth={1.7} color={lk.cor.brancoSinal} aria-hidden="true" />
                <span className={s.templateNome}>{t.nome}</span>
              </div>
              <span className={s.templateDesc}>{t.desc}</span>
              <span className={s.templateExemplo}>EX.: {t.exemplo}</span>
            </button>
          ))}
        </div>
        {isSuperAdmin && (
          <span className={s.linkAvancado}>
            Nenhum destes serve?{' '}
            <a href="#modo-avancado" onClick={(e) => { e.preventDefault(); escolherTemplate(TEMPLATES[0]); setAvancadoAberto(true) }}>
              Modo avançado
            </a>{' '}
            — só para quem cuida da plataforma.
          </span>
        )}
      </div>
    )
  }

  // ── passo editando ───────────────────────────────────────────────────────

  if (passo === 'editando' && tpl && cond) {
    const t = tpl
    const previewTexto = frase(t, nome, classesSel.map(nomeClasse), cond, seg)
    const faltaTxt = faltaNome
      ? 'Dê um nome ao lugar — ele aparece em todo evento.'
      : faltaClasse
        ? (t.minClasses > 1 ? 'Escolha as duas coisas que não devem se aproximar.' : 'Escolha ao menos uma coisa para observar.')
        : 'Escolha quando avisar.'
    const temSegundos = cond === 'permanencia'
    const svgPontos = pontos.map(([x, y]) => `${(x * 160).toFixed(1)},${(y * 90).toFixed(1)}`).join(' ')
    const semSinal = !snapshot.loading && !snapshot.url

    return (
      <div className={s.pagina}>
        <div className={s.editorTopo}>
          <button className={s.voltar} onClick={() => setPasso('lista')}>← Regras da câmera</button>
          <h2 className={s.tituloEditor}>{t.nome}</h2>
          <span className={s.espacador} />
          <div className={s.stepsNav}>
            <button
              className={editId === null ? s.stepBotao.inativo : s.stepBotao.inativo}
              disabled={editId !== null}
              onClick={() => setPasso('template')}
            >
              <span className={s.stepNumero.inativo}>1</span> Modelo
            </button>
            <span className={s.stepBotao.ativo}><span className={s.stepNumero.ativo}>2</span> Onde e o quê</span>
            <span className={s.stepBotao.ativo}><span className={s.stepNumero.ativo}>3</span> Quando avisar</span>
          </div>
        </div>

        <div className={s.avisoMobile}>DESENHAR ZONA: MELHOR NO COMPUTADOR</div>

        <div className={s.corpoEditor}>
          <div className={s.colunaCena}>
            <div
              ref={cenaRef}
              className={desenhando ? `${s.cenaBox} ${s.cenaBoxDesenhando}` : s.cenaBox}
              onClick={aoClicarCena}
            >
              {snapshot.url && <img className={s.cenaImagem} src={snapshot.url} alt="Última imagem capturada da câmera" />}
              <span className={s.cenaTagEsquerda}>{titulo.toUpperCase()} · AO VIVO</span>
              <span className={s.cenaTagDireita}>{desenhando ? 'CLIQUE PARA ADICIONAR PONTOS' : 'ARRASTE OS PONTOS PARA AJUSTAR'}</span>

              <svg viewBox="0 0 160 90" preserveAspectRatio="none" className={s.cenaSvg}>
                {zonasSalvas.map((z) => (
                  <polygon
                    key={z.nome}
                    className={s.zonaSalva}
                    points={z.pontos.map(([x, y]) => `${(x * 160).toFixed(1)},${(y * 90).toFixed(1)}`).join(' ')}
                  />
                ))}
                {t.forma === 'linha'
                  ? <polyline className={s.formaLinha} points={svgPontos} />
                  : <polygon className={s.formaArea} points={svgPontos} />}
              </svg>

              {pontos.map((p, i) => (
                <button
                  key={i}
                  type="button"
                  className={s.handle}
                  style={{ top: `${p[1] * 100}%`, left: `${p[0] * 100}%` }}
                  title={`Ponto ${i + 1} — arraste para ajustar`}
                  onPointerDown={aoIniciarArraste(i)}
                  onPointerMove={aoMoverHandle}
                  onPointerUp={aoSoltarHandle}
                />
              ))}

              {pontos.length > 0 && (
                <span
                  className={s.rotuloFlutuante}
                  style={{
                    top: `${Math.min(...pontos.map((p) => p[1])) * 100}%`,
                    left: `${Math.min(...pontos.map((p) => p[0])) * 100}%`,
                  }}
                >
                  {nome.trim() || 'sem nome ainda'}
                </span>
              )}

              {semSinal && (
                <div className={s.bannerSemSinal}>
                  <TriangleAlert size={26} strokeWidth={1.5} color={lk.estado.atencao} aria-hidden="true" />
                  <span className={s.bannerSemSinalTexto}>
                    Sem imagem para desenhar em cima — usamos o último frame guardado quando disponível.
                  </span>
                </div>
              )}
            </div>

            <div className={s.toolbarCena}>
              <button
                className={desenhando ? s.botaoToolbar.ativo : s.botaoToolbar.inativo}
                onClick={() => setDesenhando((v) => !v)}
              >
                {desenhando ? 'Terminar o desenho' : 'Ajustar o desenho'}
              </button>
              <button className={s.botaoToolbar.inativo} onClick={() => setPontos(pontosPadrao(t.forma))}>
                Recomeçar o desenho
              </button>
              <button
                className={s.botaoDependente}
                disabled
                title="Depende do pedido B6 — rodar a regra contra a gravação, antes de salvar, ainda não existe no servidor."
              >
                Simular sobre a cena
              </button>
              <span className={s.espacador} />
              <span className={s.contadorPontos}>
                {pontos.length} {t.forma === 'linha' ? 'pontos na linha' : 'cantos na zona'}
              </span>
            </div>
            <span className={s.ajudaDesenho}>
              {t.forma === 'linha'
                ? 'A linha precisa atravessar o caminho por onde as coisas passam. Quem cruza de um lado para o outro é contado.'
                : 'Cubra só o lugar que interessa. Zona grande demais pega quem está de passagem; pequena demais deixa passar.'}
            </span>
          </div>

          <div className={s.painelLateral}>
            <div className={s.blocoPasso}>
              <span className={s.overlinePasso}>PASSO 1 · ONDE</span>
              <input
                className={s.inputNome}
                value={nome}
                onChange={(e) => setNome(e.target.value)}
                placeholder="Nome deste lugar — ex.: Doca 3"
              />
              <span className={s.textoAjuda}>
                O nome aparece na imagem, no evento e no relatório. Use o nome que a equipe já usa no chão.
              </span>
            </div>

            <div className={s.blocoPasso}>
              <div className={s.overlineLinha}>
                <span className={s.overlinePasso}>PASSO 2 · O QUÊ</span>
                <span className={s.dicaInline}>{t.minClasses > 1 ? 'escolha as duas' : 'pode escolher mais de um'}</span>
              </div>
              <div className={s.linhaClasses}>
                {classes.map((c) => {
                  const on = classesSel.includes(c.class_name)
                  return (
                    <button
                      key={c.class_name}
                      className={on ? s.chipClasse.ativo : s.chipClasse.inativo}
                      onClick={() =>
                        setClassesSel((prev) => (on ? prev.filter((x) => x !== c.class_name) : [...prev, c.class_name]))
                      }
                    >
                      <span className={on ? s.pontoChip.ativo : s.pontoChip.inativo} />
                      {c.display_name}
                    </button>
                  )
                })}
              </div>
              <span className={s.textoAjuda}>
                Só aparece aqui o que esta câmera já sabe reconhecer. Falta algo?{' '}
                <Link to={rotaNova('/estudio/modelos-por-camera')}>ensine no Estúdio</Link>.
              </span>
            </div>

            <div className={s.blocoPasso}>
              <span className={s.overlinePasso}>PASSO 3 · QUANDO AVISAR</span>
              {t.key === 'aproximacao' && (
                <div className={s.avisoIncompleto}>
                  <TriangleAlert size={14} strokeWidth={2} color={lk.estado.atencao} aria-hidden="true" />
                  <span className={s.avisoIncompletoTexto}>{AVISO_APROXIMACAO_SEM_ZONA}</span>
                </div>
              )}
              <div className={s.blocoCondicoes}>
                {t.condicoes.map((c) => {
                  const on = cond === c.chave
                  return (
                    <button key={c.chave} className={on ? s.condicaoBotao.ativo : s.condicaoBotao.inativo} onClick={() => setCond(c.chave)}>
                      <span className={on ? s.radioCirculo.ativo : s.radioCirculo.inativo} />
                      <span className={s.condicaoTextos}>
                        <span className={s.condicaoTitulo}>{c.titulo}</span>
                        <span className={s.condicaoSub}>{c.sub}</span>
                      </span>
                    </button>
                  )
                })}
              </div>
              {temSegundos && (
                <div className={s.blocoSegundos}>
                  <div className={s.linhaSegundos}>
                    <span className={s.textoAjuda}>Só avisar depois de</span>
                    <span className={s.numeroSegundos}>{seg}</span>
                    <span className={s.textoAjuda}>segundos seguidos</span>
                  </div>
                  <input
                    type="range" min={1} max={60} value={seg}
                    className={s.slider}
                    onChange={(e) => setSeg(parseInt(e.target.value, 10))}
                  />
                  <span className={s.textoAjuda}>
                    {seg <= 2 ? 'Muito curto: quem passa reto também vai gerar aviso.'
                      : seg >= 30 ? 'Longo: bom para medir gargalo, ruim para segurança.'
                        : 'Bom equilíbrio — ignora quem só atravessa.'}
                  </span>
                </div>
              )}
              {t.temSensibilidade && (
                <div className={s.blocoSegundos}>
                  <span className={s.textoAjuda}>Quão perto é &quot;perto demais&quot;?</span>
                  <div className={s.linhaSensibilidade}>
                    {(['alta', 'media', 'baixa'] as const).map((k) => (
                      <button key={k} className={sens === k ? s.sensOpcao.ativo : s.sensOpcao.inativo} onClick={() => setSens(k)}>
                        {k === 'alta' ? 'Bem perto' : k === 'media' ? 'Perto' : 'Na mesma área'}
                      </button>
                    ))}
                  </div>
                  <span className={s.textoAjuda}>Consideramos aproximação quando estiverem {SENSIBILIDADE_FRASE[sens]}.</span>
                </div>
              )}
            </div>

            <div className={s.blocoPreview}>
              <span className={s.overlinePreview}>O QUE VAI ACONTECER</span>
              <span className={s.textoPreview}>{previewTexto}</span>
              {t.key === 'aproximacao' && (
                <span className={s.avisoIncompletoTexto}>{AVISO_APROXIMACAO_SEM_ZONA}</span>
              )}
              <span className={s.textoPreviewTecnico}>
                VIRA: {t.forma === 'linha' ? 'LINHA' : 'ÁREA'} DE {pontos.length} PONTOS · {classesSel.length} CLASSE(S)
              </span>
              {!completo && (
                <div className={s.avisoIncompleto}>
                  <TriangleAlert size={14} strokeWidth={2} color={lk.estado.atencao} aria-hidden="true" />
                  <span className={s.avisoIncompletoTexto}>{faltaTxt}</span>
                </div>
              )}
              {erroSalvar && <span className={s.erroSalvar}>{erroSalvar}</span>}
              <div className={s.linhaSalvar}>
                <button
                  className={completo ? `${s.botaoSalvar} ${s.botaoSalvarPronto}` : `${s.botaoSalvar} ${s.botaoSalvarIncompleto}`}
                  disabled={!completo || salvando}
                  onClick={() => void salvar()}
                >
                  {salvando ? 'Salvando…' : completo ? 'Salvar e começar a valer' : 'Complete os 3 passos'}
                </button>
                <button className={s.botaoCancelar} onClick={() => setPasso('lista')}>Cancelar</button>
              </div>
              <span className={s.notaPropagacao}>SALVAR PROPAGA AO BOX DO SITE EM ~60 S</span>
              {editId !== null && (
                <button className={s.linkAvancado} onClick={() => void excluir()} style={{ textAlign: 'left', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}>
                  Excluir esta regra
                </button>
              )}
            </div>

            {/* jargao-ok: modo avançado (superadmin) — números crus do motor,
                nunca visíveis a quem não cuida da plataforma. */}
            {isSuperAdmin && (
              <div className={s.blocoAvancado}>
                <button className={s.botaoAvancado} onClick={() => setAvancadoAberto((v) => !v)}>
                  <span className={s.rotuloAvancado}>Modo avançado</span>
                  <span className={s.seloSuperadmin}>SÓ SUPERADMIN</span>
                </button>
                {avancadoAberto && (
                  <div className={s.corpoAvancado}>
                    <span className={s.textoAvancado}>Números crus do motor. O cliente nunca precisa abrir isto.</span>
                    <div className={s.gradeAvancada}>
                      <span className={s.chaveAvancada}>operation_type</span><span>{t.typeId}</span>
                      <span className={s.chaveAvancada}>watch_classes</span><span>[{classesSel.map((c) => `"${c}"`).join(', ')}]</span>
                      <span className={s.chaveAvancada}>geometry</span><span>{t.forma} · {pontos.length} pts (normalizados 0–1)</span>
                      <span className={s.chaveAvancada}>persistence_s</span><span>{cond === 'permanencia' ? `${seg} s` : '0 s (sem persistência)'}</span>
                      <span className={s.chaveAvancada}>iou_threshold</span><span>{t.key === 'aproximacao' ? `${SENSIBILIDADE_PCT[sens]}%` : '— (não se aplica)'}</span>
                    </div>
                    <span className={s.jsonAvancado}>
                      {JSON.stringify({ template_id: t.key, type_id: t.typeId, name: nome, config: construirConfig(t, { pontos, classes: classesSel, cond, seg, sens }) })}
                    </span>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    )
  }

  // ── lista ────────────────────────────────────────────────────────────────

  return (
    <div className={s.pagina}>
      <div className={s.cabecalhoLista}>
        <h1 className={s.titulo}>O que esta câmera vigia</h1>
        <span className={s.contador}>
          {listaOps.length} REGRA{listaOps.length !== 1 ? 'S' : ''} · {ativas} ATIVA{ativas !== 1 ? 'S' : ''}
        </span>
        <span className={s.espacador} />
        <Link className={s.linkSecundario} to={rotaNova('/estudio/modelos-por-camera')}>
          <LayoutGrid size={14} strokeWidth={1.8} aria-hidden="true" /> O que a câmera reconhece
        </Link>
        {podeConfigurar && (
          <button className={s.botaoPrimario} onClick={abrirNovaRegra}>
            <Plus size={14} strokeWidth={2} aria-hidden="true" /> Desenhar nova regra
          </button>
        )}
      </div>
      <span className={s.explicacao}>
        Cada regra é uma frase: <b>onde</b> na imagem, <b>o que</b> observar e <b>quando avisar</b>. O que a
        câmera é capaz de reconhecer vem do Estúdio; aqui você escolhe o que fiscalizar.
      </span>

      {listaOps.length === 0 ? (
        <div className={s.centro}>
          <Frame size={32} strokeWidth={1.5} color={lk.cor.cinzaNevoa} aria-hidden="true" />
          <span className={s.centroTitulo}>Esta câmera ainda não vigia nada</span>
          {podeConfigurar ? (
            <>
              <span className={s.centroTexto}>
                Ela está gravando, mas ninguém disse o que observar. Desenhe a primeira zona sobre a imagem — leva
                um minuto.
              </span>
              <button className={s.botaoPrimario} onClick={abrirNovaRegra}>Desenhe sua primeira zona</button>
            </>
          ) : (
            // Sem `cameras:configure` não há botão pra oferecer — a tela não manda
            // fazer o que a pessoa não pode fazer. Frases da própria prancha: a
            // primeira é do card vazio-com-CTA, a segunda é do card SEM PERMISSÃO.
            <span className={s.centroTexto}>
              Ela está gravando, mas ninguém disse o que observar. Alterar o que a câmera vigia é do administrador
              do site.
            </span>
          )}
        </div>
      ) : (
        <>
          {listaOps.map((op) => {
            const t = templateDoOp(op)
            const ativa = opEstaAtiva(op)
            const ultimo = ultimoAvisoTexto(op)
            const classesDisplay = t ? classesDoOp(op, t).map(nomeClasse) : []
            const fraseTexto = t ? frase(t, op.name, classesDisplay, condicaoDoOp(op, t), segundosDoOp(op, t)) : null
            const svgPontos = t
              ? pontosDoOp(op, t).map(([x, y]) => `${(x * 96).toFixed(1)},${(y * 60).toFixed(1)}`).join(' ')
              : ''
            return (
              <div key={op.id} className={s.cartaoRegra}>
                <div className={s.linhaRegra}>
                  <div className={s.thumb}>
                    {t && (
                      <svg viewBox="0 0 96 60" className={s.thumbSvg}>
                        {t.forma === 'linha'
                          ? <polyline points={svgPontos} fill="none" stroke={ativa ? lk.cor.cianoVisao : lk.cor.cinzaNevoa} strokeWidth={1.6} />
                          : <polygon points={svgPontos} fill={ativa ? 'rgba(0,229,255,.1)' : 'rgba(138,143,152,.08)'} stroke={ativa ? lk.cor.cianoVisao : lk.cor.cinzaNevoa} strokeWidth={1.6} />}
                      </svg>
                    )}
                  </div>
                  <div className={s.infoRegra}>
                    <div className={s.infoTopo}>
                      <span className={s.nomeRegraTexto}>{op.name}</span>
                      <span className={s.badgeTemplate}>{t ? TEMPLATE_ROTULO[t.key] : op.type_id.toUpperCase()}</span>
                    </div>
                    <span className={s.fraseRegra}>
                      {fraseTexto ?? 'Regra de tipo avançado — a edição pela tela ainda não cobre este tipo.'}
                    </span>
                  </div>
                  <div className={s.statusColuna}>
                    <span className={s.statusLinha} style={{ color: ativa ? lk.estado.ok : lk.cor.cinzaNevoa }}>
                      <span className={s.bolinha} style={{ background: ativa ? lk.estado.ok : lk.cor.cinzaNevoa }} />
                      {ativa ? 'ATIVA' : '⏸ PAUSADA'}
                    </span>
                    {ultimo && <span className={s.ultimoAviso}>{ultimo}</span>}
                  </div>
                  <div className={s.acoesRegra}>
                    {podeConfigurar ? (
                      <>
                        {t && <button className={s.botaoAcao} onClick={() => abrirEdicao(op)}>Editar</button>}
                        {capacidadePausa === 'indisponivel' ? (
                          <button className={s.botaoDependente} disabled title="Depende do pedido B1 — pausar/retomar ainda não existe no servidor.">
                            {ativa ? 'Pausar' : 'Retomar'}
                          </button>
                        ) : (
                          <button className={s.botaoAcao} disabled={alternando === op.id} onClick={() => void alternarPausa(op)}>
                            {alternando === op.id ? '…' : ativa ? 'Pausar' : 'Retomar'}
                          </button>
                        )}
                      </>
                    ) : (
                      // Nunca some com tudo em silêncio: quem não pode editar vê
                      // por quê, no lugar onde os botões estariam.
                      <span className={s.badgeTemplate} title="Alterar o que a câmera vigia é do administrador do site.">
                        SOMENTE LEITURA
                      </span>
                    )}
                  </div>
                </div>
                <div className={s.rodapeAvaliacao}>
                  <span className={s.textoAvaliacao}>Esta regra está pegando o que devia?</span>
                  <button className={s.botaoDependente} disabled title="Depende do pedido B2 — avaliação da regra ainda não existe no servidor.">
                    Sim, está boa
                  </button>
                  <button className={s.botaoDependente} disabled title="Depende do pedido B2 — avaliação da regra ainda não existe no servidor.">
                    Não, precisa ajuste
                  </button>
                  <span className={s.seloAguarda}>AGUARDA BACKEND · B2 AVALIAR</span>
                  <span className={s.espacador} />
                  <Link className={s.linkEventos} to={`${rotaNova('/epi/eventos')}?camera_id=${cameraId}`}>
                    ver eventos desta câmera →
                  </Link>
                </div>
              </div>
            )
          })}
          <div className={s.rodapeNota}>
            <span style={{ flex: 1 }}>
              Pausar não apaga nada: a regra sai do box no próximo ciclo e volta igual. Apagar fica na tela de
              edição, com o nome por extenso.
            </span>
            <span style={{ flex: 1 }}>
              A avaliação é o seu recado para quem cuida do modelo: &quot;não, precisa ajuste&quot; abre um caso na
              fila do Estúdio com o frame do último disparo.
            </span>
          </div>
        </>
      )}
    </div>
  )
}

export default Cenario
