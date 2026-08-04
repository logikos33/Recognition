/**
 * Coletor de câmeras cross-tenant detectadas na grade de monitoramento.
 *
 * Contexto: um superadmin navegando com o próprio token (sem "assumir
 * contexto") vê a lista de câmeras vinda de outro fluxo, mas
 * GET /cameras/{id}/stream/info aplica C-01 (câmera precisa ser do tenant
 * do token) — cross-tenant vira 404, igual a câmera inexistente, de
 * propósito (não vaza existência). O CameraCell reporta aqui quando
 * confirma, via /v1/admin/inventory (superadmin-only), que a câmera 404
 * pertence a outro tenant. O banner de "assumir contexto" (MonitoringPage)
 * consome este store para oferecer o atalho em vez de deixar o superadmin
 * olhando pra um grid confuso.
 *
 * Store module-level (zustand — já usado em ui/Toast/useToast.ts, sem lib
 * nova) em vez de contexto React: CameraCell e o banner não têm relação de
 * ancestral direto garantida em todo lugar que a grade é renderizada.
 */
import { create } from 'zustand'
import { api } from './api'

export interface CrossTenantCameraEntry {
  cameraId: string
  tenantId: string
  tenantName: string
}

export interface CrossTenantTenant {
  tenantId: string
  tenantName: string
  cameraCount: number
}

interface InventoryCameraRow {
  id: string
  tenant_id?: string | null
  tenant_name?: string | null
  tenant_slug?: string | null
}

interface InventoryResponse {
  data: { cameras: InventoryCameraRow[] }
}

function computeTenants(
  cameras: Record<string, CrossTenantCameraEntry>,
): CrossTenantTenant[] {
  const map = new Map<string, CrossTenantTenant>()
  for (const cam of Object.values(cameras)) {
    const existing = map.get(cam.tenantId)
    if (existing) {
      existing.cameraCount += 1
    } else {
      map.set(cam.tenantId, { tenantId: cam.tenantId, tenantName: cam.tenantName, cameraCount: 1 })
    }
  }
  return Array.from(map.values())
}

interface CrossTenantCamerasStore {
  cameras: Record<string, CrossTenantCameraEntry>
  /** Derivado e armazenado (não recalculado no selector) — evita getSnapshot
   * instável no useSyncExternalStore do zustand. */
  tenants: CrossTenantTenant[]
  report: (entry: CrossTenantCameraEntry) => void
}

export const useCrossTenantCamerasStore = create<CrossTenantCamerasStore>((set) => ({
  cameras: {},
  tenants: [],
  report: (entry) =>
    set((s) => {
      const existing = s.cameras[entry.cameraId]
      if (existing && existing.tenantId === entry.tenantId) return s
      const cameras = { ...s.cameras, [entry.cameraId]: entry }
      return { cameras, tenants: computeTenants(cameras) }
    }),
}))

/**
 * Consulta o inventário admin p/ descobrir o tenant real de `cameraId` e,
 * se confirmado diferente do contexto atual (isto é, a câmera existe em
 * ALGUM tenant — o 404 original já garante que não é o do token atual),
 * registra no store.
 *
 * Best-effort: qualquer falha (rede, câmera de fato inexistente) resolve
 * `false` silenciosamente — o caller decide o fallback (toast genérico).
 *
 * Retorna `true` quando confirmou cross-tenant (caller deve suprimir o
 * toast genérico de "câmera não está transmitindo" para não duplicar com
 * o banner).
 */
export async function resolveCrossTenantCamera(cameraId: string): Promise<boolean> {
  try {
    const res = await api.get<InventoryResponse>(`/v1/admin/inventory?camera_id=${cameraId}`)
    const row = res.data.cameras[0]
    if (!row?.tenant_id) return false
    useCrossTenantCamerasStore.getState().report({
      cameraId,
      tenantId: row.tenant_id,
      tenantName: row.tenant_name || row.tenant_slug || 'outro tenant',
    })
    return true
  } catch {
    return false
  }
}
