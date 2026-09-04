import { computed, onMounted, onUnmounted, ref, unref, watch, type MaybeRef } from 'vue'
import { Container, Graphics, Sprite, Text, Ticker, TilingSprite } from 'pixi.js'
import { useI18n } from 'vue-i18n'
import { useTextures } from './useTextures'
import { useMapViewport } from './useMapViewport'
import { useMapStore } from '@/stores/map'
import { useUiStore } from '@/stores/ui'
import { useAudio } from '@/composables/useAudio'
import type { PhysicalGeographySnapshot, RegionSummary, RouteSummary } from '@/types/core'
import {
  MAP_BORDER,
  MAP_COAST,
  MAP_LABEL_PLATE,
  MAP_LABEL_TEXT_RESOLUTION,
  MAP_ROUTE,
  MAP_SELECTION,
  MAP_SURFACE,
  MAP_WATER_BODY,
  TERRAIN_TINT,
  TERRAIN_TINT_DEFAULT,
  TERRAIN_WASH_ALPHA,
  WATER_TINT,
  resolveLabelTier,
} from '@/constants/mapTheme'
import { getLabelCounterScale, getRegionTextStyle } from '@/utils/mapStyles'
import { buildVisibleRegionLabels, estimateRegionLabelSize } from '../utils/mapLabels'

const TILE_SIZE = 64
const WATER_TYPES = new Set(['SEA', 'WATER'])

export const MAP_LAYER_Z_INDEX = Object.freeze({
  physical: 0,
  regionPick: 90,
  selection: 120,
  sects: 150,
  institutionalPresence: 175,
  labels: 200,
})

export interface MapLayerVisibility {
  terrain: boolean
  elevation: boolean
  water: boolean
  borders: boolean
  routes: boolean
  sects: boolean
  names: boolean
  infrastructure: boolean
  institutionalPresence: boolean
}

export const DEFAULT_MAP_LAYER_VISIBILITY: MapLayerVisibility = {
  terrain: true,
  elevation: false,
  water: true,
  borders: true,
  routes: true,
  sects: true,
  names: true,
  infrastructure: true,
  institutionalPresence: true,
}

export interface MapLayerRenderInput {
  mapData: string[][]
  geography: PhysicalGeographySnapshot
  territoryRows: number[][]
  regions: RegionSummary[]
  routes: RouteSummary[]
  visibility: MapLayerVisibility
}

export type EdgeSide = 'left' | 'right' | 'top' | 'bottom'

export interface MapLayerRenderPlan {
  terrain: Array<{ x: number; y: number; type: string; tint: number }>
  elevation: Array<{ x: number; y: number; color: number; alpha: number }>
  waterBodies: Array<{
    id: string
    kind: string
    cellRefs: Array<[number, number]>
    navigable: boolean
    flowDirection?: [number, number]
  }>
  /** Land/water boundary. Gives the landmass a drawn outline. */
  coast: Array<{ x: number; y: number; side: EdgeSide }>
  borders: Array<{ x: number; y: number; side: EdgeSide }>
  routes: Array<{
    id: string
    from: { x: number; y: number }
    to: { x: number; y: number }
    mode: string
    quality: number
    capacity: number
    operationalCapacity: number
    enabled: boolean
    availability: number
  }>
}

function elevationColor(ratio: number): number {
  const normalized = Math.max(0, Math.min(1, ratio))
  // Ink-to-gold ramp, matching the palette instead of the old blue-to-orange.
  const low = { r: 32, g: 44, b: 44 }
  const high = { r: 217, g: 184, b: 119 }
  return (
    (Math.round(low.r + (high.r - low.r) * normalized) << 16)
    | (Math.round(low.g + (high.g - low.g) * normalized) << 8)
    | Math.round(low.b + (high.b - low.b) * normalized)
  )
}

function regionIdAt(rows: number[][], x: number, y: number): number {
  const value = rows[y]?.[x]
  return typeof value === 'number' && Number.isFinite(value) ? value : 0
}

function buildBorders(rows: number[][]): MapLayerRenderPlan['borders'] {
  const borders: MapLayerRenderPlan['borders'] = []
  const height = rows.length
  const width = rows[0]?.length ?? 0

  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const current = regionIdAt(rows, x, y)
      if (current <= 0) continue
      if (x === 0 || regionIdAt(rows, x - 1, y) <= 0) borders.push({ x, y, side: 'left' })
      if (y === 0 || regionIdAt(rows, x, y - 1) <= 0) borders.push({ x, y, side: 'top' })
      if (x === width - 1 || regionIdAt(rows, x + 1, y) !== current) borders.push({ x, y, side: 'right' })
      if (y === height - 1 || regionIdAt(rows, x, y + 1) !== current) borders.push({ x, y, side: 'bottom' })
    }
  }
  return borders
}

function isWater(type: string | undefined): boolean {
  return !!type && WATER_TYPES.has(type)
}

/**
 * Land cells that touch water, edge by edge. Drawing this as a weighted ink line
 * is what turns a grid of tiles into a coastline.
 */
function buildCoast(mapData: string[][]): MapLayerRenderPlan['coast'] {
  const coast: MapLayerRenderPlan['coast'] = []
  const height = mapData.length
  const width = mapData[0]?.length ?? 0

  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      if (isWater(mapData[y]?.[x])) continue
      if (x === 0 || isWater(mapData[y]?.[x - 1])) coast.push({ x, y, side: 'left' })
      if (x === width - 1 || isWater(mapData[y]?.[x + 1])) coast.push({ x, y, side: 'right' })
      if (y === 0 || isWater(mapData[y - 1]?.[x])) coast.push({ x, y, side: 'top' })
      if (y === height - 1 || isWater(mapData[y + 1]?.[x])) coast.push({ x, y, side: 'bottom' })
    }
  }
  return coast
}

function isWaterRouteMode(mode: string): boolean {
  const normalized = mode.toLowerCase()
  return ['river', 'water', 'sea', 'ferry', 'coastal'].some(token => normalized.includes(token))
}

export function terrainTint(type: string): number {
  return TERRAIN_TINT[type] ?? TERRAIN_TINT_DEFAULT
}

export function edgeToSegment(x: number, y: number, side: EdgeSide): [number, number, number, number] {
  const px = x * TILE_SIZE
  const py = y * TILE_SIZE
  const right = px + TILE_SIZE
  const bottom = py + TILE_SIZE
  if (side === 'left') return [px, py, px, bottom]
  if (side === 'right') return [right, py, right, bottom]
  if (side === 'top') return [px, py, right, py]
  return [px, bottom, right, bottom]
}

export function buildMapLayerRenderPlan(input: MapLayerRenderInput): MapLayerRenderPlan {
  const { mapData, geography, territoryRows, regions, routes, visibility } = input
  const height = mapData.length
  const width = mapData[0]?.length ?? 0
  const terrain = visibility.terrain
    ? mapData.flatMap((row, y) => row.flatMap((type, x) => (
      type === 'SEA' || type === 'WATER' || type === 'SECT'
        ? []
        : [{ x, y, type, tint: terrainTint(type) }]
    )))
    : []

  const elevationValues = geography.elevationRows.flatMap(row => row)
    .filter(value => Number.isFinite(value))
  const minElevation = elevationValues.length ? Math.min(...elevationValues) : 0
  const maxElevation = elevationValues.length ? Math.max(...elevationValues) : 0
  const elevation = visibility.elevation
    ? geography.elevationRows.flatMap((row, y) => row.flatMap((value, x) => {
      const ratio = maxElevation === minElevation ? 0.5 : (value - minElevation) / (maxElevation - minElevation)
      return [{ x, y, color: elevationColor(ratio), alpha: 0.34 }]
    }))
    : []

  const waterBodies = visibility.water
    ? geography.waterBodies.map(body => ({
      id: body.id,
      kind: body.kind,
      cellRefs: body.cellRefs.filter(([x, y]) => x >= 0 && x < width && y >= 0 && y < height),
      navigable: body.navigable,
      ...(body.flowDirection ? { flowDirection: body.flowDirection } : {}),
    }))
    : []

  const coast = visibility.water && mapData.length ? buildCoast(mapData) : []
  const borders = visibility.borders ? buildBorders(territoryRows) : []
  const anchors = new Map(regions.map(region => [String(region.id), {
    x: region.x * TILE_SIZE + TILE_SIZE / 2,
    y: region.y * TILE_SIZE + TILE_SIZE / 2,
  }]))
  const plannedRoutes = visibility.routes
    ? routes.flatMap(route => {
      const from = anchors.get(String(route.endpointRegionIds[0]))
      const to = anchors.get(String(route.endpointRegionIds[1]))
      if (!from || !to) return []
      const nominalUsableCapacity = route.capacity * route.quality
      const availability = route.enabled && nominalUsableCapacity > 0
        ? Math.max(0, Math.min(1, route.operationalCapacity / nominalUsableCapacity))
        : 0
      return [{
        id: route.id,
        from,
        to,
        mode: route.mode,
        quality: route.quality,
        capacity: route.capacity,
        operationalCapacity: route.operationalCapacity,
        enabled: route.enabled,
        availability,
      }]
    })
    : []

  return { terrain, elevation, waterBodies, coast, borders, routes: plannedRoutes }
}

export function useMapLayerRenderer(emit: {
  (e: 'mapLoaded', payload: { width: number; height: number }): void
  (e: 'regionSelected', payload: { type: 'region'; id: string; name?: string }): void
}, visibility?: MaybeRef<MapLayerVisibility | undefined>) {
  const mapContainer = ref<Container>()
  const {
    textures,
    isLoaded,
    preloadRegionTextures,
    getTileTexture,
  } = useTextures()
  const mapStore = useMapStore()
  const uiStore = useUiStore()
  const { locale } = useI18n()
  const { play } = useAudio()
  const { scale: viewportScale } = useMapViewport()

  let ticker: Ticker | null = null
  let seaLayer: TilingSprite | null = null
  let waterLayer: TilingSprite | null = null
  let renderGeneration = 0

  /** Interactive per-region territory shapes, so the land itself is clickable. */
  let regionPickLayer: Container | null = null
  /** Hover/selection feedback, redrawn independently of the expensive base map. */
  let selectionGraphics: Graphics | null = null
  /** Region names, drawn imperatively so plates and LOD stay in one place. */
  let labelLayer: Container | null = null

  const hoveredRegionId = ref<string | null>(null)

  const currentVisibility = computed(() => unref(visibility) ?? DEFAULT_MAP_LAYER_VISIBILITY)

  const selectedRegionId = computed(() => (
    uiStore.selectedTarget?.type === 'region' ? String(uiStore.selectedTarget.id) : null
  ))

  const visibleRegionLabels = computed(() =>
    currentVisibility.value.names
      ? buildVisibleRegionLabels(Array.from(mapStore.regions.values()), locale.value, {
        viewportScale: viewportScale.value,
      })
      : [],
  )

  function cleanupTicker() {
    if (ticker) {
      ticker.stop()
      ticker.destroy()
      ticker = null
    }
  }

  function clearMapContainer() {
    const container = mapContainer.value
    if (!container) return

    const oldChildren = container.removeChildren()
    oldChildren.forEach(child => {
      child.destroy({ children: true, texture: false })
    })
    seaLayer = null
    waterLayer = null
    regionPickLayer = null
    selectionGraphics = null
    labelLayer = null
  }

  function getWaterSpeed() {
    const configSpeed = mapStore.renderConfig?.water_speed || 'high'
    if (configSpeed === 'none') return 0
    if (configSpeed === 'low') return 0.1
    if (configSpeed === 'medium') return 0.3
    return 0.8
  }

  function startWaterTicker(hasSea: boolean, hasWater: boolean) {
    if (!hasSea && !hasWater) return

    ticker = new Ticker()
    ticker.add((tickerInstance: Ticker) => {
      const baseSpeed = getWaterSpeed()
      if (baseSpeed === 0) return

      const speed = baseSpeed * tickerInstance.deltaTime
      if (hasSea && seaLayer) {
        seaLayer.tilePosition.x -= speed * 0.5
        seaLayer.tilePosition.y += speed * 0.5
      }
      if (hasWater && waterLayer) {
        waterLayer.tilePosition.x += speed
        waterLayer.tilePosition.y += speed * 0.2
      }
    })
    ticker.start()
  }

  function renderGroundAndWater(rows: number, cols: number, mapWidth: number, mapHeight: number) {
    const visibilityState = currentVisibility.value
    const seaTex = textures.value.SEA_FULL || textures.value.SEA
    seaLayer = visibilityState.water ? new TilingSprite({ texture: seaTex, width: mapWidth, height: mapHeight }) : null
    seaLayer?.tileScale.set(0.5, 0.5)
    if (seaLayer) seaLayer.tint = WATER_TINT.sea
    const seaMask = new Graphics()
    if (seaLayer) seaLayer.mask = seaMask

    const waterTex = textures.value.WATER_FULL || textures.value.WATER
    waterLayer = visibilityState.water ? new TilingSprite({ texture: waterTex, width: mapWidth, height: mapHeight }) : null
    waterLayer?.tileScale.set(0.5, 0.5)
    if (waterLayer) waterLayer.tint = WATER_TINT.water
    const waterMask = new Graphics()
    if (waterLayer) waterLayer.mask = waterMask

    const groundContainer = new Container()
    let hasSea = false
    let hasWater = false

    for (let y = 0; y < rows; y++) {
      for (let x = 0; x < cols; x++) {
        const type = mapStore.mapData[y][x]
        if (type === 'SEA') {
          if (visibilityState.water) {
            seaMask.rect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
            seaMask.fill(0xffffff)
            hasSea = true
          }
          continue
        }
        if (type === 'WATER') {
          if (visibilityState.water) {
            waterMask.rect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
            waterMask.fill(0xffffff)
            hasWater = true
          }
          continue
        }
        if (!visibilityState.terrain || type === 'SECT') continue

        const tex = getTileTexture(type, x, y)
        if (!tex) {
          throw new Error(`Missing texture for tile type: ${type} at (${x}, ${y})`)
        }

        const sprite = new Sprite(tex)
        sprite.x = x * TILE_SIZE
        sprite.y = y * TILE_SIZE
        sprite.roundPixels = true
        sprite.width = TILE_SIZE
        sprite.height = TILE_SIZE
        // Collapse the saturated tile art into one tonal family.
        sprite.tint = terrainTint(type)
        sprite.eventMode = 'none'
        groundContainer.addChild(sprite)
      }
    }

    if (hasSea && seaLayer) {
      mapContainer.value?.addChild(seaLayer)
      mapContainer.value?.addChild(seaMask)
    }
    if (hasWater && waterLayer) {
      mapContainer.value?.addChild(waterLayer)
      mapContainer.value?.addChild(waterMask)
    }
    if (!hasSea) seaMask.destroy()
    if (!hasWater) waterMask.destroy()
    if (!hasSea && seaLayer) {
      seaLayer.destroy()
      seaLayer = null
    }
    if (!hasWater && waterLayer) {
      waterLayer.destroy()
      waterLayer = null
    }
    mapContainer.value?.addChild(groundContainer)

    /*
     * Colour wash over the tinted tiles. Batched into a single Graphics, so the
     * whole terrain layer costs one draw call regardless of map size.
     */
    if (visibilityState.terrain) {
      const wash = new Graphics()
      wash.eventMode = 'none'
      for (let y = 0; y < rows; y++) {
        for (let x = 0; x < cols; x++) {
          const type = mapStore.mapData[y][x]
          if (type === 'SEA' || type === 'WATER' || type === 'SECT') continue
          wash.rect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
            .fill({ color: terrainTint(type), alpha: TERRAIN_WASH_ALPHA })
        }
      }
      mapContainer.value?.addChild(wash)
    }

    startWaterTicker(hasSea, hasWater)
  }

  /**
   * Ink veil plus edge vignette. Terrain becomes ground so that structure and
   * characters can be figure.
   */
  function renderAtmosphere(mapWidth: number, mapHeight: number) {
    const container = mapContainer.value
    if (!container) return

    const veil = new Graphics()
    veil.eventMode = 'none'
    veil.rect(0, 0, mapWidth, mapHeight)
      .fill({ color: MAP_SURFACE.veilColor, alpha: MAP_SURFACE.veilAlpha })
    container.addChild(veil)

    const vignette = new Graphics()
    vignette.eventMode = 'none'
    const depth = Math.min(mapWidth, mapHeight) * MAP_SURFACE.vignetteDepth
    const bands = MAP_SURFACE.vignetteBands
    for (let index = 0; index < bands; index += 1) {
      const inset = (depth * index) / bands
      const bandDepth = depth / bands
      const alpha = MAP_SURFACE.vignetteAlpha * (1 - index / bands) / bands * 2.2
      // Four edge bands per step; stacking them yields a soft falloff without a shader.
      vignette.rect(inset, inset, mapWidth - inset * 2, bandDepth)
        .fill({ color: MAP_SURFACE.vignetteColor, alpha })
      vignette.rect(inset, mapHeight - inset - bandDepth, mapWidth - inset * 2, bandDepth)
        .fill({ color: MAP_SURFACE.vignetteColor, alpha })
      vignette.rect(inset, inset + bandDepth, bandDepth, mapHeight - (inset + bandDepth) * 2)
        .fill({ color: MAP_SURFACE.vignetteColor, alpha })
      vignette.rect(mapWidth - inset - bandDepth, inset + bandDepth, bandDepth, mapHeight - (inset + bandDepth) * 2)
        .fill({ color: MAP_SURFACE.vignetteColor, alpha })
    }
    container.addChild(vignette)
  }

  /** Dark casing under a light core: one line that reads at any zoom. */
  function strokeEdges(
    graphics: Graphics,
    edges: Array<{ x: number; y: number; side: EdgeSide }>,
    style: { casingColor: number; casingWidth: number; casingAlpha: number; inkColor: number; inkWidth: number; inkAlpha: number },
  ) {
    for (const pass of ['casing', 'ink'] as const) {
      const width = pass === 'casing' ? style.casingWidth : style.inkWidth
      const color = pass === 'casing' ? style.casingColor : style.inkColor
      const alpha = pass === 'casing' ? style.casingAlpha : style.inkAlpha
      for (const edge of edges) {
        const [x1, y1, x2, y2] = edgeToSegment(edge.x, edge.y, edge.side)
        graphics.moveTo(x1, y1).lineTo(x2, y2)
          .stroke({ width, color, alpha, cap: 'round', join: 'round' })
      }
    }
  }

  /** Dashed segment helper, used for water routes and severed links. */
  function strokeDashed(
    graphics: Graphics,
    from: { x: number; y: number },
    to: { x: number; y: number },
    style: { width: number; color: number; alpha: number },
  ) {
    const dx = to.x - from.x
    const dy = to.y - from.y
    const length = Math.hypot(dx, dy)
    if (length <= 0) return
    const ux = dx / length
    const uy = dy / length
    const step = MAP_ROUTE.dashLength + MAP_ROUTE.dashGap
    for (let travelled = 0; travelled < length; travelled += step) {
      const end = Math.min(length, travelled + MAP_ROUTE.dashLength)
      graphics.moveTo(from.x + ux * travelled, from.y + uy * travelled)
        .lineTo(from.x + ux * end, from.y + uy * end)
        .stroke({ ...style, cap: 'round' })
    }
  }

  function renderPlanOverlays(plan: MapLayerRenderPlan) {
    const container = mapContainer.value
    if (!container) return

    if (plan.elevation.length) {
      const elevationGraphics = new Graphics()
      elevationGraphics.eventMode = 'none'
      for (const cell of plan.elevation) {
        elevationGraphics.rect(cell.x * TILE_SIZE, cell.y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
          .fill({ color: cell.color, alpha: cell.alpha })
      }
      container.addChild(elevationGraphics)
    }

    // Coast before borders: the world outline is the strongest line on the map.
    if (plan.coast.length) {
      const coastGraphics = new Graphics()
      coastGraphics.eventMode = 'none'
      strokeEdges(coastGraphics, plan.coast, MAP_COAST)
      container.addChild(coastGraphics)
    }

    if (plan.borders.length) {
      const borderGraphics = new Graphics()
      borderGraphics.eventMode = 'none'
      strokeEdges(borderGraphics, plan.borders, MAP_BORDER)
      container.addChild(borderGraphics)
    }

    /*
     * Water bodies used to stamp an inset rectangle and a dot into every cell,
     * which read as debug boxes on the sea. Only the flow trace survives: a
     * sparse jade tick along the current, which is information the fill was not
     * carrying anyway.
     */
    if (plan.waterBodies.length) {
      const waterGraphics = new Graphics()
      waterGraphics.eventMode = 'none'
      for (const body of plan.waterBodies) {
        if (!body.flowDirection) continue
        const [dx, dy] = body.flowDirection
        const magnitude = Math.hypot(dx, dy)
        if (!magnitude) continue
        const unitX = dx / magnitude
        const unitY = dy / magnitude
        const half = MAP_WATER_BODY.flowLength / 2
        for (const [x, y] of body.cellRefs.filter((_, index) => index % MAP_WATER_BODY.flowSampleStride === 0)) {
          const cx = x * TILE_SIZE + TILE_SIZE / 2
          const cy = y * TILE_SIZE + TILE_SIZE / 2
          waterGraphics.moveTo(cx - unitX * half, cy - unitY * half)
            .lineTo(cx + unitX * half, cy + unitY * half)
            .stroke({
              width: MAP_WATER_BODY.flowWidth,
              color: MAP_WATER_BODY.flowColor,
              alpha: MAP_WATER_BODY.flowAlpha * (body.navigable ? 1 : 0.6),
              cap: 'round',
            })
        }
      }
      container.addChild(waterGraphics)
    }

    /*
     * Routes are the trade network, so they must read as a graph: an engraved
     * path with a node at each endpoint. Width encodes capacity, dashes encode
     * a water crossing, cinnabar encodes a severed link.
     */
    if (plan.routes.length) {
      const routeGraphics = new Graphics()
      routeGraphics.eventMode = 'none'
      for (const route of plan.routes) {
        const severed = route.availability <= 0
        const water = isWaterRouteMode(route.mode)
        const color = severed
          ? MAP_ROUTE.severedColor
          : water ? MAP_ROUTE.waterColor : MAP_ROUTE.landColor
        const width = MAP_ROUTE.minWidth
          + Math.max(0, Math.min(1, route.quality)) * MAP_ROUTE.maxWidthBonus
        const alpha = 0.45 + route.availability * 0.5

        routeGraphics.moveTo(route.from.x, route.from.y)
          .lineTo(route.to.x, route.to.y)
          .stroke({
            width: width + 3.5,
            color: MAP_ROUTE.casingColor,
            alpha: MAP_ROUTE.casingAlpha,
            cap: 'round',
          })

        if (water || severed) {
          strokeDashed(routeGraphics, route.from, route.to, { width, color, alpha })
        } else {
          routeGraphics.moveTo(route.from.x, route.from.y)
            .lineTo(route.to.x, route.to.y)
            .stroke({ width, color, alpha, cap: 'round' })
        }

        for (const node of [route.from, route.to]) {
          routeGraphics.circle(node.x, node.y, MAP_ROUTE.nodeRadius)
            .fill({ color: MAP_ROUTE.casingColor, alpha: 0.8 })
          routeGraphics.circle(node.x, node.y, MAP_ROUTE.nodeRadius - 2)
            .fill({ color, alpha: Math.min(1, alpha + 0.2) })
        }
      }
      container.addChild(routeGraphics)
    }
  }

  /** Cells belonging to each region, from the canonical territory grid. */
  function collectRegionCells(): Map<string, Array<[number, number]>> {
    const cells = new Map<string, Array<[number, number]>>()
    const rows = mapStore.territoryRows
    for (let y = 0; y < rows.length; y += 1) {
      const row = rows[y] ?? []
      for (let x = 0; x < row.length; x += 1) {
        const id = row[x]
        if (typeof id !== 'number' || !Number.isFinite(id) || id <= 0) continue
        const key = String(id)
        const bucket = cells.get(key)
        if (bucket) bucket.push([x, y])
        else cells.set(key, [[x, y]])
      }
    }
    return cells
  }

  let regionCells = new Map<string, Array<[number, number]>>()

  /**
   * A transparent, hit-testable shape per region.
   *
   * Selection used to be bound to the label's estimated text rectangle, so the
   * territory itself was not clickable and the hit box was wrong for any
   * proportional font. Now the land is the target.
   */
  function renderRegionPickLayer() {
    const container = mapContainer.value
    if (!container) return

    regionCells = collectRegionCells()
    regionPickLayer = new Container()
    regionPickLayer.zIndex = MAP_LAYER_Z_INDEX.regionPick
    regionPickLayer.sortableChildren = false

    for (const [regionId, cells] of regionCells) {
      const region = mapStore.regions.get(Number(regionId)) ?? mapStore.regions.get(regionId)
      if (!region) continue

      const shape = new Graphics()
      for (const [x, y] of cells) {
        shape.rect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
      }
      // Alpha 0 still hit-tests in Pixi; the fill only defines the shape.
      shape.fill({ color: 0xffffff, alpha: 0 })
      shape.eventMode = 'static'
      shape.cursor = 'pointer'
      shape.on('pointerover', () => { hoveredRegionId.value = regionId })
      shape.on('pointerout', () => {
        if (hoveredRegionId.value === regionId) hoveredRegionId.value = null
      })
      shape.on('pointertap', () => handleRegionSelect(region))
      regionPickLayer.addChild(shape)
    }

    container.addChild(regionPickLayer)
  }

  /** Gold seal for the selected region, quiet paper wash for the hovered one. */
  function drawSelection() {
    if (!selectionGraphics) return
    const g = selectionGraphics
    g.clear()

    const paint = (
      regionId: string,
      fill: number,
      fillAlpha: number,
      stroke: { color: number; alpha: number; width: number },
      casing?: { color: number; alpha: number; width: number },
    ) => {
      const cells = regionCells.get(regionId)
      if (!cells?.length) return
      const cellSet = new Set(cells.map(([x, y]) => `${x},${y}`))

      for (const [x, y] of cells) {
        g.rect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
          .fill({ color: fill, alpha: fillAlpha })
      }

      // Outline only the outer edge of the region, not every internal cell.
      const edges: Array<[number, number, number, number]> = []
      for (const [x, y] of cells) {
        if (!cellSet.has(`${x - 1},${y}`)) edges.push(edgeToSegment(x, y, 'left'))
        if (!cellSet.has(`${x + 1},${y}`)) edges.push(edgeToSegment(x, y, 'right'))
        if (!cellSet.has(`${x},${y - 1}`)) edges.push(edgeToSegment(x, y, 'top'))
        if (!cellSet.has(`${x},${y + 1}`)) edges.push(edgeToSegment(x, y, 'bottom'))
      }

      if (casing) {
        for (const [x1, y1, x2, y2] of edges) {
          g.moveTo(x1, y1).lineTo(x2, y2)
            .stroke({ width: casing.width, color: casing.color, alpha: casing.alpha, cap: 'round', join: 'round' })
        }
      }
      for (const [x1, y1, x2, y2] of edges) {
        g.moveTo(x1, y1).lineTo(x2, y2)
          .stroke({ width: stroke.width, color: stroke.color, alpha: stroke.alpha, cap: 'round', join: 'round' })
      }
    }

    const hovered = hoveredRegionId.value
    if (hovered && hovered !== selectedRegionId.value) {
      paint(
        hovered,
        MAP_SELECTION.hoverFill,
        MAP_SELECTION.hoverFillAlpha,
        {
          color: MAP_SELECTION.hoverStrokeColor,
          alpha: MAP_SELECTION.hoverStrokeAlpha,
          width: MAP_SELECTION.hoverStrokeWidth,
        },
      )
    }

    if (selectedRegionId.value) {
      paint(
        selectedRegionId.value,
        MAP_SELECTION.selectedFill,
        MAP_SELECTION.selectedFillAlpha,
        {
          color: MAP_SELECTION.selectedStrokeColor,
          alpha: MAP_SELECTION.selectedStrokeAlpha,
          width: MAP_SELECTION.selectedStrokeWidth,
        },
        {
          color: MAP_SELECTION.selectedCasingColor,
          alpha: MAP_SELECTION.selectedCasingAlpha,
          width: MAP_SELECTION.selectedCasingWidth,
        },
      )
    }
  }

  /**
   * Region names, with a plate behind the ones that need it and a counter-scale
   * that holds every label at its designed on-screen size.
   */
  function drawLabels() {
    const layer = labelLayer
    if (!layer) return

    const oldChildren = layer.removeChildren()
    oldChildren.forEach(child => child.destroy({ children: true }))

    const counterScale = getLabelCounterScale(viewportScale.value)

    for (const label of visibleRegionLabels.value) {
      const tier = resolveLabelTier(label.type)
      const group = new Container()
      group.x = label.labelX
      group.y = label.labelY
      group.scale.set(counterScale)
      group.alpha = tier.alpha
      group.eventMode = 'none'

      if (tier.plate) {
        const screen = estimateRegionLabelSize(label.displayName, label.type, locale.value)
        const plateWidth = (screen.width + MAP_LABEL_PLATE.paddingX * 2) * MAP_LABEL_TEXT_RESOLUTION
        const plateHeight = (screen.height + MAP_LABEL_PLATE.paddingY * 2) * MAP_LABEL_TEXT_RESOLUTION
        const plate = new Graphics()
        plate.eventMode = 'none'
        plate.roundRect(
          -plateWidth / 2,
          -plateHeight / 2,
          plateWidth,
          plateHeight,
          MAP_LABEL_PLATE.radius * MAP_LABEL_TEXT_RESOLUTION,
        ).fill({ color: MAP_LABEL_PLATE.color, alpha: MAP_LABEL_PLATE.alpha })
        group.addChild(plate)
      }

      const text = new Text({
        text: label.displayName,
        style: getRegionTextStyle(label.type, locale.value, label.displayName),
      })
      text.anchor.set(0.5)
      text.eventMode = 'none'
      /*
       * The glyph texture is rasterized at MAP_LABEL_TEXT_RESOLUTION times the
       * target size and then scaled down by the counter-scale, so the label is
       * supersampled. That is what keeps type crisp under the global `nearest`
       * texture default, which exists for the pixel tiles and not for text.
       */
      group.addChild(text)

      layer.addChild(group)
    }
  }

  function getLargeRegionBaseName(region: RegionSummary) {
    if (region.type === 'city' && region.id) {
      const cityId = typeof region.id === 'string' ? parseInt(region.id) : region.id
      return !Number.isNaN(cityId) ? `city_${cityId}` : null
    }
    if (region.type === 'sect' && region.sect_id) {
      return `sect_${region.sect_id}`
    }
    if (region.type === 'cultivate' && region.sub_type) {
      return region.sub_type
    }
    return null
  }

  function renderLargeRegions() {
    for (const region of mapStore.regions.values()) {
      const baseName = getLargeRegionBaseName(region)
      if (!baseName || !mapContainer.value) continue

      const positions = [
        { dx: 0, dy: 0, idx: 0 },
        { dx: 1, dy: 0, idx: 1 },
        { dx: 0, dy: 1, idx: 2 },
        { dx: 1, dy: 1, idx: 3 },
      ]

      for (const pos of positions) {
        const tex = textures.value[`${baseName}_${pos.idx}`]
        if (!tex) continue

        const sprite = new Sprite(tex)
        sprite.x = (region.x + pos.dx) * TILE_SIZE
        sprite.y = (region.y + pos.dy) * TILE_SIZE
        sprite.width = TILE_SIZE
        sprite.height = TILE_SIZE
        sprite.roundPixels = true
        sprite.eventMode = 'none'
        mapContainer.value.addChild(sprite)
      }
    }
  }

  async function renderMap() {
    if (!mapContainer.value || !mapStore.mapData.length) return

    const generation = ++renderGeneration
    cleanupTicker()
    clearMapContainer()
    await preloadRegionTextures(mapStore.regions.values())

    if (
      !mapContainer.value
      || !mapStore.isLoaded
      || !mapStore.mapData.length
      || generation !== renderGeneration
    ) return
    const rows = mapStore.mapData.length
    const cols = mapStore.mapData[0]?.length ?? 0
    const mapWidth = cols * TILE_SIZE
    const mapHeight = rows * TILE_SIZE

    mapContainer.value.sortableChildren = true

    renderGroundAndWater(rows, cols, mapWidth, mapHeight)
    if (currentVisibility.value.terrain) renderLargeRegions()
    renderAtmosphere(mapWidth, mapHeight)
    renderPlanOverlays(buildMapLayerRenderPlan({
      mapData: mapStore.mapData,
      geography: mapStore.geography,
      territoryRows: mapStore.territoryRows,
      regions: Array.from(mapStore.regions.values()),
      routes: mapStore.routes,
      visibility: currentVisibility.value,
    }))

    renderRegionPickLayer()

    selectionGraphics = new Graphics()
    selectionGraphics.eventMode = 'none'
    selectionGraphics.zIndex = MAP_LAYER_Z_INDEX.selection
    mapContainer.value.addChild(selectionGraphics)
    drawSelection()

    labelLayer = new Container()
    labelLayer.eventMode = 'none'
    labelLayer.zIndex = MAP_LAYER_Z_INDEX.labels
    mapContainer.value.addChild(labelLayer)
    drawLabels()

    emit('mapLoaded', { width: mapWidth, height: mapHeight })
  }

  function handleRegionSelect(region: RegionSummary) {
    play('select')
    emit('regionSelected', {
      type: 'region',
      id: String(region.id),
      name: region.name,
    })
  }

  onMounted(() => {
    if (isLoaded.value && mapStore.isLoaded) {
      void renderMap()
    }
  })

  onUnmounted(() => {
    renderGeneration += 1
    cleanupTicker()
  })

  // Cheap redraws: selection and labels never rebuild the base map.
  watch([hoveredRegionId, selectedRegionId], () => drawSelection())
  watch([visibleRegionLabels, () => locale.value], () => drawLabels())

  watch([
    () => isLoaded.value,
    () => mapStore.isLoaded,
    () => currentVisibility.value.terrain,
    () => currentVisibility.value.elevation,
    () => currentVisibility.value.water,
    () => currentVisibility.value.borders,
    () => currentVisibility.value.routes,
    () => mapStore.routes,
  ],
    ([texturesReady, mapReady]) => {
      if (texturesReady && mapReady) {
        void renderMap()
      } else if (!mapReady) {
        renderGeneration += 1
        cleanupTicker()
        clearMapContainer()
      }
    },
  )

  return {
    mapContainer,
    locale,
    visibleRegionLabels,
    hoveredRegionId,
    selectedRegionId,
    getRegionTextStyle,
    handleRegionSelect,
  }
}
