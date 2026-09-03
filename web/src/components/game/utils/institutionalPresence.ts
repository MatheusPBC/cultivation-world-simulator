import type { InstitutionalPresenceRegion, RegionSummary } from '@/types/core'

export const INSTITUTIONAL_PRESENCE_TILE_SIZE = 64

export interface InstitutionalPresenceRenderItem {
  regionId: number
  governanceColor: number
  governanceAlpha: number
  cells: Array<[number, number]>
  influenceMarkers: Array<{ color: number; share: number }>
}

function parseColor(value: string): number | null {
  const normalized = value.trim().replace(/^#/, '')
  if (!/^[0-9a-f]{6}$/i.test(normalized)) return null
  return Number.parseInt(normalized, 16)
}

function isUrban(regionType: string): boolean {
  const normalized = regionType.trim().toLowerCase()
  return normalized === 'city' || normalized === 'urban' || normalized === 'city_region'
}

function governanceColor(
  region: InstitutionalPresenceRegion,
): number {
  const governance = region.governance
  if (!governance) return 0
  if (governance.controllerKind.toLowerCase() === 'dynasty') return 0xd9aa45
  if (governance.controllerKind.toLowerCase() === 'sect') {
    const controllerId = Number(governance.controllerId)
    const sect = region.sectInfluences.find(influence => influence.sectId === controllerId)
    return sect ? (parseColor(sect.color) ?? 0x8f8a80) : 0x8f8a80
  }
  return 0x8f8a80
}

export function buildInstitutionalPresenceRenderPlan(
  presence: InstitutionalPresenceRegion[],
  regions: RegionSummary[],
  territoryRows: number[][],
  visible: boolean,
): InstitutionalPresenceRenderItem[] {
  if (!visible) return []

  const regionById = new Map(regions.map(region => [Number(region.id), region]))
  const cellsByRegion = new Map<number, Array<[number, number]>>()
  territoryRows.forEach((row, y) => row.forEach((regionId, x) => {
    if (regionId <= 0) return
    const cells = cellsByRegion.get(regionId) ?? []
    cells.push([x, y])
    cellsByRegion.set(regionId, cells)
  }))

  return presence.flatMap((region) => {
    const mapRegion = regionById.get(region.regionId)
    if (
      !mapRegion
      || !isUrban(region.regionType)
      || !isUrban(mapRegion.type)
      || !region.governance
    ) return []
    const cells = cellsByRegion.get(region.regionId) ?? []
    if (!cells.length || cells.length !== region.tileCount) return []

    const influenceMarkers = [...region.sectInfluences]
      .sort((left, right) => right.share - left.share || left.sectId - right.sectId)
      .slice(0, 3)
      .flatMap(influence => {
        const color = parseColor(influence.color)
        return color === null ? [] : [{ color, share: influence.share }]
      })

    return [{
      regionId: region.regionId,
      governanceColor: governanceColor(region),
      governanceAlpha: 0.1 + (Math.min(1, region.governance.administrativeCapacity) * 0.28),
      cells,
      influenceMarkers,
    }]
  })
}
