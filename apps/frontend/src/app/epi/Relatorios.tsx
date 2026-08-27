/**
 * EPI Relatórios — a etapa PROVAR da jornada-mestra.
 *
 * Desenho: `EPI Relatórios.dc.html`. Rota nova: `/epi/relatorios`
 * (de-para do front antigo: `/epi/reports` — `docs/migration/DELTA-PRE-MIGRACAO.md` §3.1).
 *
 * ⚠️ RELATÓRIO É PROVA. Todo número desta tela veio de
 * `GET /api/reports/compliance`. Nenhum é calculado aqui, nenhum é exemplo.
 * O que o backend não serve NÃO aparece — aparece como lacuna declarada.
 *
 * O QUE DO DESENHO NÃO ESTÁ AQUI, e por quê (nada disso é esquecimento):
 *
 * · **Cartão "DIGEST DIÁRIO POR E-MAIL"** (toggle, horário, destinatários,
 *   "o que inclui", prévia). Não existe endpoint: `/api/v1/notifications/channels`
 *   é canal genérico e o próprio contrato do design o marca com "aviso de que o
 *   ENVIO ainda não existe". Um toggle "Ativo" que não persiste e uma lista de
 *   destinatários que não é enviada para lugar nenhum seriam a mentira mais cara
 *   desta tela — o cliente confiaria num e-mail que nunca sai. O handoff coloca
 *   o digest em F5; entra quando o backend servir.
 *
 * · **Checkboxes de "Conteúdo"** (score e tendência / eventos por câmera e
 *   classe / ações corretivas e prazos). Nem `/api/reports/compliance` nem
 *   `/api/alerts/export` aceitam seleção de conteúdo: o PDF e o CSV têm forma
 *   fixa. Checkbox que não muda o arquivo gerado é controle decorativo. No lugar
 *   dela, a tela DIZ o que cada formato traz — que é a informação que a
 *   checkbox tentava dar.
 *
 * · **"2 ações vencidas — Juliana P., Carlos M."** na prévia. Não há endpoint de
 *   ações corretivas em lugar nenhum do contrato (421 entradas conferidas).
 *
 * · **Nome da câmera** no "Top câmera". `compliance_report_service._aggregate`
 *   agrega por `camera_id`; o nome não vem. Mostramos o id em mono — é o dado
 *   que existe.
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { AlertTriangle, CheckCircle2, FileText, Lock } from 'lucide-react'

import { useAuth } from '../../hooks/useAuth'
import { ApiError, api } from '../../services/api'
import { LogikosLoader } from '../shell/LogikosLoader'
import * as s from './Relatorios.css'

// ── Contrato de dados (services/api/app/domain/services/compliance_report_service.py)
export interface ResumoCompliance {
  compliance_rate: number
  total_violations: number
  top_cameras: Array<{ camera_id: string; count: number }>
  trend_by_hour: Array<{ hour: string; count: number }>
}

interface RespostaCompliance {
  summary: ResumoCompliance
  pdf_url: string
  period: { period: string; from: string; to: string }
}

const ROTA_COMPLIANCE = '/reports/compliance'
const ROTA_CSV = '/alerts/export'

type ChavePeriodo = 'sete' | 'trinta' | 'mesFechado' | 'personalizado'
type Formato = 'csv' | 'pdf'
type EstadoExport = 'ocioso' | 'gerando' | 'pronto' | 'falhou'

interface Intervalo { de: Date; ate: Date }

function comecoDoDia(base: Date, menosDias: number): Date {
  const d = new Date(base)
  d.setDate(d.getDate() - menosDias)
  d.setHours(0, 0, 0, 0)
  return d
}

/** Mês civil anterior, fechado: dia 1 00:00 → último dia 23:59:59. */
function mesFechado(agora: Date): Intervalo {
  return {
    de: new Date(agora.getFullYear(), agora.getMonth() - 1, 1, 0, 0, 0, 0),
    ate: new Date(agora.getFullYear(), agora.getMonth(), 0, 23, 59, 59, 999),
  }
}

function intervaloDe(chave: ChavePeriodo, de: string, ate: string, agora: Date): Intervalo {
  if (chave === 'trinta') return { de: comecoDoDia(agora, 30), ate: agora }
  if (chave === 'mesFechado') return mesFechado(agora)
  if (chave === 'personalizado') {
    return { de: new Date(`${de}T00:00:00`), ate: new Date(`${ate}T23:59:59`) }
  }
  return { de: comecoDoDia(agora, 7), ate: agora }
}

const dia = (d: Date) => d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
const iso = (d: Date) => d.toISOString().slice(0, 10)

/** Hora de pico do período — do `trend_by_hour` que a API devolveu, não de estimativa. */
function horaDePico(trend: ResumoCompliance['trend_by_hour']): string | null {
  if (!trend.length) return null
  const topo = trend.reduce((a, b) => (b.count > a.count ? b : a))
  const h = new Date(topo.hour)
  return Number.isNaN(h.getTime()) ? null : `${String(h.getHours()).padStart(2, '0')}h`
}

/** Dispara o download no browser. `revogar` só para blob (object URL). */
function baixar(href: string, nome: string, revogar = false): void {
  const a = document.createElement('a')
  a.href = href
  a.download = nome
  a.rel = 'noopener'
  document.body.appendChild(a)
  a.click()
  a.remove()
  if (revogar) URL.revokeObjectURL(href)
}

function statusDe(err: unknown): string {
  if (err instanceof ApiError) return String(err.status)
  const m = err instanceof Error ? /HTTP (\d{3})/.exec(err.message) : null
  return m ? m[1] : 'falhou'
}

export function Relatorios() {
  const [nomes, setNomes] = useState<Record<string, string>>({})
  useEffect(() => {
    let vivo = true
    api
      .get<{ data?: { cameras?: Array<{ id: string; name: string }> } }>('/cameras')
      .then((r) => {
        const lista = r.data?.cameras ?? []
        if (vivo) setNomes(Object.fromEntries(lista.map((c) => [c.id, c.name])))
      })
      // Falha aqui não derruba o relatório: a linha do topo degrada para
      // "câmera não identificada" e todo o resto do resumo continua de pé.
      .catch(() => undefined)
    return () => {
      vivo = false
    }
  }, [])

  const { can } = useAuth()
  const podeExportar = can('reports:export')

  const [periodo, setPeriodo] = useState<ChavePeriodo>('sete')
  const [formato, setFormato] = useState<Formato>('csv')
  const hoje = useMemo(() => new Date(), [])
  const [de, setDe] = useState(() => iso(comecoDoDia(hoje, 7)))
  const [ate, setAte] = useState(() => iso(hoje))

  const [dados, setDados] = useState<RespostaCompliance | null>(null)
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)
  const [tentativa, setTentativa] = useState(0)

  const [estadoExport, setEstadoExport] = useState<EstadoExport>('ocioso')
  const [erroExport, setErroExport] = useState<string | null>(null)

  const intervalo = useMemo(
    () => intervaloDe(periodo, de, ate, hoje),
    [periodo, de, ate, hoje],
  )

  /** `period` é obrigatório na API e só aceita dia|semana; `from`/`to` mandam. */
  const consulta = useMemo(() => {
    const horas = (intervalo.ate.getTime() - intervalo.de.getTime()) / 36e5
    return new URLSearchParams({
      period: horas <= 24 ? 'dia' : 'semana',
      from: intervalo.de.toISOString(),
      to: intervalo.ate.toISOString(),
    }).toString()
  }, [intervalo])

  const valido = !Number.isNaN(intervalo.de.getTime())
    && !Number.isNaN(intervalo.ate.getTime())
    && intervalo.de <= intervalo.ate

  const buscar = useCallback(async () => {
    const r = await api.get<{ data: RespostaCompliance }>(`${ROTA_COMPLIANCE}?${consulta}`)
    return r.data
  }, [consulta])

  useEffect(() => {
    // Intervalo inválido (data inicial depois da final, digitada à mão): limpa
    // os dados. Manter o resumo anterior sob o rótulo do período NOVO seria
    // exibir número que a API não devolveu PARA AQUELE período — a mentira que
    // esta tela existe para não contar.
    if (!valido) { setCarregando(false); setErro(null); setDados(null); return }
    let vivo = true
    setCarregando(true)
    setErro(null)
    setEstadoExport('ocioso')
    setErroExport(null)
    buscar()
      .then((d) => { if (vivo) setDados(d) })
      .catch((err) => { if (vivo) { setDados(null); setErro(statusDe(err)) } })
      .finally(() => { if (vivo) setCarregando(false) })
    return () => { vivo = false }
  }, [buscar, valido, tentativa])

  const exportar = useCallback(async () => {
    setEstadoExport('gerando')
    setErroExport(null)
    try {
      if (formato === 'pdf') {
        // Refaz a chamada: o `pdf_url` é presignado com TTL de 1h e o backend
        // gera o PDF NESTA chamada — reusar o da carga entregaria link vencido
        // numa aba aberta há mais de uma hora.
        const fresco = await buscar()
        setDados(fresco)
        baixar(fresco.pdf_url, `compliance-${iso(intervalo.de)}.pdf`)
      } else {
        const qs = new URLSearchParams({
          start_date: intervalo.de.toISOString(),
          end_date: intervalo.ate.toISOString(),
        })
        const blob = await api.downloadBlob(`${ROTA_CSV}?${qs}`)
        baixar(URL.createObjectURL(blob), `eventos-${iso(intervalo.de)}.csv`, true)
      }
      setEstadoExport('pronto')
    } catch (err) {
      setEstadoExport('falhou')
      setErroExport(
        `GET /api${formato === 'pdf' ? ROTA_COMPLIANCE : ROTA_CSV} · ${statusDe(err)}`,
      )
    }
  }, [formato, buscar, intervalo])

  const rotuloMesFechado = useMemo(() => {
    const nome = mesFechado(hoje).de.toLocaleDateString('pt-BR', { month: 'long' })
    return `Mês fechado (${nome})`
  }, [hoje])

  // ── Estados de tela: loading · erro · vazio · carregado ────────────────────
  if (carregando) {
    return <LogikosLoader estado="waiting" variante="fullscreen" rotulo="CARREGANDO RELATÓRIOS" />
  }

  if (erro) {
    return (
      <div className={s.centro}>
        <AlertTriangle size={36} strokeWidth={1.5} aria-hidden="true" className={s.aviso.nc} />
        <span className={s.centroTitulo}>Falha ao carregar o relatório</span>
        <span className={s.centroCodigo}>GET /api{ROTA_COMPLIANCE} · {erro}</span>
        <button type="button" className={s.botaoCentro} onClick={() => setTentativa((t) => t + 1)}>
          Tentar novamente
        </button>
      </div>
    )
  }

  if (!valido) {
    return (
      <div className={s.centro}>
        <AlertTriangle size={36} strokeWidth={1.5} aria-hidden="true" className={s.aviso.nc} />
        <span className={s.centroTitulo}>Intervalo inválido</span>
        <span className={s.centroTexto}>
          A data inicial é posterior à final. Corrija o intervalo para gerar o relatório.
        </span>
        <button type="button" className={s.botaoCentro} onClick={() => setPeriodo('sete')}>
          Últimos 7 dias
        </button>
      </div>
    )
  }

  const resumo = dados?.summary
  const vazio = !resumo
    || (resumo.total_violations === 0
      && resumo.top_cameras.length === 0
      && resumo.trend_by_hour.length === 0)

  if (vazio) {
    return (
      <div className={s.centro}>
        <FileText size={36} strokeWidth={1.5} aria-hidden="true" className={s.aviso.neutro} />
        <span className={s.centroTitulo}>Sem dados no período selecionado</span>
        <span className={s.centroTexto}>
          O período selecionado não tem eventos registrados. Amplie o intervalo.
        </span>
        {periodo === 'trinta' ? (
          <button type="button" className={s.botaoCentro} onClick={() => setTentativa((t) => t + 1)}>
            Recarregar
          </button>
        ) : (
          <button type="button" className={s.botaoCentro} onClick={() => setPeriodo('trinta')}>
            Últimos 30 dias
          </button>
        )}
      </div>
    )
  }

  const pico = horaDePico(resumo.trend_by_hour)
  /**
   * O agregado devolve `camera_id`, e só. Mostrar UUID para o operador não é
   * "dado real": é dado que ninguém consegue ler — ele não sabe qual das 29
   * câmeras é `eb1501db-…`. O nome vem da mesma lista de câmeras que a tela de
   * Câmeras usa; enquanto ela não chega, ou se o id não estiver nela, a linha
   * diz isso em vez de despejar o identificador.
   */
  const nomeDaCamera = (id: string) => nomes[id] ?? 'câmera não identificada'

  const topo = resumo.top_cameras[0]
  const janela = `${dia(intervalo.de)} → ${dia(intervalo.ate)}`

  return (
    <div className={s.raiz}>
      <h1 className={s.titulo}>Relatórios</h1>

      <div className={s.colunas}>
        {/* ── Exportar ─────────────────────────────────────────────────── */}
        <section className={s.cartao} aria-labelledby="rel-exportar">
          <span className={s.overline} id="rel-exportar">Exportar relatório</span>

          <div className={s.campo}>
            <label className={s.rotulo} htmlFor="rel-periodo">Período</label>
            <select
              id="rel-periodo"
              className={s.seletor}
              value={periodo}
              onChange={(e) => setPeriodo(e.target.value as ChavePeriodo)}
            >
              <option value="sete">Últimos 7 dias</option>
              <option value="trinta">Últimos 30 dias</option>
              <option value="mesFechado">{rotuloMesFechado}</option>
              <option value="personalizado">Personalizado…</option>
            </select>
          </div>

          {periodo === 'personalizado' && (
            <div className={s.linhaDatas}>
              <div className={s.campo}>
                <label className={s.rotulo} htmlFor="rel-de">De</label>
                <input
                  id="rel-de" type="date" className={s.dataInput}
                  value={de} max={ate} onChange={(e) => setDe(e.target.value)}
                />
              </div>
              <div className={s.campo}>
                <label className={s.rotulo} htmlFor="rel-ate">Até</label>
                <input
                  id="rel-ate" type="date" className={s.dataInput}
                  value={ate} min={de} onChange={(e) => setAte(e.target.value)}
                />
              </div>
            </div>
          )}

          <div className={s.campo}>
            <span className={s.rotulo} id="rel-formato">Formato</span>
            <div className={s.segmentado} role="group" aria-labelledby="rel-formato">
              {(['csv', 'pdf'] as const).map((f) => (
                <button
                  key={f}
                  type="button"
                  aria-pressed={formato === f}
                  className={formato === f ? s.segmento.ativo : s.segmento.inativo}
                  onClick={() => { setFormato(f); setEstadoExport('ocioso'); setErroExport(null) }}
                >
                  {f.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          <div className={s.campo}>
            <span className={s.rotulo}>Conteúdo</span>
            <p className={s.legenda}>
              {formato === 'csv'
                ? 'Uma linha por violação do período: data, câmera, classe, confiança e se foi reconhecida.'
                : 'Taxa de conformidade, total de violações e top câmeras do período, em PDF.'}
            </p>
          </div>

          <button
            type="button"
            className={s.botaoPrimario}
            onClick={exportar}
            disabled={!podeExportar || estadoExport === 'gerando'}
          >
            {estadoExport === 'gerando' && (
              <LogikosLoader estado="waiting" variante="spinner" tamanho={17} />
            )}
            {estadoExport === 'gerando'
              ? 'Gerando…'
              : estadoExport === 'pronto'
                ? 'Exportado · baixar de novo'
                : 'Exportar'}
          </button>

          {!podeExportar && (
            <span className={s.aviso.neutro}>
              <Lock size={15} strokeWidth={1.7} aria-hidden="true" />
              Sem permissão para exportar — seu perfil não tem reports:export.
            </span>
          )}
          {estadoExport === 'pronto' && (
            <span className={s.aviso.ok}>
              <CheckCircle2 size={15} strokeWidth={1.7} aria-hidden="true" />
              Exportado — arquivo do período {janela}.
            </span>
          )}
          {estadoExport === 'falhou' && erroExport && (
            <span className={s.aviso.nc}>
              <AlertTriangle size={15} strokeWidth={1.7} aria-hidden="true" />
              Falha ao gerar o export · {erroExport}
            </span>
          )}
        </section>

        {/* ── Resumo do período — só o que a API devolveu ───────────────── */}
        <section className={s.cartao} aria-labelledby="rel-resumo">
          <span className={s.overline} id="rel-resumo">Resumo do período</span>

          <div className={s.painel}>
            <div className={s.scoreLinha}>
              <span className={s.score}>{Math.round(resumo.compliance_rate)}</span>
              <span className={s.scoreLegenda}>score de conformidade · {janela}</span>
            </div>
            <div className={s.fatos}>
              <span>
                · <span className={s.dado}>{resumo.total_violations}</span> eventos no período
                {pico && <> — pico <span className={s.dado}>{pico}</span></>}
              </span>
              {topo ? (
                <span>
                  · Top câmera: <span className={s.dado}>{nomeDaCamera(topo.camera_id)}</span>{' '}
                  (<span className={s.dado}>{topo.count}</span> eventos)
                </span>
              ) : (
                <span>· Sem concentração por câmera no período</span>
              )}
            </div>
          </div>

        </section>
      </div>
    </div>
  )
}
