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
.chronicle-dossier-overlay { position: fixed; inset: 0; z-index: 55; display: flex; justify-content: flex-end; background: rgba(0, 0, 0, .62); }
.chronicle-dossier { width: min(520px, 100%); height: 100%; display: flex; flex-direction: column; background: #161616; box-shadow: -8px 0 28px rgba(0, 0, 0, .45); }
.chronicle-dossier__header { flex: 0 0 auto; display: flex; align-items: center; justify-content: space-between; padding: 13px 15px; border-bottom: 1px solid #303030; }
.chronicle-dossier__header h3 { margin: 0; color: #f3e9cf; font-size: 15px; }
.chronicle-dossier__close { min-width: 44px; min-height: 44px; border: 0; background: transparent; color: #bbb; font-size: 22px; }
.chronicle-dossier__body { min-height: 0; overflow-y: auto; padding: 15px; }
.chronicle-dossier__claim { margin: 0; padding: 11px 12px; border-left: 3px solid #b99652; background: #1d1d1d; color: #f1dfb9; line-height: 1.55; }
.chronicle-dossier__note, .chronicle-dossier__state { margin: 10px 0 0; padding: 10px 12px; border: 1px dashed #484036; border-radius: 8px; color: #c6af82; font-size: 11px; line-height: 1.5; }
.chronicle-dossier__state--error { color: #d28d84; }
.chronicle-dossier__section { margin-top: 17px; }
.chronicle-dossier__section h4 { margin: 0 0 8px; color: #bdb6a9; font-size: 11px; letter-spacing: .08em; text-transform: uppercase; }
.chronicle-dossier__event { position: relative; margin-top: 8px; padding: 11px 70px 11px 12px; border: 1px solid #303030; border-radius: 9px; background: #1b1b1b; }
.chronicle-dossier__event time { color: #817b71; font-size: 10px; }
.chronicle-dossier__event p { margin: 5px 0 0; color: #ded8ca; font-size: 13px; line-height: 1.5; overflow-wrap: anywhere; }
.chronicle-dossier__why { position: absolute; top: 10px; right: 8px; min-height: 30px; padding: 4px 8px; border: 1px solid rgba(197, 166, 107, .5); border-radius: 999px; background: rgba(85, 63, 27, .28); color: #f1dfb9; font-size: 10px; }
@media (max-width: 760px) { .chronicle-dossier { width: 100%; } .chronicle-dossier__event p { font-size: 16px; line-height: 1.6; } .chronicle-dossier__why { min-height: 44px; } }
</style>
