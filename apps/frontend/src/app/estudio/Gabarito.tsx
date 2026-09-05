/**
 * Gabarito — a triagem POR TOQUE que destrava o A/B das três variantes.
 *
 * POR QUE ESTA TELA NÃO É UM ANOTADOR ENCOLHIDO
 *
 * `scripts/ops/ab_ausencia.py` compara as variantes no nível da DECISÃO: "por
 * imagem e por classe de ausência, o modelo ACUSOU ou não, e o gabarito diz se
 * aquela ausência era real". Ou seja: o gabarito é uma RESPOSTA POR IMAGEM.
 * Caixa não entra na conta — e não entraria mesmo que existisse, porque estes
 * quadros são `dataset_role='holdout'` (migration 133) e nunca vão treinar;
 * caixa só serve para treinar.
 *
 * Daí a forma da tela: uma foto grande e três botões. Desenhar retângulo sobre
 * 1920x1080 num celular é ruim por natureza (~2 min por imagem, e o erro de
 * dedo vira dado errado); responder "tem alguém sem luva aqui?" é um toque
 * (~8 s). A mudança não é de conforto, é o que torna a prova viável de fazer.
 *
 * ⛔ NÃO transformar isto em editor de caixa. Se um dia o gabarito precisar de
 * geometria, é outra tela, com outra justificativa e outro destino de dados.
 *
 * ROTA PRÓPRIA, FORA DO LAYOUT DO ESTÚDIO (`ROTAS_NOVAS_SEM_SHELL`). O
 * `Estudio` tem lateral fixa de 220px e o `Shell` tem topbar — juntos comem
 * metade da largura útil de um telefone em pé. Aqui a foto precisa de cada
 * pixel. Mesmo precedente do Kiosk (`/novo/tablet/:station`), que também é
 * tela de aparelho, não tela de escritório. O gate de permissão continua
 * valendo: é aplicado no próprio componente, não herdado do layout.
 *
 * ORDEM: a fila vem pronta do backend (`priority_rank`, semeado da
 * `fila-gabarito-150.csv` — probabilidade de conter ausência real × prioridade
 * de câmera do dono). Esta tela OBEDECE. Reordenar aqui inventaria uma segunda
 * fila, e o dono deixaria de estar anotando a que ele decidiu.
 *
 * REDE: ver `filaGabarito.ts`. Resposta grava local primeiro, sobe depois.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Check, ChevronLeft, ChevronRight, HelpCircle, UserX, X } from 'lucide-react'
import { Link } from 'react-router-dom'

import { useAuth } from '../../hooks/useAuth'
import { api, API_BASE } from '../../services/api'
import type { ApiResponse } from '../../types'
import { rotaNova } from '../RotasNovas'
import { SemPermissao } from '../shell/SemPermissao'
import * as s from './Gabarito.css'
import {
  aplicarResposta,
  gravarPosicao,
  gravarRespostas,
  lerPosicao,
  lerRespostas,
  pendentes,
  semear,
  type Respostas,
  type Veredito,
} from './filaGabarito'

interface ClasseGabarito {
  class_id: number
  nome: string
  /** As duas com gabarito ZERO no holdout — as que travam o A/B. */
  foco: boolean
}

interface QuadroGabarito {
  id: string
  url?: string | null
  camera_name?: string | null
  captured_at?: string | null
  verdicts: Record<string, Veredito>
  reason?: 'sem_pessoa' | null
}

const VEREDITOS: { valor: Veredito; rotulo: string; Icone: typeof Check }[] = [
  { valor: 'sim', rotulo: 'Sim', Icone: Check },
  { valor: 'nao', rotulo: 'Não', Icone: X },
  { valor: 'nao_sei', rotulo: 'Não sei', Icone: HelpCircle },
]

/** Distância entre dois toques — a régua do pinch. */
const distancia = (a: React.Touch, b: React.Touch): number =>
  Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY)

export function Gabarito() {
  const { can } = useAuth()

  const [classes, setClasses] = useState<ClasseGabarito[]>([])
  const [quadros, setQuadros] = useState<QuadroGabarito[]>([])
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)

  const [respostas, setRespostas] = useState<Respostas>(() => lerRespostas())
  const [indice, setIndice] = useState<number>(() => lerPosicao())
  const [verSecundarias, setVerSecundarias] = useState(false)

  // ── Carga da fila ────────────────────────────────────────────────────────
  // Uma vez, inteira. Ver a docstring de get_gabarito_fila_handler: fila
  // paginada para de funcionar exatamente quando o sinal cai.
  const podeAnotar = can('frames:annotate')

  useEffect(() => {
    // O gate de permissão é um `return` lá embaixo, no corpo do render — mas
    // hooks rodam ANTES dele. Sem esta guarda, quem não pode anotar dispara a
    // busca da fila assim mesmo: a API responde 403 e o pedido nunca deveria
    // ter saído. Achado por teste, não por revisão.
    if (!podeAnotar) return
    let vivo = true
    api
      .get<ApiResponse<{ classes: ClasseGabarito[]; frames: QuadroGabarito[] }>>(
        '/training/gabarito/fila',
      )
      .then((res) => {
        if (!vivo) return
        const dados = res.data
        setClasses(dados?.classes ?? [])
        setQuadros(dados?.frames ?? [])
        // Semeia o que o servidor já sabe SEM pisar em resposta local
        // pendente — a pendência é o único dado que existe num lugar só.
        const doServidor = Object.fromEntries(
          (dados?.frames ?? [])
            .filter((f) => Object.keys(f.verdicts ?? {}).length > 0)
            .map((f) => [
              f.id,
              {
                verdicts: Object.fromEntries(
                  Object.entries(f.verdicts).map(([k, v]) => [Number(k), v]),
                ) as Record<number, Veredito>,
                ...(f.reason ? { reason: f.reason } : {}),
              },
            ]),
        )
        setRespostas((atual) => {
          const semeado = semear(atual, doServidor)
          gravarRespostas(semeado)
          return semeado
        })
      })
      .catch((e: Error) => vivo && setErro(e.message))
      .finally(() => vivo && setCarregando(false))
    return () => {
      vivo = false
    }
  }, [podeAnotar])

  // ── Envio das pendências ─────────────────────────────────────────────────
  // `respostasRef` em vez de dependência do efeito: o flush é disparado por
  // eventos (voltar a rede) e por cada resposta nova; lê-lo de um ref evita
  // recriar os listeners a cada toque — e um listener recriado no meio de um
  // envio é como uma resposta ficaria pendente para sempre.
  const respostasRef = useRef(respostas)
  respostasRef.current = respostas
  const enviando = useRef(false)

  const enviarPendentes = useCallback(async () => {
    if (enviando.current) return
    enviando.current = true
    try {
      for (const frameId of pendentes(respostasRef.current)) {
        const r = respostasRef.current[frameId]
        try {
          await api.put(`/training/gabarito/frames/${frameId}`, {
            verdicts: r.verdicts,
            reason: r.reason ?? null,
          })
        } catch {
          // Rede caiu no meio da fila. Para aqui: as seguintes também vão
          // falhar, e martelar o servidor offline só gasta bateria. A
          // pendência continua marcada e o próximo gatilho retenta.
          break
        }
        setRespostas((atual) => {
          // Confirma SÓ se nada mudou desde o envio — o dono pode ter mudado
          // de ideia enquanto a requisição estava no ar, e marcar 'enviado'
          // sobre a resposta nova a perderia para sempre.
          if (atual[frameId] !== r) return atual
          const proximo = { ...atual, [frameId]: { ...r, enviado: true } }
          gravarRespostas(proximo)
          return proximo
        })
      }
    } finally {
      enviando.current = false
    }
  }, [])

  useEffect(() => {
    void enviarPendentes()
    window.addEventListener('online', enviarPendentes)
    return () => window.removeEventListener('online', enviarPendentes)
  }, [enviarPendentes, respostas])

  // ── Zoom e arrasto ───────────────────────────────────────────────────────
  // O EPI ocupa poucas dezenas de pixels num quadro 1920x1080: sem zoom o dono
  // não consegue ver se há luva na mão, e a tela não decide nada.
  //
  // Escala/deslocamento próprios, e não o pinch nativo do navegador: o zoom da
  // PÁGINA amplia também os botões e joga o SIM/NÃO para fora da tela, então
  // responder exigiria voltar o zoom a cada imagem. `touchAction: 'none'` no
  // painel entrega os gestos a este componente; o resto da página segue normal.
  const [zoom, setZoom] = useState(1)
  const [desloc, setDesloc] = useState({ x: 0, y: 0 })
  const gesto = useRef<{ dist: number; zoom: number; x: number; y: number } | null>(null)

  const aoTocar = (e: React.TouchEvent) => {
    if (e.touches.length === 2) {
      gesto.current = {
        dist: distancia(e.touches[0], e.touches[1]),
        zoom,
        x: desloc.x,
        y: desloc.y,
      }
    } else if (e.touches.length === 1) {
      gesto.current = {
        dist: 0,
        zoom,
        x: e.touches[0].clientX - desloc.x,
        y: e.touches[0].clientY - desloc.y,
      }
    }
  }

  const aoMover = (e: React.TouchEvent) => {
    const g = gesto.current
    if (!g) return
    if (e.touches.length === 2 && g.dist > 0) {
      // Teto em 6×: acima disso o JPEG só entrega borrão, e o dono ficaria
      // arrastando um mosaico achando que a imagem é ruim.
      const novo = Math.min(6, Math.max(1, (g.zoom * distancia(e.touches[0], e.touches[1])) / g.dist))
      setZoom(novo)
      if (novo === 1) setDesloc({ x: 0, y: 0 })
    } else if (e.touches.length === 1 && zoom > 1) {
      setDesloc({ x: e.touches[0].clientX - g.x, y: e.touches[0].clientY - g.y })
    }
  }

  const zerarZoom = useCallback(() => {
    setZoom(1)
    setDesloc({ x: 0, y: 0 })
  }, [])

  // ── Navegação ────────────────────────────────────────────────────────────
  const irPara = useCallback(
    (i: number) => {
      const alvo = Math.min(Math.max(i, 0), Math.max(quadros.length - 1, 0))
      setIndice(alvo)
      gravarPosicao(alvo)
      // Zoom é do quadro que estava na tela, não da fila: mantê-lo abriria a
      // próxima imagem já ampliada num canto que não tem nada a ver com ela.
      zerarZoom()
      setVerSecundarias(false)
    },
    [quadros.length, zerarZoom],
  )

  // A posição vem do storage e a fila pode ter encolhido desde a última
  // sessão. Sem este ajuste a tela abriria em branco, sem dizer por quê.
  useEffect(() => {
    if (quadros.length > 0 && indice > quadros.length - 1) irPara(quadros.length - 1)
  }, [quadros.length, indice, irPara])

  const quadro = quadros[indice]

  const responder = useCallback(
    (classId: number, veredito: Veredito) => {
      if (!quadro) return
      setRespostas((atual) => {
        const proximo = aplicarResposta(atual, quadro.id, { [classId]: veredito })
        gravarRespostas(proximo)
        return proximo
      })
    },
    [quadro],
  )

  /**
   * "Não há pessoa" — o atalho de um toque.
   *
   * Muito quadro do gravador não tem ninguém enquadrado, e sem este botão o
   * dono gastaria 3+ toques numa imagem que não decide nada. Sem pessoa,
   * NENHUMA ausência é real: logo 'nao' para todas as classes de uma vez — e
   * é o negativo que o A/B mais precisa (modelo que acusa "sem luvas" em
   * corredor vazio está produzindo falso positivo). `reason` guarda que a
   * resposta veio daqui, para a prova poder ser auditada depois.
   */
  const semPessoa = useCallback(() => {
    if (!quadro) return
    const todas = Object.fromEntries(classes.map((c) => [c.class_id, 'nao' as Veredito]))
    setRespostas((atual) => {
      const proximo = aplicarResposta(atual, quadro.id, todas, 'sem_pessoa')
      gravarRespostas(proximo)
      return proximo
    })
    irPara(indice + 1)
  }, [quadro, classes, indice, irPara])

  const respondidos = useMemo(
    () => quadros.filter((q) => Object.keys(respostas[q.id]?.verdicts ?? {}).length > 0).length,
    [quadros, respostas],
  )
  const naFila = pendentes(respostas).length
  const doQuadro = quadro ? respostas[quadro.id] : undefined
  const foco = classes.filter((c) => c.foco)
  const secundarias = classes.filter((c) => !c.foco)

  /**
   * Aviso COM a saída junto.
   *
   * Fila vazia, rede caída e carregando eterno são os becos sem saída mais
   * prováveis desta tela — e eram os únicos estados sem o link de volta,
   * porque os `return` antecipados pulavam o cabeçalho inteiro. Quem chega a
   * um deles no celular fica preso, com uma frase e nada mais.
   */
  const avisoComSaida = (texto: string) => (
    <div className={s.aviso}>
      <Link to={rotaNova('/estudio/dados')} className={s.voltar} aria-label="Voltar ao Estúdio">
        <ChevronLeft size={18} strokeWidth={2} aria-hidden="true" />
      </Link>
      <p>{texto}</p>
    </div>
  )

  if (!podeAnotar) return <SemPermissao permissao="frames:annotate" />
  if (carregando) return avisoComSaida('Carregando a fila…')
  if (erro) return avisoComSaida(`Não foi possível carregar a fila: ${erro}`)
  if (!quadro) return avisoComSaida('Nenhum quadro de gabarito nesta fila.')

  const linhaDeClasse = (c: ClasseGabarito) => {
    const dada = doQuadro?.verdicts[c.class_id]
    return (
      <div key={c.class_id} className={s.classe}>
        <div className={s.classeNome}>
          {c.nome}
          {c.foco && <span className={s.selo}>foco</span>}
        </div>
        <div className={s.botoes} role="group" aria-label={c.nome}>
          {VEREDITOS.map(({ valor, rotulo, Icone }) => (
            <button
              key={valor}
              type="button"
              // `aria-pressed` e não só a cor: estado é cor + ícone + palavra
              // (contrato dos tokens), e o leitor de tela precisa do terceiro.
              aria-pressed={dada === valor}
              aria-label={`${c.nome}: ${rotulo}`}
              className={dada === valor ? `${s.botao} ${s.botaoAtivo[valor]}` : s.botao}
              onClick={() => responder(c.class_id, valor)}
            >
              <Icone size={18} strokeWidth={2} aria-hidden="true" />
              {rotulo}
            </button>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className={s.raiz}>
      <header className={s.topo}>
        {/* Sem Shell e sem a lateral do Estúdio, esta tela não teria NENHUMA
            saída — vira beco sem saída (guarda em shell/becoSemSaida.test.tsx,
            que foi quem pegou a falta). Link de verdade, não botão: o dono
            pode querer abrir em outra aba, e `<button>` não faz isso. Volta
            para o Estúdio, que é de onde ele veio. */}
        <Link to={rotaNova('/estudio/dados')} className={s.voltar} aria-label="Voltar ao Estúdio">
          <ChevronLeft size={18} strokeWidth={2} aria-hidden="true" />
        </Link>
        <span className={s.contador}>
          {indice + 1} de {quadros.length}
        </span>
        <span className={s.camera}>{quadro.camera_name ?? 'câmera não identificada'}</span>
        {/* Pendência é informação de confiança, não enfeite: sem ela o dono
            não tem como saber que 12 respostas ainda não saíram do aparelho. */}
        {naFila > 0 && (
          <span className={s.pendencia} title="respostas ainda não enviadas">
            {naFila} a enviar
          </span>
        )}
        <span className={s.progresso}>{respondidos} respondidos</span>
      </header>

      <div
        className={s.painelFoto}
        onTouchStart={aoTocar}
        onTouchMove={aoMover}
        onDoubleClick={zerarZoom}
      >
        <img
          className={s.foto}
          src={quadro.url ?? `${API_BASE.replace(/\/api$/, '')}/api/training/frames/${quadro.id}/image`}
          alt={`Quadro ${indice + 1} de ${quadros.length}`}
          style={{ transform: `translate(${desloc.x}px, ${desloc.y}px) scale(${zoom})` }}
          draggable={false}
        />
        {zoom > 1 && (
          <button type="button" className={s.zerarZoom} onClick={zerarZoom}>
            {zoom.toFixed(1)}× · tocar para reduzir
          </button>
        )}
      </div>

      <div className={s.painelRespostas}>
        <button
          type="button"
          className={doQuadro?.reason === 'sem_pessoa' ? `${s.semPessoa} ${s.semPessoaAtivo}` : s.semPessoa}
          onClick={semPessoa}
        >
          <UserX size={18} strokeWidth={2} aria-hidden="true" />
          Não há pessoa
        </button>

        {foco.map(linhaDeClasse)}

        {secundarias.length > 0 && (
          <>
            <button
              type="button"
              className={s.maisClasses}
              aria-expanded={verSecundarias}
              onClick={() => setVerSecundarias((v) => !v)}
            >
              {verSecundarias ? 'Ocultar' : `Mais ${secundarias.length} classes`}
            </button>
            {verSecundarias && secundarias.map(linhaDeClasse)}
          </>
        )}
      </div>

      <nav className={s.rodape} aria-label="Navegação da fila">
        <button
          type="button"
          className={s.navegar}
          disabled={indice === 0}
          onClick={() => irPara(indice - 1)}
        >
          <ChevronLeft size={20} strokeWidth={2} aria-hidden="true" />
          Anterior
        </button>
        <button
          type="button"
          className={s.navegar}
          disabled={indice >= quadros.length - 1}
          onClick={() => irPara(indice + 1)}
        >
          Próxima
          <ChevronRight size={20} strokeWidth={2} aria-hidden="true" />
        </button>
      </nav>
    </div>
  )
}
