/**
 * EPI Verificação — `/epi/verificacao` (de-para: `/epi/verification`).
 *
 * Desenho: `EPI Verificação.dc.html`. Lógica real: `pages/VerificationQueuePage`.
 * Endpoints (contrato do design, `contrato-dados.js`, categoria
 * `events-alerts-media`):
 *
 *   GET  /api/verification/queue              → fila sem veredito do tenant (verdict IS NULL)
 *   POST /api/verification/<alert_id>/review  → veredito humano
 *   GET  /api/alerts/<alert_id>/snapshot      → URL assinada da evidência
 *
 * ─── A FILA — leia antes de mexer ────────────────────────────────────────────
 *
 * Já custou caro aqui (PRs 496, 500, 487 e a fila que mentia sobre "N
 * restantes" com dois revisores ao mesmo tempo — paridade §3). As regras que
 * sobraram:
 *
 *  1. **Nunca reordena o que já está na tela; remove só quem já não é meu
 *     trabalho.** Item que EU decidi nesta sessão nunca sai (fica marcado —
 *     regra do "carimba" abaixo). Item que sumiu do servidor e não fui eu quem
 *     decidiu SAI — foi outra pessoa que revisou por fora, e deixá-lo na tela é
 *     apresentar para julgar (de novo) o que já foi julgado, sobrescrevendo em
 *     silêncio o veredito alheio. `carregar` só remove sob essa certeza (ver
 *     regra 2). O índice nunca é um número cru sobre o array: `carregar`
 *     recalcula a posição pelo ID do item que estava na tela — se um item ANTES
 *     dele sai, o índice não pode ficar apontando pra o vizinho errado, que era
 *     exatamente o bug do PR 496.
 *  2. **Reabastecimento por dedup de id, jamais por OFFSET — e só remove sob
 *     lote INTEIRO.** Decidir um alerta o tira do filtro (`verdict IS NULL`) no
 *     servidor: a próxima leitura da MESMA "página" já é outro conjunto. É a
 *     família exata do OFFSET que perdia 50% das linhas no PR 500. Quem separa
 *     "já está na fila" de "trabalho novo" é `anexarSemRepetir` — o mesmo
 *     mecanismo do estúdio de anotação, importado daqui e não reescrito. O
 *     endpoint corta em `limit` e não pagina: um lote CHEIO não prova que quem
 *     faltou foi revisado — pode estar só além do corte. Por isso a regra 1 só
 *     remove quando o lote veio ABAIXO do limite; lote cheio não tira ninguém.
 *  3. **Listener sem closure velha.** O `keydown` é re-registrado quando o item
 *     corrente muda. Um handler preso ao render antigo é o "ref atrasado" do
 *     PR 496: a tecla C carimba veredito no item que já não está na tela.
 *
 * ⚠️ Este endpoint NÃO pagina (sem cursor, sem offset — `limit` ≤100 e pronto).
 * Por isso o reabastecimento é o MESMO polling de 15s do front antigo, e não
 * `precisaDeReabastecimento`: pedir "página 2" a um endpoint que não tem
 * páginas seria inventar paginação, e inventar paginação é como o PR 500 começou.
 *
 * ⚠️ **"N RESTANTES" e o gate de "Fila zerada" usam `total` (verdade do
 * servidor), não `fila.length`.** A tela já escreveu "Fila zerada" com
 * centenas de alertas pendentes ainda no banco — `fila.length` é só os
 * `LIMITE` (50) mais incertos carregados agora, nunca "quanto falta de
 * verdade". Ver `restantes` e o comentário do endpoint em `carregar`.
 *
 * ─── FILA POR INCERTEZA (delta §2 item 9 — não podia se perder) ──────────────
 *
 * O que ordena a fila é o quanto o modelo está EM DÚVIDA, não a hora do
 * alerta. **Quem ordena é o SERVIDOR** (`get_human_queue`,
 * verification_service.py), em DUAS camadas: 1) `rank_na_rajada` — dentro de
 * cada rajada (câmera+classe repetida em <60s), o mais incerto vira rank 1,
 * e um representante de CADA rajada aparece antes de qualquer rank 2 (dedup
 * NÃO filtra ninguém, rodada 3 — só reordena: irmãos de rajada continuam
 * contados e voltam depois); 2) incerteza (`ABS(confidence - 0.5)`) desempata
 * dentro da camada. Antes ordenava por `created_at DESC`, e como o endpoint
 * não pagina (`LIMIT` corta DE VERDADE), a ordem decidia QUAIS itens
 * apareciam: medido no DEV, os 50 mais recentes tinham confiança 0,90-1,00
 * (o modelo já tinha certeza) e o operador nunca alcançava os casos
 * ambíguos.
 *
 * ⚠️ **O CLIENTE NÃO REORDENA o lote (rodada 4).** Chegou a reordenar por
 * `ordenarPorIncerteza` (só incerteza, sem noção de rajada) — isso DESFAZIA
 * a camada 1 do servidor (um irmão de rajada com incerteza baixa intercalava
 * antes do representante de OUTRA rajada, devolvendo a fila à ordem que a
 * rodada 1 já tinha reprovado). `carregar` agora passa `itens` direto pra
 * `anexarSemRepetir` — a ordem renderizada É a ordem que o servidor mandou,
 * ponto. `incertezaDe`/`ordenarPorIncerteza` continuam exportadas (testadas
 * como funções puras, documentam a fórmula — mesma de
 * `FrameRepository._INCERTEZA_SQL`) mas NINGUÉM as chama no caminho de
 * render; não reintroduza a chamada em `carregar` (teste de mutação:
 * "a ordem renderizada é a ordem que o SERVIDOR devolveu"). **A ordenação é
 * aplicada UMA VEZ, no servidor** — nunca de novo no cliente, nunca à fila
 * que já está na tela (regra 1).
 *
 * ─── PARA O DESIGN / PARA O BACKEND ─────────────────────────────────────────
 *
 *  · **"Enviar para anotação · Estúdio" (tecla A) não tem endpoint.** Varri as
 *    421 linhas do contrato: nenhuma rota leva um ALERTA para a fila de
 *    anotação (`/api/training/*` parte de `training_frames`, não de `alerts`;
 *    `POST /api/v1/feedback` é GAP-DE-PRODUTO de outra tela e ainda 500). O
 *    botão fica no lugar do desenho, **desabilitado e dizendo por quê** — e o
 *    atalho A sai da barra de atalhos, porque anunciar tecla que não faz nada é
 *    pior que não anunciar. O contador "N ENVIADOS P/ ANOTAÇÃO" do cabeçalho
 *    cai junto: sem a ação, seria um zero eterno fingindo métrica.
 *  · **"Zona"** não existe em `alerts` (nem coluna, nem no payload da fila). No
 *    lugar, a ficha mostra **Confiança** e o **motivo da IA** — que são o dado
 *    real e o que justifica a posição do item na fila por incerteza.
 *  · A evidência precisa de uma segunda chamada (`/alerts/<id>/snapshot`): a
 *    fila devolve `evidence_key`, não URL assinada. Se o design quiser uma
 *    chamada só, o pedido ao backend é `evidence_url` no item da fila.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  AlertTriangle, ArrowLeft, ArrowRight, Check, ImageOff, Lock, Minus, PenLine, Plus,
  ShieldCheck, X,
} from 'lucide-react'
import { Link } from 'react-router-dom'

import { anexarSemRepetir } from '../../components/annotation/studioQueue'
import { useAuth } from '../../hooks/useAuth'
import { api } from '../../services/api'
import { useToast } from '../../components/ui/Toast/useToast'
import { labelForClass } from '../../utils/labels'
import { LogikosLoader } from '../shell/LogikosLoader'
import * as s from './Verificacao.css'
import { rotaNova } from '../RotasNovas'

/** Única unidade de bbox projetável (contrato de `domain/detectors/base.py`). */
const BBOX_PIXELS = 'pixels_xywh_frame_original'

type Veredito = 'approve' | 'reject'

interface Violacao {
  class: string
  confidence?: number
  bbox?: [number, number, number, number]
  bbox_unidade?: string
}

export interface ItemVerificacao {
  id: string
  camera_id?: string | null
  camera_name?: string | null
  class_name?: string | null
  confidence?: number
  violations?: Violacao[]
  verification_reason?: string | null
  evidence_key?: string | null
  created_at?: string | null
  timestamp?: string | null
}

/** Envelope de `GET /verification/queue`. `total` é a contagem REAL do
 *  servidor (mesmo WHERE do `items` — verdict nulo + exclusão de
 *  conformidade + dedup, ver `get_queue_count`); `count` é só `len(items)`,
 *  capado no `limit`. Backends antigos (ou mocks de teste) podem não mandar
 *  `total` — nesse caso a tela cai para a contagem local (ver `restantes`). */
interface RespostaFila {
  items?: ItemVerificacao[]
  count?: number
  total?: number
}

/** Traço de aprendizado ativo do backend: `MIN(ABS(confidence - 0.5))`.
 *
 * A confiança do próprio alerta entra junto com a das propostas: o payload da
 * fila traz as duas, e `violations` vazio é comum em alerta de classe única —
 * ignorá-la mandaria esses itens para o fim como se não houvesse sinal.
 *
 * `1` (o `COALESCE(..., 1.0)` do SQL) quando não há confiança nenhuma para
 * ordenar: vai para o FIM, explicitamente. Pôr no começo o que não se sabe
 * medir seria ordem arbitrária vestida de prioridade. */
export function incertezaDe(item: ItemVerificacao): number {
  const confiancas = (item.violations ?? [])
    .map((v) => v.confidence)
    .concat(item.confidence)
    .filter((c): c is number => typeof c === 'number' && Number.isFinite(c))
  if (confiancas.length === 0) return 1
  return Math.min(...confiancas.map((c) => Math.abs(c - 0.5)))
}

/** Mais duvidoso primeiro. Empate mantém a ordem do servidor (sort estável) —
 *  reordenar empate seria mexer na fila sem motivo. */
export function ordenarPorIncerteza(itens: readonly ItemVerificacao[]): ItemVerificacao[] {
  return [...itens].sort((a, b) => incertezaDe(a) - incertezaDe(b))
}

/** bbox = [x, y, w, h] em pixels do frame ORIGINAL → % sobre a <img>. */
function caixaEmPorcento(
  [x, y, w, h]: [number, number, number, number],
  natW: number,
  natH: number,
) {
  const pct = (n: number, total: number) => `${+((n / total) * 100).toFixed(4)}%`
  return { left: pct(x, natW), top: pct(y, natH), width: pct(w, natW), height: pct(h, natH) }
}

/** Recorte da detecção: a MESMA imagem, enquadrada na caixa por background. */
function estiloRecorte(
  [x, y, w, h]: [number, number, number, number],
  natW: number,
  natH: number,
  url: string,
) {
  const sobraX = natW - w
  const sobraY = natH - h
  return {
    backgroundImage: `url(${url})`,
    backgroundSize: `${(natW / w) * 100}% ${(natH / h) * 100}%`,
    backgroundPosition: `${sobraX > 0 ? (x / sobraX) * 100 : 0}% ${sobraY > 0 ? (y / sobraY) * 100 : 0}%`,
  }
}

function horaDe(item: ItemVerificacao): string {
  const bruto = item.created_at ?? item.timestamp
  if (!bruto) return '—'
  const d = new Date(bruto)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString('pt-BR')
}

function classeDe(item: ItemVerificacao): string {
  return item.class_name ?? item.violations?.[0]?.class ?? '—'
}

const ZOOM_MIN = 1
const ZOOM_MAX = 3
const ZOOM_PASSO = 0.5
/** Mesmo intervalo do front antigo — é assim que alerta novo entra na fila. */
const POLL_MS = 15_000
const LIMITE = 50

export function Verificacao() {
  const { can } = useAuth()
  const toast = useToast()
  const podeLer = can('verification:read')
  const podeEscrever = can('verification:write')

  // Ver regra 1 do cabeçalho: item meu não sai; item de outro que sumiu do
  // servidor sai (sob a certeza da regra 2).
  const [fila, setFila] = useState<ItemVerificacao[]>([])
  const [indice, setIndice] = useState(0)
  const [decididos, setDecididos] = useState<Record<string, Veredito>>({})
  // Verdade do servidor para "N RESTANTES" — ver `restantes` abaixo e o
  // comentário do endpoint em `carregar`. `null` até o primeiro sync OK.
  const [totalServidor, setTotalServidor] = useState<number | null>(null)
  // Quantos itens já estavam em `decididos` no momento do ÚLTIMO sync bem
  // sucedido — a diferença para `decididos` atual é "decisão feita DEPOIS do
  // último sync", que ainda não pode estar refletida em `totalServidor`.
  const decididosNoUltimoSyncRef = useRef(0)
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)
  const [zoom, setZoom] = useState(ZOOM_MIN)
  const [urlEvidencia, setUrlEvidencia] = useState<string | null>(null)
  const [natural, setNatural] = useState<{ w: number; h: number } | null>(null)
  const cacheUrl = useRef(new Map<string, string | null>())
  // Trava síncrona: `enviando` só vale no próximo render, e duas teclas C no
  // MESMO tick leem `false` nas duas — dois POST, dois carimbos. Veredito é
  // dado de treino; duplicar aqui suja o dataset em silêncio.
  const enviandoRef = useRef(false)

  // Espelhos para leitura fora do render, de dentro de `carregar`: é um
  // useCallback estável (deps `[]`, como sempre foi) e não pode fechar sobre
  // fila/índice/decididos/toast do render em que foi criado. `toast` também
  // precisa de espelho — não é seguro assumir que ele é estável: entrar como
  // dep recriaria `carregar` a cada valor novo, e o efeito de polling abaixo
  // (que depende de `carregar`) desmontaria e chamaria `carregar()` nesse
  // instante — se a própria chamada gerar um `toast` novo (como em qualquer
  // dublê de teste que devolve `{ ...vi.fn() }` a cada render), isso realimenta
  // o próprio gatilho e derruba o processo em OOM.
  const filaRef = useRef<ItemVerificacao[]>([])
  const indiceRef = useRef(0)
  const decididosRef = useRef<Record<string, Veredito>>({})
  const toastRef = useRef(toast)
  useEffect(() => {
    filaRef.current = fila
    indiceRef.current = indice
    decididosRef.current = decididos
    toastRef.current = toast
  }, [fila, indice, decididos, toast])

  const carregar = useCallback(async () => {
    try {
      const res = await api.get<{ data?: RespostaFila }>(`/verification/queue?limit=${LIMITE}`)
      const itens = res?.data?.items ?? []
      const idsServidor = new Set(itens.map((i) => i.id))

      // `total` é a verdade do servidor no INSTANTE deste request. Decisões
      // feitas DEPOIS (ver `restantes`) descontam por cima até o próximo
      // sync realinhar tudo — é o que corrige o "Fila zerada" com centenas
      // no banco (docblock do topo): antes, "quanto falta" só existia como
      // `fila.length`, o array LOCAL de no máximo `LIMITE` itens.
      const totalNovo = res?.data?.total
      if (typeof totalNovo === 'number') {
        setTotalServidor(totalNovo)
        decididosNoUltimoSyncRef.current = Object.keys(decididosRef.current).length
      }

      // Lote CHEIO não prova nada sobre quem faltou (regra 2) — só remove
      // abaixo do limite, e nunca remove o que EU decidi (regra 1).
      const truncado = itens.length >= LIMITE
      const idAntes = filaRef.current[indiceRef.current]?.id
      const continuam = filaRef.current.filter(
        (i) => truncado || idsServidor.has(i.id) || Boolean(decididosRef.current[i.id]),
      )
      // Anexa sem repetir, na ORDEM QUE O SERVIDOR MANDOU — nunca reordena
      // quem já ficou, e não reordena o lote novo por conta própria (ver
      // docblock do topo: o servidor já rankeia por rajada + incerteza; um
      // resort aqui embaralharia esse trabalho de volta pra ordem errada).
      const nova = anexarSemRepetir(continuam, itens)

      // O item na tela sumiu e não fui eu quem decidiu: outra pessoa revisou
      // por fora enquanto o operador olhava para ele. Índice pelo ID, nunca
      // pela posição crua — item removido ANTES dele encolheria o array.
      const novoIndice = idAntes === undefined ? indiceRef.current : nova.findIndex((i) => i.id === idAntes)
      if (idAntes !== undefined && novoIndice === -1) {
        toastRef.current.info(
          'Alerta já revisado',
          'Outra pessoa decidiu este alerta enquanto ele estava aberto aqui.',
        )
      }
      setFila(nova)
      setIndice(novoIndice === -1 ? Math.min(indiceRef.current, Math.max(0, nova.length - 1)) : novoIndice)
      setErro(null)
    } catch (e) {
      setErro(e instanceof Error ? e.message : 'Erro ao carregar a fila')
    } finally {
      setCarregando(false)
    }
  }, [])

  useEffect(() => {
    if (!podeLer) {
      setCarregando(false)
      return
    }
    void carregar()
    const id = setInterval(() => void carregar(), POLL_MS)
    return () => clearInterval(id)
  }, [carregar, podeLer])

  const atual = fila[indice]
  // Progresso do LOTE carregado (feedback do "quanto já venci do que estou
  // olhando agora") — continua local de propósito, decisão é instantânea.
  const pendentesLocal = useMemo(
    () => fila.filter((i) => !decididos[i.id]).length,
    [fila, decididos],
  )
  const total = fila.length
  const progresso = total === 0 ? 0 : Math.round(((total - pendentesLocal) / total) * 100)

  // "N RESTANTES" e o gate de fila-vazia usam a VERDADE DO SERVIDOR
  // (`totalServidor`, de `get_queue_count` — ver `carregar`), não
  // `fila.length`: o array local é só os `LIMITE` (50) mais incertos, e a
  // tela já escreveu "Fila zerada" com centenas ainda no banco (docblock do
  // topo do arquivo — exatamente o bug que este contador existe pra matar).
  // Decisões feitas DEPOIS do último sync descontam na hora
  // (`decididosDesdeSync`), pro operador ver o número cair no clique — sem
  // isso "2 RESTANTES" só apareceria no próximo poll, até 15s depois.
  const decididosDesdeSync = Object.keys(decididos).length - decididosNoUltimoSyncRef.current
  const restantes = totalServidor === null
    ? pendentesLocal
    : Math.max(0, totalServidor - decididosDesdeSync)

  // Evidência do item corrente. A fila entrega `evidence_key`; a URL assinada
  // vem de /alerts/<id>/snapshot. Cache por id: voltar com ← não repede.
  useEffect(() => {
    setZoom(ZOOM_MIN)
    setNatural(null)
    if (!atual) {
      setUrlEvidencia(null)
      return
    }
    if (!atual.evidence_key) {
      setUrlEvidencia(null)
      return
    }
    const cacheado = cacheUrl.current.get(atual.id)
    if (cacheado !== undefined) {
      setUrlEvidencia(cacheado)
      return
    }
    let vivo = true
    setUrlEvidencia(null)
    api
      .get<{ data?: { snapshot_url?: string } }>(`/alerts/${atual.id}/snapshot`)
      .then((r) => {
        const url = r?.data?.snapshot_url ?? null
        cacheUrl.current.set(atual.id, url)
        if (vivo) setUrlEvidencia(url)
      })
      .catch(() => {
        // Sem evidência a tela ainda serve (classe, câmera, hora, motivo).
        // Marcar como null no cache evita re-pedir a cada ← →.
        cacheUrl.current.set(atual.id, null)
        if (vivo) setUrlEvidencia(null)
      })
    return () => {
      vivo = false
    }
  }, [atual])

  const avancar = useCallback(() => {
    setIndice((i) => Math.min(i + 1, Math.max(0, fila.length - 1)))
  }, [fila.length])

  const voltar = useCallback(() => {
    setIndice((i) => Math.max(0, i - 1))
  }, [])

  const decidir = useCallback(
    async (verdict: Veredito) => {
      // Item revisado por outro já saiu de `fila` em `carregar` — não há mais
      // botão para clicar nele. O que resta aqui é honrar o erro do backend se
      // mesmo assim ele recusar (corrida rara: revisão chegou entre o último
      // poll e este clique) — nunca engolir em silêncio.
      if (!atual || !podeEscrever || enviandoRef.current) return
      enviandoRef.current = true
      setEnviando(true)
      try {
        await api.post(`/verification/${atual.id}/review`, { verdict })
        // Carimba NA POSIÇÃO. Não remove: ver regra 1 do cabeçalho.
        setDecididos((d) => ({ ...d, [atual.id]: verdict }))
        toast.success(verdict === 'approve' ? 'Alerta confirmado' : 'Alerta rejeitado')
        avancar()
      } catch (e) {
        toast.error(e instanceof Error ? e.message : 'Erro ao registrar o veredito')
      } finally {
        enviandoRef.current = false
        setEnviando(false)
      }
    },
    [atual, avancar, podeEscrever, toast],
  )

  // ⚠️ Deps completas de propósito: o listener acompanha o item corrente. Um
  // handler preso ao primeiro render é o "ref atrasado" do PR 496 — a tecla C
  // carimbaria veredito num alerta que já saiu da tela.
  useEffect(() => {
    if (!atual) return
    const aoTeclar = (e: KeyboardEvent) => {
      const alvo = e.target as HTMLElement | null
      if (alvo && /^(INPUT|TEXTAREA|SELECT)$/.test(alvo.tagName)) return
      if (e.metaKey || e.ctrlKey || e.altKey) return
      const k = e.key.toLowerCase()
      if (e.key === 'ArrowRight') avancar()
      else if (e.key === 'ArrowLeft') voltar()
      else if (k === 'c') void decidir('approve')
      else if (k === 'r') void decidir('reject')
      else return
      e.preventDefault()
    }
    window.addEventListener('keydown', aoTeclar)
    return () => window.removeEventListener('keydown', aoTeclar)
  }, [atual, avancar, voltar, decidir])

  if (!podeLer) {
    return (
      <div className={s.centro}>
        <Lock size={36} strokeWidth={1.5} aria-hidden />
        <span className={s.centroTitulo}>Sem permissão</span>
        <span className={s.centroTexto}>
          A fila de verificação exige a permissão <code>verification:read</code>. Peça ao
          administrador do seu tenant.
        </span>
      </div>
    )
  }

  if (carregando) {
    return <LogikosLoader estado="waiting" variante="fullscreen" rotulo="CARREGANDO FILA" />
  }

  // Erro só toma a tela quando não há nada para trabalhar. Falha de um poll
  // com fila na mão não pode apagar o que o operador está julgando.
  if (erro && fila.length === 0) {
    return (
      <div className={s.centro}>
        <AlertTriangle size={36} strokeWidth={1.5} className={s.iconeNc} aria-hidden />
        <span className={s.centroTitulo}>Não foi possível carregar a fila</span>
        <span className={s.centroTecnico}>GET /api/verification/queue · {erro}</span>
        <button
          type="button"
          className={s.acaoPrimaria}
          onClick={() => {
            setCarregando(true)
            void carregar()
          }}
        >
          Tentar novamente
        </button>
      </div>
    )
  }

  if (restantes === 0 || !atual) {
    return (
      <div className={s.centro}>
        <ShieldCheck size={36} strokeWidth={1.5} className={s.iconeOk} aria-hidden />
        <span className={s.centroTitulo}>Fila zerada</span>
        <span className={s.centroTexto}>
          Nenhuma detecção aguarda verificação. As decisões de hoje já alimentam o próximo
          treino.
        </span>
        <Link className={s.acaoPrimaria} to={rotaNova('/epi/dashboard')}>
          Voltar ao dashboard
        </Link>
      </div>
    )
  }

  const classe = classeDe(atual)
  const rotuloClasse = labelForClass(classe)
  const vereditoAtual = decididos[atual.id]
  const desenhaveis = (atual.violations ?? []).filter(
    (v) => v.bbox && v.bbox_unidade === BBOX_PIXELS,
  )
  const semUnidade = (atual.violations ?? []).filter(
    (v) => v.bbox && v.bbox_unidade !== BBOX_PIXELS,
  ).length
  const principal = desenhaveis[0]?.bbox
  const confianca = atual.confidence ?? atual.violations?.[0]?.confidence

  return (
    <div className={s.pagina}>
      <div className={s.cabecalho}>
        <h1 className={s.titulo}>Verificação</h1>
        <span className={s.restantes}>{restantes} RESTANTES</span>
        <div
          className={s.trilho}
          role="progressbar"
          aria-valuenow={progresso}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Progresso da fila"
        >
          <span className={s.trilhoCheio} style={{ width: `${progresso}%`, display: 'block' }} />
        </div>
        <span className={s.espacador} />
        <span className={s.atalhos}>
          <span>
            <span className={s.tecla}>←</span> <span className={s.tecla}>→</span> NAVEGAR
          </span>
          <span>
            <span className={s.tecla}>C</span> CONFIRMAR
          </span>
          <span>
            <span className={s.tecla}>R</span> REJEITAR
          </span>
        </span>
      </div>

      <div className={s.palco}>
        <div className={s.evidencia}>
          {urlEvidencia ? (
            <div className={s.camadaZoom} style={{ transform: `scale(${zoom})` }}>
              <span className={s.quadro}>
                <img
                  className={s.imagem}
                  src={urlEvidencia}
                  alt={`Evidência de ${rotuloClasse}`}
                  draggable={false}
                  onLoad={(e) => {
                    const img = e.currentTarget
                    if (img.naturalWidth > 0 && img.naturalHeight > 0) {
                      setNatural({ w: img.naturalWidth, h: img.naturalHeight })
                    }
                  }}
                />
                {natural &&
                  desenhaveis.map((v, i) => (
                    <span
                      key={i}
                      data-testid="caixa-violacao"
                      className={s.caixa}
                      style={caixaEmPorcento(
                        v.bbox as [number, number, number, number],
                        natural.w,
                        natural.h,
                      )}
                    >
                      <span className={s.caixaRotulo}>
                        {labelForClass(v.class).toUpperCase()}
                      </span>
                    </span>
                  ))}
              </span>
            </div>
          ) : (
            <span className={s.semImagem}>
              <ImageOff size={28} strokeWidth={1.5} aria-hidden />
              Sem imagem de evidência para esta detecção
            </span>
          )}

          <span className={s.selo}>{(atual.camera_name ?? atual.camera_id ?? '—').toUpperCase()}</span>

          <div className={s.zoomBarra}>
            <button
              type="button"
              className={s.zoomBotao}
              aria-label="Diminuir zoom"
              disabled={!urlEvidencia || zoom <= ZOOM_MIN}
              onClick={() => setZoom((z) => Math.max(ZOOM_MIN, z - ZOOM_PASSO))}
            >
              <Minus size={15} strokeWidth={1.7} aria-hidden />
            </button>
            <span className={s.zoomValor}>{zoom.toFixed(1)}×</span>
            <button
              type="button"
              className={s.zoomBotao}
              aria-label="Aumentar zoom"
              disabled={!urlEvidencia || zoom >= ZOOM_MAX}
              onClick={() => setZoom((z) => Math.min(ZOOM_MAX, z + ZOOM_PASSO))}
            >
              <Plus size={15} strokeWidth={1.7} aria-hidden />
            </button>
          </div>
        </div>

        <div className={s.painel}>
          <span className={s.overline}>Detecção proposta</span>

          <div className={s.classeLinha}>
            <AlertTriangle size={20} strokeWidth={1.7} aria-hidden />
            <span className={s.classeNome}>{rotuloClasse}</span>
          </div>

          <div className={s.ficha}>
            <span className={s.fichaRotulo}>Câmera</span>
            <span className={s.fichaDado}>{atual.camera_name ?? atual.camera_id ?? '—'}</span>
            <span className={s.fichaRotulo}>Horário</span>
            <span className={s.fichaDado}>{horaDe(atual)}</span>
            <span className={s.fichaRotulo}>Confiança</span>
            <span className={s.fichaDado}>
              {typeof confianca === 'number' ? `${Math.round(confianca * 100)}%` : '—'}
            </span>
            {atual.verification_reason && (
              <>
                <span className={s.fichaRotulo}>Motivo da IA</span>
                <span className={s.fichaDado}>{atual.verification_reason}</span>
              </>
            )}
          </div>

          {principal && natural && urlEvidencia && (
            <div
              className={s.recorte}
              style={estiloRecorte(principal, natural.w, natural.h, urlEvidencia)}
              role="img"
              aria-label={`Recorte da detecção de ${rotuloClasse}`}
            >
              <span className={s.recorteRotulo}>RECORTE DA DETECÇÃO</span>
            </div>
          )}

          {semUnidade > 0 && (
            <span className={s.nota}>
              {semUnidade === 1 ? '1 violação' : `${semUnidade} violações`} sem unidade de caixa
              conhecida — não projetadas sobre o frame.
            </span>
          )}

          <div className={s.navegacao}>
            <button
              type="button"
              className={s.navBotao}
              onClick={voltar}
              disabled={indice === 0}
              aria-label="Item anterior"
            >
              <ArrowLeft size={14} strokeWidth={1.7} aria-hidden /> Anterior
            </button>
            <span className={s.espacador} />
            <button
              type="button"
              className={s.navBotao}
              onClick={avancar}
              disabled={indice >= fila.length - 1}
              aria-label="Próximo item"
            >
              Próximo <ArrowRight size={14} strokeWidth={1.7} aria-hidden />
            </button>
          </div>

          <div className={s.veredito}>
            {vereditoAtual ? (
              <span
                className={`${s.decidido} ${
                  vereditoAtual === 'approve' ? s.decididoOk : s.decididoNc
                }`}
              >
                {vereditoAtual === 'approve' ? (
                  <Check size={14} strokeWidth={2.4} aria-hidden />
                ) : (
                  <X size={14} strokeWidth={2.4} aria-hidden />
                )}
                {vereditoAtual === 'approve' ? 'Confirmado' : 'Rejeitado'}
              </span>
            ) : null}

            <button
              type="button"
              className={s.confirmar}
              onClick={() => void decidir('approve')}
              disabled={!podeEscrever || enviando}
              title={podeEscrever ? undefined : 'Exige a permissão verification:write'}
            >
              <Check size={17} strokeWidth={2.4} aria-hidden />
              Confirmar <span className={s.teclaBotao}>C</span>
            </button>

            <button
              type="button"
              className={s.rejeitar}
              onClick={() => void decidir('reject')}
              disabled={!podeEscrever || enviando}
              title={podeEscrever ? undefined : 'Exige a permissão verification:write'}
            >
              <X size={16} strokeWidth={2.4} aria-hidden />
              Rejeitar <span className={s.teclaBotao}>R</span>
            </button>

            <button
              type="button"
              className={s.anotar}
              disabled
              title="Sem endpoint que leve um alerta para a fila de anotação do Estúdio — registrado para o backend"
            >
              <PenLine size={14} strokeWidth={1.8} aria-hidden />
              Enviar para anotação · Estúdio
            </button>

            <span className={s.nota}>
              Cada decisão vira dado de treino. O envio para a fila de anotação do Estúdio
              ainda não tem endpoint — registrado, e a verificação não trava por isso.
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
