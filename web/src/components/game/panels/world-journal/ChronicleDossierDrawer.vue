<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import type { ChronicleDossierResponseDTO, EventDTO } from '@/types/api'

const props = withDefaults(defineProps<{
  open?: boolean
  dossier?: ChronicleDossierResponseDTO | null
  loading?: boolean
  error?: boolean
  onClose?: () => void
  onOpenWhy?: (eventId: string) => void
}>(), {
  open: false,
  dossier: null,
  loading: false,
  error: false,
})

const emit = defineEmits<{ close: [] }>()
const { t } = useI18n()

function close() {
  props.onClose?.()
  emit('close')
}

function openWhy(eventId: string) {
  props.onOpenWhy?.(eventId)
}

function eventText(event: EventDTO) {
  return event.content || event.text
}

function eventDate(event: EventDTO) {
  return `${event.year}${t('common.year')} ${event.month}${t('common.month')}`
}
</script>

<template>
  <div v-if="open" class="chronicle-dossier-overlay" data-testid="chronicle-dossier-overlay" role="dialog" aria-modal="true">
    <aside class="chronicle-dossier" data-testid="chronicle-dossier">
      <header class="chronicle-dossier__header">
        <h3>{{ t('game.world_journal.chronicle.dossier') }}</h3>
        <button type="button" class="chronicle-dossier__close" :aria-label="t('game.world_journal.chronicle.close')" @click="close">&times;</button>
      </header>
      <div class="chronicle-dossier__body">
        <p v-if="loading" class="chronicle-dossier__state">{{ t('game.world_journal.chronicle.loading') }}</p>
        <p v-else-if="error" class="chronicle-dossier__state chronicle-dossier__state--error">{{ t('game.world_journal.chronicle.dossier_error') }}</p>
        <template v-else-if="dossier">
          <p class="chronicle-dossier__claim">{{ dossier.anchor.label }}</p>
          <p v-if="dossier.pruned_source_ids.length" class="chronicle-dossier__note">
            {{ t('game.world_journal.chronicle.pruned', { count: dossier.pruned_source_ids.length }) }}
            <span class="chronicle-dossier__pruned-ids">{{ dossier.pruned_source_ids.join(', ') }}</span>
          </p>
          <p v-if="dossier.truncated" class="chronicle-dossier__note">
            {{ t('game.world_journal.chronicle.truncated') }}
          </p>
          <section class="chronicle-dossier__section">
            <h4>{{ t('game.world_journal.chronicle.sequence') }}</h4>
            <p v-if="dossier.sequence.length === 0" class="chronicle-dossier__state">{{ t('game.world_journal.chronicle.sequence_empty') }}</p>
            <article v-for="event in dossier.sequence" :key="event.id" class="chronicle-dossier__event">
              <time>{{ eventDate(event) }}</time>
              <p>{{ eventText(event) }}</p>
              <button type="button" class="chronicle-dossier__why" :data-testid="`dossier-why-${event.id}`" @click="openWhy(event.id)">
                {{ t('game.world_journal.chronicle.why') }}
              </button>
            </article>
          </section>
        </template>
      </div>
    </aside>
  </div>
</template>

<style scoped>
/*
 * The dossier is the evidence behind a chronicle claim: a lacquered drawer with
 * the claim as its dateline and the source sequence as a ruled ledger.
 */
.chronicle-dossier-overlay {
  position: fixed;
  inset: 0;
  z-index: 55;
  display: flex;
  justify-content: flex-end;
  background: var(--surface-scrim);
}

.chronicle-dossier {
  width: min(520px, 100%);
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--surface-panel);
  border-left: 1px solid var(--rule-strong);
  box-shadow: var(--shadow-panel);
}

.chronicle-dossier__header {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--s-5) var(--s-6);
  border-bottom: 1px solid var(--rule);
}

.chronicle-dossier__header h3 {
  margin: 0;
  color: var(--text-muted);
  font-size: 10px;
  font-weight: 400;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
}

.chronicle-dossier__close {
  min-width: var(--touch-target);
  min-height: var(--touch-target);
  border: 0;
  background: transparent;
  color: var(--text-secondary);
  font-size: 20px;
  cursor: pointer;
  transition: color var(--motion-fast);
}

.chronicle-dossier__close:hover {
  color: var(--text-primary);
}

.chronicle-dossier__close:focus-visible {
  outline: none;
  box-shadow: inset var(--focus-ring);
}

.chronicle-dossier__body {
  min-height: 0;
  overflow-y: auto;
  padding: var(--s-6);
}

.chronicle-dossier__claim {
  margin: 0;
  padding: 0 0 var(--s-5) var(--s-5);
  border-left: 2px solid var(--accent);
  border-bottom: 1px solid var(--rule);
  background: transparent;
  color: var(--text-primary);
  font-family: var(--font-display);
  font-size: var(--t-lg);
  line-height: 1.6;
}

/* Pruning and truncation are epistemic caveats: gold rule, quiet copy. */
.chronicle-dossier__note,
.chronicle-dossier__state {
  margin: var(--s-5) 0 0;
  padding: 0 0 0 var(--s-4);
  border: 0;
  border-left: 2px solid var(--gold-600);
  border-radius: 0;
  color: var(--text-muted);
  font-size: var(--t-xs);
  line-height: 1.55;
}

.chronicle-dossier__state--error {
  border-left-color: var(--cinnabar-400);
  color: var(--state-alert);
}

.chronicle-dossier__section {
  margin-top: var(--s-7);
}

.chronicle-dossier__section h4 {
  margin: 0 0 var(--s-4);
  color: var(--text-muted);
  font-size: 10px;
  font-weight: 400;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
}

.chronicle-dossier__event {
  position: relative;
  margin-top: 0;
  padding: var(--s-5) 64px var(--s-5) 0;
  border: 0;
  border-radius: 0;
  background: transparent;
}

.chronicle-dossier__event + .chronicle-dossier__event {
  border-top: 1px solid var(--rule-soft);
}

.chronicle-dossier__event time {
  color: var(--text-muted);
  font-family: var(--font-numeric);
  font-size: 10px;
  font-variant-numeric: tabular-nums;
}

.chronicle-dossier__event p {
  margin: var(--s-2) 0 0;
  color: var(--text-primary);
  font-size: var(--t-md);
  line-height: 1.55;
  overflow-wrap: anywhere;
}

.chronicle-dossier__why {
  position: absolute;
  top: var(--s-5);
  right: 0;
  min-height: 26px;
  padding: 0 var(--s-3);
  border: 0;
  border-bottom: 1px solid var(--gold-600);
  border-radius: 0;
  background: transparent;
  color: var(--accent);
  font-family: var(--font-ui);
  font-size: 10px;
  cursor: pointer;
  transition: color var(--motion-fast), border-color var(--motion-fast);
}

.chronicle-dossier__why:hover {
  color: var(--accent-strong);
  border-bottom-color: var(--accent);
}

.chronicle-dossier__why:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring);
}

@media (max-width: 760px) {
  .chronicle-dossier {
    width: 100%;
  }

  .chronicle-dossier__event p {
    font-size: 16px;
    line-height: 1.6;
  }

  .chronicle-dossier__why {
    min-height: 44px;
  }
}
</style>
