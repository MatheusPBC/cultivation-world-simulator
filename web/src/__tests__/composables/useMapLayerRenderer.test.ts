import { defineComponent, nextTick, ref } from 'vue'
import { mount } from '@vue/test-utils'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useMapStore } from '@/stores/map'

const mockTexture = vi.hoisted(() => ({ valid: true }))
const preloadRegionTexturesMock = vi.hoisted(() => vi.fn())

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    locale: ref('zh-CN'),
  }),
}))

vi.mock('@/composables/useAudio', () => ({
  useAudio: () => ({
    play: vi.fn(),
  }),
}))

vi.mock('@/components/game/composables/useTextures', () => ({
  useTextures: () => ({
    textures: ref({
      PLAIN: mockTexture,
      SEA: mockTexture,
      WATER: mockTexture,
    }),
    isLoaded: ref(true),
    preloadRegionTextures: preloadRegionTexturesMock,
    getTileTexture: vi.fn(() => mockTexture),
  }),
}))

const spriteDestroyMock = vi.hoisted(() => vi.fn())
const graphicsDestroyMock = vi.hoisted(() => vi.fn())
const graphicsStrokeMock = vi.hoisted(() => vi.fn())
const tilingSpriteDestroyMock = vi.hoisted(() => vi.fn())
const tickerDestroyMock = vi.hoisted(() => vi.fn())
const tickerStopMock = vi.hoisted(() => vi.fn())
const containerDestroyMock = vi.hoisted(() => vi.fn())

vi.mock('pixi.js', () => ({
  Container: class {
    x = 0
    y = 0
    alpha = 1
    zIndex = 0
    eventMode = 'none'
    sortableChildren = false
    scale = { set: vi.fn() }
    children: Array<{ destroy?: (options?: unknown) => void }> = []
    addChild(child: { destroy?: (options?: unknown) => void }) {
      this.children.push(child)
      return child
    }
    removeChildren() {
      return this.children.splice(0, this.children.length)
    }
    destroy(options?: { children?: boolean }) {
      containerDestroyMock(options)
      if (options?.children) {
        this.children.forEach(child => child.destroy?.(options))
      }
    }
  },
  Sprite: class {
    x = 0
    y = 0
    width = 0
    height = 0
    roundPixels = false
    tint = 0xffffff
    eventMode = 'none'
    constructor(public texture: unknown) {}
    destroy = spriteDestroyMock
  },
  Graphics: class {
    eventMode = 'none'
    cursor = 'default'
    zIndex = 0
    clear() {
      return this
    }
    rect() {
      return this
    }
    roundRect() {
      return this
    }
    circle() {
      return this
    }
    ellipse() {
      return this
    }
    fill() {
      return this
    }
    moveTo() {
      return this
    }
    lineTo() {
      return this
    }
    stroke(options?: unknown) {
      graphicsStrokeMock(options)
      return this
    }
    on() {
      return this
    }
    destroy = graphicsDestroyMock
  },
  Text: class {
    anchor = { set: vi.fn() }
    eventMode = 'none'
    texture = { source: { scaleMode: 'nearest' } }
    constructor(public options: unknown) {}
    destroy = vi.fn()
  },
  TilingSprite: class {
    tint = 0xffffff
    tileScale = { set: vi.fn() }
    tilePosition = { x: 0, y: 0 }
    mask: unknown = null
    constructor(public options: unknown) {}
    destroy = tilingSpriteDestroyMock
  },
  Ticker: class {
    add = vi.fn()
    start = vi.fn()
    stop = tickerStopMock
    destroy = tickerDestroyMock
  },
}))

import { MAP_ROUTE, TERRAIN_TINT } from '@/constants/mapTheme'
import {
  buildMapLayerRenderPlan,
  DEFAULT_MAP_LAYER_VISIBILITY,
  type MapLayerRenderInput,
  useMapLayerRenderer,
} from '@/components/game/composables/useMapLayerRenderer'

function createMockContainer() {
  const children: Array<{ destroy: ReturnType<typeof vi.fn> }> = []
  return {
    children,
    addChild(child: { destroy: ReturnType<typeof vi.fn> }) {
      children.push(child)
      return child
    },
    removeChildren() {
      return children.splice(0, children.length)
    },
  }
}

describe('useMapLayerRenderer', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    preloadRegionTexturesMock.mockResolvedValue(undefined)
  })

  it('destroys old Pixi display objects before rerendering the map', async () => {
    const mapStore = useMapStore()
    mapStore.mapData = [['PLAIN']]

    const container = createMockContainer()
    mount(defineComponent({
      setup() {
        const renderer = useMapLayerRenderer(vi.fn())
        renderer.mapContainer.value = container as never
        return () => null
      },
    }))

    mapStore.isLoaded = true
    await nextTick()
    await nextTick()
    const firstRenderChildren = [...container.children]
    expect(firstRenderChildren.length).toBeGreaterThan(0)

    mapStore.mapData = [['PLAIN', 'PLAIN']]
    mapStore.isLoaded = false
    await nextTick()
    mapStore.isLoaded = true
    await nextTick()
    await nextTick()

    expect(containerDestroyMock).toHaveBeenCalledWith({ children: true, texture: false })
    expect(spriteDestroyMock).toHaveBeenCalledWith({ children: true, texture: false })
  })

  it('destroys unused animated water layers on a dry map', async () => {
    const mapStore = useMapStore()
    mapStore.mapData = [['PLAIN']]

    const container = createMockContainer()
    mount(defineComponent({
      setup() {
        const renderer = useMapLayerRenderer(vi.fn())
        renderer.mapContainer.value = container as never
        return () => null
      },
    }))

    mapStore.isLoaded = true
    await nextTick()
    await nextTick()

    expect(tilingSpriteDestroyMock).toHaveBeenCalledTimes(2)
  })

  it('discards an obsolete render that finishes after a newer layer render', async () => {
    const mapStore = useMapStore()
    mapStore.mapData = [['PLAIN']]
    const visibility = ref({ ...DEFAULT_MAP_LAYER_VISIBILITY })
    const emit = vi.fn()
    let resolveFirst!: () => void
    let resolveSecond!: () => void
    preloadRegionTexturesMock
      .mockImplementationOnce(() => new Promise<void>(resolve => { resolveFirst = resolve }))
      .mockImplementationOnce(() => new Promise<void>(resolve => { resolveSecond = resolve }))

    const container = createMockContainer()
    mount(defineComponent({
      setup() {
        const renderer = useMapLayerRenderer(emit, visibility)
        renderer.mapContainer.value = container as never
        return () => null
      },
    }))

    mapStore.isLoaded = true
    await nextTick()
    visibility.value = { ...visibility.value, elevation: true }
    await nextTick()

    resolveSecond()
    await Promise.resolve()
    await nextTick()
    resolveFirst()
    await Promise.resolve()
    await nextTick()

    expect(emit).toHaveBeenCalledTimes(1)
  })

  it('discards a pending render when the map store is reset', async () => {
    const mapStore = useMapStore()
    mapStore.mapData = [['PLAIN']]
    const emit = vi.fn()
    let resolvePreload!: () => void
    preloadRegionTexturesMock.mockImplementationOnce(
      () => new Promise<void>(resolve => { resolvePreload = resolve }),
    )

    const container = createMockContainer()
    mount(defineComponent({
      setup() {
        const renderer = useMapLayerRenderer(emit)
        renderer.mapContainer.value = container as never
        return () => null
      },
    }))

    mapStore.isLoaded = true
    await nextTick()
    mapStore.reset()
    await nextTick()
    resolvePreload()
    await Promise.resolve()
    await nextTick()

    expect(emit).not.toHaveBeenCalled()
    expect(container.children).toEqual([])
  })

  it('does not rebuild Pixi terrain when only region names or sects are toggled', async () => {
    const mapStore = useMapStore()
    mapStore.mapData = [['PLAIN']]
    const visibility = ref({ ...DEFAULT_MAP_LAYER_VISIBILITY })
    const container = createMockContainer()
    mount(defineComponent({
      setup() {
        const renderer = useMapLayerRenderer(vi.fn(), visibility)
        renderer.mapContainer.value = container as never
        return () => null
      },
    }))

    mapStore.isLoaded = true
    await nextTick()
    await nextTick()
    expect(preloadRegionTexturesMock).toHaveBeenCalledTimes(1)

    visibility.value = { ...visibility.value, names: false }
    await nextTick()
    await nextTick()
    visibility.value = { ...visibility.value, sects: false }
    await nextTick()
    await nextTick()

    expect(preloadRegionTexturesMock).toHaveBeenCalledTimes(1)
  })

  it('builds water overlays only from canonical water-body cell refs', () => {
    const input: MapLayerRenderInput = {
      mapData: [['WATER', 'PLAIN'], ['PLAIN', 'PLAIN']],
      geography: {
        elevationRows: [[10, 20], [30, 40]],
        waterBodies: [{
          id: 'river:1',
          kind: 'river',
          cellRefs: [[1, 1]],
          navigable: true,
          flowDirection: [1, 0],
        }],
      },
      territoryRows: [[1, 1], [1, 1]],
      regions: [{ id: '1', name: 'Vale', x: 0, y: 0, type: 'city' }],
      routes: [],
      visibility: DEFAULT_MAP_LAYER_VISIBILITY,
    }

    const plan = buildMapLayerRenderPlan(input)

    expect(plan.waterBodies).toEqual([expect.objectContaining({
      id: 'river:1',
      cellRefs: [[1, 1]],
      navigable: true,
      flowDirection: [1, 0],
    })])
    expect(plan.waterBodies[0]?.cellRefs).not.toContainEqual([0, 0])
  })

  it('derives region borders from territory rows and not from visual terrain', () => {
    const input: MapLayerRenderInput = {
      mapData: [['PLAIN', 'PLAIN'], ['PLAIN', 'PLAIN']],
      geography: { elevationRows: [], waterBodies: [] },
      territoryRows: [[1, 1], [1, 2]],
      regions: [],
      routes: [],
      visibility: DEFAULT_MAP_LAYER_VISIBILITY,
    }

    const plan = buildMapLayerRenderPlan(input)

    expect(plan.borders).toEqual(expect.arrayContaining([
      { x: 1, y: 1, side: 'right' },
      { x: 1, y: 1, side: 'bottom' },
    ]))
  })

  it('projects each shared regional boundary only once', () => {
    const plan = buildMapLayerRenderPlan({
      mapData: [['PLAIN', 'PLAIN']],
      geography: { elevationRows: [], waterBodies: [] },
      territoryRows: [[1, 2]],
      regions: [],
      routes: [],
      visibility: DEFAULT_MAP_LAYER_VISIBILITY,
    })

    const sharedEdgeCount = plan.borders.filter(edge => (
      (edge.x === 0 && edge.y === 0 && edge.side === 'right')
      || (edge.x === 1 && edge.y === 0 && edge.side === 'left')
    )).length

    expect(sharedEdgeCount).toBe(1)
  })

  it('projects enabled routes as direct topological lines between region anchors', () => {
    const input: MapLayerRenderInput = {
      mapData: [['PLAIN']],
      geography: { elevationRows: [], waterBodies: [] },
      territoryRows: [[1]],
      regions: [
        { id: '1', name: 'Origem', x: 2, y: 3, type: 'city' },
        { id: '2', name: 'Destino', x: 8, y: 5, type: 'city' },
      ],
      routes: [{
        id: 'route:1',
        endpointRegionIds: [1, 2],
        mode: 'road',
        capacity: 100,
        operationalCapacity: 75,
        quality: 0.75,
        enabled: true,
        allowedResourceIds: [],
        dependencySiteIds: [],
      }],
      visibility: DEFAULT_MAP_LAYER_VISIBILITY,
    }

    const plan = buildMapLayerRenderPlan(input)

    expect(plan.routes).toEqual([expect.objectContaining({
      id: 'route:1',
      from: { x: 2 * 64 + 32, y: 3 * 64 + 32 },
      to: { x: 8 * 64 + 32, y: 5 * 64 + 32 },
      mode: 'road',
      operationalCapacity: 75,
      enabled: true,
    })])
  })

  it('rerenders route overlays when operational capacity changes', async () => {
    const mapStore = useMapStore()
    mapStore.mapData = [['PLAIN']]
    mapStore.territoryRows = [[1]]
    mapStore.regions = new Map([
      ['1', { id: '1', name: 'Origem', x: 0, y: 0, type: 'city' }],
      ['2', { id: '2', name: 'Destino', x: 1, y: 0, type: 'city' }],
    ])
    mapStore.routes = [{
      id: 'route:1', endpointRegionIds: [1, 2], mode: 'road', capacity: 100,
      operationalCapacity: 80, quality: 0.8, enabled: true,
      allowedResourceIds: [], dependencySiteIds: ['bridge:1'],
    }]
    const emit = vi.fn()
    const container = createMockContainer()
    mount(defineComponent({
      setup() {
        const renderer = useMapLayerRenderer(emit)
        renderer.mapContainer.value = container as never
        return () => null
      },
    }))

    mapStore.isLoaded = true
    await nextTick()
    await nextTick()
    expect(emit).toHaveBeenCalledTimes(1)
    graphicsStrokeMock.mockClear()

    mapStore.applyRouteUpdates([{
      id: 'route:1', operational_capacity: 20, dependency_site_ids: ['bridge:1'],
    }])
    await nextTick()
    await nextTick()

    expect(emit).toHaveBeenCalledTimes(2)
    // 20/(100*0.8) = 0.25 availability -> still a land route, dimmed.
    expect(graphicsStrokeMock).toHaveBeenCalledWith(expect.objectContaining({
      color: MAP_ROUTE.landColor,
      alpha: 0.45 + 0.25 * 0.5,
    }))
  })

  it('derives a coastline from every land cell that touches water', () => {
    const plan = buildMapLayerRenderPlan({
      mapData: [['SEA', 'PLAIN'], ['PLAIN', 'PLAIN']],
      geography: { elevationRows: [], waterBodies: [] },
      territoryRows: [[1, 1], [1, 1]],
      regions: [],
      routes: [],
      visibility: DEFAULT_MAP_LAYER_VISIBILITY,
    })

    // (1,0) is land with sea to its left; (0,1) is land with sea above it.
    expect(plan.coast).toEqual(expect.arrayContaining([
      { x: 1, y: 0, side: 'left' },
      { x: 0, y: 1, side: 'top' },
    ]))
    // A water cell never contributes a coast edge of its own.
    expect(plan.coast.some(edge => edge.x === 0 && edge.y === 0)).toBe(false)
  })

  it('tints terrain into the shared tonal family instead of leaving raw tile art', () => {
    const plan = buildMapLayerRenderPlan({
      mapData: [['PLAIN', 'DESERT']],
      geography: { elevationRows: [], waterBodies: [] },
      territoryRows: [[1, 1]],
      regions: [],
      routes: [],
      visibility: DEFAULT_MAP_LAYER_VISIBILITY,
    })

    expect(plan.terrain).toEqual([
      { x: 0, y: 0, type: 'PLAIN', tint: TERRAIN_TINT.PLAIN },
      { x: 1, y: 0, type: 'DESERT', tint: TERRAIN_TINT.DESERT },
    ])
  })

  it('assigns elevation colors deterministically and omits the overlay when hidden', () => {
    const input: MapLayerRenderInput = {
      mapData: [['PLAIN', 'PLAIN']],
      geography: { elevationRows: [[0, 100]], waterBodies: [] },
      territoryRows: [[1, 1]],
      regions: [],
      routes: [],
      visibility: { ...DEFAULT_MAP_LAYER_VISIBILITY, elevation: true },
    }

    const plan = buildMapLayerRenderPlan(input)

    expect(plan.elevation).toHaveLength(2)
    expect(plan.elevation[0]?.color).not.toBe(plan.elevation[1]?.color)
    expect(buildMapLayerRenderPlan({ ...input, visibility: DEFAULT_MAP_LAYER_VISIBILITY }).elevation)
      .toEqual([])
  })
})
