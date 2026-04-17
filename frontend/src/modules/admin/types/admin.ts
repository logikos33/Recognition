/**
 * Admin module TypeScript types.
 */

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
  user_count?: number
  worker_status?: WorkerStatus
  worker_metrics?: WorkerLiveMetrics | null
  pending_approvals?: TrainingApproval[]
  users?: AdminUser[]
  created_at: string
  updated_at?: string
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
