/**
 * MonitoringPage — fullscreen CameraGrid (no KPIs).
 */
import { CameraGrid } from '../components/camera-grid/CameraGrid'

export function MonitoringPage() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
      <CameraGrid module="epi" />
    </div>
  )
}
