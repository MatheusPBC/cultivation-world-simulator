import type { InstitutionalPresenceResponseDTO } from '@/types/api'
import type {
  InstitutionalPresenceRegion,
  InstitutionalPresenceSectInfluence,
} from '@/types/core'

function invalid(reason: string): never {
  throw new Error(`Resposta de presença institucional inválida: ${reason}`)
}

function isFiniteUnitInterval(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 1
}

function isPositiveInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value > 0
}

function isFiniteNonNegative(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0
}

function isHexColor(value: unknown): value is string {
  return typeof value === 'string' && /^#[0-9a-f]{6}$/i.test(value)
}

function mapInfluence(input: unknown, regionId: number, index: number): InstitutionalPresenceSectInfluence {
  if (!input || typeof input !== 'object') invalid(`influência ${index} da região ${regionId} não é um objeto`)
  const influence = input as Record<string, unknown>
  if (
    !isPositiveInteger(influence.sect_id)
    || typeof influence.sect_name !== 'string'
    || influence.sect_name.trim().length === 0
    || !isHexColor(influence.color)
    || !isPositiveInteger(influence.owned_tile_count)
    || !isFiniteUnitInterval(influence.share)
  ) {
    invalid(`influência ${index} da região ${regionId} possui campos inválidos`)
  }

  return {
    sectId: influence.sect_id,
    sectName: influence.sect_name,
    color: influence.color,
    ownedTileCount: influence.owned_tile_count,
    share: influence.share,
  }
}

export function mapInstitutionalPresenceDTO(
  input: InstitutionalPresenceResponseDTO,
): InstitutionalPresenceRegion[] {
  if (!input || typeof input !== 'object' || !Array.isArray(input.regions)) {
    invalid('regions deve ser uma lista')
  }

  const regionIds = new Set<number>()
  return input.regions.map((rawRegion, index) => {
    if (!rawRegion || typeof rawRegion !== 'object') invalid(`região ${index} não é um objeto`)
    const region = rawRegion as unknown as Record<string, unknown>
    const regionId = region.region_id
    if (
      !isPositiveInteger(regionId)
      || regionIds.has(regionId)
      || typeof region.region_name !== 'string'
      || region.region_name.trim().length === 0
      || typeof region.region_type !== 'string'
      || region.region_type.trim().length === 0
      || !isPositiveInteger(region.tile_count)
      || !Array.isArray(region.sect_influences)
      || (region.dominant_sect_id !== null && !isPositiveInteger(region.dominant_sect_id))
    ) {
      invalid(`região ${index} possui campos inválidos`)
    }

    let governance: InstitutionalPresenceRegion['governance'] = null
    if (region.governance !== null) {
      if (!region.governance || typeof region.governance !== 'object') {
        invalid(`governança da região ${regionId} é inválida`)
      }
      const rawGovernance = region.governance as Record<string, unknown>
      if (
        typeof rawGovernance.controller_kind !== 'string'
        || rawGovernance.controller_kind.trim().length === 0
        || typeof rawGovernance.controller_id !== 'string'
        || rawGovernance.controller_id.trim().length === 0
        || !isFiniteNonNegative(rawGovernance.administrative_capacity)
      ) {
        invalid(`governança da região ${regionId} possui campos inválidos`)
      }
      governance = {
        controllerKind: rawGovernance.controller_kind,
        controllerId: rawGovernance.controller_id,
        administrativeCapacity: rawGovernance.administrative_capacity,
      }
    }

    const sectInfluences = region.sect_influences.map((influence, influenceIndex) => (
      mapInfluence(influence, regionId, influenceIndex)
    ))
    const influenceIds = new Set<number>()
    for (const influence of sectInfluences) {
      if (influenceIds.has(influence.sectId)) {
        invalid(`a região ${regionId} repete uma seita nas influências`)
      }
      if (
        influence.ownedTileCount > region.tile_count
        || Math.abs(influence.share - (influence.ownedTileCount / region.tile_count)) > 1e-9
      ) {
        invalid(`a influência da seita ${influence.sectId} é inconsistente com a região ${regionId}`)
      }
      influenceIds.add(influence.sectId)
    }
    const influencedTileCount = sectInfluences.reduce((total, item) => total + item.ownedTileCount, 0)
    if (influencedTileCount > region.tile_count) {
      invalid(`as influências excedem as células da região ${regionId}`)
    }
    const expectedOrder = [...sectInfluences].sort((left, right) => (
      right.ownedTileCount - left.ownedTileCount || left.sectId - right.sectId
    ))
    if (expectedOrder.some((item, index) => item.sectId !== sectInfluences[index]?.sectId)) {
      invalid(`as influências da região ${regionId} não estão em ordem determinística`)
    }
    const expectedDominant = sectInfluences[0]?.sectId ?? null
    if (region.dominant_sect_id !== expectedDominant) {
      invalid(`a seita dominante da região ${regionId} é inconsistente`)
    }

    regionIds.add(regionId)
    return {
      regionId,
      regionName: region.region_name,
      regionType: region.region_type,
      tileCount: region.tile_count,
      governance,
      sectInfluences,
      dominantSectId: region.dominant_sect_id,
    }
  })
}
