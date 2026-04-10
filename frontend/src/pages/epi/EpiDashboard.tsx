/**
 * EpiDashboard — KPI row + DVR-style camera container.
 */
import { KPIRow } from '../../components/dashboard/KPIRow'
import { CameraGrid } from '../../components/camera-grid/CameraGrid'
import { container, cameraSection } from './EpiDashboard.css'

export function EpiDashboard() {
  return (
    <div className={container}>
      <KPIRow />
      <div className={cameraSection}>
        <CameraGrid />
      </div>
    </div>
  )
}

export default EpiDashboard
