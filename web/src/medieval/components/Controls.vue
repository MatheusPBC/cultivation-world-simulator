<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useObserverStore } from '../stores/world'
import { api } from '../api'
import { calendar } from '../mappers'
defineProps<{ aiAvailable: boolean }>()
const store = useObserverStore(), { t } = useI18n()
function speed(e: Event) { return store.perform(() => api.command('speed', { jumps_per_second: Number((e.target as HTMLSelectElement).value) })) }
function setAI(enabled: boolean) {
  return store.perform(() => api.command('ai', {
    enabled,
    ai_calls_per_step: store.snapshot!.world.config.ai_calls_per_step,
  }))
}
function setAIBudget(e: Event) {
  const aiCallsPerStep = Number((e.target as HTMLInputElement).value)
  return store.perform(() => api.command('ai', {
    enabled: store.snapshot!.world.config.ai_enabled,
    ai_calls_per_step: aiCallsPerStep,
  }))
}
</script>
<template>
  <section class="timebar" :aria-label="t('simulation')">
    <div><strong>{{ calendar(store.snapshot!.world.day) }}</strong><small data-testid="absolute-day">{{ t('absoluteDay') }} {{ store.snapshot!.world.day }}</small></div>
    <span class="status-pill" :class="{ active: !store.status?.paused }">{{ store.status?.paused ? t('paused') : t('running') }}</span>
    <div class="time-actions">
      <button :disabled="store.busy" class="primary" @click="store.perform(() => api.command(store.status?.paused ? 'resume' : 'pause', {}))">{{ store.status?.paused ? t('resume') : t('pause') }}</button>
      <button data-testid="step" :disabled="store.busy || !store.status?.paused" @click="store.perform(() => api.command('step', {}))">{{ t('step') }}</button>
      <button data-testid="ai-toggle" :disabled="store.busy || !store.status?.paused || (!aiAvailable && !store.snapshot!.world.config.ai_enabled)" @click="setAI(!store.snapshot!.world.config.ai_enabled)">{{ store.snapshot!.world.config.ai_enabled ? t('aiOn') : t('aiOff') }}</button>
      <label class="compact-label">{{ t('aiCallBudget') }}
        <input data-testid="ai-call-budget" type="number" min="1" max="256" step="1"
          :value="store.snapshot!.world.config.ai_calls_per_step" :disabled="store.busy || !store.status?.paused"
          @change="setAIBudget" />
      </label>
      <label class="compact-label">{{ t('speed') }}<select :value="store.status?.jumps_per_second" :disabled="store.busy" @change="speed"><option v-for="v in [1, 2, 5, 10, 20]" :key="v" :value="v">{{ v }}×</option></select></label>
    </div>
    <span class="muted sync-status" role="status">{{ store.busy ? t('working') : store.error ? t('stale') : t('latest') }}</span>
    <small v-if="!aiAvailable && !store.snapshot!.world.config.ai_enabled" class="muted ai-unavailable" data-testid="ai-unavailable">{{ t('aiUnavailable') }}</small>
    <small class="muted ai-budget-help">{{ t('aiCallBudgetHelp') }}</small>
  </section>
</template>
