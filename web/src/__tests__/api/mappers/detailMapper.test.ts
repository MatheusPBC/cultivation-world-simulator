import { describe, expect, it } from 'vitest'
import { mapDetailDTOToDomain } from '@/api/mappers/detailMapper'
import type { InfrastructureSiteDetailDTO, RouteDetailDTO } from '@/types/api'

describe('detail mapper', () => {
  it('maps the site detail payload from the public snake_case DTO', () => {
    const dto: InfrastructureSiteDetailDTO = {
      id: 'bridge-1',
      name: 'Ponte',
      kind: 'bridge',
      cell_refs: [[1, 2]],
      region_ids: [1, 2],
      route_ids: ['route-1'],
      water_body_ids: ['river-1'],
      capability_ids: ['land_transport'],
      owner_ref: { kind: 'sect', id: '1' },
      maintainer_ref: null,
      integrity: 0.5,
      enabled: true,
      status: 'impaired',
      x: 1,
      y: 2,
      clickable: true,
      last_event_id: 'event-1',
      desc: 'Uma ponte antiga.',
      source_event_ids: ['event-1'],
    }

    expect(mapDetailDTOToDomain(dto, 'site')).toEqual({
      id: 'bridge-1',
      name: 'Ponte',
      kind: 'bridge',
      cellRefs: [[1, 2]],
      regionIds: [1, 2],
      routeIds: ['route-1'],
      waterBodyIds: ['river-1'],
      capabilityIds: ['land_transport'],
      ownerRef: { kind: 'sect', id: '1' },
      maintainerRef: null,
      integrity: 0.5,
      enabled: true,
      status: 'impaired',
      x: 1,
      y: 2,
      clickable: true,
      lastEventId: 'event-1',
      desc: 'Uma ponte antiga.',
      sourceEventIds: ['event-1'],
    })
  })

  it('maps the complete route detail payload to the domain shape', () => {
    const dto: RouteDetailDTO = {
      id: 'route-1',
      mode: 'land',
      endpoint_region_ids: [1, 2],
      capacity: 100,
      operational_capacity: 64,
      quality: 0.8,
      enabled: true,
      allowed_resource_ids: ['grain', 'elixir'],
      dependency_site_ids: ['bridge-1'],
      source_event_ids: ['event-1'],
    }

    expect(mapDetailDTOToDomain(dto, 'route')).toEqual({
      id: 'route-1',
      mode: 'land',
      endpointRegionIds: [1, 2],
      capacity: 100,
      operationalCapacity: 64,
      quality: 0.8,
      enabled: true,
      allowedResourceIds: ['grain', 'elixir'],
      dependencySiteIds: ['bridge-1'],
      sourceEventIds: ['event-1'],
    })
  })

  it('rejects incomplete or invalid route detail payloads', () => {
    expect(() => mapDetailDTOToDomain({
      id: 'route-1',
      mode: 'land',
      endpoint_region_ids: [1, 2],
      capacity: 100,
      operational_capacity: 64,
      quality: 0.8,
      enabled: true,
      allowed_resource_ids: [],
      dependency_site_ids: [],
    } as never, 'route')).toThrow('Invalid route detail payload')

    expect(() => mapDetailDTOToDomain({
      id: 'route-1',
      mode: 'land',
      endpoint_region_ids: [1, 2],
      capacity: 100,
      operational_capacity: -1,
      quality: 0.8,
      enabled: true,
      allowed_resource_ids: [],
      dependency_site_ids: [],
      source_event_ids: [],
    } as never, 'route')).toThrow('Invalid route detail payload')

    expect(() => mapDetailDTOToDomain({
      id: 'route-1',
      mode: 'land',
      endpoint_region_ids: [1, 1],
      capacity: 100,
      operational_capacity: 81,
      quality: 0.8,
      enabled: true,
      allowed_resource_ids: [],
      dependency_site_ids: [],
      source_event_ids: [],
    } as never, 'route')).toThrow('Invalid route detail payload')
  })
})
