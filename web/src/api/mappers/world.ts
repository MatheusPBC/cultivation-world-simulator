import type {
  InitialStateDTO,
  MapRenderConfigDTO,
  MapResponseDTO,
  PhenomenonDTO,
  RankingsDTO,
  RankingAvatarDTO,
  RankingSectDTO,
  TournamentSummaryDTO,
} from '@/types/api'
import type {
  AvatarSummary,
  CelestialPhenomenon,
  PhysicalGeographySnapshot,
  InfrastructureSiteSummary,
  POISummary,
  RegionSummary,
  RouteSummary,
} from '@/types/core'

export interface WorldStateSnapshot {
  status: InitialStateDTO['status']
  year: number
  month: number
  avatars: AvatarSummary[]
  events: NonNullable<InitialStateDTO['events']>
  phenomenon: CelestialPhenomenon | null
  activeDomains: NonNullable<InitialStateDTO['active_domains']>
  worldRevision: number
}

export interface WorldMapSnapshot {
  mapId: string
  mapName: string
  presetVersion: number
  width: number
  height: number
  data: MapResponseDTO['data']
  territoryRows: number[][]
  routes: RouteSummary[]
  geography: PhysicalGeographySnapshot
  infrastructureSites: InfrastructureSiteSummary[]
  regions: RegionSummary[]
  pois: POISummary[]
  renderConfig: MapRenderConfigDTO
}

export function normalizeMapRenderConfig(config?: MapRenderConfigDTO): MapRenderConfigDTO {
  return {
    water_speed: config?.water_speed ?? 'high',
    cloud_frequency: config?.cloud_frequency ?? 'none',
  }
}

export function normalizeInitialState(input: InitialStateDTO): WorldStateSnapshot {
  return {
    status: input.status,
    year: input.year,
    month: input.month,
    avatars: Array.isArray(input.avatars)
      ? input.avatars.map((avatar) => ({
          ...avatar,
          name: avatar.name ?? '',
        }))
      : [],
    events: Array.isArray(input.events) ? input.events : [],
    phenomenon: input.phenomenon ?? null,
    activeDomains: Array.isArray(input.active_domains) ? input.active_domains : [],
    worldRevision: input.world_revision ?? 0,
  }
}

function invalidMapResponse(reason: string): never {
  throw new Error(`Resposta pública do mapa inválida: ${reason}`)
}

const PHYSICAL_TERRAIN_TYPES = new Set([
  'PLAIN',
  'WATER',
  'SEA',
  'MOUNTAIN',
  'FOREST',
  'DESERT',
  'RAINFOREST',
  'GLACIER',
  'SNOW_MOUNTAIN',
  'VOLCANO',
  'GRASSLAND',
  'SWAMP',
  'FARM',
  'ISLAND',
  'BAMBOO',
  'GOBI',
  'TUNDRA',
  'MARSH',
])
const WATER_TERRAIN_TYPES = new Set(['WATER', 'SEA', 'MARSH'])
const WATER_BODY_KINDS = new Set(['river', 'lake', 'sea'])

function validateMatrix(
  matrix: unknown,
  name: string,
  expectedHeight?: number,
  expectedWidth?: number,
  isValidCell?: (cell: unknown) => boolean,
): asserts matrix is unknown[][] {
  if (!Array.isArray(matrix)) invalidMapResponse(`${name} deve ser uma matriz`)
  if (expectedHeight !== undefined && matrix.length !== expectedHeight) {
    invalidMapResponse(`a altura de ${name} não corresponde ao terreno`)
  }
  const width = expectedWidth ?? (Array.isArray(matrix[0]) ? matrix[0].length : 0)
  if (matrix.some(row => !Array.isArray(row) || row.length !== width)) {
    invalidMapResponse(`${name} deve ser retangular e ter a mesma largura do terreno`)
  }
  if (isValidCell && matrix.some(row => (row as unknown[]).some(cell => !isValidCell(cell)))) {
    invalidMapResponse(`${name} contém uma célula inválida`)
  }
}

function validateMapResponse(input: MapResponseDTO): void {
  validateMatrix(
    input.data,
    'data',
    undefined,
    undefined,
    cell => typeof cell === 'string' && PHYSICAL_TERRAIN_TYPES.has(cell),
  )
  const height = input.data.length
  const width = input.data[0]?.length ?? 0
  if (width <= 0 || height <= 0) invalidMapResponse('o terreno deve ter largura e altura positivas')
  if (input.width !== undefined && (!Number.isInteger(input.width) || input.width !== width)) {
    invalidMapResponse('a largura declarada não corresponde ao terreno')
  }
  if (input.height !== undefined && (!Number.isInteger(input.height) || input.height !== height)) {
    invalidMapResponse('a altura declarada não corresponde ao terreno')
  }

  if (!Array.isArray(input.regions)) invalidMapResponse('regions deve ser uma lista')
  const regionIds = new Set<string>()
  for (const region of input.regions) {
    const id = String(region?.id ?? '')
    const numericId = Number(id)
    if (
      !id
      || !Number.isInteger(numericId)
      || numericId <= 0
      || regionIds.has(id)
      || typeof region.name !== 'string'
      || typeof region.type !== 'string'
      || !Number.isInteger(region.x)
      || !Number.isInteger(region.y)
      || region.x < 0
      || region.x >= width
      || region.y < 0
      || region.y >= height
    ) {
      invalidMapResponse('os dados de uma região são inválidos')
    }
    regionIds.add(id)
  }

  validateMatrix(
    input.territory_rows,
    'territory_rows',
    height,
    width,
    cell => Number.isInteger(cell) && (cell === -1 || regionIds.has(String(cell))),
  )
  validateMatrix(
    input.geography?.elevation_rows,
    'geography.elevation_rows',
    height,
    width,
    cell => (
      typeof cell === 'number'
      && Number.isFinite(cell)
      && cell >= -12_000
      && cell <= 10_000
    ),
  )

  if (!Array.isArray(input.geography?.water_bodies)) {
    invalidMapResponse('geography.water_bodies deve ser uma lista')
  }
  const waterBodyIds = new Set<string>()
  for (const body of input.geography.water_bodies) {
    if (
      !body
      || typeof body.id !== 'string'
      || !body.id
      || waterBodyIds.has(body.id)
      || typeof body.kind !== 'string'
      || !WATER_BODY_KINDS.has(body.kind)
    ) {
      invalidMapResponse('a identidade de um corpo d’água é inválida')
    }
    waterBodyIds.add(body.id)
    if (typeof body.navigable !== 'boolean' || !Array.isArray(body.cell_refs) || !body.cell_refs.length) {
      invalidMapResponse(`o corpo d’água ${body.id} está incompleto`)
    }
    if (body.region_id !== undefined && !regionIds.has(String(body.region_id))) {
      invalidMapResponse(`o corpo d’água ${body.id} aponta para uma região inexistente`)
    }
    const flowDirectionIsValid = body.flow_direction !== undefined
      && Array.isArray(body.flow_direction)
      && body.flow_direction.length === 2
      && body.flow_direction.every(value => Number.isInteger(value) && value >= -1 && value <= 1)
      && Math.hypot(body.flow_direction[0], body.flow_direction[1]) > 0
    if (
      (body.kind === 'river' && !flowDirectionIsValid)
      || (body.kind !== 'river' && body.flow_direction !== undefined)
    ) {
      invalidMapResponse(`o corpo d’água ${body.id} possui direção de fluxo inválida`)
    }
    const seenCells = new Set<string>()
    for (const cell of body.cell_refs) {
      if (
        !Array.isArray(cell)
        || cell.length !== 2
        || !Number.isInteger(cell[0])
        || !Number.isInteger(cell[1])
        || cell[0] < 0
        || cell[0] >= width
        || cell[1] < 0
        || cell[1] >= height
        || seenCells.has(`${cell[0]}:${cell[1]}`)
        || !WATER_TERRAIN_TYPES.has(input.data[cell[1]][cell[0]])
      ) {
        invalidMapResponse(`o corpo d’água ${body.id} possui uma célula inválida`)
      }
      seenCells.add(`${cell[0]}:${cell[1]}`)
    }
  }

  if (!Array.isArray(input.routes)) invalidMapResponse('routes deve ser uma lista')
  const routeIds = new Set<string>()
  for (const route of input.routes) {
    if (
      !route
      || typeof route.id !== 'string'
      || !route.id
      || routeIds.has(route.id)
      || !Array.isArray(route.endpoint_region_ids)
      || route.endpoint_region_ids.length !== 2
      || !route.endpoint_region_ids.every(Number.isInteger)
      || route.endpoint_region_ids[0] === route.endpoint_region_ids[1]
      || !route.endpoint_region_ids.every(id => regionIds.has(String(id)))
      || typeof route.mode !== 'string'
      || !route.mode
      || !Number.isFinite(route.capacity)
      || route.capacity < 0
      || !Number.isFinite(route.operational_capacity)
      || route.operational_capacity < 0
      || !Number.isFinite(route.quality)
      || route.quality < 0
      || route.quality > 1
      || typeof route.enabled !== 'boolean'
      || !Array.isArray(route.allowed_resource_ids)
      || !route.allowed_resource_ids.every(id => typeof id === 'string' && id.length > 0)
      || !Array.isArray(route.dependency_site_ids)
      || !route.dependency_site_ids.every(id => typeof id === 'string' && id.length > 0)
    ) {
      invalidMapResponse('os dados de uma rota são inválidos')
    }
    routeIds.add(route.id)
  }

  if (!Array.isArray(input.infrastructure_sites)) {
    invalidMapResponse('infrastructure_sites deve ser uma lista')
  }
  const siteIds = new Set<string>()
  for (const site of input.infrastructure_sites) {
    if (
      !site
      || typeof site.id !== 'string'
      || !site.id
      || siteIds.has(site.id)
      || typeof site.kind !== 'string'
      || !site.kind
      || typeof site.name !== 'string'
      || !Array.isArray(site.cell_refs)
      || site.cell_refs.length === 0
      || !Array.isArray(site.region_ids)
      || site.region_ids.length === 0
      || !site.region_ids.every(id => Number.isInteger(id) && regionIds.has(String(id)))
      || !Array.isArray(site.route_ids)
      || !site.route_ids.every(id => typeof id === 'string' && routeIds.has(id))
      || !Array.isArray(site.water_body_ids)
      || !site.water_body_ids.every(id => typeof id === 'string' && waterBodyIds.has(id))
      || !Array.isArray(site.capability_ids)
      || !site.capability_ids.every(id => typeof id === 'string' && id.length > 0)
      || !validEntityReference(site.owner_ref)
      || !validEntityReference(site.maintainer_ref)
      || typeof site.integrity !== 'number'
      || !Number.isFinite(site.integrity)
      || site.integrity < 0
      || site.integrity > 1
      || typeof site.enabled !== 'boolean'
      || !['active', 'impaired', 'destroyed'].includes(site.status)
      || !Number.isInteger(site.x)
      || !Number.isInteger(site.y)
      || site.x < 0
      || site.x >= width
      || site.y < 0
      || site.y >= height
      || typeof site.clickable !== 'boolean'
      || !(site.last_event_id === null || (typeof site.last_event_id === 'string' && site.last_event_id.length > 0))
    ) {
      invalidMapResponse('os dados de um site de infraestrutura são inválidos')
    }
    siteIds.add(site.id)
    const seenCells = new Set<string>()
    for (const cell of site.cell_refs) {
      if (
        !Array.isArray(cell)
        || cell.length !== 2
        || !Number.isInteger(cell[0])
        || !Number.isInteger(cell[1])
        || cell[0] < 0
        || cell[0] >= width
        || cell[1] < 0
        || cell[1] >= height
        || seenCells.has(`${cell[0]}:${cell[1]}`)
      ) {
        invalidMapResponse(`o site de infraestrutura ${site.id} possui uma célula inválida`)
      }
      seenCells.add(`${cell[0]}:${cell[1]}`)
    }
  }
  for (const route of input.routes) {
    if (!route.dependency_site_ids.every(id => siteIds.has(id))) {
      invalidMapResponse(`a rota ${route.id} referencia um site de infraestrutura desconhecido`)
    }
    const actualDependencyIds = input.infrastructure_sites
      .filter(site => site.route_ids.includes(route.id))
      .map(site => site.id)
      .sort()
    const declaredDependencyIds = [...route.dependency_site_ids].sort()
    if (
      actualDependencyIds.length !== declaredDependencyIds.length
      || actualDependencyIds.some((id, index) => id !== declaredDependencyIds[index])
    ) {
      invalidMapResponse(`as dependências da rota ${route.id} não correspondem aos sites projetados`)
    }
  }
}

function validEntityReference(value: unknown): boolean {
  return value === null || (
    typeof value === 'object'
    && value !== null
    && typeof (value as { kind?: unknown }).kind === 'string'
    && (value as { kind: string }).kind.length > 0
    && typeof (value as { id?: unknown }).id === 'string'
    && (value as { id: string }).id.length > 0
  )
}

export function normalizeMapResponse(input: MapResponseDTO): WorldMapSnapshot {
  validateMapResponse(input)
  const geography: PhysicalGeographySnapshot = {
    elevationRows: input.geography.elevation_rows.map(row => [...row]),
    waterBodies: input.geography.water_bodies.map((body) => ({
          id: String(body.id),
          kind: body.kind,
          cellRefs: body.cell_refs.map(cell => [...cell] as [number, number]),
          navigable: Boolean(body.navigable),
          ...(body.region_id === undefined ? {} : { regionId: body.region_id }),
          ...(body.flow_direction === undefined
            ? {}
            : { flowDirection: [...body.flow_direction] as [number, number] }),
        })),
  }

  return {
    mapId: input.map_id ?? 'classic',
    mapName: input.map_name ?? '',
    presetVersion: input.preset_version ?? 1,
    width: input.width ?? input.data?.[0]?.length ?? 0,
    height: input.height ?? input.data?.length ?? 0,
    data: input.data.map(row => [...row]),
    territoryRows: input.territory_rows.map(row => [...row]),
    routes: input.routes.map((route): RouteSummary => ({
      id: route.id,
      endpointRegionIds: [...route.endpoint_region_ids],
      mode: route.mode,
      capacity: route.capacity,
      operationalCapacity: route.operational_capacity,
      quality: route.quality,
      enabled: route.enabled,
      allowedResourceIds: [...route.allowed_resource_ids],
      dependencySiteIds: [...route.dependency_site_ids],
    })),
    infrastructureSites: input.infrastructure_sites.map((site): InfrastructureSiteSummary => ({
      id: site.id,
      kind: site.kind,
      name: site.name,
      cellRefs: site.cell_refs.map(cell => [...cell] as [number, number]),
      regionIds: [...site.region_ids],
      routeIds: [...site.route_ids],
      waterBodyIds: [...site.water_body_ids],
      capabilityIds: [...site.capability_ids],
      ownerRef: site.owner_ref ? { ...site.owner_ref } : null,
      maintainerRef: site.maintainer_ref ? { ...site.maintainer_ref } : null,
      integrity: site.integrity,
      enabled: site.enabled,
      status: site.status,
      x: site.x,
      y: site.y,
      clickable: site.clickable,
      lastEventId: site.last_event_id,
    })),
    geography,
    regions: input.regions.map((region) => ({
      ...region,
      id: String(region.id),
    })),
    pois: Array.isArray(input.pois)
      ? input.pois.map((poi) => ({
          ...poi,
          id: String(poi.id),
          icon_key: poi.icon_key ?? '',
          clickable: poi.clickable ?? true,
        }))
      : [],
    renderConfig: normalizeMapRenderConfig(input.render_config),
  }
}

export function normalizePhenomenaList(
  input: { phenomena?: PhenomenonDTO[] } | null | undefined,
): CelestialPhenomenon[] {
  return Array.isArray(input?.phenomena) ? input.phenomena : []
}

function normalizeAvatarRankList(list: RankingAvatarDTO[] | undefined): RankingAvatarDTO[] {
  return Array.isArray(list) ? list : []
}

function normalizeSectRankList(list: RankingSectDTO[] | undefined): RankingSectDTO[] {
  return Array.isArray(list) ? list : []
}

function normalizeTournament(tournament?: TournamentSummaryDTO): TournamentSummaryDTO | undefined {
  if (!tournament) return undefined
  return {
    next_year: tournament.next_year ?? 0,
    heaven_first: tournament.heaven_first,
    earth_first: tournament.earth_first,
    human_first: tournament.human_first,
  }
}

export function normalizeRankingsResponse(input: Partial<RankingsDTO> | null | undefined): RankingsDTO {
  return {
    heaven: normalizeAvatarRankList(input?.heaven),
    earth: normalizeAvatarRankList(input?.earth),
    human: normalizeAvatarRankList(input?.human),
    sect: normalizeSectRankList(input?.sect),
    tournament: normalizeTournament(input?.tournament),
  }
}
