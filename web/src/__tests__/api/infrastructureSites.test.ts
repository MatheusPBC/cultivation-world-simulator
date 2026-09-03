import { describe, expect, it } from 'vitest'
import { normalizeMapResponse } from '@/api/mappers/world'
import type { InfrastructureSiteDTO, MapResponseDTO } from '@/types/api'

const site: InfrastructureSiteDTO = {
  id: 'bridge:north-gate',
  kind: 'bridge',
  name: 'Ponte do Portão Norte',
  cell_refs: [[1, 0], [1, 1]],
  region_ids: [1, 2],
  route_ids: ['route-1'],
  water_body_ids: ['river-1'],
  capability_ids: ['land_transport'],
  owner_ref: { kind: 'organization', id: 'sect:1' },
  maintainer_ref: null,
  integrity: 0.72,
  enabled: true,
  status: 'impaired',
  x: 1,
  y: 0,
  clickable: true,
  last_event_id: 'event-bridge-1',
}

function mapWith(overrides: Partial<MapResponseDTO> = {}): MapResponseDTO {
  return {
    width: 2,
    height: 2,
    data: [['PLAIN', 'WATER'], ['PLAIN', 'PLAIN']],
    territory_rows: [[1, 2], [1, 2]],
    routes: [{
      id: 'route-1',
      endpoint_region_ids: [1, 2],
      mode: 'road',
      capacity: 120,
      operational_capacity: 69.12,
      quality: 0.8,
      enabled: true,
      allowed_resource_ids: ['grain'],
      dependency_site_ids: [site.id],
    }],
    geography: {
      elevation_rows: [[0, 0], [0, 0]],
      water_bodies: [{
        id: 'river-1',
        kind: 'river',
        cell_refs: [[1, 0]],
        navigable: true,
        flow_direction: [0, 1],
      }],
    },
    regions: [
      { id: 1, name: 'Origem', x: 0, y: 0, type: 'city' },
      { id: 2, name: 'Destino', x: 1, y: 0, type: 'city' },
    ],
    infrastructure_sites: [site],
    ...overrides,
  }
}

describe('infrastructure site public mapper', () => {
  it('maps the complete canonical site without losing references or status', () => {
    const result = normalizeMapResponse(mapWith())

    expect(result.infrastructureSites).toEqual([{
      id: site.id,
      kind: site.kind,
      name: site.name,
      cellRefs: [[1, 0], [1, 1]],
      regionIds: [1, 2],
      routeIds: ['route-1'],
      waterBodyIds: ['river-1'],
      capabilityIds: ['land_transport'],
      ownerRef: { kind: 'organization', id: 'sect:1' },
      maintainerRef: null,
      integrity: 0.72,
      enabled: true,
      status: 'impaired',
      x: 1,
      y: 0,
      clickable: true,
      lastEventId: 'event-bridge-1',
    }])
  })

  it.each([
    ['site sem id', { infrastructure_sites: [{ ...site, id: '' }] }],
    ['célula fora do mapa', { infrastructure_sites: [{ ...site, cell_refs: [[9, 0]] }] }],
    ['região inexistente', { infrastructure_sites: [{ ...site, region_ids: [99] }] }],
    ['rota inexistente', { infrastructure_sites: [{ ...site, route_ids: ['missing'] }] }],
    ['corpo d’água inexistente', { infrastructure_sites: [{ ...site, water_body_ids: ['missing'] }] }],
    ['integridade inválida', { infrastructure_sites: [{ ...site, integrity: 1.1 }] }],
    ['status inválido', { infrastructure_sites: [{ ...site, status: 'unknown' }] }],
    ['dependência de rota divergente', { routes: [{
      ...mapWith().routes[0],
      dependency_site_ids: [],
    }] }],
  ])('rejeita %s', (_label, override) => {
    expect(() => normalizeMapResponse(mapWith(override as Partial<MapResponseDTO>)))
      .toThrow('Resposta pública do mapa inválida')
  })

  it('rejects a response without the canonical site collection', () => {
    const input = mapWith()
    delete (input as Partial<MapResponseDTO>).infrastructure_sites

    expect(() => normalizeMapResponse(input)).toThrow('Resposta pública do mapa inválida')
  })
})
