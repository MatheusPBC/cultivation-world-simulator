<script setup lang="ts">
import { Viewport as PixiViewport } from 'pixi-viewport'
import { useApplication } from 'vue3-pixi'
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { Container } from 'pixi.js'
import { useMapViewport } from './composables/useMapViewport'

const props = defineProps<{
  screenWidth: number
  screenHeight: number
  worldWidth: number
  worldHeight: number
}>()

const app = useApplication()
const containerRef = ref<Container>()
let viewport: PixiViewport | null = null

const { register, setFitScale, syncScale, maxScale } = useMapViewport()

onMounted(async () => {
  await nextTick()
  if (!containerRef.value || !app.value) return

  viewport = new PixiViewport({
    screenWidth: props.screenWidth,
    screenHeight: props.screenHeight,
    worldWidth: props.worldWidth,
    worldHeight: props.worldHeight,
    events: app.value.renderer.events
  })

  viewport
    .drag()
    .pinch()
    .wheel()
    .decelerate({ friction: 0.9 })

  fitMap()

  // Zoom drives label level-of-detail and the zoom readout, so it has to be
  // observable rather than only living inside Pixi.
  viewport.on('zoomed', syncScale)
  viewport.on('zoomed-end', syncScale)
  viewport.on('moved-end', syncScale)

  const container = containerRef.value
  if (container.parent) container.parent.removeChild(container)
  app.value.stage.addChild(viewport)
  viewport.addChild(container)

  register(viewport)
})

function fitMap() {
    if (!viewport) return
    const { worldWidth, worldHeight, screenWidth, screenHeight } = props
    if (worldWidth < 100) return

    /*
     * Cover, not contain. Containing a 1.4:1 world inside a portrait phone
     * viewport letterboxed the map into a thin band with black above and
     * below; covering fills the frame at every aspect ratio and lets the
     * player pan. On a wide desktop the two scales are within a percent of
     * each other, so nothing is lost there.
     */
    const coverScale = Math.max(screenWidth / worldWidth, screenHeight / worldHeight)

    // Clamp the floor at the cover scale: zooming out past the world left the
    // viewport staring into empty black.
    viewport.clampZoom({ minScale: coverScale, maxScale })
    viewport.resize(screenWidth, screenHeight, worldWidth, worldHeight)
    viewport.setZoom(coverScale, true)
    viewport.moveCenter(worldWidth / 2, worldHeight / 2)
    // Keep the view inside the world so panning cannot reveal empty space.
    viewport.clamp({ direction: 'all' })

    setFitScale(coverScale)
    syncScale()
}

watch(() => [props.screenWidth, props.screenHeight], () => {
  if (viewport) {
    fitMap()
  }
})

watch(() => [props.worldWidth, props.worldHeight], () => {
    fitMap()
})

onUnmounted(() => {
  register(null)
  if (viewport) {
    viewport.destroy({ children: false })
  }
})
</script>

<template>
  <container ref="containerRef" sortable-children>
    <slot />
  </container>
</template>
