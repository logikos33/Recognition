/**
 * Admin module API service.
 * Todos os métodos usam a instância `api` de services/api.ts.
 */
import { api } from '../../../services/api'
import type {
  AdminDashboard,
  AdminUser,
  Announcement,
  AuditEntry,
  CameraRetention,
  ChangelogEntry,
  FeatureFlag,
  Paginated,
  PermissionMatrix,
  Plan,
  PlatformHealth,
  R,
  SupportTicket,
  SystemVersion,
  Tenant,
  TenantRetention,
  TicketMessage,
  TrainingApproval,
  VersionType,
  WorkerInfo,
  WorkerMetricPoint,
} from '../types/admin'

// ── Dashboard ──────────────────────────────────────────────────────────────

export const adminService = {
  getDashboard: () =>
    api.get<R<AdminDashboard>>('/v1/admin/dashboard').then((r) => r.data),

  // ── Tenants ──────────────────────────────────────────────────────────────

  getTenants: () =>
    api.get<R<{ tenants: Tenant[] }>>('/v1/admin/tenants').then((r) => r.data.tenants),

  getTenant: (id: string) =>
    api.get<R<{ tenant: Tenant }>>(`/v1/admin/tenants/${id}`).then((r) => r.data.tenant),

  createTenant: (data: Partial<Tenant> & { slug: string; name: string }) =>
    api.post<R<{ tenant: Tenant; admin_email: string; temp_password: string }>>(
      '/v1/admin/tenants',
      data,
    ).then((r) => r.data),

  updateTenant: (id: string, data: Partial<Tenant>) =>
    api.patch<R<{ updated: boolean }>>(`/v1/admin/tenants/${id}`, data).then((r) => r.data),

  suspendTenant: (id: string, reason: string) =>
    api.post<R<{ suspended: boolean }>>(`/v1/admin/tenants/${id}/suspend`, { reason })
      .then((r) => r.data),

  reactivateTenant: (id: string) =>
    api.post<R<{ reactivated: boolean }>>(`/v1/admin/tenants/${id}/reactivate`, {})
      .then((r) => r.data),

  getTenantOverview: (id: string) =>
    api.get<R<Record<string, unknown>>>(`/v1/admin/tenants/${id}/overview`).then((r) => r.data),

  getTenantPlanHistory: (id: string) =>
    api.get<R<{ history: unknown[] }>>(`/v1/admin/tenants/${id}/plan-history`)
      .then((r) => r.data.history),

  // ── Users ─────────────────────────────────────────────────────────────────

  getUsers: (params?: {
    tenant_id?: string; role?: string; active?: boolean; search?: string;
    page?: number; per_page?: number
  }) => {
    const qs = new URLSearchParams()
    if (params?.tenant_id) qs.set('tenant_id', params.tenant_id)
    if (params?.role) qs.set('role', params.role)
    if (params?.active !== undefined) qs.set('active', String(params.active))
    if (params?.search) qs.set('search', params.search)
    if (params?.page) qs.set('page', String(params.page))
    if (params?.per_page) qs.set('per_page', String(params.per_page))
    return api.get<R<Paginated<AdminUser>>>(`/v1/admin/users?${qs}`).then((r) => r.data)
  },

  getUser: (id: string) =>
    api.get<R<{ user: AdminUser }>>(`/v1/admin/users/${id}`).then((r) => r.data.user),

  createUser: (data: { email: string; role: string; tenant_id: string; access_expires_at?: string }) =>
    api.post<R<{ user: AdminUser; temp_password: string }>>('/v1/admin/users', data)
      .then((r) => r.data),

  updateUser: (id: string, data: { role?: string; access_expires_at?: string }) =>
    api.patch<R<{ updated: boolean }>>(`/v1/admin/users/${id}`, data).then((r) => r.data),

  deactivateUser: (id: string) =>
    api.post<R<{ deactivated: boolean }>>(`/v1/admin/users/${id}/deactivate`, {})
      .then((r) => r.data),

  reactivateUser: (id: string) =>
    api.post<R<{ reactivated: boolean }>>(`/v1/admin/users/${id}/reactivate`, {})
      .then((r) => r.data),

  forcePasswordReset: (id: string) =>
    api.post<R<{ forced: boolean }>>(`/v1/admin/users/${id}/force-password-reset`, {})
      .then((r) => r.data),

  getUserSessions: (id: string) =>
    api.get<R<{ sessions: unknown[] }>>(`/v1/admin/users/${id}/sessions`)
      .then((r) => r.data.sessions),

  revokeUserSessions: (id: string) =>
    api.delete<R<{ revoked: boolean }>>(`/v1/admin/users/${id}/sessions`).then((r) => r.data),

  getPermissionMatrix: () =>
    api.get<R<{ matrix: PermissionMatrix }>>('/v1/admin/permissions/matrix')
      .then((r) => r.data.matrix),

  // ── Training Approvals ───────────────────────────────────────────────────

  getTrainingApprovals: (params?: { status?: string; tenant_id?: string; module?: string; page?: number }) => {
    const qs = new URLSearchParams()
    if (params?.status) qs.set('status', params.status)
    if (params?.tenant_id) qs.set('tenant_id', params.tenant_id)
    if (params?.module) qs.set('module', params.module)
    if (params?.page) qs.set('page', String(params.page))
    return api.get<R<Paginated<TrainingApproval>>>(`/v1/admin/training-approvals?${qs}`)
      .then((r) => r.data)
  },

  getTrainingApproval: (id: string) =>
    api.get<R<{ approval: TrainingApproval }>>(`/v1/admin/training-approvals/${id}`)
      .then((r) => r.data.approval),

  approveTraining: (id: string, notes?: string) =>
    api.post<R<{ approved: boolean }>>(`/v1/admin/training-approvals/${id}/approve`, { notes })
      .then((r) => r.data),

  rejectTraining: (id: string, reason: string) =>
    api.post<R<{ rejected: boolean }>>(`/v1/admin/training-approvals/${id}/reject`, { reason })
      .then((r) => r.data),

  // ── Workers ───────────────────────────────────────────────────────────────

  getWorkers: () =>
    api.get<R<{ workers: WorkerInfo[] }>>('/v1/admin/workers').then((r) => r.data.workers),

  getWorkerDetail: (tenantSchema: string) =>
    api.get<R<{ worker: WorkerInfo }>>(`/v1/admin/workers/${tenantSchema}`)
      .then((r) => r.data.worker),

  restartWorker: (tenantSchema: string) =>
    api.post<R<{ command_sent: string }>>(`/v1/admin/workers/${tenantSchema}/restart`, {})
      .then((r) => r.data),

  getWorkerMetrics: (tenantSchema: string, period: '1h' | '24h' | '7d' = '24h') =>
    api.get<R<{ metrics: WorkerMetricPoint[] }>>(
      `/v1/admin/workers/${tenantSchema}/metrics?period=${period}`,
    ).then((r) => r.data.metrics),

  // ── Plans ─────────────────────────────────────────────────────────────────

  getPlans: () =>
    api.get<R<{ plans: Plan[] }>>('/v1/admin/plans').then((r) => r.data.plans),

  createPlan: (data: Partial<Plan>) =>
    api.post<R<{ plan: Plan }>>('/v1/admin/plans', data).then((r) => r.data.plan),

  updatePlan: (id: string, data: Partial<Plan>) =>
    api.patch<R<{ updated: boolean }>>(`/v1/admin/plans/${id}`, data).then((r) => r.data),

  getPlanTenants: (id: string) =>
    api.get<R<{ tenants: Tenant[] }>>(`/v1/admin/plans/${id}/tenants`)
      .then((r) => r.data.tenants),

  // ── Feature Flags ─────────────────────────────────────────────────────────

  getFeatureFlags: () =>
    api.get<R<{ flags: FeatureFlag[] }>>('/v1/admin/feature-flags').then((r) => r.data.flags),

  updateFeatureFlag: (key: string, value: boolean) =>
    api.patch<R<{ updated: boolean }>>(`/v1/admin/feature-flags/${key}`, { value })
      .then((r) => r.data),

  getTenantFeatureFlags: (tenantId: string) =>
    api.get<R<{ flags: Record<string, boolean> }>>(
      `/v1/admin/feature-flags/tenant/${tenantId}`,
    ).then((r) => r.data.flags),

  updateTenantFeatureFlag: (tenantId: string, key: string, value: boolean) =>
    api.patch<R<{ updated: boolean }>>(
      `/v1/admin/feature-flags/tenant/${tenantId}`,
      { key, value },
    ).then((r) => r.data),

  // ── Tickets ───────────────────────────────────────────────────────────────

  getTickets: (params?: { status?: string; priority?: string; page?: number }) => {
    const qs = new URLSearchParams()
    if (params?.status) qs.set('status', params.status)
    if (params?.priority) qs.set('priority', params.priority)
    if (params?.page) qs.set('page', String(params.page))
    return api.get<R<Paginated<SupportTicket>>>(`/v1/admin/tickets?${qs}`).then((r) => r.data)
  },

  getTicket: (id: string) =>
    api.get<R<{ ticket: SupportTicket & { messages: TicketMessage[] } }>>(
      `/v1/admin/tickets/${id}`,
    ).then((r) => r.data.ticket),

  replyTicket: (id: string, content: string, isInternal: boolean) =>
    api.post<R<{ message_id: string }>>(`/v1/admin/tickets/${id}/reply`, {
      content,
      is_internal: isInternal,
    }).then((r) => r.data),

  updateTicket: (id: string, data: Partial<SupportTicket>) =>
    api.patch<R<{ updated: boolean }>>(`/v1/admin/tickets/${id}`, data).then((r) => r.data),

  getTicketStats: () =>
    api.get<R<{ stats: Record<string, number> }>>('/v1/admin/tickets/stats')
      .then((r) => r.data.stats),

  // ── Audit Log ─────────────────────────────────────────────────────────────

  getAuditLog: (params?: {
    tenant_id?: string; action?: string; date_from?: string; date_to?: string; page?: number
  }) => {
    const qs = new URLSearchParams()
    if (params?.tenant_id) qs.set('tenant_id', params.tenant_id)
    if (params?.action) qs.set('action', params.action)
    if (params?.date_from) qs.set('date_from', params.date_from)
    if (params?.date_to) qs.set('date_to', params.date_to)
    if (params?.page) qs.set('page', String(params.page))
    return api.get<R<Paginated<AuditEntry>>>(`/v1/admin/audit-log?${qs}`).then((r) => r.data)
  },

  exportAuditLog: (params?: { tenant_id?: string; action?: string }) => {
    const qs = new URLSearchParams()
    if (params?.tenant_id) qs.set('tenant_id', params.tenant_id)
    if (params?.action) qs.set('action', params.action)
    return api.downloadBlob(`/v1/admin/audit-log/export?${qs}`)
  },

  // ── Announcements ─────────────────────────────────────────────────────────

  getAnnouncements: () =>
    api.get<R<{ announcements: Announcement[] }>>('/v1/admin/announcements')
      .then((r) => r.data.announcements),

  createAnnouncement: (data: Partial<Announcement>) =>
    api.post<R<{ announcement: Announcement }>>('/v1/admin/announcements', data)
      .then((r) => r.data.announcement),

  updateAnnouncement: (id: string, data: Partial<Announcement>) =>
    api.patch<R<{ updated: boolean }>>(`/v1/admin/announcements/${id}`, data).then((r) => r.data),

  deleteAnnouncement: (id: string) =>
    api.delete<R<{ deleted: boolean }>>(`/v1/admin/announcements/${id}`).then((r) => r.data),

  // ── Health ────────────────────────────────────────────────────────────────

  getPlatformHealth: () =>
    api.get<R<PlatformHealth>>('/v1/admin/health/platform').then((r) => r.data),

  // ── Versions ──────────────────────────────────────────────────────────────

  getVersions: () =>
    api.get<R<{ versions: SystemVersion[] }>>('/v1/admin/versions')
      .then((r) => r.data.versions),

  createVersion: (data: { version: string; version_type: VersionType; title: string; description?: string }) =>
    api.post<R<{ version_id: string; version: string }>>('/v1/admin/versions', data)
      .then((r) => r.data),

  getVersion: (id: string) =>
    api.get<R<{ version: SystemVersion }>>(`/v1/admin/versions/${id}`)
      .then((r) => r.data.version),

  rollbackVersion: (id: string) =>
    api.post<R<{ rolled_back_to: string; tenants_restored: number }>>(
      `/v1/admin/versions/${id}/rollback`, { confirm: true }
    ).then((r) => r.data),

  // ── Changelog ─────────────────────────────────────────────────────────────

  getChangelog: (params?: {
    category?: string; importance?: string; affected_area?: string
    version_id?: string; page?: number; per_page?: number
  }) => {
    const qs = new URLSearchParams()
    if (params?.category) qs.set('category', params.category)
    if (params?.importance) qs.set('importance', params.importance)
    if (params?.affected_area) qs.set('affected_area', params.affected_area)
    if (params?.version_id) qs.set('version_id', params.version_id)
    if (params?.page) qs.set('page', String(params.page))
    if (params?.per_page) qs.set('per_page', String(params.per_page))
    return api.get<R<Paginated<ChangelogEntry> & { page: number; per_page: number }>>(
      `/v1/admin/changelog?${qs}`
    ).then((r) => r.data)
  },

  createChangelogEntry: (data: {
    title: string; category?: string; importance?: string
    description?: string; affected_area?: string; version_id?: string
  }) =>
    api.post<R<{ id: string }>>('/v1/admin/changelog', data).then((r) => r.data),

  // ── Retention Tiers (task-047) ────────────────────────────────────────────

  getCameraRetention: (cameraId: string) =>
    api.get<R<CameraRetention>>(`/cameras/${cameraId}/retention`).then((r) => r.data),

  setCameraRetention: (cameraId: string, retentionDays: number | null) =>
    api.put<R<CameraRetention>>(`/cameras/${cameraId}/retention`, {
      retention_days: retentionDays,
    }).then((r) => r.data),

  getTenantRetention: () =>
    api.get<R<TenantRetention>>('/cameras/tenant/retention').then((r) => r.data),

  setTenantRetention: (retentionDays: number) =>
    api.put<R<TenantRetention>>('/cameras/tenant/retention', {
      retention_days: retentionDays,
    }).then((r) => r.data),
}
