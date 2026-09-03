<script setup lang="ts">
import type { MapLayerVisibility } from './composables/useMapLayerRenderer'

const props = defineProps<{
  modelValue: MapLayerVisibility
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: MapLayerVisibility): void
}>()

const layerLabels: Array<{ key: keyof MapLayerVisibility; label: string; title?: string }> = [
  { key: 'terrain', label: 'Terreno' },
  { key: 'elevation', label: 'Elevação' },
  { key: 'water', label: "Corpos d'água" },
  { key: 'borders', label: 'Fronteiras regionais' },
  {
    key: 'routes',
    label: 'Rotas',
    title: 'Ligações entre regiões; as linhas não representam o trajeto físico exato',
  },
  { key: 'sects', label: 'Influência das seitas' },
  { key: 'names', label: 'Nomes' },
  { key: 'infrastructure', label: 'Infraestrutura' },
  { key: 'institutionalPresence', label: 'Presença institucional' },
]

function toggleLayer(key: keyof MapLayerVisibility) {
  emit('update:modelValue', { ...props.modelValue, [key]: !props.modelValue[key] })
}
</script>

<template>
  <nav class="map-layer-controls" aria-label="Camadas do mapa">
    <button
      v-for="layer in layerLabels"
      :key="layer.key"
      type="button"
      class="map-layer-controls__button"
      :aria-label="layer.label"
      :aria-pressed="props.modelValue[layer.key]"
      :title="layer.title ?? layer.label"
      @click="toggleLayer(layer.key)"
    >
      <span class="map-layer-controls__dot" aria-hidden="true" />
      <span>{{ layer.label }}</span>
    </button>
  </nav>
</template>

<style scoped>
.map-layer-controls {
  position: absolute;
  z-index: 20;
  top: 0.75rem;
  left: 0.75rem;
  display: grid;
  grid-template-columns: repeat(2, max-content);
  gap: 0.35rem;
  max-width: calc(100% - 1.5rem);
  padding: 0.35rem;
  border: 1px solid rgba(238, 224, 196, 0.28);
  border-radius: 0.4rem;
  background: rgba(17, 19, 25, 0.82);
  backdrop-filter: blur(0.2rem);
}

.map-layer-controls__button {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  min-height: 1.8rem;
  padding: 0.25rem 0.5rem;
  border: 1px solid transparent;
  border-radius: 0.25rem;
  color: rgba(247, 239, 220, 0.72);
  background: transparent;
  font: inherit;
  font-size: 0.72rem;
  cursor: pointer;
}

.map-layer-controls__button:hover,
.map-layer-controls__button:focus-visible {
  border-color: rgba(238, 224, 196, 0.45);
  color: #fff5dc;
  outline: none;
}

.map-layer-controls__button[aria-pressed='true'] {
  border-color: rgba(238, 224, 196, 0.36);
  color: #fff5dc;
  background: rgba(238, 224, 196, 0.12);
}

.map-layer-controls__dot {
  width: 0.38rem;
  height: 0.38rem;
  border-radius: 50%;
  background: currentColor;
  opacity: 0.55;
}

@media (max-width: 560px) {
  .map-layer-controls {
    grid-template-columns: max-content;
  }
}
</style>
