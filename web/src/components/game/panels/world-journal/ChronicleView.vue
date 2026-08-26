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
.chronicle-view { min-width: 0; padding: 12px; overflow-y: auto; color: #e8e2d4; }
.chronicle-state { margin: 0; padding: 14px; border: 1px dashed #303030; border-radius: 9px; color: #777; font-size: 12px; }
.chronicle-state--error { color: #d28d84; }
.chronicle-chapter { margin-bottom: 14px; padding: 13px; border: 1px solid #36322a; border-radius: 11px; background: #191817; }
.chronicle-chapter__header { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }
.chronicle-chapter h3 { margin: 0; color: #f3e9cf; font-size: 15px; }
.chronicle-trigger { flex: 0 0 auto; color: #9d927d; font-size: 10px; }
.chronicle-paragraph { margin: 13px 0 0; color: #ddd5c7; font-size: 13px; line-height: 1.7; overflow-wrap: anywhere; }
.chronicle-reference { display: inline; padding: 1px 3px; border: 0; border-bottom: 1px solid #b99652; background: transparent; color: #f1dfb9; font: inherit; text-align: left; cursor: pointer; }
.chronicle-reference--avatar { border-bottom-color: #65bba1; color: #8fe1c4; }
.chronicle-reference--sect { border-bottom-color: #b99edc; color: #ceb6ed; }
.chronicle-reference--region { border-bottom-color: #8db1db; color: #a9c9ee; }
.chronicle-badge { margin-left: 5px; padding: 1px 4px; border-radius: 4px; font-size: 9px; letter-spacing: .04em; }
.chronicle-badge--fact { background: rgba(110, 175, 147, .18); color: #9be0c3; }
.chronicle-badge--inference { background: rgba(190, 154, 91, .18); color: #e5c58f; }
.chronicle-reference__label { margin-left: 4px; color: #a39b8d; font-size: 10px; }
.chronicle-source-count { display: block; margin-top: 8px; color: #7d776c; font-size: 10px; }
.chronicle-load-more { width: 100%; min-height: 44px; border: 1px solid #474032; border-radius: 8px; background: #211e19; color: #e5c58f; }
@media (max-width: 760px) { .chronicle-view { padding: 12px 14px 24px; } .chronicle-paragraph { font-size: 16px; line-height: 1.65; } .chronicle-reference, .chronicle-load-more { min-height: 48px; } }
</style>
