/**
 * AlertDetailPage — /epi/alerts/:alertId. O deep-link do evento: LEVA AO ACONTECIDO.
 *
 * Mostra o FRAME INTEIRO da evidência com a bbox no LUGAR EXATO (projetada do
 * `bbox` em PIXELS do frame original que o edge gravou), a câmera, a hora REAL de captura
 * (`alerts.timestamp`, que nenhuma outra tela usava) e classe + confiança de
 * cada violação. Substitui o modal sem URL cuja caixa era hardcoded.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../../services/api'
import { vars } from '../../styles/theme.css'
import { labelForClass } from '../../utils/labels'
import { Button } from '../../components/ui/Button/Button'
import { LoadingSpinner } from '../../components/shared/LoadingSpinner'
import { ProcedenciaBadge } from '../../components/shared/ProcedenciaBadge'
import { page, pageHeader, pageTitle, emptyBox } from '../AlertsHistoryPage.css'
import {
  proximoEstado, LUPA_INICIAL, ESCALA_MIN, ESCALA_MAX,
  distanciaEntre, type EventoLupa, type Palco,
} from './lupaEvidencia'

type Bbox = [number, number, number, number]
interface Violation { class: string; confidence: number; bbox?: Bbox; bbox_unidade?: string }

/** Única unidade de bbox que esta tela sabe projetar (contrato de domain/detectors/base.py). */
export const BBOX_PIXELS = 'pixels_xywh_frame_original'
/** Última correção de caixa registrada no ledger append-only do alerta. */
interface Correcao { por: string | null; em: string | null }
/** Vocabulário do wire = o mesmo que a IA grava (comparabilidade). A tela traduz. */
type Verdict = 'approve' | 'reject'

interface AlertDetail {
  id: string
  camera_id: string | null
  camera_name?: string | null
  violations: Violation[]
  acknowledged: boolean
  captured_at: string | null
  created_at?: string | null
  evidence_url: string | null
  evidence_key?: string | null
  verification_verdict?: string | null
  verified_at?: string | null
  correcao_ultima?: Correcao | null
}

/** Arrasto menor que isto (em pixels do frame) é clique acidental, não caixa. */
const ARRASTO_MINIMO_PX = 4

/**
 * bbox = [x, y, w, h] em PIXELS do frame ORIGINAL (canto superior-esquerdo, NÃO centro)
 * → caixa em % sobre a <img>. O alerta não carrega width/height do frame, então as
 * dimensões vêm da própria imagem carregada (naturalWidth/naturalHeight).
 * Exportada para teste: é a única lógica não-trivial da tela.
 */
export function boxStyle([x, y, w, h]: Bbox, natW: number, natH: number) {
  // toFixed(4) só apara o ruído binário; 4 casas em % é sub-pixel em qualquer frame.
  const pct = (n: number, total: number) => `${+((n / total) * 100).toFixed(4)}%`
  return {
    left: pct(x, natW),
    top: pct(y, natH),
    width: pct(w, natW),
    height: pct(h, natH),
  }
}

export function AlertDetailPage() {
  const { alertId } = useParams<{ alertId: string }>()
  const navigate = useNavigate()
  const [alert, setAlert] = useState<AlertDetail | null>(null)
  const [loading, setLoading] = useState(true)
  // Dimensões do frame ORIGINAL: só existem depois que a <img> carrega.
  const [natural, setNatural] = useState<{ w: number; h: number } | null>(null)

  // ── revisão: veredito + correção de caixa ───────────────────────────────
  const imgRef = useRef<HTMLImageElement>(null)
  const [selecionada, setSelecionada] = useState<number | null>(null)
  const [rascunho, setRascunho] = useState<Bbox | null>(null)
  const inicioArrasto = useRef<{ x: number; y: number } | null>(null)
  const [salvando, setSalvando] = useState(false)
  const [erroAcao, setErroAcao] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    setLoading(true)
    setSelecionada(null)
    setRascunho(null)
    // Frame novo = dimensões novas; sem isto a caixa do próximo alerta cairia
    // projetada nas dimensões do frame anterior até a <img> carregar.
    setNatural(null)
    api.get<{ data?: { alert: AlertDetail } }>(`/alerts/${alertId}`)
      .then(res => { if (alive) setAlert(res.data?.alert ?? null) })
      .catch(() => { if (alive) setAlert(null) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [alertId])

  const recarregar = useCallback(
    () => api.get<{ data?: { alert: AlertDetail } }>(`/alerts/${alertId}`)
      .then(res => setAlert(res.data?.alert ?? null))
      .catch(() => { /* a tela já mostra o estado anterior */ }),
    [alertId],
  )

  /**
   * Veredito humano — POST /verification/:id/review. NÃO toca /acknowledge:
   * reconhecer é ciência do operador, veredito é verdade sobre a detecção.
   */
  const darVeredito = async (verdict: Verdict) => {
    setSalvando(true)
    setErroAcao(null)
    try {
      await api.post(`/verification/${alertId}/review`, { verdict })
      await recarregar()
    } catch {
      setErroAcao('Não foi possível registrar o veredito.')
    } finally {
      setSalvando(false)
    }
  }

  /**
   * Ponto do cursor → PIXELS do frame ORIGINAL.
   *
   * O rect vem da <img>, não de `natural` nem do palco: a imagem é exibida a
   * width:100% E dentro da camada com `transform` da lupa — só o rect medido
   * reflete escala e pan. Trocar por naturalWidth grava caixa deslocada, e o
   * erro é SILENCIOSO (fica bonito na tela em que foi desenhada).
   */
  const pontoNoFrame = (clientX: number, clientY: number) => {
    const img = imgRef.current
    if (!img || !natural) return null
    const r = img.getBoundingClientRect()
    if (!r.width || !r.height) return null
    const limitar = (n: number, max: number) => Math.min(Math.max(n, 0), max)
    return {
      x: limitar(((clientX - r.left) / r.width) * natural.w, natural.w),
      y: limitar(((clientY - r.top) / r.height) * natural.h, natural.h),
    }
  }

  const retangulo = (a: { x: number; y: number }, b: { x: number; y: number }): Bbox => [
    Math.round(Math.min(a.x, b.x)), Math.round(Math.min(a.y, b.y)),
    Math.round(Math.abs(b.x - a.x)), Math.round(Math.abs(b.y - a.y)),
  ]

  const bboxDe = (i: number | null): Bbox | null =>
    (i === null ? null : alert?.violations[i]?.bbox ?? null)

  const iniciarCorrecao = (i: number) => {
    setSelecionada(i)
    setRascunho(bboxDe(i))
    setErroAcao(null)
  }

  const cancelarCorrecao = () => { setSelecionada(null); setRascunho(null) }

  const salvarCaixa = async () => {
    if (selecionada === null || !rascunho) return
    setSalvando(true)
    setErroAcao(null)
    try {
      const res = await api.patch<{ data?: { violations: Violation[]; correcao_ultima: Correcao | null } }>(
        `/alerts/${alertId}/violations`,
        { correcoes: [{ index: selecionada, bbox: rascunho }] },
      )
      const d = res.data
      if (d) {
        setAlert(a => (a ? { ...a, violations: d.violations, correcao_ultima: d.correcao_ultima } : a))
      }
      cancelarCorrecao()
    } catch {
      setErroAcao('Não foi possível salvar a caixa.')
    } finally {
      setSalvando(false)
    }
  }

  // Enquanto uma violação está selecionada o arrasto DESENHA em vez de deslocar
  // (mesma superfície, dois gestos — o modo decide qual).
  const corrigindo = selecionada !== null

  // ── lupa ────────────────────────────────────────────────────────────────
  // A evidência é uma caixa de orelha num frame 1920x1080: sem ampliar, o dono
  // não consegue julgar. Zoom/pan vivem numa ÚNICA camada transformada que
  // envolve a <img> E as caixas — por isso a caixa escala/translada junto,
  // ancorada nos mesmos pixels, sem tocar em boxStyle(). Tirar as caixas de
  // dentro dessa camada dessincroniza a marcação em silêncio.
  const stageRef = useRef<HTMLDivElement>(null)
  const [lupa, setLupa] = useState(LUPA_INICIAL)
  // O listener de wheel é registrado uma vez (precisa ser não-passivo); o ref
  // dá a ele o estado atual sem re-registrar.
  const lupaRef = useRef(lupa)
  lupaRef.current = lupa
  const ponteiros = useRef(new Map<number, { x: number; y: number }>())
  const distPinca = useRef(0)

  // Frame novo = enquadramento novo.
  useEffect(() => { setLupa(LUPA_INICIAL) }, [alertId])

  const medir = useCallback((): { rect: DOMRect; palco: Palco } | null => {
    const el = stageRef.current
    if (!el) return null
    const rect = el.getBoundingClientRect()
    return { rect, palco: { largura: rect.width, altura: rect.height } }
  }, [])

  const despachar = useCallback((evento: EventoLupa, palco: Palco) => {
    setLupa(prev => proximoEstado(prev, evento, palco))
  }, [])

  // Âncora relativa ao CENTRO do palco (transform-origin: center).
  const ancorar = (rect: DOMRect, clientX: number, clientY: number) => ({
    ancoraX: clientX - (rect.left + rect.width / 2),
    ancoraY: clientY - (rect.top + rect.height / 2),
  })

  const evidenceUrl = alert?.evidence_url
  useEffect(() => {
    const el = stageRef.current
    if (!el) return
    const onWheel = (ev: WheelEvent) => {
      // Já no piso e afastando: NÃO sequestra a roda — a página rola normal.
      if (lupaRef.current.escala === ESCALA_MIN && ev.deltaY > 0) return
      ev.preventDefault()   // exige passive:false; o onWheel do React é passivo.
      const m = medir()
      if (!m) return
      despachar({
        tipo: 'zoom', fator: ev.deltaY < 0 ? 1.15 : 1 / 1.15,
        ...ancorar(m.rect, ev.clientX, ev.clientY),
      }, m.palco)
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [despachar, medir, evidenceUrl])

  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (corrigindo) {
      inicioArrasto.current = pontoNoFrame(e.clientX, e.clientY)
      return
    }
    ponteiros.current.set(e.pointerId, { x: e.clientX, y: e.clientY })
    if (ponteiros.current.size === 2) {
      distPinca.current = distanciaEntre([...ponteiros.current.values()])
    }
    e.currentTarget.setPointerCapture(e.pointerId)
  }

  const onPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (corrigindo) {
      const inicio = inicioArrasto.current
      const atual = inicio && pontoNoFrame(e.clientX, e.clientY)
      if (inicio && atual) setRascunho(retangulo(inicio, atual))
      return
    }
    const anterior = ponteiros.current.get(e.pointerId)
    if (!anterior) return
    ponteiros.current.set(e.pointerId, { x: e.clientX, y: e.clientY })
    const m = medir()
    if (!m) return
    const pontos = [...ponteiros.current.values()]
    if (pontos.length >= 2) {
      // Pinça: fator = variação da distância, âncora no ponto médio.
      const nova = distanciaEntre(pontos)
      if (distPinca.current > 0 && nova > 0) {
        const meio = {
          x: (pontos[0].x + pontos[1].x) / 2,
          y: (pontos[0].y + pontos[1].y) / 2,
        }
        despachar({
          tipo: 'zoom', fator: nova / distPinca.current,
          ...ancorar(m.rect, meio.x, meio.y),
        }, m.palco)
      }
      distPinca.current = nova
      return
    }
    // Em escala 1 o limite de pan é 0: arrastar já é inócuo, sem guarda extra.
    despachar({ tipo: 'arrastar', dx: e.clientX - anterior.x, dy: e.clientY - anterior.y }, m.palco)
  }

  const encerrarPonteiro = (e: React.PointerEvent<HTMLDivElement>) => {
    if (corrigindo) {
      const inicio = inicioArrasto.current
      const fim = inicio && pontoNoFrame(e.clientX, e.clientY)
      inicioArrasto.current = null
      if (!inicio || !fim) return
      const [, , w, h] = retangulo(inicio, fim)
      // Arrasto minúsculo é clique acidental: volta à caixa gravada em vez de
      // deixar um retângulo degenerado pronto para ser salvo.
      setRascunho(w < ARRASTO_MINIMO_PX || h < ARRASTO_MINIMO_PX
        ? bboxDe(selecionada)
        : retangulo(inicio, fim))
      return
    }
    ponteiros.current.delete(e.pointerId)
    distPinca.current = 0
  }

  const onDoubleClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const m = medir()
    if (!m) return
    if (lupaRef.current.escala >= ESCALA_MAX) { despachar({ tipo: 'reset' }, m.palco); return }
    despachar({ tipo: 'zoom', fator: 2, ...ancorar(m.rect, e.clientX, e.clientY) }, m.palco)
  }

  // Teclado: zoom só na roda é inutilizável sem mouse. Não é enfeite.
  const PASSO_TECLA = 40
  const onKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    const m = medir()
    if (!m) return
    const noCentro = { ancoraX: 0, ancoraY: 0 }
    const setas: Record<string, [number, number]> = {
      ArrowLeft: [PASSO_TECLA, 0], ArrowRight: [-PASSO_TECLA, 0],
      ArrowUp: [0, PASSO_TECLA], ArrowDown: [0, -PASSO_TECLA],
    }
    if (e.key === '+' || e.key === '=') despachar({ tipo: 'zoom', fator: 1.5, ...noCentro }, m.palco)
    else if (e.key === '-' || e.key === '_') despachar({ tipo: 'zoom', fator: 1 / 1.5, ...noCentro }, m.palco)
    else if (e.key === '0') despachar({ tipo: 'reset' }, m.palco)
    else if (setas[e.key]) {
      const [dx, dy] = setas[e.key]
      despachar({ tipo: 'arrastar', dx, dy }, m.palco)
    } else return
    e.preventDefault()
  }

  const zoomBotao = (fator: number) => {
    const m = medir()
    if (m) despachar({ tipo: 'zoom', fator, ancoraX: 0, ancoraY: 0 }, m.palco)
  }

  // Só desenha o que sabemos projetar. Unidade ausente/estranha = origem desconhecida:
  // melhor nenhuma caixa que caixa mentirosa.
  const drawable = (alert?.violations ?? []).filter(v => v.bbox && v.bbox_unidade === BBOX_PIXELS)
  const unknownUnit = (alert?.violations ?? []).filter(v => v.bbox && v.bbox_unidade !== BBOX_PIXELS)

  return (
    <div className={page}>
      <div className={pageHeader}>
        <h2 className={pageTitle}>Detalhe do Alerta</h2>
        <Button size="sm" variant="secondary" onClick={() => navigate('/epi/alerts')}>
          Voltar ao histórico
        </Button>
      </div>

      {loading ? <LoadingSpinner /> : !alert ? (
        <div className={emptyBox}>Alerta não encontrado</div>
      ) : (
        <>
          {/* Dois ESTADOS SEPARADOS, de propósito: "Reconhecido" é ciência do
              operador; "Veredito" é verdade sobre a detecção. A tela os
              mostrava fundidos num único botão "Reconhecer" — e o veredito
              nunca era gravado. */}
          <div style={{
            marginBottom: '16px', padding: '12px', borderRadius: '8px',
            border: `1px solid ${vars.color.borderDefault}`,
            background: vars.color.bgElevated,
            color: vars.color.textPrimary, fontSize: '14px',
          }}>
            <div>
              <strong style={{ color: vars.color.textMuted }}>Reconhecimento:</strong>{' '}
              {alert.acknowledged ? 'Reconhecido' : 'Pendente'}
            </div>
            <div style={{ marginTop: '4px' }}>
              <strong style={{ color: vars.color.textMuted }}>Veredito:</strong>{' '}
              <span style={{
                color: alert.verification_verdict === 'approve' ? vars.color.success
                  : alert.verification_verdict === 'reject' ? vars.color.warning
                  : vars.color.textMuted,
              }}>
                {alert.verification_verdict === 'approve' ? 'Procedente'
                  : alert.verification_verdict === 'reject' ? 'Falso positivo'
                  : 'Sem veredito'}
              </span>
              {alert.verified_at && ` · ${new Date(alert.verified_at).toLocaleString('pt-BR')}`}
            </div>
            <p style={{ color: vars.color.textMuted, fontSize: '13px', marginTop: '8px' }}>
              Veredito é sobre a DETECÇÃO: ela é procedente ou o modelo errou. Não
              confundir com <strong>Reconhecer</strong>, que só registra que alguém
              viu o alerta.
            </p>
            <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
              <Button size="sm" onClick={() => darVeredito('approve')} disabled={salvando}>
                Confirmar (procedente)
              </Button>
              <Button size="sm" variant="secondary" onClick={() => darVeredito('reject')}
                      disabled={salvando}>
                Errado (falso positivo)
              </Button>
            </div>
          </div>

          {alert.evidence_url ? (
            <>
            <div
              ref={stageRef}
              tabIndex={0}
              role="group"
              aria-label="Frame da evidência. Roda do mouse ou + e − para ampliar, setas para deslocar, 0 para voltar ao enquadramento inteiro."
              onPointerDown={onPointerDown}
              onPointerMove={onPointerMove}
              onPointerUp={encerrarPonteiro}
              onPointerCancel={encerrarPonteiro}
              onDoubleClick={onDoubleClick}
              onKeyDown={onKeyDown}
              style={{
                position: 'relative', display: 'inline-block', maxWidth: '960px',
                width: '100%', borderRadius: '8px', overflow: 'hidden',
                border: `1px solid ${vars.color.borderDefault}`,
                touchAction: 'none',    // sem isto o navegador rouba a pinça
                userSelect: 'none',
                cursor: lupa.escala > ESCALA_MIN ? 'grab' : 'zoom-in',
              }}>
              {/* CAMADA TRANSFORMADA: <img> e caixas juntas — é o que mantém a
                  marcação colada nos mesmos pixels em qualquer zoom. */}
              <div style={{
                transform: `translate(${lupa.x}px, ${lupa.y}px) scale(${lupa.escala})`,
                transformOrigin: 'center',   // a âncora de lupaEvidencia.ts assume isto
                willChange: 'transform',
              }}>
              <img ref={imgRef} src={alert.evidence_url} alt="Frame da evidência"
                   draggable={false}       // o drag nativo da imagem atropela o pan
                   style={{ width: '100%', display: 'block' }}
                   onLoad={e => {
                     const img = e.currentTarget
                     if (img.naturalWidth > 0 && img.naturalHeight > 0) {
                       setNatural({ w: img.naturalWidth, h: img.naturalHeight })
                     }
                   }} />
              {natural && drawable.map((v, i) => (
                <div key={i} data-testid="violation-box"
                     style={{
                       position: 'absolute', ...boxStyle(v.bbox as Bbox, natural.w, natural.h),
                       // contra-escala: a 8x uma borda de 3px come a evidência
                       border: `${3 / lupa.escala}px solid ${vars.color.danger}`,
                       borderRadius: `${4 / lupa.escala}px`,
                       pointerEvents: 'none',
                     }}>
                  <span style={{
                    position: 'absolute', bottom: '100%', left: 0,
                    transformOrigin: '0 100%',            // fixa no canto da caixa
                    transform: `scale(${1 / lupa.escala})`,
                    background: vars.color.danger, color: vars.color.textOnPrimary,
                    fontSize: '11px', padding: '2px 6px', borderRadius: '3px',
                    whiteSpace: 'nowrap',
                  }}>
                    {labelForClass(v.class)} — {(v.confidence * 100).toFixed(0)}%
                  </span>
                </div>
              ))}
              {/* Rascunho da correção, tracejado sobre a caixa gravada. Dentro
                  da MESMA camada transformada — senão descola no zoom. */}
              {natural && corrigindo && rascunho && (
                <div data-testid="rascunho-box"
                     style={{
                       position: 'absolute', ...boxStyle(rascunho, natural.w, natural.h),
                       border: `${3 / lupa.escala}px dashed ${vars.color.warning}`,
                       pointerEvents: 'none',
                     }} />
              )}
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '8px' }}>
              <Button size="sm" variant="secondary" onClick={() => zoomBotao(1.5)}
                      disabled={lupa.escala >= ESCALA_MAX} aria-label="Ampliar">+</Button>
              <Button size="sm" variant="secondary" onClick={() => zoomBotao(1 / 1.5)}
                      disabled={lupa.escala <= ESCALA_MIN} aria-label="Reduzir">−</Button>
              <Button size="sm" variant="secondary"
                      onClick={() => { const m = medir(); if (m) despachar({ tipo: 'reset' }, m.palco) }}
                      disabled={lupa.escala === ESCALA_MIN}>Frame inteiro</Button>
              <span style={{ color: vars.color.textMuted, fontSize: '12px' }}>
                {lupa.escala.toFixed(1).replace('.', ',')}× · roda amplia, arrastar desloca, 2 cliques aproximam
              </span>
            </div>
            </>
          ) : (
            <div className={emptyBox}>Sem imagem de evidência para este evento</div>
          )}

          {alert.evidence_url && alert.violations.every(v => !v.bbox) && (
            <p style={{ color: vars.color.warning, fontSize: '13px', marginTop: '8px' }}>
              Evento sem coordenadas gravadas — frame exibido sem marcação.
            </p>
          )}

          {alert.evidence_url && unknownUnit.length > 0 && (
            <p style={{ color: vars.color.warning, fontSize: '13px', marginTop: '8px' }}>
              Coordenadas de origem desconhecida — caixa não desenhada para{' '}
              {unknownUnit.length === 1 ? '1 violação' : `${unknownUnit.length} violações`}.
            </p>
          )}

          <div style={{
            display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px',
            marginTop: '16px', color: vars.color.textPrimary, fontSize: '14px',
          }}>
            <div>
              <strong style={{ color: vars.color.textMuted }}>Câmera:</strong>{' '}
              {alert.camera_name ?? '—'}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span>
                <strong style={{ color: vars.color.textMuted }}>Captura:</strong>{' '}
                {alert.captured_at ? new Date(alert.captured_at).toLocaleString('pt-BR') : '—'}
              </span>
              {/* A tela do ACONTECIDO é justamente onde a distância entre a
                  captura e a gravação precisa aparecer: sem isto o detalhe
                  mostra uma hora antiga sem dizer que o evento é de coleta
                  retroativa. Mesmo componente do histórico e do dashboard. */}
              <ProcedenciaBadge
                capturadoEm={alert.captured_at}
                gravadoEm={alert.created_at}
              />
            </div>
          </div>

          <ul style={{
            marginTop: '12px', paddingLeft: '18px',
            color: vars.color.textPrimary, fontSize: '14px',
          }}>
            {alert.violations.map((v, i) => (
              <li key={i} style={{ marginBottom: '4px' }}>
                {labelForClass(v.class)} — {(v.confidence * 100).toFixed(0)}%{' '}
                {alert.evidence_url && (
                  <Button size="sm" variant="secondary" onClick={() => iniciarCorrecao(i)}
                          disabled={selecionada === i}>
                    {selecionada === i ? 'Corrigindo caixa' : 'Corrigir caixa'}
                  </Button>
                )}
              </li>
            ))}
          </ul>

          {corrigindo && (
            <div style={{
              marginTop: '12px', padding: '12px', borderRadius: '8px',
              border: `1px solid ${vars.color.borderDefault}`,
              background: vars.color.bgElevated,
              color: vars.color.textPrimary, fontSize: '14px',
            }}>
              <p style={{ color: vars.color.textMuted, fontSize: '13px', margin: 0 }}>
                Arraste sobre o frame para redesenhar a caixa — ou digite as
                coordenadas, em pixels do frame original.
              </p>
              {/* Caminho de TECLADO: quem não arrasta, digita. Mesmo `rascunho`. */}
              <div style={{ display: 'flex', gap: '8px', marginTop: '8px', flexWrap: 'wrap' }}>
                {(['x', 'y', 'largura', 'altura'] as const).map((rotulo, eixo) => (
                  <label key={rotulo} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <span style={{ color: vars.color.textMuted, fontSize: '13px' }}>{rotulo}</span>
                    <input type="number" min={0} style={{ width: '86px' }}
                           value={rascunho ? rascunho[eixo] : ''}
                           onChange={e => {
                             const n = Math.round(Number(e.target.value))
                             if (!Number.isFinite(n)) return
                             const base: Bbox = rascunho ?? [0, 0, 0, 0]
                             const nova: Bbox = [base[0], base[1], base[2], base[3]]
                             nova[eixo] = Math.max(0, n)
                             setRascunho(nova)
                           }} />
                  </label>
                ))}
              </div>
              <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
                <Button size="sm" onClick={salvarCaixa}
                        disabled={salvando || !rascunho || rascunho[2] <= 0 || rascunho[3] <= 0}>
                  Salvar caixa
                </Button>
                <Button size="sm" variant="secondary" onClick={cancelarCorrecao} disabled={salvando}>
                  Cancelar
                </Button>
              </div>
            </div>
          )}

          {alert.correcao_ultima && (
            <p style={{ color: vars.color.textMuted, fontSize: '13px', marginTop: '8px' }}>
              Caixa corrigida por {alert.correcao_ultima.por ?? '—'}
              {alert.correcao_ultima.em
                ? ` em ${new Date(alert.correcao_ultima.em).toLocaleString('pt-BR')}`
                : ''}.
            </p>
          )}

          {erroAcao && (
            <p role="alert" style={{ color: vars.color.danger, fontSize: '13px', marginTop: '8px' }}>
              {erroAcao}
            </p>
          )}
        </>
      )}
    </div>
  )
}

export default AlertDetailPage
