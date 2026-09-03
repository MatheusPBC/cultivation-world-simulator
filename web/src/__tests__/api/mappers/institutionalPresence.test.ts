import { describe, expect, it } from 'vitest'
import { mapInstitutionalPresenceDTO } from '@/api/mappers/institutionalPresence'

const valid = {
  regions: [{
    region_id: 301,
    region_name: 'Cidade do Tianhe',
    region_type: 'city',
    tile_count: 24,
    governance: {
      controller_kind: 'dynasty',
      controller_id: 'dynasty-1',
      administrative_capacity: 0.72,
    },
    sect_influences: [{
      sect_id: 8,
      sect_name: 'Seita Azure',
      color: '#4DD0E1',
      owned_tile_count: 6,
      share: 0.25,
    }],
    dominant_sect_id: 8,
  }],
}

describe('institutional presence mapper', () => {
  it('maps governance and sect overlap without conflating the two', () => {
    expect(mapInstitutionalPresenceDTO(valid)).toEqual([{
      regionId: 301,
      regionName: 'Cidade do Tianhe',
      regionType: 'city',
      tileCount: 24,
      governance: {
        controllerKind: 'dynasty',
        controllerId: 'dynasty-1',
        administrativeCapacity: 0.72,
      },
      sectInfluences: [{
        sectId: 8,
        sectName: 'Seita Azure',
        color: '#4DD0E1',
        ownedTileCount: 6,
        share: 0.25,
      }],
      dominantSectId: 8,
    }])
  })

  it.each([
    ['regions ausente', { regions: undefined }],
    ['governança inválida', { regions: [{ ...valid.regions[0], governance: { ...valid.regions[0].governance, administrative_capacity: -1 } }] }],
    ['influência duplicada', { regions: [{ ...valid.regions[0], sect_influences: [...valid.regions[0].sect_influences, ...valid.regions[0].sect_influences] }] }],
    ['dominante ausente das influências', { regions: [{ ...valid.regions[0], dominant_sect_id: 99 }] }],
    ['contagem maior que a região', { regions: [{ ...valid.regions[0], sect_influences: [{ ...valid.regions[0].sect_influences[0], owned_tile_count: 25 }] }] }],
    ['proporção sem base mecânica', { regions: [{ ...valid.regions[0], sect_influences: [{ ...valid.regions[0].sect_influences[0], share: 0.5 }] }] }],
    ['cor sectária inválida', { regions: [{ ...valid.regions[0], sect_influences: [{ ...valid.regions[0].sect_influences[0], color: 'azul' }] }] }],
  ])('rejeita %s', (_label, override) => {
    expect(() => mapInstitutionalPresenceDTO({ ...valid, ...override } as never))
      .toThrow('Resposta de presença institucional inválida')
  })

  it('preserves an explicitly ungoverned region as null', () => {
    const result = mapInstitutionalPresenceDTO({
      regions: [{ ...valid.regions[0], governance: null, sect_influences: [], dominant_sect_id: null }],
    })
    expect(result[0].governance).toBeNull()
  })
})
