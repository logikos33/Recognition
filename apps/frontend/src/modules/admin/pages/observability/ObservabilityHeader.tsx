/**
 * ObservabilityHeader — controles globais do dashboard de observability (WS11).
 *
 * Contrato de Operabilidade: seletor de intervalo (Pausado/10s/30s/1m/5m,
 * persistido em localStorage), botão Pausar/Retomar com estado visível,
 * seletor de janela histórica (1h/6h/24h/7d, persistido) e 'Coletar agora'
 * com loading + Toast. Badge de status geral legível pela gestão.
 */
import { Pause, Play, Zap } from 'lucide-react'
import { Badge } from '../../../../components/ui/Badge/Badge'
import type { BadgeVariant } from '../../../../components/ui/Badge/Badge'
import { Button } from '../../../../components/ui/Button/Button'
import { Tooltip } from '../../../../components/ui/Tooltip/Tooltip'
import * as s from '../../components/admin.css'
import type { ObsWindow, PlatformStatus } from '../../types/admin'

export const REFRESH_OPTIONS: { value: number; label: string }[] = [
  { value: 0, label: 'Pausado' },
  { value: 10_000, label: '10s' },
  { value: 30_000, label: '30s' },
  { value: 60_000, label: '1m' },
  { value: 300_000, label: '5m' },
]

export const WINDOW_OPTIONS: { value: ObsWindow; label: string }[] = [
  { value: '1h', label: 'Última hora' },
  { value: '6h', label: 'Últimas 6h' },
  { value: '24h', label: 'Últimas 24h' },
  { value: '7d', label: 'Últimos 7 dias' },
]

function statusBadge(status: PlatformStatus | null): { variant: BadgeVariant; label: string } {
  switch (status) {
    case 'healthy':  return { variant: 'success', label: 'OK' }
    case 'degraded': return { variant: 'warning', label: 'Degradado' }
    case 'critical': return { variant: 'danger', label: 'Crítico' }
    default:         return { variant: 'neutral', label: 'Sem dados' }
  }
}

function collectedAgo(collectedAt: string | null): string {
  if (!collectedAt) return 'nenhuma coleta ainda'
  const diffS = Math.max(Math.floor((Date.now() - new Date(collectedAt).getTime()) / 1000), 0)
  if (diffS < 60) return `coletado há ${diffS}s`
  const mins = Math.floor(diffS / 60)
  if (mins < 60) return `coletado há ${mins}min`
  return `coletado há ${Math.floor(mins / 60)}h`
}

interface ObservabilityHeaderProps {
  status: PlatformStatus | null
  collectedAt: string | null
  intervalMs: number
  paused: boolean
  windowSel: ObsWindow
  collecting: boolean
  onIntervalChange: (ms: number) => void
  onTogglePause: () => void
  onWindowChange: (w: ObsWindow) => void
  onCollectNow: () => void
}

export function ObservabilityHeader({
  status, collectedAt, intervalMs, paused, windowSel, collecting,
  onIntervalChange, onTogglePause, onWindowChange, onCollectNow,
}: ObservabilityHeaderProps) {
  const badge = statusBadge(status)

  return (
    <div className={s.flex} style={{ flexWrap: 'wrap', gap: 12, marginBottom: 20 }}>
      <Tooltip label="Estado geral da plataforma: OK = tudo saudável; Degradado = algum serviço lento ou instável; Crítico = banco ou Redis fora do ar">
        <span><Badge variant={badge.variant}>{badge.label}</Badge></span>
      </Tooltip>

      <Tooltip label="Quando o coletor gravou o último snapshot de métricas. Se este valor parar de avançar, o coletor (worker) está fora do ar">
        <span className={s.muted}>{collectedAgo(collectedAt)}</span>
      </Tooltip>

      <div className={s.spacer} />

      <label className={s.flex} style={{ gap: 6 }}>
        <span className={s.muted}>Atualização</span>
        <select
          className={s.select}
          value={String(intervalMs)}
          onChange={(e) => onIntervalChange(Number(e.target.value))}
          aria-label="Intervalo de atualização automática"
        >
          {REFRESH_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </label>

      <label className={s.flex} style={{ gap: 6 }}>
        <span className={s.muted}>Janela</span>
        <select
          className={s.select}
          value={windowSel}
          onChange={(e) => onWindowChange(e.target.value as ObsWindow)}
          aria-label="Janela histórica dos gráficos"
        >
          {WINDOW_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </label>

      <Button
        variant="ghost"
        size="sm"
        onClick={onTogglePause}
        aria-pressed={paused}
        aria-label={paused ? 'Retomar atualização automática' : 'Pausar atualização automática'}
      >
        {paused ? <Play size={13} /> : <Pause size={13} />}
        {paused ? 'Retomar' : 'Pausar'}
      </Button>

      <Tooltip label="Grava um snapshot de métricas agora, sem esperar o ciclo de 60s do coletor">
        <Button
          variant="secondary"
          size="sm"
          loading={collecting}
          onClick={onCollectNow}
        >
          <Zap size={13} />
          Coletar agora
        </Button>
      </Tooltip>
    </div>
  )
}
