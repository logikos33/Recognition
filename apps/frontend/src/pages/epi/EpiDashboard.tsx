/**
 * ⚠️ SUPERADA — esta tela tem substituta no front novo.
 *
 * @migrado-para src/app/epi/Dashboard.tsx
 * rota nova: /novo/epi/dashboard
 *
 * @paridade-pendente ranking de câmeras com mais alertas; presets e montagem manual da parede
 *
 * ⛔ NÃO APAGUE: a substituta existe, mas NÃO faz tudo o que esta faz. A lista
 * completa e verificada está em docs/migration/PARIDADE-ANTIGO-VS-NOVO.md.
 *
 * Continua VIVA e servindo a rota antiga: os dois fronts convivem até a
 * migração terminar (decisão do Vitor, 27/08). Não apague nesta rodada.
 *
 * Na rodada de remoção, ANTES de apagar: a substituta foi provada renderizando
 * com dado real no DEV, mas paridade de FUNCIONALIDADE não foi conferida item a
 * item. Compare as duas telas primeiro — e confira quem mais importa deste
 * arquivo (componentes e estilos só dele saem junto; os compartilhados, não).
 * A lista está em docs/migration/MANIFESTO-FRONT-ANTIGO.md.
 */
/**
 * EpiDashboard — dashboard BI do módulo EPI (mutirão WS3).
 *
 * Estrutura: KPIRow (fixa) → CameraGrid/VMS (fixa, coração do módulo) →
 * DashboardToolbar (período + Personalizar) → grid de widgets BI
 * movimentáveis (@dnd-kit) com ordem/visibilidade persistidas em
 * localStorage (dashboardStore).
 */
import {
  DndContext,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core'
import { SortableContext, rectSortingStrategy } from '@dnd-kit/sortable'
import { KPIRow } from '../../components/dashboard/KPIRow'
import { CrossTenantCameraBanner } from '../../components/CrossTenantCameraBanner'
import { DashboardToolbar } from '../../components/dashboard/DashboardToolbar'
import { CameraGrid } from '../../components/camera-grid/CameraGrid'
import { WidgetShell } from '../../components/dashboard/widgets/WidgetShell'
import { AlertsTimelineWidget } from '../../components/dashboard/widgets/AlertsTimelineWidget'
import { ViolationsDistributionWidget } from '../../components/dashboard/widgets/ViolationsDistributionWidget'
import { TopCamerasWidget } from '../../components/dashboard/widgets/TopCamerasWidget'
import { RecentAlertsWidget } from '../../components/dashboard/widgets/RecentAlertsWidget'
import { EventLogWidget } from '../../components/dashboard/widgets/EventLogWidget'
import { useDashboardStore, type WidgetId } from '../../stores/dashboardStore'
import { container, cameraSection, widgetGrid, widgetSpan2 } from './EpiDashboard.css'

const WIDGET_INFO: Record<WidgetId, string> = {
  'alerts-timeline':
    'Quantidade de alertas por período. Em "Hoje (24h)" cada ponto é uma hora; em 7/30 dias, cada ponto é um dia.',
  'violations-distribution':
    'Distribuição das violações detectadas por tipo de EPI no período selecionado (todo o período, não amostra).',
  'top-cameras': 'Câmeras com mais alertas no período selecionado (top 10).',
  'recent-alerts': 'Os 5 alertas mais recentes do módulo.',
  'event-log': 'Últimos eventos registrados com violação, confiança e horário.',
}

export function EpiDashboard() {
  const widgetOrder = useDashboardStore((s) => s.widgetOrder)
  const hiddenWidgets = useDashboardStore((s) => s.hiddenWidgets)
  const period = useDashboardStore((s) => s.period)
  const moveWidget = useDashboardStore((s) => s.moveWidget)
  const toggleWidget = useDashboardStore((s) => s.toggleWidget)

  const visibleWidgets = widgetOrder.filter((id) => !hiddenWidgets.includes(id))

  // distance:4 evita que cliques/hover (tooltips do recharts) iniciem drag
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } })
  )

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event
    if (!over || active.id === over.id) return
    const from = widgetOrder.indexOf(active.id as WidgetId)
    const to = widgetOrder.indexOf(over.id as WidgetId)
    if (from >= 0 && to >= 0) moveWidget(from, to)
  }

  const renderWidget = (id: WidgetId) => {
    const shellProps = {
      id,
      info: WIDGET_INFO[id],
      onHide: () => toggleWidget(id),
    }
    switch (id) {
      case 'alerts-timeline':
        return (
          <WidgetShell
            key={id}
            {...shellProps}
            title="Alertas ao longo do tempo"
            className={widgetSpan2}
          >
            <AlertsTimelineWidget period={period} />
          </WidgetShell>
        )
      case 'violations-distribution':
        return (
          <WidgetShell key={id} {...shellProps} title="Distribuição de Violações">
            <ViolationsDistributionWidget period={period} />
          </WidgetShell>
        )
      case 'top-cameras':
        return (
          <WidgetShell key={id} {...shellProps} title="Câmeras com mais alertas">
            <TopCamerasWidget period={period} />
          </WidgetShell>
        )
      case 'recent-alerts':
        return (
          <WidgetShell key={id} {...shellProps} title="Últimos Alertas">
            <RecentAlertsWidget />
          </WidgetShell>
        )
      case 'event-log':
        return (
          <WidgetShell key={id} {...shellProps} title="Registro de Eventos">
            <EventLogWidget />
          </WidgetShell>
        )
      default:
        return null
    }
  }

  return (
    <div className={container}>
      <CrossTenantCameraBanner />
      <KPIRow />

      {/* VMS em destaque — seção fixa, não participa do drag (WS9) */}
      <div className={cameraSection}>
        <CameraGrid module="epi" />
      </div>

      <DashboardToolbar />

      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext items={visibleWidgets} strategy={rectSortingStrategy}>
          <div className={widgetGrid}>{visibleWidgets.map(renderWidget)}</div>
        </SortableContext>
      </DndContext>
    </div>
  )
}

export default EpiDashboard
