<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { MapLayerVisibility } from './composables/useMapLayerRenderer'
import { DEFAULT_MAP_LAYER_VISIBILITY } from './composables/useMapLayerRenderer'
import chevronIcon from '@/assets/icons/ui/lucide/chevron-down.svg'

const props = withDefaults(defineProps<{ visibility?: MapLayerVisibility }>(), {
  visibility: undefined,
})

const { t } = useI18n()
const isOpen = ref(false)

const layers = computed(() => props.visibility ?? DEFAULT_MAP_LAYER_VISIBILITY)

/**
 * The legend documents the drawing vocabulary the renderer actually uses, and
 * only for layers currently switched on. Nothing here is invented: each entry
 * corresponds to a mark produced by `useMapLayerRenderer` from canonical map
 * state.
 */
type LegendEntry = {
  key: string
  swatch: 'route-land' | 'route-water' | 'route-severed' | 'coast' | 'border' | 'sect' | 'site' | 'flow'
  when: boolean
}

const entries = computed<LegendEntry[]>(() => ([
  { key: 'coast', swatch: 'coast', when: layers.value.water },
  { key: 'flow', swatch: 'flow', when: layers.value.water },
  { key: 'border', swatch: 'border', when: layers.value.borders },
  { key: 'route_land', swatch: 'route-land', when: layers.value.routes },
  { key: 'route_water', swatch: 'route-water', when: layers.value.routes },
  { key: 'route_severed', swatch: 'route-severed', when: layers.value.routes },
  { key: 'sect', swatch: 'sect', when: layers.value.sects },
  { key: 'site', swatch: 'site', when: layers.value.infrastructure },
].filter(entry => entry.when) as LegendEntry[]))
</script>

<template>
  <section v-if="entries.length" class="map-legend" :class="{ 'map-legend--open': isOpen }">
    <button
      type="button"
      class="map-legend__handle"
      :aria-expanded="isOpen"
      aria-controls="map-legend-body"
      @click="isOpen = !isOpen"
    >
      <span class="map-legend__title">{{ t('game.map.legend.title') }}</span>
      <span
        class="cw-icon map-legend__chevron"
        :style="{ '--icon-url': `url(${chevronIcon})` }"
        aria-hidden="true"
      />
    </button>

    <dl v-show="isOpen" id="map-legend-body" class="map-legend__body">
      <div v-for="entry in entries" :key="entry.key" class="map-legend__row">
        <dt class="map-legend__swatch" :class="`map-legend__swatch--${entry.swatch}`" aria-hidden="true" />
        <dd class="map-legend__label">{{ t(`game.map.legend.${entry.key}`) }}</dd>
      </div>
    </dl>
  </section>
</template>

<style scoped>
.map-legend {
  /*
   * Positioning is owned by the `.map-chrome-stack` column in GameCanvas: an
   * absolute offset computed from the layer panel's height cannot work, because
   * that panel grows and collapses.
   */
  width: 210px;
  max-width: 100%;
  background: var(--surface-chrome);
  border: 1px solid var(--rule);
  border-radius: var(--r-2);
  box-shadow: var(--shadow-float);
  overflow: hidden;
}

.map-legend__handle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--s-4);
  width: 100%;
  min-height: 34px;
  padding: 0 var(--s-5);
  border: 0;
  background: transparent;
  color: var(--text-muted);
  font-family: var(--font-ui);
  cursor: pointer;
}

.map-legend__handle:hover {
  color: var(--text-primary);
}

.map-legend__handle:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring);
}

.map-legend__title {
  font-size: 10px;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
}

.map-legend__chevron {
  width: 13px;
  height: 13px;
  transform: rotate(-90deg);
  transition: transform var(--motion);
}

.map-legend--open .map-legend__chevron {
  transform: rotate(0deg);
}

.map-legend__body {
  margin: 0;
  padding: var(--s-2) var(--s-5) var(--s-5);
  border-top: 1px solid var(--rule-soft);
}

.map-legend__row {
  display: flex;
  align-items: center;
  gap: var(--s-4);
  min-height: 22px;
}

.map-legend__swatch {
  flex: 0 0 auto;
  width: 22px;
  height: 10px;
  margin: 0;
}

/* Swatches mirror the exact marks drawn on the map. */
.map-legend__swatch--coast {
  border-bottom: 2px solid var(--paper-200);
  box-shadow: 0 3px 0 -1px rgba(18, 26, 28, 0.6);
}

.map-legend__swatch--border {
  border-bottom: 1.5px dotted var(--paper-300);
}

.map-legend__swatch--flow {
  border-bottom: 2px solid var(--jade-300);
  opacity: 0.6;
}

.map-legend__swatch--route-land {
  border-bottom: 3px solid var(--gold-400);
}

.map-legend__swatch--route-water {
  border-bottom: 3px dashed var(--jade-400);
}

.map-legend__swatch--route-severed {
  border-bottom: 3px dashed var(--cinnabar-400);
}

.map-legend__swatch--sect {
  height: 12px;
  border: 1px solid var(--paper-300);
  background: repeating-linear-gradient(
    -45deg,
    rgba(205, 198, 182, 0.35) 0 2px,
    transparent 2px 6px
  );
}

.map-legend__swatch--site {
  width: 12px;
  height: 12px;
  border: 2px solid var(--paper-200);
  border-radius: 50%;
  background: var(--jade-300);
  background-clip: content-box;
  padding: 2px;
}

.map-legend__label {
  margin: 0;
  min-width: 0;
  color: var(--text-secondary);
  font-family: var(--font-ui);
  font-size: var(--t-xs);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 720px) {
  .map-legend {
    width: 190px;
  }
}
</style>
