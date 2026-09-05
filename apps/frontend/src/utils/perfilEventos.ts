/**
 * perfilEventos — dobra as linhas de `/api/v1/events/profile` nos dois recortes
 * que o painel de EPI mostra: HORA DO DIA e DIA.
 *
 * Por que a dobra é do cliente e não do servidor: o backend agrupa em bucket de
 * hora UTC (mesma convenção de `/events/timeline`); quem sabe o fuso de quem
 * está lendo é o navegador. Dobrar no servidor obrigaria a cravar o fuso do
 * tenant no SQL — e às 22h UTC de um dia é 19h do MESMO dia em Blumenau, mas
 * às 02h UTC já é 23h do dia ANTERIOR. Errar isso move violação de turno.
 *
 * Zero-fill deliberadamente diferente nos dois recortes:
 *  · HORA DO DIA — sempre 24 posições. Uma hora sem evento é informação
 *    ("de madrugada não há ninguém na fábrica"), e uma curva com buraco no
 *    meio não é lida como curva.
 *  · DIA — só entre a PRIMEIRA e a ÚLTIMA captura, nunca a janela pedida.
 *    Zero-fill dos 90 dias pedidos desenharia 86 barras vazias antes do
 *    primeiro registro, o que se lê como "o sistema ficou desligado 3 meses".
 *    Entre a primeira e a última captura, o buraco é real e tem de aparecer:
 *    dia sem registro entre dois dias com registro é um dado de operação.
 */
import type { EventKind, ProfileRow } from '../services/eventsService'

const DAY_MS = 86_400_000

export interface ContagemPorTipo {
  violacao: number
  conformidade: number
  indefinido: number
}

export interface PontoHora {
  /** Hora local do dia, 0–23. */
  hora: number
  total: number
  violacoes: number
}

export interface PontoDia {
  /** Data local em ISO curto, `YYYY-MM-DD` — chave estável, não rótulo. */
  dia: string
  total: number
  violacoes: number
}

export interface PerfilEventos {
  porHora: PontoHora[]
  porDia: PontoDia[]
  porTipo: ContagemPorTipo
  total: number
  violacoes: number
  /** Dias distintos com pelo menos um evento capturado. */
  diasComRegistro: number
}

/**
 * `date_trunc` volta naive ("2026-08-21T13:00:00", sem offset) e o JS leria
 * isso como hora local. Mesma normalização de `timeBuckets.toUtcMs` — os dois
 * leem o MESMO campo do MESMO endpoint e não podem discordar do fuso.
 */
function paraData(iso: string): Date | null {
  const temOffset = /Z$|[+-]\d{2}:?\d{2}$/.test(iso)
  const d = new Date(temOffset ? iso : `${iso}Z`)
  return Number.isNaN(d.getTime()) ? null : d
}

/** `YYYY-MM-DD` da data em fuso LOCAL (nunca `toISOString`, que devolve UTC). */
function diaLocal(d: Date): string {
  const mes = String(d.getMonth() + 1).padStart(2, '0')
  const dia = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${mes}-${dia}`
}

export function agregarPerfil(rows: ProfileRow[]): PerfilEventos {
  const porTipo: ContagemPorTipo = { violacao: 0, conformidade: 0, indefinido: 0 }
  const porHora: PontoHora[] = Array.from({ length: 24 }, (_, hora) => ({
    hora,
    total: 0,
    violacoes: 0,
  }))
  const dias = new Map<string, PontoDia>()

  for (const row of rows) {
    if (!row.bucket) continue
    const d = paraData(row.bucket)
    if (!d) continue
    const contagem = Number(row.count) || 0
    const ehViolacao = row.kind === 'violacao'

    if (row.kind in porTipo) porTipo[row.kind as EventKind] += contagem

    const h = porHora[d.getHours()]
    h.total += contagem
    if (ehViolacao) h.violacoes += contagem

    const chave = diaLocal(d)
    const ponto = dias.get(chave) ?? { dia: chave, total: 0, violacoes: 0 }
    ponto.total += contagem
    if (ehViolacao) ponto.violacoes += contagem
    dias.set(chave, ponto)
  }

  const diasComRegistro = dias.size
  const total = porTipo.violacao + porTipo.conformidade + porTipo.indefinido

  return {
    porHora,
    porDia: preencherDias(dias),
    porTipo,
    total,
    violacoes: porTipo.violacao,
    diasComRegistro,
  }
}

/** Série densa entre o primeiro e o último dia COM registro (ver cabeçalho). */
function preencherDias(dias: Map<string, PontoDia>): PontoDia[] {
  const chaves = [...dias.keys()].sort()
  if (chaves.length === 0) return []

  const primeiro = new Date(`${chaves[0]}T00:00:00`)
  const ultimo = new Date(`${chaves[chaves.length - 1]}T00:00:00`)
  const serie: PontoDia[] = []
  // Passo por MEIO-DIA, não por 24h: somar 86.400.000ms a uma data local
  // atravessa horário de verão sem erro só se a hora tiver folga. Normalizar
  // para 12h e reler o dia local é o jeito que não pula nem repete data.
  for (let t = primeiro.getTime(); t <= ultimo.getTime(); t += DAY_MS) {
    const d = new Date(t + DAY_MS / 2)
    const chave = diaLocal(d)
    serie.push(dias.get(chave) ?? { dia: chave, total: 0, violacoes: 0 })
  }
  return serie
}

/** Hora com mais VIOLAÇÕES. `null` quando não houve violação nenhuma. */
export function picoDeViolacao(porHora: PontoHora[]): PontoHora | null {
  let pico: PontoHora | null = null
  for (const p of porHora) {
    if (p.violacoes > 0 && (pico === null || p.violacoes > pico.violacoes)) pico = p
  }
  return pico
}

/** Rótulo pt-BR curto de `YYYY-MM-DD` → "21/08". */
export function rotuloDia(dia: string): string {
  const [ano, mes, d] = dia.split('-')
  return ano && mes && d ? `${d}/${mes}` : dia
}
