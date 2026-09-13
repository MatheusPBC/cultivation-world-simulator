<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useObserverStore } from '../stores/world'
import { api } from '../api'
import { calendar } from '../mappers'
const store = useObserverStore(), { t } = useI18n()
function speed(e: Event) { return store.perform(() => api.command('speed', { jumps_per_second: Number((e.target as HTMLSelectElement).value) })) }
</script>
<template>
  <section class="timebar" :aria-label="t('simulation')">
    <div><strong>{{ calendar(store.snapshot!.world.day) }}</strong><small data-testid="absolute-day">{{ t('absoluteDay') }} {{ store.snapshot!.world.day }}</small></div>
    <span class="status-pill" :class="{ active: !store.status?.paused }">{{ store.status?.paused ? t('paused') : t('running') }}</span>
    <div class="time-actions">
      <button :disabled="store.busy" class="primary" @click="store.perform(() => api.command(store.status?.paused ? 'resume' : 'pause', {}))">{{ store.status?.paused ? t('resume') : t('pause') }}</button>
      <button data-testid="step" :disabled="store.busy || !store.status?.paused" @click="store.perform(() => api.command('step', {}))">{{ t('step') }}</button>
      <label class="compact-label">{{ t('speed') }}<select :value="store.status?.jumps_per_second" :disabled="store.busy" @change="speed"><option v-for="v in [1, 2, 5, 10, 20]" :key="v" :value="v">{{ v }}×</option></select></label>
    </div>
    <span class="muted sync-status" role="status">{{ store.busy ? t('working') : store.error ? t('stale') : t('latest') }}</span>
  </section>
</template>
