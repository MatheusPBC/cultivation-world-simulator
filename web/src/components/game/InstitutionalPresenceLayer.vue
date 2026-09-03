<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { Container, Graphics } from 'pixi.js'
import { useMapStore } from '@/stores/map'
import { useInstitutionalPresenceStore } from '@/stores/institutionalPresence'
import { buildInstitutionalPresenceRenderPlan, INSTITUTIONAL_PRESENCE_TILE_SIZE } from './utils/institutionalPresence'

const props = withDefaults(defineProps<{
  visible?: boolean
  zIndex?: number
}>(), {
  visible: true,
  zIndex: 175,
})

const mapStore = useMapStore()
const presenceStore = useInstitutionalPresenceStore()
const container = ref<Container>()
let overlayLayer: Container | null = null

function drawPresence() {
  if (!overlayLayer) return
  const oldChildren = overlayLayer.removeChildren()
  oldChildren.forEach(child => child.destroy({ children: true }))

  const plan = buildInstitutionalPresenceRenderPlan(
    presenceStore.regions,
    Array.from(mapStore.regions.values()),
    mapStore.territoryRows,
    props.visible,
  )
  for (const item of plan) {
    const graphics = new Graphics()
    graphics.eventMode = 'none'
    for (const [x, y] of item.cells) {
      graphics.rect(
        x * INSTITUTIONAL_PRESENCE_TILE_SIZE + 3,
        y * INSTITUTIONAL_PRESENCE_TILE_SIZE + 3,
        INSTITUTIONAL_PRESENCE_TILE_SIZE - 6,
        INSTITUTIONAL_PRESENCE_TILE_SIZE - 6,
      ).fill({ color: item.governanceColor, alpha: item.governanceAlpha })
    }

    const anchor = item.cells.reduce(
      (sum, [x, y]) => ({ x: sum.x + x, y: sum.y + y }),
      { x: 0, y: 0 },
    )
    const centerX = ((anchor.x / item.cells.length) + 0.5) * INSTITUTIONAL_PRESENCE_TILE_SIZE
    const centerY = ((anchor.y / item.cells.length) + 0.5) * INSTITUTIONAL_PRESENCE_TILE_SIZE
    item.influenceMarkers.forEach((marker, index) => {
      const angle = (Math.PI * 2 * index) / Math.max(item.influenceMarkers.length, 1) - Math.PI / 2
      const radius = 13
      graphics.circle(centerX + Math.cos(angle) * radius, centerY + Math.sin(angle) * radius, 3)
        .fill({ color: marker.color, alpha: 0.35 + marker.share * 0.35 })
    })
    overlayLayer.addChild(graphics)
  }
}

onMounted(() => {
  if (!container.value || typeof container.value.addChild !== 'function') return
  overlayLayer = new Container()
  overlayLayer.eventMode = 'none'
  container.value.addChild(overlayLayer)
  drawPresence()
})

onUnmounted(() => {
  overlayLayer?.destroy({ children: true })
  overlayLayer = null
})

watch(
  [() => presenceStore.regions, () => mapStore.territoryRows, () => mapStore.regions, () => props.visible],
  drawPresence,
  { deep: true },
)
</script>

<template>
  <container
    ref="container"
    label="institutional-presence"
    :visible="props.visible"
    :z-index="props.zIndex"
    event-mode="none"
  />
</template>
