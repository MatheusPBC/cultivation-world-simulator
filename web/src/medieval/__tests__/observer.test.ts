import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { api } from '../api'
import { useObserverStore } from '../stores/world'
import { acceptSnapshot, mapProjection } from '../mappers'
import type { MapView, ObservatoryView } from '../../types/medieval-api'
import world from './world.json'

beforeEach(() => { setActivePinia(createPinia()); vi.restoreAllMocks() })

it.each(['stock', 'resource', 'target'])('rejects an invalid supply %s before publishing the snapshot', (invalid) => {
  const data = structuredClone(world) as ObservatoryView
  const objective = data.governance.objectives[0]!
  if (invalid === 'stock') objective.stock_id = 'missing'
  else if (invalid === 'resource') objective.resource_id = 'missing'
  else Reflect.deleteProperty(objective, 'target_quantity')
  expect(() => acceptSnapshot(data)).toThrow()
})

it('rejects a snapshot without the canonical campaign threat projection', () => {
  const data = structuredClone(world) as ObservatoryView
  Reflect.deleteProperty(data.campaigns, 'threats')
  expect(() => acceptSnapshot(data)).toThrow('incompleto')
})

describe('observer transport', () => {
  it('returns typed failure instead of treating failed save as success', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({
      ok: false, error: { code: 'SAVE_EXISTS', message: 'Já existe.' }, revision: 2,
    }), { status: 409 })))
    await expect(api.command('save', { save_id: 'ano' })).rejects.toMatchObject({ code: 'SAVE_EXISTS' })
  })
  it('rejects a successful HTML fallback as an invalid API response', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('<html>app</html>')))
    await expect(api.query('status')).rejects.toMatchObject({ code: 'INVALID_RESPONSE' })
  })
})

describe('snapshot publication', () => {
  it('does not hide a failed initial snapshot behind a successful status query', async () => {
    const store = useObserverStore()
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      if (url.endsWith('/status')) return new Response(JSON.stringify({ok:true,revision:1,data:{...world.status,ready:true}}))
      throw new Error('offline')
    }))
    await store.boot()
    expect(store.snapshot).toBeNull()
    expect(store.error?.code).toBe('NETWORK_ERROR')
  })
  it('preserves the last coherent snapshot on network failure', async () => {
    const store = useObserverStore()
    const snapshot = structuredClone(world) as ObservatoryView
    snapshot.world.day = 30
    store.snapshot = snapshot
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('offline') }))
    await store.refresh()
    expect(store.snapshot?.world.day).toBe(30)
    expect(store.error?.code).toBe('NETWORK_ERROR')
  })
  it('ignores an older response that completes after a newer refresh', async () => {
    const store = useObserverStore()
    let complete!: (r: Response) => void
    const reply = (day: number) => new Response(JSON.stringify({ ok: true, revision: day,
      data: { ...world, world: { ...world.world, day } } }))
    vi.stubGlobal('fetch', vi.fn().mockImplementationOnce(() => new Promise<Response>(r => { complete = r }))
      .mockImplementationOnce(async () => reply(60)))
    const first = store.refresh()
    await store.refresh()
    complete(reply(30))
    await first
    expect(store.snapshot?.world.day).toBe(60)
  })
})

it('projects only explicit routes, retaining operational capacity from the server', () => {
  const map = { width: 2, height: 1, region_rows: [[1, 2]],
    geography: { terrain_rows: [['water', 'plain']], elevation_rows: [[0, 50]], water_bodies: [] },
    settlements: [{ id: 'a', region_id: 1, center: [0, 0] }, { id: 'b', region_id: 2, center: [1, 0] }],
    routes: [{ route: { id: 'road', endpoint_region_ids: [1, 2], mode: 'road', enabled: true },
      operational_capacity: 17 }], sites: [] } as unknown as MapView
  const projected = mapProjection(map)
  expect(projected.cells[0]).toMatchObject({ terrain: 'water', regionId: 1 })
  expect(projected.routes).toHaveLength(1)
  expect(projected.routes[0]).toMatchObject({ capacity: 17, from: [0.5, 0.5], to: [1.5, 0.5] })
  expect(mapProjection({ ...map, routes: [] }).routes).toEqual([])
})
