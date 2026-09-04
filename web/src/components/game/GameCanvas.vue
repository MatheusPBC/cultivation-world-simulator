<script setup lang="ts">
import { Application } from 'vue3-pixi'
import { ref, onMounted } from 'vue'
import { useElementSize } from '@vueuse/core'
import Viewport from './Viewport.vue'
import MapLayer from './MapLayer.vue'
import EntityLayer from './EntityLayer.vue'
import POILayer from './POILayer.vue'
import InfrastructureSiteLayer from './InfrastructureSiteLayer.vue'
import PerceptionLayer from './PerceptionLayer.vue'
import MapLayerControls from './MapLayerControls.vue'
import MapViewControls from './MapViewControls.vue'
import MapLegend from './MapLegend.vue'
import { DEFAULT_MAP_LAYER_VISIBILITY } from './composables/useMapLayerRenderer'
import CloudLayer from './CloudLayer.vue'
import { useTextures } from './composables/useTextures'
import { MAP_INK } from '@/constants/mapTheme'

const container = ref<HTMLElement>()
const { width, height } = useElementSize(container)
const { loadBaseTextures, isLoaded } = useTextures()

const mapSize = ref({ width: 2000, height: 2000 })
const layerVisibility = ref({ ...DEFAULT_MAP_LAYER_VISIBILITY })

defineProps<{
  sidebarWidth?: number
  /** Mobile hides the layer panel to keep the map surface clear. */
  compact?: boolean
}>()

const emit = defineEmits<{
  (e: 'avatarSelected', payload: { type: 'avatar'; id: string; name?: string }): void
  (e: 'regionSelected', payload: { type: 'region'; id: string; name?: string }): void
  (e: 'poiSelected', payload: { type: 'avatar' | 'poi'; id: string; kind?: string; name?: string }): void
  (e: 'siteSelected', payload: { type: 'site'; id: string; kind?: string; name?: string }): void
}>()

function onMapLoaded(size: { width: number, height: number }) {
    mapSize.value = size
}

function handleAvatarSelected(payload: { type: 'avatar'; id: string; name?: string }) {
  emit('avatarSelected', payload)
}

function handleRegionSelected(payload: { type: 'region'; id: string; name?: string }) {
  emit('regionSelected', payload)
}

function handlePoiSelected(payload: { type: 'avatar' | 'poi'; id: string; kind?: string; name?: string }) {
  emit('poiSelected', payload)
}

function handleSiteSelected(payload: { type: 'site'; id: string; kind?: string; name?: string }) {
  emit('siteSelected', payload)
}

const devicePixelRatio = 1 // 强制为 1，避免像素风游戏在高分屏下的坐标和缩放问题

onMounted(() => {
  loadBaseTextures()
})
</script>

<template>
  <div ref="container" class="game-canvas-container">
    <!--
      antialias: false (像素风必须关闭)
      resolution: devicePixelRatio (保证清晰度)
    -->
    <Application
      v-if="width > 0 && height > 0"
      :width="width"
      :height="height"
      :resizeTo="container"
      :background-color="MAP_INK.void"
      :antialias="false"
      :resolution="devicePixelRatio"
    >
      <Viewport
        v-if="isLoaded"
        :screen-width="width"
        :screen-height="height"
        :world-width="mapSize.width"
        :world-height="mapSize.height"
      >
        <MapLayer
          @mapLoaded="onMapLoaded"
          :visibility="layerVisibility"
          @regionSelected="handleRegionSelected"
        />
        <POILayer @poiSelected="handlePoiSelected" />
        <InfrastructureSiteLayer
          :visible="layerVisibility.infrastructure"
          @siteSelected="handleSiteSelected"
        />
        <EntityLayer @avatarSelected="handleAvatarSelected" />
        <PerceptionLayer :width="mapSize.width" :height="mapSize.height" />
        <CloudLayer :width="mapSize.width" :height="mapSize.height" />
      </Viewport>
    </Application>

    <!-- Chrome sits above the canvas, never inside the Pixi scene graph. -->
    <div v-if="!compact" class="map-chrome-stack">
      <MapLegend :visibility="layerVisibility" />
      <MapLayerControls v-model="layerVisibility" />
    </div>
    <MapViewControls />
  </div>
</template>

<style scoped>
.game-canvas-container {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: var(--ink-void);
}

.game-canvas-container :deep(canvas) {
  display: block;
}

/*
 * One column owns the bottom-left chrome. Stacking with flex instead of two
 * absolute offsets means the legend cannot land on top of the layer panel when
 * that panel expands.
 */
.map-chrome-stack {
  position: absolute;
  z-index: 20;
  left: var(--s-5);
  bottom: var(--s-5);
  /* Never taller than the stage. */
  top: var(--s-5);
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  gap: var(--s-3);
  max-width: calc(100% - var(--s-7));
  /* Only the panels themselves take pointer events, not the empty column. */
  pointer-events: none;
}

.map-chrome-stack > * {
  pointer-events: auto;
}

@media (max-width: 720px) {
  .map-chrome-stack {
    left: var(--s-4);
    bottom: var(--s-4);
    top: var(--s-4);
    gap: var(--s-2);
  }
}
</style>
