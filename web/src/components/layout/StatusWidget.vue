<script setup lang="ts">
import { NPopover } from 'naive-ui'

/**
 * A single HUD navigation entry.
 *
 * Restyled from the old bold, per-item coloured text separated by literal `|`
 * characters. Colour is no longer used for identity — that read as a rainbow
 * bookmark bar and left nothing to express state, which the repo's status-bar
 * rule explicitly warns against. Identity now comes from the icon and the
 * group it sits in; `accent` is reserved for items that carry live state
 * (currently the world phenomenon, whose rarity is meaningful).
 */
interface Props {
  label: string
  icon?: string
  /** Optional meaningful accent. Omit for plain navigation entries. */
  accent?: string
  disablePopover?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  disablePopover: false,
})

const emit = defineEmits(['trigger-click'])
</script>

<template>
  <div class="status-widget">
    <button
      v-if="disablePopover"
      type="button"
      class="widget-trigger"
      :class="{ 'widget-trigger--accented': !!props.accent }"
      :style="props.accent ? { '--widget-accent': props.accent } : undefined"
      :title="props.label"
      @click="emit('trigger-click')"
      v-sound="'open'"
    >
      <span
        v-if="props.icon"
        class="cw-icon widget-icon"
        :style="{ '--icon-url': `url(${props.icon})` }"
        aria-hidden="true"
      />
      <span class="widget-label">{{ props.label }}</span>
    </button>

    <n-popover v-else trigger="click" placement="bottom" style="max-width: 600px;">
      <template #trigger>
        <button
          type="button"
          class="widget-trigger"
          :class="{ 'widget-trigger--accented': !!props.accent }"
          :style="props.accent ? { '--widget-accent': props.accent } : undefined"
          :title="props.label"
          @click="emit('trigger-click')"
          v-sound="'open'"
        >
          <span
            v-if="props.icon"
            class="cw-icon widget-icon"
            :style="{ '--icon-url': `url(${props.icon})` }"
            aria-hidden="true"
          />
          <span class="widget-label">{{ props.label }}</span>
        </button>
      </template>

      <div class="widget-content">
        <slot name="single"></slot>
      </div>
    </n-popover>
  </div>
</template>

<style scoped>
.status-widget {
  min-width: 0;
  flex: 0 0 auto;
}

.widget-trigger {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: var(--s-3);
  /* 44px touch target: the old 36px bar had none. */
  min-height: var(--touch-target);
  padding: 0 var(--s-4);
  border: 0;
  border-radius: var(--r-1);
  background: transparent;
  color: var(--text-secondary);
  font-family: var(--font-ui);
  font-size: var(--t-sm);
  font-weight: 400;
  white-space: nowrap;
  cursor: pointer;
  transition: color var(--motion-fast), background var(--motion-fast);
}

/* Active/hover is a gold underline, one accent for the whole bar. */
.widget-trigger::after {
  content: '';
  position: absolute;
  left: var(--s-4);
  right: var(--s-4);
  bottom: 6px;
  height: 1px;
  background: var(--accent);
  opacity: 0;
  transition: opacity var(--motion-fast);
}

.widget-trigger:hover {
  color: var(--text-primary);
  background: var(--surface-raised);
}

.widget-trigger:hover::after {
  opacity: 0.8;
}

.widget-trigger:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring);
}

.widget-trigger:active {
  background: var(--surface-sunken);
}

.widget-trigger--accented {
  color: var(--widget-accent, var(--text-primary));
}

.widget-trigger--accented .widget-icon {
  color: var(--widget-accent, var(--accent));
}

.widget-icon {
  width: 15px;
  height: 15px;
}

.widget-label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/*
 * Below the desktop breakpoint the rail becomes icon-only. The accessible name
 * survives in `title`, and the target stays 44px, so nothing is lost and the
 * bar stops silently overflowing into a hidden horizontal scroll.
 */
@media (max-width: 1180px) {
  .widget-label {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip-path: inset(50%);
    white-space: nowrap;
  }

  .widget-trigger {
    min-width: var(--touch-target);
    justify-content: center;
    padding: 0;
  }

  .widget-icon {
    width: 17px;
    height: 17px;
  }
}
</style>
