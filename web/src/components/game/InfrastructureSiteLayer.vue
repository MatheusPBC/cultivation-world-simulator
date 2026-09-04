<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { Container, Graphics, Rectangle } from 'pixi.js'
import { useMapStore } from '@/stores/map'
import { useAudio } from '@/composables/useAudio'
import { buildInfrastructureSiteRenderPlan } from './utils/infrastructureSites'
import { MAP_SITE } from '@/constants/mapTheme'

const props = withDefaults(defineProps<{
  visible?: boolean
  zIndex?: number
}>(), {
  visible: true,
  zIndex: 350,
})

const emit = defineEmits<{
  (event: 'siteSelected', payload: { type: 'site'; id: string; name?: string; kind?: string }): void
}>()

const mapStore = useMapStore()
const { play } = useAudio()
const container = ref<Container>()
let markerLayer: Container | null = null

const sites = computed(() => Array.from(mapStore.infrastructureSites.values()))

/**
 * Sites are engraved survey marks: a dark plate, a paper rim and a status
 * glyph. The old solid colored disc competed with the characters for
 * attention while carrying far less meaning.
 */
function drawMarker(graphics: Graphics, color: number, status: string) {
  graphics.clear()
  const r = MAP_SITE.radius

  graphics.circle(0, 0, r + 2).fill({ color: MAP_SITE.casingColor, alpha: 0.85 })
  graphics.circle(0, 0, r).fill({ color: MAP_SITE.plateColor, alpha: 0.95 })
  // The owner/kind color survives as a thin rim, so identity is kept.
  graphics.circle(0, 0, r).stroke({ color, width: 2, alpha: 0.9 })

  if (status === 'destroyed') {
    graphics.moveTo(-4.5, -4.5).lineTo(4.5, 4.5)
      .stroke({ color: MAP_SITE.destroyedAccent, width: 2.4, cap: 'round' })
    graphics.moveTo(4.5, -4.5).lineTo(-4.5, 4.5)
      .stroke({ color: MAP_SITE.destroyedAccent, width: 2.4, cap: 'round' })
    return
  }
  if (status === 'impaired') {
    graphics.moveTo(-5, 0).lineTo(5, 0)
      .stroke({ color: MAP_SITE.impairedAccent, width: 2.4, cap: 'round' })
    return
  }
  graphics.circle(0, 0, 3).fill({ color: MAP_SITE.activeAccent, alpha: 0.95 })
}

function handleSiteSelect(site: { id: string; name: string; kind: string; clickable: boolean }) {
  if (!site.clickable) return
  play('select')
  emit('siteSelected', { type: 'site', id: site.id, name: site.name, kind: site.kind })
}

function renderSites() {
  if (!markerLayer) return
  const oldChildren = markerLayer.removeChildren()
  oldChildren.forEach(child => child.destroy({ children: true }))

  const plan = buildInfrastructureSiteRenderPlan(sites.value, props.visible)
  for (const item of plan) {
    const site = mapStore.infrastructureSites.get(item.id)
    if (!site) continue
    const marker = new Container()
    marker.x = item.position.x
    marker.y = item.position.y
    marker.eventMode = item.clickable ? 'static' : 'none'
    marker.cursor = item.clickable ? 'pointer' : 'default'
    marker.hitArea = new Rectangle(-24, -24, 48, 48)
    marker.on('pointertap', () => handleSiteSelect(site))

    const graphics = new Graphics()
    drawMarker(graphics, item.color, item.status)
    graphics.eventMode = 'none'
    marker.addChild(graphics)
    markerLayer.addChild(marker)
  }
}

onMounted(() => {
  if (!container.value) return
  markerLayer = new Container()
  markerLayer.sortableChildren = true
  container.value.addChild(markerLayer)
  renderSites()
})

onUnmounted(() => {
  markerLayer?.destroy({ children: true })
  markerLayer = null
})

watch(
  [sites, () => props.visible],
  () => renderSites(),
  { deep: true },
)
</script>

<template>
  <container
    ref="container"
    label="infrastructure-sites"
    :z-index="props.zIndex"
    :visible="props.visible"
    event-mode="none"
  />
</template>
