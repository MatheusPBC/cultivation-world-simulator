<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { Container, Graphics, Rectangle } from 'pixi.js'
import { useMapStore } from '@/stores/map'
import { useAudio } from '@/composables/useAudio'
import { buildInfrastructureSiteRenderPlan } from './utils/infrastructureSites'

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

function drawMarker(graphics: Graphics, color: number, status: string) {
  graphics.clear()
  graphics.circle(0, 0, 15).fill({ color, alpha: 0.9 })
  graphics.circle(0, 0, 15).stroke({ color: 0x201b16, width: 3, alpha: 0.9 })
  if (status === 'destroyed') {
    graphics.moveTo(-7, -7).lineTo(7, 7).stroke({ color: 0x201b16, width: 3 })
    graphics.moveTo(7, -7).lineTo(-7, 7).stroke({ color: 0x201b16, width: 3 })
  } else if (status === 'impaired') {
    graphics.moveTo(-7, 0).lineTo(7, 0).stroke({ color: 0x201b16, width: 3 })
  } else {
    graphics.circle(0, 0, 5).fill({ color: 0xfff1c2, alpha: 0.95 })
  }
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
    marker.hitArea = new Rectangle(-20, -20, 40, 40)
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
