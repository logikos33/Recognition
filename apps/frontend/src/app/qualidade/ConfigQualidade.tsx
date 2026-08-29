/**
 * `/qualidade/config` — Configuração do módulo Qualidade.
 *
 * Spec: `design/Configuração Qualidade.dc.html`, abas C1 "Pontos & rotas" e
 * C2 "Limiares & estações".
 *
 * ─── O DESENHO PEDE UM OBJETO QUE O BACKEND NÃO TEM ─────────────────────────
 *
 * Medido no código, não suposto. **PONTO DE INSPEÇÃO não existe** — nem tabela,
 * nem rota, nem coluna. O schema por tenant (migration 104) tem
 * `quality_stations`, `quality_pieces`, `quality_camera_config`,
 * `quality_inspections` e `quality_reworks`; nenhuma delas é ponto. Com isso cai
 * junto tudo que o desenho pendura nele: código (P1/P4/H1), situação visual
 * (A/B/C/D), CRITÉRIO, TOLERÂNCIA, FOTO ESPECIFICADO, DOCUMENTO INFO/FP, as
 * ROTAS POR TIPO DE PRODUTO e o arrastar-para-reordenar. A aba C1 inteira é
 * lacuna — e por isso ela mostra a lacuna, não seis linhas inventadas.
 *
 * O que sobra de real, e é o que a aba C2 serve:
 *
 *  · `GET /v1/quality/gate/stations` — as estações de verdade.
 *  · `GET /v1/quality/cameras` — a ÚNICA rota que resolve NOME de câmera, e a
 *    dona dos únicos limiares que existem (`ok_confidence_threshold` /
 *    `nok_confidence_threshold`), que são **por câmera**, nunca por ponto.
 *
 * ─── DUAS PROMESSAS DO DESENHO QUE SERIAM MENTIRA ───────────────────────────
 *
 *  1. **"Alterações valem imediatamente nas estações — sem deploy."** É falso
 *     para limiar: `ok_confidence_threshold`/`nok_confidence_threshold` são
 *     gravados e NUNCA LIDOS. Quem decide é o worker, com variável de ambiente
 *     (`quality_inference.py:539`, `QUALITY_VOTING_THRESHOLD`). Mudar pela tela
 *     não muda decisão nenhuma; mudar de verdade exige deploy. A legenda do
 *     desenho foi trocada pelo texto verdadeiro, e o editor de limiar fica
 *     desabilitado dizendo por quê — `PATCH /cameras/<id>/config` existe e
 *     grava, mas gravar um número que ninguém lê é o pior tipo de botão: o que
 *     responde "salvo" e não muda nada.
 *  2. **As TRÊS FAIXAS** (refazer/NC · dúvida · conforme). O caminho servido é
 *     BINÁRIO: `quality_inference.py:619` decide `"ok"` ou `"nok"`, e
 *     `quality_inspections.result` só carrega esses dois. Não existe "dúvida"
 *     em tabela, rota ou worker. Desenhar três faixas seria desenhar um estado
 *     que o produto não sabe produzir.
 *
 * ─── COLUNAS DA TABELA DE ESTAÇÕES QUE SAÍRAM ───────────────────────────────
 *
 *  · **PONTOS ATENDIDOS** — `quality_stations` não tem o vínculo (só
 *    `camera_ids`). Sem ponto, não há o que atender.
 *  · **TOKEN DA ESTAÇÃO / regenerar** — não existe token de estação. O análogo
 *    (enrollment token) é de SITE EDGE, e nem ele serviria: o plaintext sai uma
 *    única vez na criação, então exibir "••••7f2a" depois é impossível.
 *  · **box-edge-01 / cam-04** — o vínculo estação→site edge não está modelado;
 *    `camera_ids` vem como UUID cru, sem JOIN. Resolvemos o NOME pela rota de
 *    câmeras e omitimos o box. UUID na tela é dado ilegível, não dado real.
 *
 * ⛔ Nada aqui é inventado: sem endpoint, sem dado; sem rota, sem ação.
 */
import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle2, CircleSlash, Plus, SlidersHorizontal } from 'lucide-react'

import { useAuth } from '../../hooks/useAuth'
import { api } from '../../services/api'
import { LogikosLoader } from '../shell/LogikosLoader'
import { lk } from '../tokens/lk.css'
import * as s from './ConfigQualidade.css'

const ROTA_ESTACOES = '/v1/quality/gate/stations'
const ROTA_CAMERAS = '/v1/quality/cameras'
const ROTA_DISPONIVEIS = '/v1/quality/cameras/available'

/** Colunas reais de `{tenant_schema}.quality_stations` (o GET faz SELECT *). */
interface Estacao {
  id?: string
  station_code: string
  name?: string | null
  description?: string | null
  camera_ids?: unknown
  is_active?: boolean | null
}

/** `GET /v1/quality/cameras` — nome + a config de qualidade da câmera. */
interface CameraQualidade {
  id: string
  name?: string | null
  location?: string | null
  ok_confidence_threshold?: number | null
  nok_confidence_threshold?: number | null
}

type Aba = 'c1' | 'c2'

/**
 * `camera_ids` é JSONB. Vem como array na prática, mas um SELECT * não promete
 * forma: se vier qualquer outra coisa, tratamos como vazio em vez de explodir a
 * tela inteira por causa de uma célula.
 */
function idsDe(valor: unknown): string[] {
  return Array.isArray(valor) ? valor.filter((v): v is string => typeof v === 'string') : []
}

/**
 * Limiar é float (0.6). Sem valor gravado, a célula DIZ que não há — "0,00"
 * seria afirmar um limiar que ninguém configurou.
 */
function limiar(v: number | null | undefined): string | null {
  return typeof v === 'number' && Number.isFinite(v) ? v.toFixed(2).replace('.', ',') : null
}

/** Motivo único, repetido nos `title` — um lugar só para manter a verdade. */
const PORQUE_LIMIAR_TRAVADO =
  'Gravar não mudaria decisão nenhuma: o worker lê a variável de ambiente ' +
  'QUALITY_VOTING_THRESHOLD (quality_inference.py:539) e nunca lê estas colunas.'

export function ConfigQualidade() {
  const { can } = useAuth()
  const [aba, setAba] = useState<Aba>('c1')
  const [estacoes, setEstacoes] = useState<Estacao[] | null>(null)
  const [cameras, setCameras] = useState<CameraQualidade[] | null>(null)
  const [nomes, setNomes] = useState<Record<string, string>>({})
  const [erro, setErro] = useState<string | null>(null)

  const podeConfigurar = can('cameras:configure')

  const carregar = useCallback(() => {
    setErro(null)
    setEstacoes(null)
    setCameras(null)

    api
      .get<{ data?: { stations?: Estacao[] } }>(ROTA_ESTACOES)
      .then((r) => setEstacoes(r.data?.stations ?? []))
      .catch((e) => setErro(e instanceof Error ? e.message : 'Erro ao carregar'))

    api
      .get<{ data?: { cameras?: CameraQualidade[] } }>(ROTA_CAMERAS)
      .then((r) => {
        const lista = r.data?.cameras ?? []
        setCameras(lista)
        setNomes((n) => ({ ...n, ...mapaDeNomes(lista) }))
      })
      .catch((e) => setErro(e instanceof Error ? e.message : 'Erro ao carregar'))

    // Câmeras ainda NÃO atribuídas ao módulo entram só para resolver nome: uma
    // estação pode apontar para uma delas, e sem este mapa a célula cairia em
    // "não identificada" por falta de tradução, não por falta de câmera.
    api
      .get<{ data?: { cameras?: CameraQualidade[] } }>(ROTA_DISPONIVEIS)
      .then((r) => setNomes((n) => ({ ...n, ...mapaDeNomes(r.data?.cameras ?? []) })))
      .catch(() => undefined)
  }, [])

  useEffect(carregar, [carregar])

  if (erro) {
    return (
      <div className={s.centro}>
        <AlertTriangle size={36} strokeWidth={1.5} color={lk.estado.nc} aria-hidden="true" />
        <span className={s.centroTitulo}>Não foi possível carregar a configuração</span>
        <span className={s.centroTecnico}>
          GET /api{ROTA_ESTACOES} · {erro}
        </span>
        <button className={s.botaoRetry} onClick={carregar}>
          Tentar novamente
        </button>
      </div>
    )
  }

  if (estacoes === null || cameras === null) {
    return (
      <LogikosLoader estado="waiting" variante="fullscreen" rotulo="CARREGANDO CONFIGURAÇÃO" />
    )
  }

  return (
    <div className={s.raiz}>
      <div className={s.cabecalho}>
        <h1 className={s.titulo}>Configuração</h1>
        <div className={s.abas} role="tablist" aria-label="Seções da configuração">
          <button
            className={s.aba}
            role="tab"
            aria-selected={aba === 'c1'}
            onClick={() => setAba('c1')}
          >
            Pontos &amp; rotas
          </button>
          <button
            className={s.aba}
            role="tab"
            aria-selected={aba === 'c2'}
            onClick={() => setAba('c2')}
          >
            Limiares &amp; estações
          </button>
        </div>
        <span className={s.espacador} />
        {/*
          O desenho promete aqui "valem imediatamente nas estações — sem deploy".
          Para limiar isso é falso, e uma legenda falsa é pior que legenda
          nenhuma: ela vira a razão de alguém não investigar por que o ajuste não
          surtiu efeito.
        */}
        <span className={s.avisoTopo}>
          <AlertTriangle
            size={14}
            strokeWidth={2}
            color={lk.estado.atencao}
            style={{ flex: 'none' }}
            aria-hidden="true"
          />
          Mudar limiar por aqui não altera a decisão do motor — ele lê uma variável de
          ambiente, e trocá-la exige deploy.
        </span>
      </div>

      {aba === 'c1' ? <PontosERotas /> : (
        <Limiares
          cameras={cameras}
          estacoes={estacoes}
          nomes={nomes}
          podeConfigurar={podeConfigurar}
        />
      )}
    </div>
  )
}

function mapaDeNomes(lista: CameraQualidade[]): Record<string, string> {
  return Object.fromEntries(
    lista.filter((c) => c.id && c.name).map((c) => [c.id, String(c.name)]),
  )
}

/**
 * C1 — a aba inteira é lacuna. Os dois controles do desenho ficam no lugar
 * deles, desabilitados e dizendo por quê; a lista some, porque uma lista de
 * pontos inventados é pior que a ausência: ela some do radar de quem decide o
 * roadmap, e alguém acaba tentando operar por ela.
 */
function PontosERotas() {
  return (
    <div className={s.colunas}>
      <div className={s.colunaPrincipal}>
        <div className={s.secaoCabecalho}>
          <h2 className={s.secaoTitulo}>Pontos de inspeção</h2>
          <span className={s.espacador} />
          <button
            className={s.botaoContorno}
            disabled
            title="Sem rota: não existe tabela nem endpoint de ponto de inspeção no backend."
          >
            <Plus size={14} strokeWidth={2} aria-hidden="true" /> Novo ponto
          </button>
        </div>

        <div className={s.vazio}>
          <SlidersHorizontal
            size={34}
            strokeWidth={1.5}
            color={lk.cor.cinzaNevoa}
            aria-hidden="true"
          />
          <span className={s.vazioTitulo}>Ponto de inspeção ainda não existe no servidor</span>
          <span className={s.vazioTexto}>
            O módulo guarda estações, peças, configuração por câmera e inspeções — mas não
            guarda o ponto. Sem ele não há código, critério, tolerância, foto de
            especificado nem documento de instrução para mostrar, e nada disso seria
            verdade se aparecesse aqui.
          </span>
        </div>

        <h2 className={s.secaoTitulo}>Rotas por tipo de produto</h2>
        <div className={s.vazio}>
          <span className={s.vazioTexto}>
            A rota é uma sequência de pontos por tipo de produto. Sem ponto e sem tabela de
            sequência, não há o que ordenar — <code>product_type</code> hoje é só um texto
            livre na peça e na configuração da câmera, não uma entidade com rota.
          </span>
        </div>
      </div>

      <div className={s.painelLateral}>
        <span className={s.painelTitulo}>Editar ponto</span>
        <span className={s.rotulo}>o que falta no servidor</span>
        <ul className={s.listaFalta}>
          <li>Critério — o texto que o operador lê. Sem coluna, sem campo.</li>
          <li>Tolerância e unidade. Sem coluna, sem campo.</li>
          <li>
            Foto do especificado. O que existe é por câmera e ordem de produção, e a rota
            devolve a chave do arquivo, não uma URL assinada — a imagem nem carregaria.
          </li>
          <li>Documento de instrução (código, revisão, data). Não existe em lugar nenhum.</li>
        </ul>
        <button
          className={s.botaoPrimario}
          disabled
          title="Sem rota: não há POST, PUT ou PATCH de ponto de inspeção — não existe o que publicar."
        >
          PUBLICAR ALTERAÇÃO
        </button>
      </div>
    </div>
  )
}

function Limiares({
  cameras,
  estacoes,
  nomes,
  podeConfigurar,
}: {
  cameras: CameraQualidade[]
  estacoes: Estacao[]
  nomes: Record<string, string>
  podeConfigurar: boolean
}) {
  return (
    <>
      <h2 className={s.secaoTitulo}>Limiares por câmera</h2>
      <p className={s.avisoTopo}>
        O desenho pede três faixas (refazer · dúvida · conforme) por ponto de inspeção. O
        caminho servido é binário — ok ou nok — e o limiar mora na câmera, não no ponto.
        Estes são os dois números que existem de verdade.
      </p>

      {cameras.length === 0 ? (
        <div className={s.vazio}>
          <span className={s.vazioTitulo}>Nenhuma câmera atribuída ao módulo Qualidade</span>
          <span className={s.vazioTexto}>
            Os limiares vivem na configuração de qualidade da câmera. Enquanto nenhuma
            câmera estiver atribuída ao módulo, não há limiar para exibir.
          </span>
        </div>
      ) : (
        cameras.map((c) => {
          const ok = limiar(c.ok_confidence_threshold)
          const nok = limiar(c.nok_confidence_threshold)
          return (
            <div className={s.linhaLimiar} key={c.id}>
              <span className={s.identificacao}>
                <span className={s.nomeCamera}>{c.name ?? 'Câmera sem nome'}</span>
                {c.location && <span className={s.localCamera}>{c.location}</span>}
              </span>
              <span className={s.espacador} />
              <span className={s.parLimiar}>
                <span className={s.rotulo}>conforme ≥</span>
                {ok ? (
                  <span className={s.valor}>{ok}</span>
                ) : (
                  <span className={s.valorAusente}>não definido</span>
                )}
              </span>
              <span className={s.parLimiar}>
                <span className={s.rotulo}>não conforme ≥</span>
                {nok ? (
                  <span className={s.valor}>{nok}</span>
                ) : (
                  <span className={s.valorAusente}>não definido</span>
                )}
              </span>
              <button className={s.acao} disabled title={PORQUE_LIMIAR_TRAVADO}>
                Editar limiar
              </button>
            </div>
          )
        })
      )}

      {podeConfigurar && (
        <div className={s.faixaFalta}>
          <AlertTriangle
            size={14}
            strokeWidth={2}
            color={lk.estado.atencao}
            style={{ flex: 'none' }}
            aria-hidden="true"
          />
          <span>
            <strong>Editar limiar está travado de propósito.</strong> A rota de gravação
            existe e responderia "salvo", mas as duas colunas nunca são lidas: quem decide é
            o worker, pela variável de ambiente. Um botão que grava sem efeito é pior que um
            botão desabilitado — ele faz a pessoa parar de procurar a causa. Ligar o ajuste
            de verdade é pedido ao backend, não à tela.
          </span>
        </div>
      )}

      <h2 className={s.secaoTitulo}>Estações</h2>

      {estacoes.length === 0 ? (
        <div className={s.vazio}>
          <span className={s.vazioTitulo}>Nenhuma estação cadastrada</span>
          <span className={s.vazioTexto}>
            Estação é a bancada onde a peça é inspecionada. O cadastro pela tela ainda não
            foi desenhado — hoje ela nasce pela API.
          </span>
        </div>
      ) : (
        <div className={s.tabela}>
          <div className={s.th}>Estação</div>
          <div className={s.th}>Câmera</div>
          <div className={s.th}>Situação</div>
          {estacoes.map((e) => {
            const nomesDasCameras = idsDe(e.camera_ids)
              .map((id) => nomes[id])
              .filter(Boolean)
            const ativa = e.is_active !== false
            return (
              <div key={e.station_code} style={{ display: 'contents' }}>
                <div className={s.td}>
                  <span>{e.name ?? e.station_code}</span>
                  <span className={s.codigoEstacao}>{e.station_code}</span>
                </div>
                <div className={s.td}>
                  {nomesDasCameras.length > 0 ? (
                    nomesDasCameras.map((n) => <span key={n}>{n}</span>)
                  ) : (
                    <span
                      className={s.valorAusente}
                      title="A estação aponta para câmeras que nenhuma rota do módulo resolve por nome. O identificador cru não é exibido de propósito."
                    >
                      câmera não identificada
                    </span>
                  )}
                </div>
                <div className={s.td}>
                  <span
                    className={s.estado}
                    style={{ color: ativa ? lk.estado.ok : lk.cor.cinzaNevoa }}
                    title="Somente leitura: nenhuma rota grava a situação da estação."
                  >
                    {ativa ? (
                      <CheckCircle2 size={14} strokeWidth={2.2} aria-hidden="true" />
                    ) : (
                      <CircleSlash size={14} strokeWidth={2.2} aria-hidden="true" />
                    )}
                    {ativa ? 'ATIVA' : 'INATIVA'}
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      )}

      <div className={s.faixaFalta}>
        <AlertTriangle
          size={14}
          strokeWidth={2}
          color={lk.estado.atencao}
          style={{ flex: 'none' }}
          aria-hidden="true"
        />
        <span>
          <strong>Três colunas do desenho não estão aqui.</strong> "Pontos atendidos" exige
          o vínculo estação→ponto, que não existe. "Token da estação" não existe como
          conceito — o token parecido é de site do edge, e o seu valor só aparece uma vez,
          na criação, então nem os últimos dígitos poderiam ser mostrados depois. E o box do
          edge não está modelado na estação, por isso a coluna Câmera traz só o nome da
          câmera. A situação é somente leitura pelo mesmo motivo do Pausar em Operações:
          nenhuma rota a grava.
        </span>
      </div>
    </>
  )
}
