<script setup lang="ts">
import { Rectangle } from 'pixi.js'
import { computed } from 'vue'
import SectInfluenceLayer from './SectInfluenceLayer.vue'
import InstitutionalPresenceLayer from './InstitutionalPresenceLayer.vue'
import {
  DEFAULT_MAP_LAYER_VISIBILITY,
  MAP_LAYER_Z_INDEX,
  useMapLayerRenderer,
  type MapLayerVisibility,
} from './composables/useMapLayerRenderer'
import { estimateRegionLabelSize } from './utils/mapLabels'

const props = withDefaults(defineProps<{ visibility?: MapLayerVisibility }>(), {
  visibility: undefined,
})

const emit = defineEmits<{
  (e: 'mapLoaded', payload: { width: number, height: number }): void
  (e: 'regionSelected', payload: { type: 'region'; id: string; name?: string }): void
}>()

const mapVisibility = computed(() => props.visibility)
const resolvedVisibility = computed(() => props.visibility ?? DEFAULT_MAP_LAYER_VISIBILITY)
const renderer = useMapLayerRenderer(emit, mapVisibility)

// Keep the public bindings explicit: the labels are rendered by Vue, while
// the physical/territorial layers are owned by the Pixi renderer.
const mapContainer = renderer.mapContainer
const locale = renderer.locale
const visibleRegionLabels = renderer.visibleRegionLabels
const getRegionTextStyle = renderer.getRegionTextStyle
const handleRegionSelect = renderer.handleRegionSelect

function getRegionLabelHitArea(label: string, type: string, locale: string) {
  const { width, height } = estimateRegionLabelSize(label, type, locale)
  return new Rectangle(-width / 2, -height / 2, width, height)
}

</script>

<template>
  <container label="map-layers" sortable-children>
     <!-- Tile Layer -->
     <container ref="mapContainer" label="physical-map" :z-index="MAP_LAYER_Z_INDEX.physical" />

     <SectInfluenceLayer
       :visible="resolvedVisibility.sects"
       :z-index="MAP_LAYER_Z_INDEX.sects"
     />

     <InstitutionalPresenceLayer
       :visible="resolvedVisibility.institutionalPresence"
       :z-index="MAP_LAYER_Z_INDEX.institutionalPresence"
     />
     
     <!-- Region Labels Layer (Above tiles) -->
     <container label="region-labels" :z-index="MAP_LAYER_Z_INDEX.labels">
        <!-- @vue-ignore -->
        <container
            v-for="r in visibleRegionLabels"
            :key="r.id"
            :x="r.labelX"
            :y="r.labelY"
            :hitArea="getRegionLabelHitArea(r.displayName, r.type, locale)"
            event-mode="static"
            cursor="pointer"
            @pointertap="handleRegionSelect(r)"
        >
            <!-- @vue-ignore -->
            <text
                :text="r.displayName"
                :anchor="0.5"
                :style="getRegionTextStyle(r.type, locale)"
                event-mode="none"
            />
        </container>
     </container>
  </container>
</template>
