<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { useUiStore } from '@/stores/ui'
import type { ChronicleChapterDTO, ChronicleReferenceDTO, WorldChronicleResponseDTO } from '@/types/api'

const props = withDefaults(defineProps<{
  chapters?: ChronicleChapterDTO[]
  hasMore?: boolean
  loading?: boolean
  error?: boolean
  onOpenDossier?: (chapterId: string, anchorId: string) => void
  onLoadMore?: () => void
}>(), {
  chapters: () => [],
  hasMore: false,
  loading: false,
  error: false,
})

const emit = defineEmits<{
  'open-dossier': [chapterId: string, anchorId: string]
  'load-more': []
}>()
const { t } = useI18n()
const uiStore = useUiStore()

function openReference(chapter: ChronicleChapterDTO, reference: ChronicleReferenceDTO) {
  if (reference.kind === 'event') {
    props.onOpenDossier?.(chapter.id, reference.id)
    emit('open-dossier', chapter.id, reference.id)
    return
  }
  if (!reference.target_id) return
  if (reference.kind === 'avatar') {
    void uiStore.select('avatar', reference.target_id)
  } else if (reference.kind === 'sect') {
    void uiStore.select('sect', reference.target_id)
  } else if (reference.kind === 'region') {
    void uiStore.select('region', reference.target_id)
  }
}

function loadMore() {
  props.onLoadMore?.()
  emit('load-more')
}

function sourceCount(chapter: ChronicleChapterDTO, sourceIds: string[]) {
  return new Set(sourceIds.length ? sourceIds : chapter.source_event_ids).size
}

function referenceLabel(reference: ChronicleReferenceDTO) {
  return reference.label
}
</script>

<template>
  <div class="chronicle-view" data-testid="chronicle-view">
    <p v-if="loading && chapters.length === 0" class="chronicle-state">{{ t('game.world_journal.chronicle.loading') }}</p>
    <p v-else-if="error && chapters.length === 0" class="chronicle-state chronicle-state--error">
      {{ t('game.world_journal.chronicle.error') }}
    </p>
    <p v-else-if="chapters.length === 0" class="chronicle-state">{{ t('game.world_journal.chronicle.empty') }}</p>
    <p v-if="error" class="chronicle-state chronicle-state--error" data-testid="chronicle-error">
      {{ t('game.world_journal.chronicle.error') }}
    </p>

    <article v-for="chapter in chapters" :key="chapter.id" class="chronicle-chapter">
      <header class="chronicle-chapter__header">
        <h3>{{ chapter.title }}</h3>
        <span class="chronicle-trigger">{{ t(`game.world_journal.chronicle.trigger.${chapter.trigger}`) }}</span>
      </header>
      <p v-for="(paragraph, paragraphIndex) in chapter.paragraphs" :key="`${chapter.id}-${paragraphIndex}`" class="chronicle-paragraph">
        <template v-for="(segment, segmentIndex) in paragraph.segments" :key="`${chapter.id}-${paragraphIndex}-${segmentIndex}`">
          <button
            v-if="segment.reference"
            type="button"
            class="chronicle-reference"
            :class="`chronicle-reference--${segment.reference.kind}`"
            :data-testid="`chronicle-ref-${segment.reference.id}`"
            @click="openReference(chapter, segment.reference)"
          >
            <span>{{ segment.text }}</span>
            <span
              v-if="segment.reference.claim_kind === 'fact'"
              class="chronicle-badge chronicle-badge--fact"
              data-testid="chronicle-fact-badge"
            >{{ t('game.world_journal.chronicle.fact') }}</span>
            <span
              v-else-if="segment.reference.claim_kind === 'inference'"
              class="chronicle-badge chronicle-badge--inference"
              data-testid="chronicle-inference-badge"
            >{{ t('game.world_journal.chronicle.inference') }}</span>
            <span v-if="segment.reference.kind === 'event'" class="chronicle-reference__label">{{ referenceLabel(segment.reference) }}</span>
          </button>
          <span v-else>{{ segment.text }}</span>
        </template>
        <small class="chronicle-source-count">
          {{ t('game.world_journal.chronicle.source_count', { count: sourceCount(chapter, paragraph.source_event_ids) }) }}
        </small>
      </p>
    </article>

    <button v-if="hasMore" type="button" class="chronicle-load-more" :disabled="loading" @click="loadMore">
      {{ loading ? t('game.world_journal.chronicle.loading') : t('game.world_journal.chronicle.load_more') }}
    </button>
  </div>
</template>

<style scoped>
/*
 * The chronicle is the panel's long-form register: running prose in the display
 * serif, with each chapter separated by a rule instead of sitting in its own
 * rounded card.
 */
.chronicle-view {
  --chronicle-copy: #eee7da;
  --chronicle-meta: #b5ad9f;
  --chronicle-event: #f3dfb9;
  --chronicle-avatar: #a8e3d0;
  --chronicle-sect: #d8c2f2;
  --chronicle-region: #b9d7f3;
  min-width: 0;
  padding: var(--s-5);
  overflow-y: auto;
  color: var(--text-secondary);
  font-family: var(--font-ui);
}

.chronicle-state {
  margin: 0;
  padding: var(--s-5) 0;
  border: 0;
  border-top: 1px solid var(--rule-soft);
  color: var(--text-muted);
  font-size: var(--t-sm);
  font-style: italic;
}

.chronicle-state--error {
  color: var(--state-alert);
  font-style: normal;
}

.chronicle-chapter {
  margin-bottom: 0;
  padding: var(--s-6) 0;
  border: 0;
  border-radius: 0;
  background: transparent;
}

.chronicle-chapter + .chronicle-chapter {
  border-top: 1px solid var(--rule);
}

.chronicle-chapter__header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--s-4);
}

/* Chapter title: the largest type in the sidebar, and the only display serif
   heading — this is the register's byline. */
.chronicle-chapter h3 {
  margin: 0;
  color: var(--gold-200);
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 600;
  line-height: 1.35;
}

.chronicle-trigger {
  flex: 0 0 auto;
  color: var(--chronicle-meta);
  font-size: 11px;
  line-height: 1.35;
  letter-spacing: var(--tracking-wide);
  text-align: right;
  text-transform: uppercase;
}

.chronicle-paragraph {
  margin: var(--s-5) 0 0;
  color: var(--chronicle-copy);
  font-family: var(--font-display);
  font-size: 17px;
  line-height: 1.78;
  overflow-wrap: anywhere;
}

/*
 * Reference kind is meaningful, so it keeps four distinguishable marks — but
 * drawn from the palette: gold for the event itself, jade for a person,
 * cinnabar for an organization, paper for a place.
 */
.chronicle-reference {
  display: inline;
  padding: 1px 2px;
  border: 0;
  border-bottom: 1px solid color-mix(in srgb, var(--chronicle-event) 65%, transparent);
  background: transparent;
  color: var(--chronicle-event);
  font: inherit;
  font-weight: 500;
  text-align: left;
  cursor: pointer;
  transition: background var(--motion-fast);
}

.chronicle-reference:hover {
  background: var(--accent-wash);
}

.chronicle-reference:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring);
}

.chronicle-reference--avatar {
  border-bottom-color: color-mix(in srgb, var(--chronicle-avatar) 65%, transparent);
  color: var(--chronicle-avatar);
}

.chronicle-reference--avatar:hover {
  background: var(--jade-wash);
}

.chronicle-reference--sect {
  border-bottom-color: color-mix(in srgb, var(--chronicle-sect) 65%, transparent);
  color: var(--chronicle-sect);
}

.chronicle-reference--sect:hover {
  background: rgba(216, 194, 242, 0.1);
}

.chronicle-reference--region {
  border-bottom-color: color-mix(in srgb, var(--chronicle-region) 65%, transparent);
  color: var(--chronicle-region);
}

.chronicle-reference--region:hover {
  background: rgba(185, 215, 243, 0.1);
}

/* Fact vs inference is an epistemic distinction: it stays legible as a tracked
   caption, not as a coloured pill. */
.chronicle-badge {
  margin-left: var(--s-2);
  padding: 0 var(--s-2);
  border-radius: var(--r-1);
  font-family: var(--font-ui);
  font-size: 9px;
  letter-spacing: var(--tracking-wide);
  text-transform: uppercase;
}

.chronicle-badge--fact {
  border: 1px solid color-mix(in srgb, var(--chronicle-avatar) 55%, transparent);
  background: rgba(168, 227, 208, 0.11);
  color: var(--chronicle-avatar);
}

.chronicle-badge--inference {
  border: 1px dashed color-mix(in srgb, var(--chronicle-event) 55%, transparent);
  background: rgba(243, 223, 185, 0.1);
  color: var(--chronicle-event);
}

.chronicle-reference__label {
  margin-left: var(--s-1);
  color: var(--chronicle-meta);
  font-family: var(--font-ui);
  font-size: 11px;
}

.chronicle-source-count {
  display: block;
  margin-top: var(--s-4);
  color: var(--chronicle-meta);
  font-family: var(--font-numeric);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}

.chronicle-load-more {
  width: 100%;
  min-height: 36px;
  margin-top: var(--s-5);
  border: 1px solid var(--rule);
  border-radius: var(--r-1);
  background: transparent;
  color: var(--accent-strong);
  font-family: var(--font-ui);
  font-size: var(--t-sm);
  cursor: pointer;
  transition: background var(--motion-fast), border-color var(--motion-fast);
}

.chronicle-load-more:hover:not(:disabled) {
  background: var(--accent-wash);
  border-color: var(--gold-600);
}

.chronicle-load-more:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring);
}

.chronicle-load-more:disabled {
  color: var(--paper-700);
  cursor: not-allowed;
}

@media (max-width: 760px) {
  .chronicle-view {
    padding: var(--s-5) var(--s-6) var(--s-7);
  }

  .chronicle-paragraph {
    font-size: 17px;
    line-height: 1.78;
  }

  .chronicle-load-more {
    min-height: 48px;
  }
}

@container journal (max-width: 460px) {
  .chronicle-chapter__header {
    display: block;
  }

  .chronicle-trigger {
    display: block;
    margin-top: var(--s-2);
    text-align: left;
  }
}
</style>
