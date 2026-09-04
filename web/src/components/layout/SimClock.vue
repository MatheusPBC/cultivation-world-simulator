<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import playIcon from '@/assets/icons/ui/lucide/play.svg'
import pauseIcon from '@/assets/icons/ui/lucide/pause.svg'

/**
 * Time and the run/pause control, as one object.
 *
 * These are the two most important pieces of state in a simulation, and they
 * used to be a low-contrast text chip in a bookmark bar and a translucent
 * square in the opposite corner of the screen. Binding them together makes the
 * simulation's status readable at a glance and puts the control where the state
 * is.
 */
const props = withDefaults(defineProps<{
  year: number | string
  month: number | string
  paused: boolean
  connected?: boolean
  /** Compact drops the era caption; used by the mobile header. */
  compact?: boolean
}>(), {
  connected: true,
  compact: false,
})

const emit = defineEmits<{
  (e: 'toggle-pause'): void
  (e: 'open-time'): void
}>()

const { t, locale } = useI18n()

const isCjk = computed(() => locale.value.startsWith('zh') || locale.value.startsWith('ja'))

/*
 * The year/month units come from the locale (`common.year` / `common.month`),
 * so PT-BR renders "106 A · 12 M" rather than the CJK 年/月 that leaked through
 * before. CJK locales keep their tight, unspaced form.
 */
const yearLabel = computed(() => `${props.year}${isCjk.value ? t('common.year') : ''}`)
const monthLabel = computed(() => (
  isCjk.value ? `${props.month}${t('common.month')}` : `${props.month}`
))

const stateLabel = computed(() => (
  props.paused ? t('game.controls.paused') : t('game.controls.running')
))

const toggleLabel = computed(() => (
  props.paused ? t('game.controls.resume') : t('game.controls.pause')
))
</script>

<template>
  <div class="clock" :class="{ 'clock--paused': paused, 'clock--compact': compact }">
    <button
      type="button"
      class="clock__toggle"
      :aria-label="toggleLabel"
      :title="toggleLabel"
      @click="emit('toggle-pause')"
    >
      <span
        class="cw-icon clock__toggle-icon"
        :style="{ '--icon-url': `url(${paused ? playIcon : pauseIcon})` }"
        aria-hidden="true"
      />
    </button>

    <button
      v-if="!compact"
      type="button"
      class="clock__readout"
      :title="t('game.status_bar.time_detail')"
      @click="emit('open-time')"
    >
      <span class="clock__date">
        <span class="clock__year">{{ yearLabel }}</span>
        <span class="clock__sep" aria-hidden="true">·</span>
        <span class="clock__month">{{ monthLabel }}</span>
      </span>
      <span class="clock__state">
        <span
          class="clock__pip"
          :class="{ 'clock__pip--offline': !connected }"
          :title="connected ? t('game.status_bar.connected') : t('game.status_bar.disconnected')"
        />
        <span class="clock__state-text">{{ stateLabel }}</span>
      </span>
    </button>

    <div v-else class="clock__readout clock__readout--static">
      <span class="clock__date">
        <span class="clock__year">{{ yearLabel }}</span>
        <span class="clock__sep" aria-hidden="true">·</span>
        <span class="clock__month">{{ monthLabel }}</span>
      </span>
      <span class="clock__state">
        <span
          class="clock__pip"
          :class="{ 'clock__pip--offline': !connected }"
          :title="connected ? t('game.status_bar.connected') : t('game.status_bar.disconnected')"
        />
        <span class="clock__state-text">{{ stateLabel }}</span>
      </span>
    </div>
  </div>
</template>

<style scoped>
.clock {
  display: flex;
  align-items: stretch;
  flex: 0 0 auto;
  border: 1px solid var(--rule);
  border-radius: var(--r-2);
  background: var(--surface-sunken);
  overflow: hidden;
}

/* Paused is a state of the whole clock, not a floating pill elsewhere. */
.clock--paused {
  border-color: var(--gold-600);
  background: linear-gradient(var(--gold-wash), var(--gold-wash)), var(--surface-sunken);
}

.clock__toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--touch-target);
  border: 0;
  border-right: 1px solid var(--rule);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: color var(--motion-fast), background var(--motion-fast);
}

.clock__toggle:hover {
  color: var(--text-primary);
  background: var(--surface-raised);
}

.clock__toggle:focus-visible {
  outline: none;
  box-shadow: inset var(--focus-ring);
}

.clock--paused .clock__toggle {
  color: var(--gold-200);
}

.clock__toggle-icon {
  width: 18px;
  height: 18px;
}

.clock__readout {
  display: flex;
  align-items: baseline;
  gap: var(--s-4);
  min-height: var(--touch-target);
  padding: 0 var(--s-5);
  border: 0;
  background: transparent;
  color: var(--text-primary);
  cursor: pointer;
  text-align: left;
}

.clock__readout:hover .clock__date {
  color: var(--accent-strong);
}

.clock__readout:focus-visible {
  outline: none;
  box-shadow: inset var(--focus-ring);
}

.clock__readout--static {
  cursor: default;
}

/* The date is the display voice of the setting: a book serif, tabular. */
.clock__date {
  display: inline-flex;
  align-items: baseline;
  gap: var(--s-3);
  font-family: var(--font-display);
  font-size: var(--t-display);
  line-height: 1;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
  transition: color var(--motion-fast);
}

.clock__sep {
  color: var(--paper-700);
}

.clock__month {
  font-size: var(--t-lg);
  color: var(--text-secondary);
}

.clock__state {
  display: inline-flex;
  align-items: center;
  gap: var(--s-3);
}

.clock__state-text {
  font-family: var(--font-ui);
  font-size: 10px;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  color: var(--text-muted);
}

.clock--paused .clock__state-text {
  color: var(--gold-300);
}

.clock__pip {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--state-ok);
}

.clock__pip--offline {
  background: var(--state-alert);
}

.clock--compact .clock__date {
  font-size: var(--t-lg);
}

.clock--compact .clock__month {
  font-size: var(--t-md);
}

@media (max-width: 900px) {
  .clock__state-text {
    display: none;
  }
}
</style>
