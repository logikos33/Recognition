/**
 * Admin module TypeScript types.
 */

// ── Branding (task-048) ──────────────────────────────────────────────────────
export interface TenantBranding {
  product_name: string
  color_primary: string
  color_secondary: string
  logo_url: string | null
  favicon_url: string | null
  // WS1 — Containers & Superfícies (persistidos no mesmo JSONB branding)
  color_bg_base?: string | null
  color_bg_surface?: string | null
  color_bg_elevated?: string | null
  color_bg_card?: string | null
  color_text_primary?: string | null
  color_text_secondary?: string | null
  color_border?: string | null
}

export type WorkerStatus = 'onpremise' | 'railway' | 'offline'
export type TenantPlan = 'basic' | 'standard' | 'premium' | 'enterprise'
export type UserRole = 'superadmin' | 'admin' | 'operator' | 'analyst' | 'trainer' | 'viewer'
export type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'auto_approved'
export type TicketStatus = 'open' | 'in_progress' | 'waiting_client' | 'resolved' | 'closed'
export type TicketPriority = 'low' | 'normal' | 'high' | 'critical'
export type TicketCategory = 'bug' | 'question' | 'retrain' | 'new_module' | 'billing' | 'other'
export type AnnouncementType = 'info' | 'maintenance' | 'feature' | 'security'
export type PlatformStatus = 'healthy' | 'degraded' | 'critical'

export interface AdminDashboard {
  tenants_active: number
  users_total: number
  cameras_online: number
  alerts_24h: number
  training_approvals_pending: number
  tickets_open: number
  mrr_estimated: number
  workers: { online: number; fallback: number; offline: number }
  recent_critical_events: AuditEntry[]
  top_tenants_users: Array<{ tenant_name: string; user_count: number }>
}

export interface Tenant {
  id: string
  slug: string
  name: string
  plan: TenantPlan
  schema_name: string
  modules_enabled: string[]
  is_active: boolean
  suspended_at?: string
  requires_training_approval: boolean
  mrr_per_camera: Record<string, number>
  internal_notes?: string
  contract_cameras: number
  video_retention_days?: number
  user_count?: number
  worker_status?: WorkerStatus
  worker_metrics?: WorkerLiveMetrics | null
  pending_approvals?: TrainingApproval[]
  users?: AdminUser[]
  created_at: string
  updated_at?: string
}

// ── Retention Tiers (task-047) ───────────────────────────────────────────────

export type RetentionTierDays = 1 | 7 | 30 | 90

export interface CameraRetention {
  camera_id: string
  retention_days: RetentionTierDays | null
  effective_days: number
  tenant_default_days: number
  valid_tiers: RetentionTierDays[]
}

export interface TenantRetention {
  tenant_id: string
  retention_days: number
  valid_tiers: RetentionTierDays[]
}

export interface AdminUser {
  id: string
  email: string
  name?: string
  role: UserRole
  tenant_id: string
  tenant_name?: string
  is_active: boolean
  last_login_at?: string
  last_login_ip?: string
  login_count: number
  access_expires_at?: string
  force_password_reset: boolean
  created_at: string
}

export interface WorkerLiveMetrics {
  gpu_pct: number
  vram_used_gb: number
  fps_avg: number
  cameras_active: number
  timestamp: string
  hostname?: string
}

export interface WorkerInfo {
  id: string
  tenant_id: string
  tenant_schema: string
  tenant_name?: string
  tenant_slug?: string
  hostname?: string
  tailscale_ip?: string
  software_version?: string
  gpu_model?: string
  gpu_vram_gb?: number
  status: WorkerStatus
  last_heartbeat_at?: string
  live_metrics?: WorkerLiveMetrics | null
  registered_at?: string
}

export interface WorkerMetricPoint {
  gpu_pct: number
  vram_used_gb: number
  fps_avg: number
  cameras_active: number
  recorded_at: string
}

export interface TrainingApproval {
  id: string
  tenant_id: string
  tenant_name?: string
  training_job_id: string
  module: string
  job_name?: string
  metrics: {
    mAP50?: number
    mAP50_95?: number
    box_loss?: number
    dataset_size?: number
    classes?: string[]
    epochs?: number
  }
  dataset_sample_urls?: string[]
  status: ApprovalStatus
  reviewed_at?: string
  reviewer_notes?: string
  rejection_reason?: string
  created_at: string
}

export interface SupportTicket {
  id: string
  tenant_id: string
  tenant_name?: string
  subject: string
  category: TicketCategory
  priority: TicketPriority
  status: TicketStatus
  first_responded_at?: string
  sla_breached?: boolean
  created_at: string
  updated_at: string
}

export interface TicketMessage {
  id: string
  ticket_id: string
  author_id?: string
  author_email?: string
  content: string
  is_internal: boolean
  created_at: string
}

export interface AuditEntry {
  id: string
  action: string
  target_type: string
  target_id?: string
  actor_role: string
  actor_email?: string
  tenant_name?: string
  ip_address?: string
  created_at: string
}

export interface Plan {
  id: string
  slug: string
  name: string
  modules_allowed: string[]
  max_cameras: number
  video_retention_days: number
  requires_training_approval: boolean
  price_per_camera: Record<string, number>
  active: boolean
}

export interface FeatureFlag {
  id: string
  flag_key: string
  flag_value: boolean
  description?: string
  updated_at?: string
}

export interface PlatformHealth {
  status: PlatformStatus
  services: Record<string, { status: string; latency_ms?: number; details?: string }>
  celery_queues: Record<string, number>
}

export interface Announcement {
  id: string
  title: string
  content: string
  type: AnnouncementType
  target: string
  target_tenant_id?: string
  published_at?: string
  expires_at?: string
  created_at: string
}

export interface PermissionMatrix {
  [permission: string]: UserRole[]
}

export interface Paginated<T> {
  items: T[]
  total: number
}

// API response envelope
export type R<T> = { status: string; data: T }

// ── Custom Roles & Permissions ────────────────────────────────────────────────

/** Keys de permissões disponíveis no sistema. */
export type PermissionKey =
  | 'cameras:read'
  | 'cameras:write'
  | 'cameras:delete'
  | 'alerts:read'
  | 'alerts:export'
  | 'training:read'
  | 'training:write'
  | 'training:approve'
  | 'reports:read'
  | 'reports:export'
  | 'admin:users'
  | 'admin:roles'
  | 'admin:settings'
  | 'counting:read'
  | 'counting:write'
  | 'verification:read'
  | 'verification:write'

/** Agrupamento de permissões por área funcional. */
export interface PermissionGroup {
  label: string
  permissions: PermissionKey[]
}

export const PERMISSION_GROUPS: PermissionGroup[] = [
  {
    label: 'Câmeras',
    permissions: ['cameras:read', 'cameras:write', 'cameras:delete'],
  },
  {
    label: 'Alertas',
    permissions: ['alerts:read', 'alerts:export'],
  },
  {
    label: 'Treinamento',
    permissions: ['training:read', 'training:write', 'training:approve'],
  },
  {
    label: 'Relatórios',
    permissions: ['reports:read', 'reports:export'],
  },
  {
    label: 'Administração',
    permissions: ['admin:users', 'admin:roles', 'admin:settings'],
  },
  {
    label: 'Contagem',
    permissions: ['counting:read', 'counting:write'],
  },
  {
    label: 'Verificação',
    permissions: ['verification:read', 'verification:write'],
  },
]

export interface CustomRole {
  id: string
  tenant_id: string
  name: string
  permissions: Record<PermissionKey, boolean>
  user_count: number
  created_at: string
  updated_at: string
}

export interface UserCustomRole {
  user_id: string
  email: string
  system_role: UserRole
  custom_role_id: string | null
  custom_role_name: string | null
  permissions: Record<PermissionKey, boolean> | null
}

// ── Versioning & Changelog ────────────────────────────────────────────────────

export type VersionType = 'major' | 'minor' | 'patch'
export type ChangeCategory = 'feature' | 'fix' | 'config' | 'security' | 'breaking' | 'infra'
export type ChangeImportance = 'critical' | 'high' | 'normal' | 'low'

export interface SystemVersion {
  id: string
  version: string
  version_type: VersionType
  title: string
  description?: string
  created_by_email?: string
  created_at: string
  is_current: boolean
  rolled_back_at?: string
  rolled_back_by_email?: string
  changelog_count?: number
  changelog?: ChangelogEntry[]
  config_snapshot?: Record<string, unknown>
}

export interface ChangelogEntry {
  id: string
  version_id?: string
  version_label?: string
  category: ChangeCategory
  importance: ChangeImportance
  title: string
  description?: string
  affected_area?: string
  created_by_email?: string
  created_at: string
}

// ── Test Console (task-056) ───────────────────────────────────────────────────

export type TestConsoleSessionStatus = 'idle' | 'running' | 'stopped' | 'error'

export interface TestConsoleMetrics {
  detections_per_sec: number
  latency_ms: number
  throughput_infs: number
  vram_pct: number
  cameras_active: number
}

export interface TestConsoleStatus {
  status: TestConsoleSessionStatus
  session_id: string | null
  started_at: string | null
  stopped_at: string | null
  config: {
    camera_count: number
    model_id: string
    scenario_config: Record<string, unknown>
    mode: 'stub' | 'harness'
  } | null
  metrics: TestConsoleMetrics
  log_lines: string[]
  vast_ai_configured: boolean
}

// ── Integrations (task-056) ───────────────────────────────────────────────────

export interface Integration {
  id: string
  tenant_id: string
  tenant_name?: string
  key: string
  configured: true
  created_at: string
  updated_at: string
}
