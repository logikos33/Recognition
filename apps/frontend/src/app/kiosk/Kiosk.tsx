/**
 * Kiosk — `/novo/tablet/:station`, o tablet de bancada do Quality Gate na
 * identidade Logikos Vision (F5 SR3). Referência de desenho:
 * `docs/design/handoff-f5/Kiosk RVB.dc.html`.
 *
 * A máquina de estados é EXATAMENTE a de `TabletKiosk`
 * (modules/quality/tablet) — mesmo hook (`useTabletWebSocket`), mesma
 * decisão de vista a partir do status da peça. Só a pele muda: este arquivo
 * não importa nenhum componente visual do kiosk antigo, só o hook de dados
 * e os tipos do gate. A rota antiga `/tablet/:station` (AppRoutes.tsx)
 * continua servindo o kiosk de produção da RVB, intocada.
 *
 * Zero jargão de ML na tela: nada de "confiança", "detecção", "inferência" —
 * o operador vê peça, defeito e ação, não o motor por trás.
 */
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { ArrowRight, Check, Clock, Loader2, Scan, Trophy, Wrench, X } from 'lucide-react'

import { useTabletWebSocket } from '../../modules/quality/tablet/useTabletWebSocket'
import { api, API_BASE } from '../../services/api'
import type { InspectionResultEvent, QualityPiece } from '../../modules/quality/types/gate'
import { lk } from '../tokens/lk.css'
import * as s from './Kiosk.css'

/** As mesmas 7 vistas de `TabletKiosk` — só o nome muda para português. */
type Vista =
  | 'ociosa'
  | 'identificada'
  | 'validando'
  | 'conforme'
  | 'reprovada'
  | 'transicao'
  | 'aprovada'

export function Kiosk() {
  // station vem da URL: /novo/tablet/bench_a ou /novo/tablet/bench-a (ambos aceitos)
  const { station: estacaoBruta = 'bench_a' } = useParams<{ station: string }>()
  const estacao = estacaoBruta.replace('-', '_')

  const { stationState, lastResult, lastIdentified, clearResult } = useTabletWebSocket(estacao)

  const [vista, setVista] = useState<Vista>('ociosa')
  const [peca, setPeca] = useState<QualityPiece | null>(null)

  // Sincroniza a vista com o estado da bancada — mapeamento idêntico ao de
  // `TabletKiosk`, só com nomes de tela em português.
  useEffect(() => {
    if (!stationState) return
    const p = stationState.current_piece
    setPeca(p)

    if (!p) {
      setVista('ociosa')
      return
    }

    const st = p.status
    if (st === 'idle') setVista('ociosa')
    else if (st === 'identified') setVista('identificada')
    else if (st === 'validating_v1' || st === 'validating_v2' || st === 'validating_v3')
      setVista('validando')
    else if (st === 'waiting_bench_b' && estacao === 'bench_a') setVista('transicao')
    else if (st === 'rework_v1' || st === 'rework_v2' || st === 'rework_v3') setVista('reprovada')
    else if (st === 'approved') setVista('aprovada')
    else if (st === 'rejected') setVista('reprovada')
  }, [stationState, estacao])

  // Reage ao resultado de inspeção do worker (ok/nok)
  useEffect(() => {
    if (!lastResult) return
    setVista(lastResult.result === 'ok' ? 'conforme' : 'reprovada')
  }, [lastResult])

  // lastIdentified: peça nova identificada — muda vista independente de stationState
  useEffect(() => {
    if (!lastIdentified) return
    setVista('identificada')
  }, [lastIdentified])

  return (
    <div className={s.raiz}>
      {vista === 'ociosa' && <TelaOciosa estacao={estacao} />}
      {vista === 'identificada' && <TelaIdentificada peca={peca} estacao={estacao} />}
      {vista === 'validando' && <TelaValidando peca={peca} />}
      {vista === 'conforme' && (
        <TelaConforme
          peca={peca}
          resultado={lastResult}
          onAvancar={() => {
            clearResult()
            setVista('validando')
          }}
        />
      )}
      {vista === 'reprovada' && (
        <TelaReprovada
          peca={peca}
          resultado={lastResult}
          estacao={estacao}
          onCorrigido={() => setVista('validando')}
        />
      )}
      {vista === 'transicao' && <TelaTransicao peca={peca} />}
      {vista === 'aprovada' && <TelaAprovada peca={peca} />}
    </div>
  )
}

// ── K1 — ociosa ──────────────────────────────────────────────────────────────

function TelaOciosa({ estacao }: { estacao: string }) {
  const nome = estacao === 'bench_a' ? 'BANCADA A' : 'BANCADA B'
  const escopo = estacao === 'bench_a' ? 'V1 e V2' : 'V3'
  return (
    <div className={s.tela.neutra}>
      <Clock size={80} strokeWidth={1.5} style={{ opacity: 0.7 }} aria-hidden />
      <div className={s.tituloEstacao}>{nome}</div>
      <div className={s.subtitulo}>Aguardando peça · {escopo}</div>
      <div className={s.rodape}>RECOGNITION · QUALITY GATE</div>
    </div>
  )
}

// ── K2 — identificada ────────────────────────────────────────────────────────

function TelaIdentificada({ peca, estacao }: { peca: QualityPiece | null; estacao: string }) {
  const [carregando, setCarregando] = useState(false)

  // Dispara inspeção — o backend emite quality_gate_result via WebSocket
  const iniciar = async () => {
    if (!peca || carregando) return
    setCarregando(true)
    try {
      await api.post(`/v1/quality/gate/pieces/${peca.id}/inspect`, { station: estacao })
    } catch (e) {
      console.error('kiosk:inspect_error', e)
    } finally {
      setCarregando(false)
    }
  }

  return (
    <div className={s.tela.neutra}>
      <PassosValidacao status={peca?.status} />
      <div className={s.overline}>Peça identificada</div>
      <div className={s.codigoPeca}>{peca?.piece_number ?? '—'}</div>
      {peca?.work_order && <div className={s.subtitulo}>OP {peca.work_order}</div>}
      <button className={s.botao.primario} onClick={iniciar} disabled={carregando}>
        <Scan size={22} aria-hidden />
        {carregando ? 'INICIANDO…' : 'INICIAR INSPEÇÃO'}
      </button>
    </div>
  )
}

/** Progresso V1 → V2 → V3 — mesma lógica do kiosk antigo, só a pele muda. */
function PassosValidacao({ status }: { status?: string }) {
  const aprovado = status === 'approved'
  const emOuApos = (marcos: string[]) => aprovado || (status !== undefined && marcos.includes(status))

  const passos = [
    { rotulo: 'V1', ativo: emOuApos(['validating_v1', 'rework_v1', 'validating_v2', 'rework_v2', 'waiting_bench_b', 'validating_v3', 'rework_v3']) },
    { rotulo: 'V2', ativo: emOuApos(['validating_v2', 'rework_v2', 'waiting_bench_b', 'validating_v3', 'rework_v3']) },
    { rotulo: 'V3', ativo: emOuApos(['validating_v3', 'rework_v3']) },
  ]

  return (
    <div className={s.passos}>
      {passos.map((p, i) => (
        <div key={p.rotulo} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div className={s.passoCirculo[aprovado ? 'aprovado' : p.ativo ? 'ativo' : 'inativo']}>
            {p.rotulo}
          </div>
          {i < passos.length - 1 && <div className={s.passoConector} />}
        </div>
      ))}
    </div>
  )
}

// ── K3 — validando ───────────────────────────────────────────────────────────

const ROTULO_VALIDACAO: Record<string, string> = {
  validating_v1: 'V1 — fio alinhado no anel',
  validating_v2: 'V2 — saída isolada',
  validating_v3: 'V3 — anel encapado',
}

function TelaValidando({ peca }: { peca: QualityPiece | null }) {
  const rotulo = ROTULO_VALIDACAO[peca?.status ?? ''] ?? 'Analisando…'
  return (
    <div className={s.tela.neutra}>
      <Loader2 size={72} className={s.spinner} style={{ color: lk.cor.cianoVisao }} aria-hidden />
      <div className={s.tituloMedio}>Validando</div>
      <div className={s.subtitulo}>{rotulo}</div>
      {peca && <div className={s.codigoNota}>Peça {peca.piece_number}</div>}
    </div>
  )
}

// ── K4 — conforme (uma validação aprovada) ──────────────────────────────────

function TelaConforme({
  peca,
  resultado,
  onAvancar,
}: {
  peca: QualityPiece | null
  resultado: InspectionResultEvent | null
  /** Chamado após 3s — volta para TelaValidando esperando a próxima inspeção */
  onAvancar: () => void
}) {
  useEffect(() => {
    const t = setTimeout(onAvancar, 3000)
    return () => clearTimeout(t)
  }, [onAvancar])

  return (
    <div className={s.tela.aprovada}>
      <Check size={110} strokeWidth={2.5} aria-hidden />
      <div className={s.veredito}>CONFORME</div>
      {resultado?.validation_type && (
        <div className={s.subtitulo}>{resultado.validation_type.toUpperCase()} aprovado</div>
      )}
      {peca && <div className={s.codigoPeca}>{peca.piece_number}</div>}
    </div>
  )
}

// ── K5/K6 — reprovada ────────────────────────────────────────────────────────

function TelaReprovada({
  peca,
  resultado,
  estacao,
  onCorrigido,
}: {
  peca: QualityPiece | null
  resultado: InspectionResultEvent | null
  estacao: string
  /** Chamado após iniciar retrabalho — volta para TelaValidando */
  onCorrigido: () => void
}) {
  // null = nenhuma ação em andamento, 'rework' | 'fp' = botão ativo
  const [carregando, setCarregando] = useState<string | null>(null)

  // Inicia retrabalho e notifica o kiosk
  const corrigir = async () => {
    if (!peca || carregando) return
    setCarregando('rework')
    try {
      await api.post('/v1/quality/gate/reworks', {
        piece_id: peca.id,
        validation_type: resultado?.validation_type,
        station: estacao,
      })
      onCorrigido()
    } catch (e) {
      console.error('kiosk:rework_error', e)
    } finally {
      setCarregando(null)
    }
  }

  // Marca resultado como falso positivo — operador descartou a detecção
  const discordar = async () => {
    if (!peca || !resultado || carregando) return
    setCarregando('fp')
    try {
      await api.post(`/v1/quality/gate/pieces/${peca.id}/false-positive`, {
        inspection_id: resultado.camera_id,
      })
    } catch (e) {
      console.error('kiosk:false_positive_error', e)
    } finally {
      setCarregando(null)
    }
  }

  // API_BASE já inclui o prefixo /api — usar apenas o path a partir de /v1/
  const fotoUrl = resultado?.photo_path
    ? `${API_BASE}/v1/quality/gate/photos/${encodeURIComponent(resultado.photo_path)}`
    : null
  const defeito = resultado?.detections?.find((d) => d.is_defect) ?? resultado?.detections?.[0]

  return (
    <div className={s.telaComFaixa}>
      <div className={s.faixaEstado}>
        <X size={40} strokeWidth={2.5} aria-hidden />
        <span className={s.veredito}>NÃO CONFORME</span>
      </div>
      <div className={s.corpoFaixa}>
        {peca && <div className={s.overline}>Peça {peca.piece_number}</div>}
        {fotoUrl && <img src={fotoUrl} alt="Foto do defeito identificado" className={s.foto} />}
        {defeito && <div className={s.subtitulo}>Defeito identificado: {defeito.class}</div>}
        <div className={s.linhaAcoes}>
          <button className={s.botao.perigo} onClick={corrigir} disabled={!!carregando}>
            <Wrench size={20} aria-hidden />
            {carregando === 'rework' ? 'CORRIGINDO…' : 'CORRIGIR'}
          </button>
          <button className={s.botao.contorno} onClick={discordar} disabled={!!carregando}>
            <X size={20} aria-hidden />
            {carregando === 'fp' ? 'ENVIANDO…' : 'DISCORDO — FALSO POSITIVO'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── transição — peça aprovada em A, aguardando ida para B ──────────────────

function TelaTransicao({ peca }: { peca: QualityPiece | null }) {
  const [carregando, setCarregando] = useState(false)

  // Libera a peça para a Bancada B — backend atualiza status e emite station_state
  const confirmar = async () => {
    if (!peca || carregando) return
    setCarregando(true)
    try {
      await api.post(`/v1/quality/gate/pieces/${peca.id}/release-to-bench-b`)
    } catch (e) {
      console.error('kiosk:release_error', e)
    } finally {
      setCarregando(false)
    }
  }

  return (
    <div className={s.tela.neutra}>
      <ArrowRight size={72} style={{ color: lk.cor.cianoVisao }} aria-hidden />
      <div className={s.tituloMedio}>V1 e V2 aprovadas</div>
      <div className={s.subtitulo}>Leve a peça para a Bancada B</div>
      {peca && <div className={s.codigoPeca}>{peca.piece_number}</div>}
      <button className={s.botao.primario} onClick={confirmar} disabled={carregando}>
        <Check size={22} aria-hidden />
        {carregando ? 'CONFIRMANDO…' : 'CONFIRMAR MOVIMENTAÇÃO'}
      </button>
    </div>
  )
}

// ── K8 — aprovada 3/3 ────────────────────────────────────────────────────────

function TelaAprovada({ peca }: { peca: QualityPiece | null }) {
  const tempoRetrabalho =
    peca?.total_rework_time_seconds && peca.total_rework_time_seconds > 0
      ? `${Math.ceil(peca.total_rework_time_seconds / 60)} min de retrabalho`
      : null

  return (
    <div className={s.tela.aprovada}>
      <Trophy size={96} strokeWidth={2} aria-hidden />
      <div className={s.veredito}>APROVADA 3/3</div>
      <div className={s.subtitulo}>Todas as validações passaram</div>
      {peca && <div className={s.codigoPeca}>{peca.piece_number}</div>}
      {peca?.work_order && <div className={s.subtitulo}>OP {peca.work_order}</div>}
      {(peca?.total_rework_count ?? 0) > 0 && (
        <div className={s.subtitulo}>
          {peca!.total_rework_count} retrabalho(s)
          {tempoRetrabalho ? ` · ${tempoRetrabalho}` : ''}
        </div>
      )}
      <div className={s.overline}>Bipe a próxima peça</div>
    </div>
  )
}
