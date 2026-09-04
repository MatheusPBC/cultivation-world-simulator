<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useMapViewport } from './composables/useMapViewport'
import plusIcon from '@/assets/icons/ui/lucide/plus.svg'
import minusIcon from '@/assets/icons/ui/lucide/minus.svg'
import maximizeIcon from '@/assets/icons/ui/lucide/maximize.svg'

const { t } = useI18n()

/*
 * Zoom used to be wheel/pinch only: undiscoverable, unreachable from a
 * keyboard, and with no indication of where you were in the zoom range. These
 * are real buttons over the same viewport state.
 */
const { zoomIn, zoomOut, fit, canZoomIn, canZoomOut, zoomPercent } = useMapViewport()
</script>

<template>
  <div class="map-view" role="group" :aria-label="t('game.map.view.group')">
    <button
      type="button"
      class="map-view__btn"
      :disabled="!canZoomIn"
      :title="t('game.map.view.zoom_in')"
      :aria-label="t('game.map.view.zoom_in')"
      @click="zoomIn"
    >
      <span class="cw-icon" :style="{ '--icon-url': `url(${plusIcon})` }" aria-hidden="true" />
    </button>

    <output class="map-view__readout" :aria-label="t('game.map.view.zoom_level')">
      {{ zoomPercent }}%
    </output>

    <button
      type="button"
      class="map-view__btn"
      :disabled="!canZoomOut"
      :title="t('game.map.view.zoom_out')"
      :aria-label="t('game.map.view.zoom_out')"
      @click="zoomOut"
    >
      <span class="cw-icon" :style="{ '--icon-url': `url(${minusIcon})` }" aria-hidden="true" />
    </button>

    <button
      type="button"
      class="map-view__btn map-view__btn--fit"
      :title="t('game.map.view.fit')"
      :aria-label="t('game.map.view.fit')"
      @click="fit"
    >
      <span class="cw-icon" :style="{ '--icon-url': `url(${maximizeIcon})` }" aria-hidden="true" />
    </button>
  </div>
</template>

<style scoped>
.map-view {
  position: absolute;
  z-index: 20;
  right: var(--s-5);
  bottom: var(--s-5);
  display: flex;
  flex-direction: column;
  align-items: stretch;
  background: var(--surface-chrome);
  border: 1px solid var(--rule);
  border-radius: var(--r-2);
  box-shadow: var(--shadow-float);
  overflow: hidden;
}

.map-view__btn {
  display: flex;
  align-items: center;
  justify-content: center;
  /* 44px touch target. */
  width: var(--touch-target);
  height: var(--touch-target);
  border: 0;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: color var(--motion-fast), background var(--motion-fast);
}

.map-view__btn + .map-view__btn,
.map-view__readout + .map-view__btn {
  border-top: 1px solid var(--rule-soft);
}

.map-view__btn:hover:not(:disabled) {
  color: var(--text-primary);
  background: var(--surface-raised);
}

.map-view__btn:focus-visible {
  outline: none;
  box-shadow: inset var(--focus-ring);
}

.map-view__btn:disabled {
  color: var(--paper-700);
  cursor: not-allowed;
}

.map-view__btn--fit {
  border-top: 1px solid var(--rule);
}

.map-view__readout {
  padding: var(--s-1) 0 var(--s-2);
  border-top: 1px solid var(--rule-soft);
  color: var(--text-muted);
  font-family: var(--font-numeric);
  font-size: 10px;
  font-variant-numeric: tabular-nums;
  text-align: center;
  letter-spacing: 0;
}

@media (max-width: 720px) {
  .map-view {
    right: var(--s-4);
    /* Clear of the mobile sheet handle. */
    bottom: var(--s-4);
  }
}
</style>
