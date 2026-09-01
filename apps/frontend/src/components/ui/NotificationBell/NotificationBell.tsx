import { useState, useEffect, useMemo, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bell, ChevronDown, ChevronRight } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../../services/api'
import { vars } from '../../../styles/theme.css'
import { agruparPorRajada } from '../../../utils/rajadas'
import {
  bellWrap,
  bellBtn,
  badge,
  panel,
  panelHeader,
  panelTitle,
  panelBody,
  alertCard,
  alertIcon,
  alertContent,
  alertCamera,
  alertViolation,
  alertTime,
  rajadaToggle,
  rajadaLista,
  rajadaItem,
  emptyPanel,
  viewAllBtn,
} from './NotificationBell.css'

interface Violation {
  class: string
  confidence: number
}

interface Alert {
  id: string
  camera_id: string
  camera_name?: string
  violations: Violation[]
  acknowledged: boolean
  created_at: string
}

interface AlertsResponse {
  alerts: Alert[]
  total: number
  /** Rajadas (câmera+classe em <60s) do MESMO filtro — ux2/dedup. Ausente em
   *  backend/mock antigo: o badge cai para `alerts.length` (ver `count`). */
  total_situacoes?: number
}

const VIOLATION_LABELS: Record<string, string> = {
  no_helmet: 'Sem capacete',
  no_vest: 'Sem colete',
  no_gloves: 'Sem luvas',
  no_safety_glasses: 'Sem óculos',
  no_glasses: 'Sem óculos',
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'agora'
  if (mins < 60) return `há ${mins}min`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `há ${hrs}h`
  return `há ${Math.floor(hrs / 24)}d`
}

export function NotificationBell() {
  const navigate = useNavigate()
  const [isOpen, setIsOpen] = useState(false)
  const wrapRef = useRef<HTMLDivElement>(null)

  const { data } = useQuery({
    // ADR-0065: o sino NÃO toca por EPI presente. O roteamento de notificação
    // segue desligado (notification_channels vazia) e, quando nascer, nasce
    // ligado a este mesmo recorte de AUSÊNCIA.
    queryKey: ['alerts-unack', 'violation'],
    // ux2/dedup: achado do Vitor — "10 pendentes" que eram a MESMA cena de 6
    // dias atrás. per_page subiu de 10 pra 30: nenhuma paginação nova, só
    // mais chance de UMA rajada isolada não preencher o painel inteiro e
    // esconder outras situações mais antigas.
    // ponytail: não existe `group=1` no backend ainda pra pedir direto N
    // situações distintas — pedido registrado no handoff desta rodada.
    queryFn: () => api.get<{ data?: AlertsResponse } & AlertsResponse>(
      '/alerts?acknowledged=false&per_page=30&page=1&kind=violation'
    ),
    refetchInterval: 30000,
    staleTime: 20000,
  })

  const alerts: Alert[] = data?.data?.alerts ?? (data as AlertsResponse | undefined)?.alerts ?? []
  const totalSituacoes = data?.data?.total_situacoes ?? (data as AlertsResponse | undefined)?.total_situacoes
  // Badge/contagem conta SITUAÇÕES (rajadas), não linhas — ux2/dedup. Sem
  // `total_situacoes` (backend/mock antigo), cai pro que já existia.
  const count = Math.min(totalSituacoes ?? alerts.length, 99)

  // Agrupa o que está NA TELA (as até 30 linhas buscadas) por câmera+classe
  // em <60s — mesma janela do backend (VerificationService). Representante +
  // alternador "+N repetições"; nunca esconde, cada repetição mantém o
  // próprio deep-link.
  const grupos = useMemo(
    () =>
      agruparPorRajada(alerts, {
        cameraId: (a) => a.camera_id,
        classe: (a) => a.violations?.[0]?.class ?? '',
        criadoEm: (a) => a.created_at,
      }),
    [alerts],
  )
  const [expandidos, setExpandidos] = useState<Set<string>>(new Set())
  const alternarExpandido = (id: string) =>
    setExpandidos((atual) => {
      const novo = new Set(atual)
      if (novo.has(id)) novo.delete(id)
      else novo.add(id)
      return novo
    })

  useEffect(() => {
    if (!isOpen) return

    function handleMouseDown(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }

    document.addEventListener('mousedown', handleMouseDown)
    return () => document.removeEventListener('mousedown', handleMouseDown)
  }, [isOpen])

  return (
    <div className={bellWrap} ref={wrapRef}>
      <button
        className={bellBtn}
        onClick={() => setIsOpen(v => !v)}
        aria-label="Notificações"
      >
        <Bell
          size={18}
          color={isOpen ? vars.color.primary : vars.color.textSecondary}
        />
        {count > 0 && (
          <span className={badge}>{count > 99 ? '99+' : count}</span>
        )}
      </button>

      {isOpen && (
        <div className={panel}>
          <div className={panelHeader}>
            <span className={panelTitle}>Notificações</span>
            <span style={{ fontSize: 11, color: vars.color.textDim }}>
              {count} pendente{count !== 1 ? 's' : ''}
            </span>
          </div>

          <div className={panelBody}>
            {alerts.length === 0 ? (
              <div className={emptyPanel}>Nenhum alerta pendente</div>
            ) : (
              grupos.map(grupo => {
                const alert = grupo.representante
                const repeticoes = grupo.repeticoes.filter(r => r.id !== alert.id)
                const expandido = expandidos.has(alert.id)
                const violationText = alert.violations
                  .map(v => VIOLATION_LABELS[v.class] ?? v.class)
                  .join(', ')
                const abrir = (id: string, cameraId: string) => {
                  navigate(
                    `/epi/alerts?camera_id=${encodeURIComponent(cameraId)}&acknowledged=false&kind=violation&highlight=${encodeURIComponent(id)}`
                  )
                  setIsOpen(false)
                }
                return (
                  <div key={alert.id}>
                    <button
                      type="button"
                      className={alertCard}
                      onClick={() => abrir(alert.id, alert.camera_id)}
                      aria-label={`Abrir alerta de ${alert.camera_name ?? 'câmera'}: ${violationText}`}
                    >
                      <div className={alertIcon}>
                        <span style={{ color: vars.color.warning, fontSize: 14 }}>⚠</span>
                      </div>
                      <div className={alertContent}>
                        <div className={alertCamera}>
                          {alert.camera_name ?? 'Câmera'}
                        </div>
                        <div className={alertViolation}>{violationText}</div>
                        <div className={alertTime}>{timeAgo(alert.created_at)}</div>
                      </div>
                    </button>
                    {/* Rajada (ux2/dedup): mesma câmera+classe em <60s — nunca
                        esconde, cada repetição mantém o próprio deep-link. */}
                    {repeticoes.length > 0 && (
                      <button
                        type="button"
                        className={rajadaToggle}
                        onClick={(e) => { e.stopPropagation(); alternarExpandido(alert.id) }}
                      >
                        {expandido ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                        +{repeticoes.length} repetiç{repeticoes.length === 1 ? 'ão' : 'ões'} da mesma cena
                      </button>
                    )}
                    {expandido && repeticoes.length > 0 && (
                      <div className={rajadaLista}>
                        {repeticoes.map(r => (
                          <button
                            key={r.id}
                            type="button"
                            className={rajadaItem}
                            onClick={() => abrir(r.id, r.camera_id)}
                            aria-label={`Abrir alerta de ${r.camera_name ?? 'câmera'} · ${timeAgo(r.created_at)}`}
                          >
                            {timeAgo(r.created_at)}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )
              })
            )}
          </div>

          <button
            className={viewAllBtn}
            onClick={() => {
              navigate('/epi/alerts?acknowledged=false&kind=violation')
              setIsOpen(false)
            }}
          >
            Ver todos os alertas →
          </button>
        </div>
      )}
    </div>
  )
}
