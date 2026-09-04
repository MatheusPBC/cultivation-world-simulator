<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { Container, Graphics } from 'pixi.js'
import { useMapStore } from '../../stores/map'
import { useWorldStore } from '../../stores/world'
import { useSectStore } from '../../stores/sect'
import { MAP_SECT } from '@/constants/mapTheme'

const props = defineProps<{
  visible?: boolean
  zIndex?: number
}>()

const visible = computed(() => props.visible ?? true)

const TILE_SIZE = 64
const container = ref<Container>()
const mapStore = useMapStore()
const worldStore = useWorldStore()
let influenceGraphics: Graphics | null = null
const sectStore = useSectStore()

function hexToNumber(hex: string): number {
  if (!hex) return 0xffffff
  return parseInt(hex.replace(/^#/, ''), 16)
}

function mixToward(colorNum: number, target: number, t: number): number {
  const mix = (shift: number) => {
    const a = (colorNum >> shift) & 0xff
    const b = (target >> shift) & 0xff
    return Math.round(a + (b - a) * t)
  }
  return (mix(16) << 16) | (mix(8) << 8) | mix(0)
}

/**
 * Sect territory keeps the organization's canonical color, but expressed as a
 * diagonal hatch plus a thin double border rather than a flat slab. A 38%-alpha
 * fill over every owned tile was the loudest thing on the map and buried the
 * terrain, the routes and the names underneath it.
 */
function updateInfluence() {
  if (!influenceGraphics) return

  const g = influenceGraphics
  g.clear()

  if (!sectStore.activeTerritories.length) {
    return
  }

  for (const summary of sectStore.activeTerritories) {
    const colorNum = hexToNumber(summary.color)
    const tiles = summary.owned_tiles ?? []
    const owned = new Set(tiles.map(tile => `${tile.x},${tile.y}`))

    for (const tile of tiles) {
      const px = tile.x * TILE_SIZE
      const py = tile.y * TILE_SIZE
      g.rect(px, py, TILE_SIZE, TILE_SIZE)
        .fill({ color: colorNum, alpha: MAP_SECT.fillAlpha })

      // Diagonal hatch, clipped to the tile, reads as "claimed" without
      // obscuring what is claimed.
      for (let offset = 0; offset < TILE_SIZE; offset += MAP_SECT.hatchSpacing) {
        g.moveTo(px + offset, py)
          .lineTo(px, py + offset)
          .stroke({ width: MAP_SECT.hatchWidth, color: colorNum, alpha: MAP_SECT.hatchAlpha })
        g.moveTo(px + TILE_SIZE, py + offset)
          .lineTo(px + offset, py + TILE_SIZE)
          .stroke({ width: MAP_SECT.hatchWidth, color: colorNum, alpha: MAP_SECT.hatchAlpha })
      }
    }

    const borderColor = mixToward(colorNum, 0xf2ece0, MAP_SECT.borderLift)
    const edges = summary.boundary_edges ?? []
    // Only draw the outer silhouette: interior seams between two owned tiles
    // are not a boundary.
    const outer = edges.filter(edge => {
      const neighbour = edge.side === 'left'
        ? `${edge.x - 1},${edge.y}`
        : edge.side === 'right'
          ? `${edge.x + 1},${edge.y}`
          : edge.side === 'top'
            ? `${edge.x},${edge.y - 1}`
            : `${edge.x},${edge.y + 1}`
      return !owned.has(neighbour)
    })

    const segment = (edge: { x: number; y: number; side: string }): [number, number, number, number] => {
      const px = edge.x * TILE_SIZE
      const py = edge.y * TILE_SIZE
      const pr = px + TILE_SIZE
      const pb = py + TILE_SIZE
      if (edge.side === 'left') return [px, py, px, pb]
      if (edge.side === 'right') return [pr, py, pr, pb]
      if (edge.side === 'top') return [px, py, pr, py]
      return [px, pb, pr, pb]
    }

    for (const edge of outer) {
      const [x1, y1, x2, y2] = segment(edge)
      g.moveTo(x1, y1).lineTo(x2, y2).stroke({
        width: MAP_SECT.casingWidth,
        color: MAP_SECT.casingColor,
        alpha: MAP_SECT.casingAlpha,
        cap: 'round',
        join: 'round',
      })
    }
    for (const edge of outer) {
      const [x1, y1, x2, y2] = segment(edge)
      g.moveTo(x1, y1).lineTo(x2, y2).stroke({
        width: MAP_SECT.borderWidth,
        color: borderColor,
        alpha: MAP_SECT.borderAlpha,
        cap: 'round',
        join: 'round',
      })
    }
  }
}

onMounted(() => {
  if (container.value) {
    influenceGraphics = new Graphics()
    influenceGraphics.eventMode = 'none'
    container.value.addChild(influenceGraphics)
    updateInfluence()
  }

  if (mapStore.isLoaded) {
    void sectStore.refreshTerritories()
  }
})

onUnmounted(() => {
  if (influenceGraphics) {
    influenceGraphics.destroy()
    influenceGraphics = null
  }
})

watch(
  () => [
    sectStore.activeTerritories
  ],
  () => {
    updateInfluence()
  },
  { deep: true }
)

watch(
  () => [mapStore.isLoaded, worldStore.year, worldStore.month],
  ([mapLoaded]) => {
    if (!mapLoaded) {
      updateInfluence()
      return
    }

    if (!sectStore.isLoading) {
      void sectStore.refreshTerritories()
    }
  }
)
</script>

<template>
  <container
    ref="container"
    label="sect-influence"
    :visible="visible"
    :z-index="props.zIndex ?? 150"
    event-mode="none"
  />
</template>
