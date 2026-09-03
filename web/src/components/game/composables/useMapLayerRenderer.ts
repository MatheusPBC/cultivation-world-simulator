import { computed, onMounted, onUnmounted, ref, unref, watch, type MaybeRef } from 'vue'
import { Container, Graphics, Sprite, Ticker, TilingSprite } from 'pixi.js'
import { useI18n } from 'vue-i18n'
import { useTextures } from './useTextures'
import { useMapStore } from '@/stores/map'
import { useAudio } from '@/composables/useAudio'
import type { PhysicalGeographySnapshot, RegionSummary, RouteSummary } from '@/types/core'
import { getRegionTextStyle } from '@/utils/mapStyles'
import { buildVisibleRegionLabels } from '../utils/mapLabels'

const TILE_SIZE = 64

export const MAP_LAYER_Z_INDEX = Object.freeze({
  physical: 0,
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

export interface MapLayerRenderPlan {
  terrain: Array<{ x: number; y: number; type: string }>
  elevation: Array<{ x: number; y: number; color: number; alpha: number }>
  waterBodies: Array<{
    id: string
    kind: string
    cellRefs: Array<[number, number]>
    navigable: boolean
    flowDirection?: [number, number]
  }>
  borders: Array<{ x: number; y: number; side: 'left' | 'right' | 'top' | 'bottom' }>
  routes: Array<{
    id: string
    from: { x: number; y: number }
    to: { x: number; y: number }
    mode: string
    quality: number
    capacity: number
    operationalCapacity: number
    enabled: boolean
  }>
}

function elevationColor(ratio: number): number {
  const normalized = Math.max(0, Math.min(1, ratio))
  const low = { r: 35, g: 82, b: 125 }
  const high = { r: 215, g: 166, b: 75 }
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

function isWaterRouteMode(mode: string): boolean {
  const normalized = mode.toLowerCase()
  return ['river', 'water', 'sea', 'ferry', 'coastal'].some(token => normalized.includes(token))
}

export function buildMapLayerRenderPlan(input: MapLayerRenderInput): MapLayerRenderPlan {
  const { mapData, geography, territoryRows, regions, routes, visibility } = input
  const height = mapData.length
  const width = mapData[0]?.length ?? 0
  const terrain = visibility.terrain
    ? mapData.flatMap((row, y) => row.flatMap((type, x) => (
      type === 'SEA' || type === 'WATER' || type === 'SECT'
        ? []
        : [{ x, y, type }]
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
      return [{
        id: route.id,
        from,
        to,
        mode: route.mode,
        quality: route.quality,
        capacity: route.capacity,
        operationalCapacity: route.operationalCapacity,
        enabled: route.enabled,
      }]
    })
    : []

  return { terrain, elevation, waterBodies, borders, routes: plannedRoutes }
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
  const { locale } = useI18n()
  const { play } = useAudio()

  let ticker: Ticker | null = null
  let seaLayer: TilingSprite | null = null
  let waterLayer: TilingSprite | null = null
  let renderGeneration = 0

  const currentVisibility = computed(() => unref(visibility) ?? DEFAULT_MAP_LAYER_VISIBILITY)

  const visibleRegionLabels = computed(() =>
    currentVisibility.value.names
      ? buildVisibleRegionLabels(Array.from(mapStore.regions.values()), locale.value)
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
    const seaMask = new Graphics()
    if (seaLayer) seaLayer.mask = seaMask

    const waterTex = textures.value.WATER_FULL || textures.value.WATER
    waterLayer = visibilityState.water ? new TilingSprite({ texture: waterTex, width: mapWidth, height: mapHeight }) : null
    waterLayer?.tileScale.set(0.5, 0.5)
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
    startWaterTicker(hasSea, hasWater)
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

    if (plan.waterBodies.length) {
      const waterGraphics = new Graphics()
      waterGraphics.eventMode = 'none'
      for (const body of plan.waterBodies) {
        const kind = body.kind.toLowerCase()
        const color = kind.includes('river') ? 0x67c8e8 : kind.includes('sea') ? 0x3c74c8 : 0x4d9ee8
        for (const [x, y] of body.cellRefs) {
          waterGraphics.rect(x * TILE_SIZE + 5, y * TILE_SIZE + 5, TILE_SIZE - 10, TILE_SIZE - 10)
            .fill({ color, alpha: body.navigable ? 0.3 : 0.2 })
          if (body.navigable) {
            waterGraphics.rect(x * TILE_SIZE + TILE_SIZE / 2 - 3, y * TILE_SIZE + TILE_SIZE / 2 - 3, 6, 6)
              .fill({ color, alpha: 0.82 })
          }
        }
        if (body.flowDirection) {
          const [dx, dy] = body.flowDirection
          const magnitude = Math.hypot(dx, dy)
          const unitX = dx / magnitude
          const unitY = dy / magnitude
          for (const [x, y] of body.cellRefs.filter((_, index) => index % 4 === 0)) {
            const cx = x * TILE_SIZE + TILE_SIZE / 2
            const cy = y * TILE_SIZE + TILE_SIZE / 2
            const tipX = cx + unitX * 10
            const tipY = cy + unitY * 10
            waterGraphics.moveTo(cx - unitX * 10, cy - unitY * 10)
              .lineTo(tipX, tipY)
              .lineTo(tipX - unitX * 5 - unitY * 4, tipY - unitY * 5 + unitX * 4)
              .moveTo(tipX, tipY)
              .lineTo(tipX - unitX * 5 + unitY * 4, tipY - unitY * 5 - unitX * 4)
              .stroke({ width: 2, color, alpha: 0.75 })
          }
        }
      }
      container.addChild(waterGraphics)
    }

    if (plan.routes.length) {
      const routeGraphics = new Graphics()
      routeGraphics.eventMode = 'none'
      for (const route of plan.routes) {
        const nominalUsableCapacity = route.capacity * route.quality
        const availability = route.enabled && nominalUsableCapacity > 0
          ? Math.max(0, Math.min(1, route.operationalCapacity / nominalUsableCapacity))
          : 0
        const color = availability <= 0
          ? 0x91564b
          : isWaterRouteMode(route.mode) ? 0x82a9ff : 0xd8b36a
        const width = 6 + Math.max(0, Math.min(1, route.quality)) * 4
        const alpha = 0.24 + availability * 0.56
        routeGraphics.moveTo(route.from.x, route.from.y)
          .lineTo(route.to.x, route.to.y)
          .stroke({ width: width + 4, color: 0x17130d, alpha: 0.2 + availability * 0.42 })
        routeGraphics.moveTo(route.from.x, route.from.y)
          .lineTo(route.to.x, route.to.y)
          .stroke({ width, color, alpha })
      }
      container.addChild(routeGraphics)
    }

    if (plan.borders.length) {
      const borderGraphics = new Graphics()
      borderGraphics.eventMode = 'none'
      for (const edge of plan.borders) {
        const px = edge.x * TILE_SIZE
        const py = edge.y * TILE_SIZE
        const right = px + TILE_SIZE
        const bottom = py + TILE_SIZE
        const [x1, y1, x2, y2] = edge.side === 'left'
          ? [px, py, px, bottom]
          : edge.side === 'right'
            ? [right, py, right, bottom]
            : edge.side === 'top'
              ? [px, py, right, py]
              : [px, bottom, right, bottom]
        borderGraphics.moveTo(x1, y1).lineTo(x2, y2)
          .stroke({ width: 2, color: 0xf5e7c8, alpha: 0.64 })
      }
      container.addChild(borderGraphics)
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

    renderGroundAndWater(rows, cols, mapWidth, mapHeight)
    renderPlanOverlays(buildMapLayerRenderPlan({
      mapData: mapStore.mapData,
      geography: mapStore.geography,
      territoryRows: mapStore.territoryRows,
      regions: Array.from(mapStore.regions.values()),
      routes: mapStore.routes,
      visibility: currentVisibility.value,
    }))
    if (currentVisibility.value.terrain) renderLargeRegions()
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
    getRegionTextStyle,
    handleRegionSelect,
  }
}
