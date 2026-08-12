/**
 * EdgeMonitoringPage — página OCULTA /monitoring (superadmin only).
 * Observabilidade do box edge (Jetson Orin): semáforo, hardware, serviços,
 * pipeline, coleta, rede, OTA e inferência. Sem link em menu/sidebar de
 * propósito — para não-superadmin a rota se comporta como inexistente (C-01).
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { SlidersHorizontal } from 'lucide-react'
import { Banner } from '../../components/ui/Banner/Banner'
import { Button } from '../../components/ui/Button/Button'
import { EmptyState } from '../../components/ui/EmptyState/EmptyState'
import { Skeleton } from '../../components/ui/Skeleton/Skeleton'
import { useToast } from '../../components/ui/Toast/useToast'
import { monitoringService } from '../../services/monitoringService'
import type {
  MonitoringSite,
  MonitoringThresholds,
  MonitoringWindow,
} from '../../types/monitoring'
import { DEFAULT_THRESHOLDS, mergeThresholds, siteTargetRef } from './health'
import { SiteMonitor } from './SiteMonitor'
import { ThresholdsModal } from './ThresholdsModal'
import * as s from './monitoring.css'

const WINDOW_OPTIONS: { value: MonitoringWindow; label: string }[] = [
  { value: '2h', label: '2h' },
  { value: '24h', label: '24h' },
  { value: '7d', label: '7d' },
  { value: '30d', label: '30d' },
]

export function EdgeMonitoringPage() {
  const toast = useToast()

  // ── Sites ─────────────────────────────────────────────────────────────────
  const [sites, setSites] = useState<MonitoringSite[] | null>(null)
  const [sitesError, setSitesError] = useState<string | null>(null)
  const [selectedSiteId, setSelectedSiteId] = useState<string | null>(null)

  const loadSites = useCallback(async () => {
    setSitesError(null)
    try {
      const list = await monitoringService.getSites()
      setSites(list)
      // Auto-seleciona o primeiro (mantém a seleção atual se ainda existir)
      setSelectedSiteId((cur) =>
        cur != null && list.some((site) => site.id === cur) ? cur : (list[0]?.id ?? null),
      )
    } catch (e: unknown) {
      setSites([])
      setSitesError(e instanceof Error ? e.message : 'Falha ao carregar os sites.')
    }
  }, [])

  useEffect(() => {
    void loadSites()
  }, [loadSites])

  const selectedSite = useMemo(
    () => sites?.find((site) => site.id === selectedSiteId) ?? null,
    [sites, selectedSiteId],
  )

  // ── Janela ────────────────────────────────────────────────────────────────
  const [windowSel, setWindowSel] = useState<MonitoringWindow>('2h')

  // ── Thresholds (por site; defaults do cliente quando GET vier vazio) ─────
  const [thresholds, setThresholds] = useState<MonitoringThresholds>(DEFAULT_THRESHOLDS)
  const [thresholdsOpen, setThresholdsOpen] = useState(false)
  const [savingThresholds, setSavingThresholds] = useState(false)

  useEffect(() => {
    if (!selectedSiteId) return
    let cancelled = false
    setThresholds(DEFAULT_THRESHOLDS)
    monitoringService
      .getThresholds(selectedSiteId)
      .then((raw) => {
        if (!cancelled) setThresholds(mergeThresholds(raw))
      })
      .catch(() => {
        // Sem thresholds persistidos (ou erro): defaults do cliente valem
        if (!cancelled) setThresholds(DEFAULT_THRESHOLDS)
      })
    return () => {
      cancelled = true
    }
  }, [selectedSiteId])

  const handleSaveThresholds = async (values: MonitoringThresholds) => {
    if (!selectedSiteId) return
    setSavingThresholds(true)
    try {
      const saved = await monitoringService.putThresholds(selectedSiteId, values)
      setThresholds(mergeThresholds(saved))
      setThresholdsOpen(false)
      toast.success('Limiares salvos', 'O semáforo e os badges já usam os novos valores.')
    } catch (e: unknown) {
      toast.error('Falha ao salvar limiares', e instanceof Error ? e.message : 'Erro inesperado')
    } finally {
      setSavingThresholds(false)
    }
  }

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className={s.page}>
      <div className={s.headerRow}>
        <div>
          <h1 className={s.pageTitle}>Monitoramento do box edge</h1>
          <p className={s.pageSubtitle}>
            Observabilidade do Jetson no site do cliente — página restrita (superadmin)
          </p>
        </div>
        <div className={s.controls}>
          {sites != null && sites.length > 0 && (
            <>
              <select
                className={s.select}
                value={selectedSiteId ?? ''}
                onChange={(e) => setSelectedSiteId(e.target.value)}
                aria-label="Site"
              >
                {sites.map((site) => (
                  <option key={site.id} value={site.id}>
                    {site.name}
                    {site.tenant_name ? ` — ${site.tenant_name}` : ''}
                  </option>
                ))}
              </select>
              <div className={s.windowGroup} role="group" aria-label="Janela histórica">
                {WINDOW_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    className={`${s.windowBtn}${windowSel === opt.value ? ` ${s.windowBtnActive}` : ''}`}
                    aria-pressed={windowSel === opt.value}
                    onClick={() => setWindowSel(opt.value)}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setThresholdsOpen(true)}
                disabled={!selectedSiteId}
              >
                <SlidersHorizontal size={14} aria-hidden="true" style={{ marginRight: 4, verticalAlign: -2 }} />
                Limiares
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Target do canal OTA — o veredito de divergência fica no painel
          OTA/Versão, que compara o current_ref REAL da amostra do box com o
          target (edge_version do heartbeat é rótulo manual, não SHA). */}
      {selectedSite && (
        <div className={s.controls}>
          <span className={s.muted}>
            Target do canal:{' '}
            <span className={s.mono}>{siteTargetRef(selectedSite) ?? '—'}</span>
          </span>
          {(selectedSite.devices?.length ?? 0) > 0 && (
            <span className={s.muted}>
              {selectedSite.devices?.length === 1
                ? '1 device'
                : `${selectedSite.devices?.length} devices`}
            </span>
          )}
        </div>
      )}

      {sitesError && (
        <Banner variant="danger">
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            {sitesError}
            <Button size="sm" variant="secondary" onClick={() => void loadSites()}>
              Tentar de novo
            </Button>
          </span>
        </Banner>
      )}

      {sites == null && (
        <div className={s.cardsGrid}>
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} variant="rect" height={180} />
          ))}
        </div>
      )}

      {sites != null && sites.length === 0 && !sitesError && (
        <EmptyState
          title="Nenhum site edge disponível"
          description="Cadastre um site com device enrolado para ver o monitoramento do box"
        />
      )}

      {selectedSite && (
        // key remonta o monitor na troca de site/janela — todo polling
        // reinicia limpo (padrão da casa, ver AdminObservabilityPage)
        <SiteMonitor
          key={`${selectedSite.id}:${windowSel}`}
          site={selectedSite}
          windowSel={windowSel}
          thresholds={thresholds}
          onExpandWindow={setWindowSel}
        />
      )}

      <ThresholdsModal
        open={thresholdsOpen}
        initial={thresholds}
        saving={savingThresholds}
        onSave={(values) => void handleSaveThresholds(values)}
        onClose={() => setThresholdsOpen(false)}
      />
    </div>
  )
}
