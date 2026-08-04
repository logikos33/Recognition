/**
 * Coletor de câmeras cross-tenant (bug liveview-contexto-visivel).
 *
 * GET /cameras/{id}/stream/info aplica C-01 e devolve 404 quando a câmera é
 * de outro tenant — indistinguível de câmera offline/inexistente pro
 * usuário. resolveCrossTenantCamera consulta /v1/admin/inventory
 * (superadmin-only) pra decidir qual dos dois é, e reporta ao store
 * compartilhado só quando confirma que a câmera existe em outro tenant.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../../services/api'
import { resolveCrossTenantCamera, useCrossTenantCamerasStore } from '../../services/crossTenantCameras'

vi.mock('../../services/api', async () => {
  const actual = await vi.importActual<typeof import('../../services/api')>('../../services/api')
  return { ...actual, api: { ...actual.api, get: vi.fn() } }
})

beforeEach(() => {
  vi.resetAllMocks()
  useCrossTenantCamerasStore.setState({ cameras: {}, tenants: [] })
})

describe('resolveCrossTenantCamera', () => {
  it('reporta ao store quando a câmera existe em outro tenant', async () => {
    vi.mocked(api.get).mockResolvedValue({
      status: 'success',
      data: {
        cameras: [
          { id: 'cam-1', tenant_id: 'tenant-rvb', tenant_name: 'RVB Isolantes', tenant_slug: 'rvb' },
        ],
      },
    })

    const isCrossTenant = await resolveCrossTenantCamera('cam-1')

    expect(isCrossTenant).toBe(true)
    expect(api.get).toHaveBeenCalledWith('/v1/admin/inventory?camera_id=cam-1')
    expect(useCrossTenantCamerasStore.getState().cameras['cam-1']).toEqual({
      cameraId: 'cam-1',
      tenantId: 'tenant-rvb',
      tenantName: 'RVB Isolantes',
    })
  })

  it('usa tenant_slug como fallback quando tenant_name vem vazio', async () => {
    vi.mocked(api.get).mockResolvedValue({
      status: 'success',
      data: { cameras: [{ id: 'cam-2', tenant_id: 'tenant-x', tenant_name: null, tenant_slug: 'tenant-x-slug' }] },
    })

    await resolveCrossTenantCamera('cam-2')

    expect(useCrossTenantCamerasStore.getState().cameras['cam-2'].tenantName).toBe('tenant-x-slug')
  })

  it('câmera de fato inexistente (inventário vazio): não reporta, retorna false', async () => {
    vi.mocked(api.get).mockResolvedValue({ status: 'success', data: { cameras: [] } })

    const isCrossTenant = await resolveCrossTenantCamera('cam-deleted')

    expect(isCrossTenant).toBe(false)
    expect(useCrossTenantCamerasStore.getState().cameras['cam-deleted']).toBeUndefined()
  })

  it('falha de rede/403 (não-superadmin): best-effort, resolve false sem lançar', async () => {
    vi.mocked(api.get).mockRejectedValue(new Error('Sem permissao para esta acao.'))

    await expect(resolveCrossTenantCamera('cam-3')).resolves.toBe(false)
    expect(useCrossTenantCamerasStore.getState().cameras['cam-3']).toBeUndefined()
  })

  it('agrupa por tenant — várias câmeras do mesmo tenant contam uma vez em tenants', async () => {
    vi.mocked(api.get)
      .mockResolvedValueOnce({
        status: 'success',
        data: { cameras: [{ id: 'cam-a', tenant_id: 'tenant-rvb', tenant_name: 'RVB Isolantes' }] },
      })
      .mockResolvedValueOnce({
        status: 'success',
        data: { cameras: [{ id: 'cam-b', tenant_id: 'tenant-rvb', tenant_name: 'RVB Isolantes' }] },
      })

    await resolveCrossTenantCamera('cam-a')
    await resolveCrossTenantCamera('cam-b')

    const tenants = useCrossTenantCamerasStore.getState().tenants
    expect(tenants).toHaveLength(1)
    expect(tenants[0]).toMatchObject({ tenantId: 'tenant-rvb', cameraCount: 2 })
  })

  it('distingue tenants diferentes — um item por tenant em `tenants`', async () => {
    vi.mocked(api.get)
      .mockResolvedValueOnce({
        status: 'success',
        data: { cameras: [{ id: 'cam-a', tenant_id: 'tenant-rvb', tenant_name: 'RVB Isolantes' }] },
      })
      .mockResolvedValueOnce({
        status: 'success',
        data: { cameras: [{ id: 'cam-c', tenant_id: 'tenant-outro', tenant_name: 'Outro Cliente' }] },
      })

    await resolveCrossTenantCamera('cam-a')
    await resolveCrossTenantCamera('cam-c')

    const tenants = useCrossTenantCamerasStore.getState().tenants
    expect(tenants).toHaveLength(2)
    expect(tenants.map((t) => t.tenantId).sort()).toEqual(['tenant-outro', 'tenant-rvb'])
  })
})
