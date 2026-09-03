import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useMapStore } from '@/stores/map'
import type { InfrastructureSiteSummary } from '@/types/core'

const createSite = (overrides: Partial<InfrastructureSiteSummary> = {}): InfrastructureSiteSummary => ({
  id: 'bridge:1',
  kind: 'bridge',
  name: 'Ponte',
  cellRefs: [[1, 1]],
  regionIds: [1, 2],
  routeIds: ['route-1'],
  waterBodyIds: [],
  capabilityIds: ['land_transport'],
  ownerRef: null,
  maintainerRef: null,
  integrity: 1,
  enabled: true,
  status: 'active',
  x: 1,
  y: 1,
  clickable: true,
  lastEventId: null,
  ...overrides,
})

describe('map infrastructure site registry', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('loads and resets sites as a shallow keyed registry', () => {
    const store = useMapStore()
    store.infrastructureSites = new Map([['bridge:1', createSite()]])

    expect(store.infrastructureSites.get('bridge:1')?.name).toBe('Ponte')

    store.reset()

    expect(store.infrastructureSites.size).toBe(0)
  })

  it('applies upserts and removals without replacing unrelated sites', () => {
    const store = useMapStore()
    const first = createSite()
    const second = createSite({ id: 'mine:2', kind: 'mine', name: 'Mina' })
    store.infrastructureSites = new Map([[first.id, first]])

    const toDto = (value: InfrastructureSiteSummary) => ({
      id: value.id,
      kind: value.kind,
      name: value.name,
      cell_refs: value.cellRefs,
      region_ids: value.regionIds,
      route_ids: value.routeIds,
      water_body_ids: value.waterBodyIds,
      capability_ids: value.capabilityIds,
      owner_ref: value.ownerRef,
      maintainer_ref: value.maintainerRef,
      integrity: value.integrity,
      enabled: value.enabled,
      status: value.status,
      x: value.x,
      y: value.y,
      clickable: value.clickable,
      last_event_id: value.lastEventId,
    })

    store.applyInfrastructureSiteUpdates([
      { op: 'upsert', site: { ...toDto(second), status: 'destroyed', enabled: false } },
      { op: 'upsert', site: { ...toDto(first), status: 'impaired', integrity: 0.4, last_event_id: 'event-2' } },
      { op: 'remove', id: second.id },
    ])

    expect(store.infrastructureSites.size).toBe(1)
    expect(store.infrastructureSites.get(first.id)).toMatchObject({
      status: 'impaired',
      integrity: 0.4,
      lastEventId: 'event-2',
    })
  })
})
