/**
 * `/epi/cameras/:id/operations` — o que esta câmera vigia, e com qual modelo.
 *
 * Spec: `design/Câmera Operações.dc.html`.
 *
 * ─── DUAS AÇÕES DO DESENHO NÃO TÊM BACKEND ──────────────────────────────────
 *
 * Medido no código, não suposto:
 *
 *  1. **Pausar / Retomar.** `PUT /api/operations/<id>` aceita SÓ `name` e
 *     `config` (routes.py:128-164). O campo `status` da tabela é escrito
 *     exclusivamente pelo worker, em `update_live_value`
 *     (operation_repository.py:170-186) — não existe caminho humano para pausar.
 *  2. **Avaliações** (o registro humano "esta operação está detectando bem?",
 *     com nota e autor). Não há tabela nem rota: `/operations/<id>/results` é
 *     outra coisa — é o que a operação MEDIU, não o que a pessoa JULGOU.
 *
 * Os dois ficam no lugar do desenho, **desabilitados e dizendo por quê** — é o
 * mesmo tratamento que a Verificação deu ao "Enviar para anotação". Anunciar
 * botão que não faz nada é pior que não anunciar; escondê-lo faria a lacuna
 * sumir do radar de quem decide o roadmap.
 *
 * ⛔ Nada aqui é inventado: sem endpoint, sem ação.
 */
import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle, LayoutGrid, Plus } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import { useAuth } from '../../hooks/useAuth'
import { api } from '../../services/api'
import { LogikosLoader } from '../shell/LogikosLoader'
import { rotaNova } from '../RotasNovas'
import { lk } from '../tokens/lk.css'
import * as s from './Operacoes.css'

/** Campos reais de `operations` (operation_repository.py:24-26). */
interface Operacao {
  id: number
  camera_id: string
  module_id: string
  type_id: string
  name: string
  config?: Record<string, unknown> | null
  status?: string | null
  version?: number
  last_evaluated_at?: string | null
  created_at?: string
}

interface Camera {
  id: string
  name?: string
  stream_status?: string | null
}

type Situacao = 'rodando' | 'pausada' | 'erro' | 'desconhecida'

/**
 * `status` vem do worker e não tem enum publicado no contrato. Mapeamos o que
 * se conhece e caímos em "desconhecida" no resto — inventar um rótulo bonito
 * para um valor que ninguém documentou é como se afirma o que não se sabe.
 */
function situacaoDe(status: string | null | undefined): Situacao {
  const v = (status ?? '').toLowerCase()
  if (v === 'active' || v === 'running') return 'rodando'
  if (v === 'inactive' || v === 'paused') return 'pausada'
  if (v === 'error' || v === 'failed') return 'erro'
  return 'desconhecida'
}

const APARENCIA: Record<Situacao, { rotulo: string; cor: string }> = {
  rodando: { rotulo: 'RODANDO', cor: lk.estado.ok },
  pausada: { rotulo: 'PAUSADA', cor: lk.cor.cinzaNevoa },
  erro: { rotulo: 'ERRO', cor: lk.estado.nc },
  desconhecida: { rotulo: 'SEM SINAL', cor: lk.cor.cinzaNevoa },
}

/**
 * "MÓDULO EPI · TIPO ppe_zone · v3".
 *
 * `module_id` da operação é um UUID que casa com `modules[].id` de
 * `GET /api/modules/`, cujo `module_code` é o nome legível. Sem resolver, a
 * linha mostrava `MÓDULO C925CAB6-ED2B-…` — UUID cru não é dado real, é dado
 * ilegível, e é o mesmo defeito que já apareceu no "Top câmera" de Relatórios.
 * Sem a resolução, o módulo simplesmente não entra na linha.
 */
function metaDe(op: Operacao, codigoDoModulo: string | undefined): string {
  const partes = [
    codigoDoModulo ? `MÓDULO ${codigoDoModulo.toUpperCase()}` : null,
    op.type_id ? `TIPO ${op.type_id}` : null,
    op.version ? `v${op.version}` : null,
  ].filter(Boolean)
  return partes.join(' · ')
}

function ultimaDe(op: Operacao): string {
  if (!op.last_evaluated_at) return 'NUNCA AVALIADA'
  const d = new Date(op.last_evaluated_at)
  if (Number.isNaN(d.getTime())) return 'NUNCA AVALIADA'
  return `ÚLTIMA AVALIAÇÃO ${d.toLocaleString('pt-BR', {
    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
  })}`
}

export function Operacoes() {
  const { cameraId = '' } = useParams<{ cameraId: string }>()
  const { can } = useAuth()
  const [ops, setOps] = useState<Operacao[] | null>(null)
  const [camera, setCamera] = useState<Camera | null>(null)
  const [modulos, setModulos] = useState<Record<string, string>>({})
  const [erro, setErro] = useState<string | null>(null)

  const podeConfigurar = can('cameras:configure')

  const carregar = useCallback(() => {
    setErro(null)
    setOps(null)
    api
      .get<{ data?: { operations?: Operacao[] } }>(`/cameras/${cameraId}/operations`)
      .then((r) => setOps(r.data?.operations ?? []))
      .catch((e) => setErro(e instanceof Error ? e.message : 'Erro ao carregar'))
    // O nome da câmera é enfeite útil, não requisito: se falhar, o título cai
    // para o id e a tela continua inteira.
    // A rota devolve a câmera DIRETO em `data`, não aninhada em `data.camera`
    // — medido. Aceito as duas formas para não quebrar se o envelope mudar.
    api
      .get<{ data?: (Camera & { camera?: Camera }) | null }>(`/cameras/${cameraId}`)
      .then((r) => setCamera(r.data?.camera ?? r.data ?? null))
      .catch(() => undefined)

    // Mapa UUID → código do módulo, para a linha não mostrar identificador.
    api
      .get<{ data?: { modules?: Array<{ id: string; module_code: string }> } }>('/modules/')
      .then((r) =>
        setModulos(
          Object.fromEntries((r.data?.modules ?? []).map((m) => [m.id, m.module_code])),
        ),
      )
      .catch(() => undefined)
  }, [cameraId])

  useEffect(carregar, [carregar])

  if (erro) {
    return (
      <div className={s.centro}>
        <AlertTriangle size={36} strokeWidth={1.5} color={lk.estado.nc} aria-hidden="true" />
        <span className={s.centroTitulo}>Não foi possível carregar</span>
        <span className={s.centroTecnico}>{erro}</span>
        <button className={s.botaoPrimario} onClick={carregar}>
          Tentar novamente
        </button>
      </div>
    )
  }

  if (ops === null) {
    return (
      <LogikosLoader estado="waiting" variante="fullscreen" rotulo="CARREGANDO OPERAÇÕES" />
    )
  }

  const titulo = camera?.name ?? cameraId

  if (ops.length === 0) {
    return (
      <div className={s.centro}>
        <LayoutGrid size={36} strokeWidth={1.5} color={lk.cor.cinzaNevoa} aria-hidden="true" />
        <span className={s.centroTitulo}>Esta câmera ainda não vigia nada</span>
        <span className={s.centroTexto}>
          Uma operação diz o que a câmera observa e com qual modelo. A criação pela tela
          ainda não foi desenhada — hoje ela nasce pela API.
        </span>
        <Link className={s.botaoSecundario} to={rotaNova('/epi/cameras')}>
          Voltar para câmeras
        </Link>
      </div>
    )
  }

  return (
    <div className={s.raiz}>
      <div className={s.cabecalho}>
        <Link className={s.voltar} to={rotaNova('/epi/cameras')}>
          ← Câmeras
        </Link>
        <h1 className={s.titulo}>{titulo}</h1>
        <span className={s.espacador} />
        <Link
          className={s.botaoSecundario}
          to={rotaNova(`/epi/cameras/${cameraId}/scenario`)}
        >
          <LayoutGrid size={15} strokeWidth={1.8} aria-hidden="true" />
          Editar zonas (cenário)
        </Link>
        {/* POST /cameras/<id>/operations existe, mas o formulário de criação
            não foi desenhado — botão sem tela é convite a um beco. */}
        <button
          className={s.botaoPrimario}
          disabled
          title="A criação de operação pela tela ainda não foi desenhada."
        >
          <Plus size={15} strokeWidth={2} aria-hidden="true" /> Nova operação
        </button>
      </div>

      <p className={s.explicacao}>
        Operação = o que esta câmera vigia e com qual modelo. As zonas que ela usa moram
        no cenário; mudanças propagam ao edge no próximo heartbeat.
      </p>

      {ops.map((op) => {
        const sit = situacaoDe(op.status)
        const ap = APARENCIA[sit]
        return (
          <div
            key={op.id}
            className={sit === 'erro' ? `${s.cartao} ${s.cartaoComErro}` : s.cartao}
          >
            <div className={s.linha}>
              <span className={s.estado} style={{ color: ap.cor }}>
                <span className={s.bolinha} style={{ background: ap.cor }} />
                {ap.rotulo}
              </span>
              <span className={s.identificacao}>
                <span className={s.nome}>{op.name}</span>
                <span className={s.meta}>{metaDe(op, modulos[op.module_id])}</span>
              </span>
              <span className={s.espacador} />
              <span className={s.ultima}>{ultimaDe(op)}</span>
              <button
                className={s.acao}
                disabled
                title="Pausar e retomar ainda não está disponível — a operação segue como está."
              >
                {sit === 'pausada' ? 'Retomar' : 'Pausar'}
              </button>
              <button
                className={s.acao}
                disabled
                title="Sem tabela nem rota para o registro humano de avaliação da operação."
              >
                Avaliações
              </button>
            </div>

            {/*
              A faixa de lacuna é por cartão, e não um aviso global, porque é
              sobre ESTA operação que a pessoa quer agir agora.
            */}
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
                  <strong>Pausar e Avaliações ainda não existem no servidor.</strong> Pausar
                  exige uma rota que aceite mudança de status; Avaliações exige onde
                  guardar o julgamento humano. Os dois estão registrados como pedidos ao
                  backend.
                </span>
              </div>
            )}
          </div>
        )
      })}

      <div className={s.rodape}>
        <span style={{ flex: 1 }}>
          Pausar não apagaria nada: a operação sairia do edge no próximo heartbeat e
          voltaria igual. Excluir é pelo nome, na ficha — nunca no fluxo do dia.
        </span>
        <span style={{ flex: 1 }}>
          Avaliação é o registro humano de "esta operação está detectando bem?" — alimenta
          o ajuste de zona e o retreino.
        </span>
      </div>
    </div>
  )
}
