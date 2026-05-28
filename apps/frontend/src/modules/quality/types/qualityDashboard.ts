export interface DashboardSummary {
  pieces_total: number
  ok_pct: number
  nok_count: number
  rework_active: number
  stations_active: number
  stations_total: number
}

export interface StationOperator {
  id: string
  name: string | null
}

export interface ActivePiece {
  op: string | null
  code: string | null
  product_type: string | null
  status: string
  status_label: string
  started_at: string | null
}

export interface StationLive {
  id: string
  station_code: string
  name: string
  camera_ids: string[]
  online: boolean
  operator: StationOperator | null
  active_piece: ActivePiece | null
  shift_stats: { ok: number; nok: number }
  status: 'ok' | 'warning' | 'critical' | 'offline'
}

export interface DashboardSummaryResponse {
  status: string
  data: { summary: DashboardSummary; updated_at: string }
}

export interface DashboardStationsResponse {
  status: string
  data: { stations: StationLive[]; updated_at: string }
}
