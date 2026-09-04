<script setup lang="ts">
import { computed } from 'vue'
import SectInfluenceLayer from './SectInfluenceLayer.vue'
import InstitutionalPresenceLayer from './InstitutionalPresenceLayer.vue'
import {
  DEFAULT_MAP_LAYER_VISIBILITY,
  MAP_LAYER_Z_INDEX,
  useMapLayerRenderer,
  type MapLayerVisibility,
} from './composables/useMapLayerRenderer'

const props = withDefaults(defineProps<{ visibility?: MapLayerVisibility }>(), {
  visibility: undefined,
})

const emit = defineEmits<{
  (e: 'mapLoaded', payload: { width: number, height: number }): void
  (e: 'regionSelected', payload: { type: 'region'; id: string; name?: string }): void
}>()

const mapVisibility = computed(() => props.visibility)
const resolvedVisibility = computed(() => props.visibility ?? DEFAULT_MAP_LAYER_VISIBILITY)

/*
 * The physical map, the region hit areas, the selection feedback and the region
 * names are all owned by the renderer. Names in particular need plate geometry,
 * a zoom counter-scale and level-of-detail, which is not expressible as a
 * template loop — they used to be a `@vue-ignore` block with an estimated text
 * hit area, which is why the territory itself was not clickable.
 */
const renderer = useMapLayerRenderer(emit, mapVisibility)
const mapContainer = renderer.mapContainer
</script>

<template>
  <container label="map-layers" sortable-children>
    <container ref="mapContainer" label="physical-map" :z-index="MAP_LAYER_Z_INDEX.physical" />

    <SectInfluenceLayer
      :visible="resolvedVisibility.sects"
      :z-index="MAP_LAYER_Z_INDEX.sects"
    />

    <InstitutionalPresenceLayer
      :visible="resolvedVisibility.institutionalPresence"
      :z-index="MAP_LAYER_Z_INDEX.institutionalPresence"
    />
  </container>
</template>
