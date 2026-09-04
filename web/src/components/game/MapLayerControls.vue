<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { MapLayerVisibility } from './composables/useMapLayerRenderer'
import layersIcon from '@/assets/icons/ui/lucide/layers.svg'
import chevronIcon from '@/assets/icons/ui/lucide/chevron-down.svg'

const props = defineProps<{
  modelValue: MapLayerVisibility
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: MapLayerVisibility): void
}>()

const { t, te } = useI18n()

/**
 * Layers are grouped by what they describe, which is also how the map spec
 * separates them: `geography` is physical truth, `region_rows` is territory,
 * and sects/sites/presence belong to organizations. Nine identical buttons in a
 * flat 2-column grid gave no clue that these are three different kinds of
 * information.
 */
type LayerGroupKey = 'physical' | 'territorial' | 'organizational'

const groups: Array<{ key: LayerGroupKey; layers: Array<keyof MapLayerVisibility> }> = [
  { key: 'physical', layers: ['terrain', 'water', 'elevation'] },
  { key: 'territorial', layers: ['borders', 'routes', 'names'] },
  { key: 'organizational', layers: ['sects', 'infrastructure', 'institutionalPresence'] },
]

/*
 * Collapsed by default: the map is the point, and an expanded nine-row panel
 * covers a quarter of the western map. The handle keeps the active-layer count
 * visible, so the state is legible without opening it.
 */
const isOpen = ref(false)

const activeCount = computed(() =>
  groups
    .flatMap(group => group.layers)
    .filter(layer => props.modelValue[layer]).length,
)

const totalCount = computed(() => groups.flatMap(group => group.layers).length)

function layerLabel(key: keyof MapLayerVisibility) {
  return t(`game.map.layers.${key}.label`)
}

function layerHint(key: keyof MapLayerVisibility) {
  // Only some layers carry a caveat (routes are topological, not literal
  // paths). The rest fall back to their own label as the tooltip.
  const hintKey = `game.map.layers.${key}.hint`
  return te(hintKey) ? t(hintKey) : layerLabel(key)
}

function toggleLayer(key: keyof MapLayerVisibility) {
  emit('update:modelValue', { ...props.modelValue, [key]: !props.modelValue[key] })
}
</script>

<template>
  <section class="map-layers" :class="{ 'map-layers--collapsed': !isOpen }">
    <button
      type="button"
      class="map-layers__handle"
      :aria-expanded="isOpen"
      aria-controls="map-layers-body"
      @click="isOpen = !isOpen"
    >
      <span class="cw-icon" :style="{ '--icon-url': `url(${layersIcon})` }" aria-hidden="true" />
      <span class="map-layers__title">{{ t('game.map.layers.title') }}</span>
      <span class="map-layers__count">{{ activeCount }}/{{ totalCount }}</span>
      <span
        class="cw-icon map-layers__chevron"
        :style="{ '--icon-url': `url(${chevronIcon})` }"
        aria-hidden="true"
      />
    </button>

    <div v-show="isOpen" id="map-layers-body" class="map-layers__body">
      <div v-for="group in groups" :key="group.key" class="map-layers__group">
        <h3 class="cw-eyebrow map-layers__group-title">
          {{ t(`game.map.layers.groups.${group.key}`) }}
        </h3>
        <ul class="map-layers__list">
          <li v-for="layer in group.layers" :key="layer">
            <button
              type="button"
              class="map-layers__toggle"
              role="switch"
              :aria-checked="props.modelValue[layer]"
              :title="layerHint(layer)"
              @click="toggleLayer(layer)"
            >
              <span class="map-layers__mark" aria-hidden="true" />
              <span class="map-layers__label">{{ layerLabel(layer) }}</span>
            </button>
          </li>
        </ul>
      </div>
    </div>
  </section>
</template>

<style scoped>
.map-layers {
  /* Positioned by the `.map-chrome-stack` column in GameCanvas. */
  display: flex;
  flex-direction: column;
  min-height: 0;
  width: 210px;
  max-width: 100%;
  background: var(--surface-chrome);
  border: 1px solid var(--rule);
  border-radius: var(--r-2);
  box-shadow: var(--shadow-float);
  overflow: hidden;
}

.map-layers__handle {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: var(--s-4);
  width: 100%;
  min-height: var(--touch-target);
  padding: 0 var(--s-5);
  border: 0;
  background: var(--surface-raised);
  color: var(--text-secondary);
  font-family: var(--font-ui);
  font-size: var(--t-sm);
  cursor: pointer;
}

.map-layers__handle:hover {
  color: var(--text-primary);
}

.map-layers__handle:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring);
}

.map-layers__title {
  flex: 1;
  text-align: left;
  letter-spacing: var(--tracking-wide);
  text-transform: uppercase;
  font-size: var(--t-xs);
}

.map-layers__count {
  font-family: var(--font-numeric);
  font-size: var(--t-xs);
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
}

.map-layers__chevron {
  width: 14px;
  height: 14px;
  transition: transform var(--motion);
}

.map-layers--collapsed .map-layers__chevron {
  transform: rotate(-90deg);
}

.map-layers__body {
  /* Scrolls rather than growing past the viewport on a short window. */
  min-height: 0;
  overflow-y: auto;
  padding: var(--s-4) 0 var(--s-3);
}

.map-layers__group + .map-layers__group {
  margin-top: var(--s-2);
  border-top: 1px solid var(--rule-soft);
  padding-top: var(--s-3);
}

.map-layers__group-title {
  margin: 0;
  padding: 0 var(--s-5) var(--s-1);
  font-size: 10px;
}

.map-layers__list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.map-layers__toggle {
  display: flex;
  align-items: center;
  gap: var(--s-4);
  width: 100%;
  /* Touch target: the old buttons were 1.8rem tall. */
  min-height: 36px;
  padding: 0 var(--s-5);
  border: 0;
  background: transparent;
  color: var(--text-muted);
  font-family: var(--font-ui);
  font-size: var(--t-sm);
  text-align: left;
  cursor: pointer;
  transition: color var(--motion-fast), background var(--motion-fast);
}

.map-layers__toggle:hover {
  color: var(--text-primary);
  background: var(--surface-raised);
}

.map-layers__toggle:focus-visible {
  outline: none;
  box-shadow: inset var(--focus-ring);
}

/*
 * The on state is a filled gold mark plus a full-contrast label. Previously
 * "on" was a 0.12-alpha wash that was indistinguishable from "off".
 */
.map-layers__mark {
  position: relative;
  flex: 0 0 auto;
  width: 12px;
  height: 12px;
  border: 1px solid var(--paper-700);
  border-radius: var(--r-1);
  background: transparent;
  transition: background var(--motion-fast), border-color var(--motion-fast);
}

.map-layers__toggle[aria-checked='true'] {
  color: var(--text-primary);
}

.map-layers__toggle[aria-checked='true'] .map-layers__mark {
  border-color: var(--gold-400);
  background: var(--gold-400);
}

.map-layers__toggle[aria-checked='true'] .map-layers__mark::after {
  content: '';
  position: absolute;
  inset: 2px 2px 3px 2px;
  border-left: 1.5px solid var(--ink-900);
  border-bottom: 1.5px solid var(--ink-900);
  transform: rotate(-45deg);
}

.map-layers__label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 720px) {
  .map-layers {
    width: 190px;
  }
}
</style>
