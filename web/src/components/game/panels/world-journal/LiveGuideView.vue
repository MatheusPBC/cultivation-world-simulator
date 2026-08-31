<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import type { LiveGuideAnswerDTO, LiveGuideResponseDTO, LiveGuideSubjectDTO } from '@/types/api'

const props = withDefaults(defineProps<{
  guide?: LiveGuideResponseDTO | null
  answer?: LiveGuideAnswerDTO | null
  loading?: boolean
  error?: boolean
  answerLoading?: boolean
  answerError?: boolean
}>(), {
  guide: null,
  answer: null,
  loading: false,
  error: false,
  answerLoading: false,
  answerError: false,
})

const emit = defineEmits<{
  ask: [question: string]
  retry: []
  'open-why': [eventId: string]
  'open-subject': [subject: LiveGuideSubjectDTO]
  'open-avatar': [avatarId: string]
}>()

const { t } = useI18n()
const question = ref('')

const conceptName = computed(() => {
  const key = props.guide?.concept.term_key
  return key ? t(`game.world_info.entries.${key}_NAME`) : ''
})

const conceptDescription = computed(() => {
  const key = props.guide?.concept.term_key
  return key ? t(`game.world_info.entries.${key}_DESC`) : ''
})

const suggestions = computed(() => [
  t('game.world_journal.guide.suggestion_people'),
  t('game.world_journal.guide.suggestion_conflict'),
  t('game.world_journal.guide.suggestion_change'),
])

function submitQuestion(value = question.value) {
  const normalized = value.trim()
  if (!normalized || props.answerLoading) return
  question.value = normalized
  emit('ask', normalized)
}

function selectSuggestion(value: string) {
  question.value = value
  submitQuestion(value)
}
</script>

<template>
  <div class="live-guide" data-testid="live-guide">
    <p v-if="loading && !guide" class="guide-state">{{ t('game.world_journal.guide.loading') }}</p>
    <div v-else-if="error && !guide" class="guide-state guide-state--error" data-testid="live-guide-error">
      <p>{{ t('game.world_journal.guide.error') }}</p>
      <button type="button" @click="emit('retry')">{{ t('game.world_journal.guide.retry') }}</button>
    </div>

    <template v-else-if="guide">
      <section class="guide-lede">
        <div class="guide-date">
          {{ t('game.world_journal.guide.date', { year: guide.date.year, month: guide.date.month }) }}
        </div>
        <span class="guide-kicker">{{ t('game.world_journal.guide.world_in_one_sentence') }}</span>
        <h3>{{ guide.headline || t('game.world_journal.guide.no_headline') }}</h3>
        <button
          v-if="guide.source_event_ids.length"
          type="button"
          class="source-link"
          data-testid="guide-headline-source"
          @click="emit('open-why', guide.source_event_ids[0])"
        >
          {{ t('game.world_journal.guide.sources', { count: guide.source_event_ids.length }) }}
        </button>
      </section>

      <div class="guide-layout">
        <main class="guide-main">
          <header class="guide-section-heading">
            <h4>{{ t('game.world_journal.guide.happening') }}</h4>
            <p>{{ t('game.world_journal.guide.happening_hint') }}</p>
          </header>

          <p v-if="guide.threads.length === 0" class="guide-state">
            {{ t('game.world_journal.guide.empty') }}
          </p>
          <article
            v-for="thread in guide.threads"
            :key="thread.id"
            class="guide-thread"
            :class="`guide-thread--${thread.severity}`"
          >
            <span class="thread-marker" aria-hidden="true"></span>
            <div class="thread-copy">
              <h5>{{ thread.title }}</h5>
              <p>{{ thread.summary }}</p>
              <div v-if="thread.subjects.length" class="thread-subjects">
                <button
                  v-for="subject in thread.subjects"
                  :key="`${subject.kind}-${subject.id}`"
                  type="button"
                  @click="emit('open-subject', subject)"
                >
                  {{ subject.name }}
                </button>
              </div>
              <button
                type="button"
                class="why-link"
                :data-testid="`guide-why-${thread.primary_event_id}`"
                @click="emit('open-why', thread.primary_event_id)"
              >
                {{ t('game.world_journal.guide.understand_why') }}
                <span aria-hidden="true">→</span>
              </button>
            </div>
          </article>
        </main>

        <aside class="guide-context">
          <section class="context-block">
            <h4>{{ t('game.world_journal.guide.people') }}</h4>
            <p v-if="guide.people.length === 0" class="context-empty">
              {{ t('game.world_journal.guide.people_empty') }}
            </p>
            <button
              v-for="person in guide.people"
              v-else
              :key="person.avatar_id"
              type="button"
              class="person-row"
              @click="emit('open-avatar', person.avatar_id)"
            >
              <span class="person-name">{{ person.name }}</span>
              <span class="person-role">{{ person.current_action || t('game.world_journal.guide.no_current_action') }}</span>
              <span class="person-ambition">{{ person.ambition || t('game.world_journal.guide.no_ambition') }}</span>
            </button>
          </section>

          <section class="context-block concept-block">
            <span class="context-eyebrow">{{ t('game.world_journal.guide.concept') }}</span>
            <h4>{{ conceptName }}</h4>
            <p>{{ conceptDescription }}</p>
          </section>
        </aside>
      </div>

      <section class="chronicler-box">
        <header>
          <div>
            <span class="context-eyebrow">{{ t('game.world_journal.guide.ask_eyebrow') }}</span>
            <h4>{{ t('game.world_journal.guide.ask_title') }}</h4>
          </div>
          <span class="grounded-note">{{ t('game.world_journal.guide.grounded_note') }}</span>
        </header>

        <form @submit.prevent="submitQuestion()">
          <label class="sr-only" for="live-guide-question">{{ t('game.world_journal.guide.question_label') }}</label>
          <input
            id="live-guide-question"
            v-model="question"
            maxlength="500"
            :placeholder="t('game.world_journal.guide.question_placeholder')"
            :disabled="answerLoading"
          >
          <button type="submit" :disabled="answerLoading || !question.trim()">
            {{ answerLoading ? t('game.world_journal.guide.answering') : t('game.world_journal.guide.ask_button') }}
          </button>
        </form>

        <div class="question-suggestions">
          <button
            v-for="suggestion in suggestions"
            :key="suggestion"
            type="button"
            :disabled="answerLoading"
            @click="selectSuggestion(suggestion)"
          >
            {{ suggestion }}
          </button>
        </div>

        <p v-if="answerError" class="answer-state answer-state--error" data-testid="guide-answer-error">
          {{ t('game.world_journal.guide.answer_error') }}
        </p>
        <article v-else-if="answer" class="guide-answer" data-testid="guide-answer">
          <p>{{ answer.answer || t('game.world_journal.guide.answer_unavailable') }}</p>
          <div v-if="answer.source_event_ids.length" class="answer-sources">
            <span>{{ t('game.world_journal.guide.answer_sources') }}</span>
            <button
              v-for="(eventId, index) in answer.source_event_ids"
              :key="eventId"
              type="button"
              @click="emit('open-why', eventId)"
            >
              {{ t('game.world_journal.guide.source_number', { number: index + 1 }) }}
            </button>
          </div>
        </article>
      </section>
    </template>
  </div>
</template>

<style scoped>
/* Hallmark · pre-emit critique: P5 H5 E4 S5 R4 V5
 * composition: editorial split · tone: xianxia chronicle · anchor hue: antique gold
 */
.live-guide {
  --guide-paper: #121211;
  --guide-paper-raised: #191816;
  --guide-paper-soft: #211f1b;
  --guide-ink: #eee7d8;
  --guide-ink-soft: #c9c2b5;
  --guide-ink-muted: #9e978a;
  --guide-rule: #38342c;
  --guide-gold: #c8a96a;
  --guide-gold-soft: rgba(200, 169, 106, 0.15);
  --guide-teal: #78cbb1;
  --guide-teal-soft: rgba(120, 203, 177, 0.08);
  --guide-teal-rule: rgba(120, 203, 177, 0.35);
  --guide-crimson: #ba655d;
  --guide-error: #d89087;
  --guide-focus: #e1c48d;
  --guide-gold-text: #f0d8a6;
  --guide-ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  min-width: 0;
  min-height: 100%;
  padding: 16px;
  background: var(--guide-paper);
  color: var(--guide-ink);
}

.guide-state {
  margin: 0;
  padding: 18px;
  border: 1px dashed var(--guide-rule);
  color: var(--guide-ink-muted);
}

.guide-state--error,
.answer-state--error { color: var(--guide-error); }
.guide-state--error p { margin: 0 0 12px; }
.guide-state--error button { min-height: 44px; }

.guide-lede {
  position: relative;
  min-width: 0;
  padding: 2px 110px 18px 0;
  border-bottom: 1px solid var(--guide-rule);
}

.guide-date,
.guide-kicker,
.context-eyebrow {
  color: var(--guide-gold);
  font-size: 10px;
  letter-spacing: 0.11em;
  text-transform: uppercase;
}

.guide-kicker { display: block; margin-top: 9px; }
.guide-lede h3 {
  min-width: 0;
  max-width: 760px;
  margin: 7px 0 0;
  color: var(--guide-ink);
  font-size: clamp(19px, 3vw, 28px);
  font-weight: 600;
  line-height: 1.22;
  overflow-wrap: anywhere;
}

.source-link {
  position: absolute;
  right: 0;
  bottom: 18px;
  min-height: 36px;
  padding: 0 11px;
  border: 1px solid var(--guide-rule);
  border-radius: 6px;
  background: transparent;
  color: var(--guide-ink-muted);
  white-space: nowrap;
}

.guide-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.65fr) minmax(240px, 1fr);
  min-width: 0;
}

.guide-main { min-width: 0; padding: 20px 24px 10px 0; }
.guide-context { min-width: 0; padding: 20px 0 10px 24px; border-left: 1px solid var(--guide-rule); }

.guide-section-heading h4,
.context-block h4,
.chronicler-box h4 {
  margin: 0;
  color: var(--guide-ink);
  font-size: 14px;
  font-style: normal;
}

.guide-section-heading p {
  margin: 5px 0 0;
  color: var(--guide-ink-muted);
  font-size: 11px;
}

.guide-thread {
  display: grid;
  grid-template-columns: 8px minmax(0, 1fr);
  gap: 12px;
  padding: 18px 0;
  border-bottom: 1px solid var(--guide-rule);
}

.thread-marker {
  width: 4px;
  height: 100%;
  min-height: 62px;
  border-radius: 2px;
  background: var(--guide-gold);
}
.guide-thread--critical .thread-marker { background: var(--guide-crimson); }
.guide-thread--notable .thread-marker { background: var(--guide-teal); }

.thread-copy { min-width: 0; }
.thread-copy h5 { margin: 0; color: var(--guide-ink); font-size: 15px; line-height: 1.35; overflow-wrap: anywhere; }
.thread-copy > p { margin: 7px 0 0; color: var(--guide-ink-soft); font-size: 13px; line-height: 1.62; overflow-wrap: anywhere; }

.thread-subjects { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.thread-subjects button {
  min-height: 30px;
  padding: 3px 8px;
  border: 1px solid var(--guide-teal-rule);
  border-radius: 999px;
  background: var(--guide-teal-soft);
  color: var(--guide-teal);
}

.why-link {
  min-height: 40px;
  margin-top: 8px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--guide-gold);
  font-weight: 600;
}
.why-link span { margin-left: 5px; }

.context-block + .context-block { margin-top: 26px; padding-top: 22px; border-top: 1px solid var(--guide-rule); }
.person-row {
  display: grid;
  width: 100%;
  min-width: 0;
  min-height: 62px;
  margin-top: 8px;
  padding: 10px 0;
  border: 0;
  border-bottom: 1px solid var(--guide-rule);
  background: transparent;
  text-align: left;
}
.person-name { color: var(--guide-teal); font-size: 13px; font-weight: 700; }
.person-role { margin-top: 3px; color: var(--guide-ink); font-size: 11px; }
.person-ambition { margin-top: 5px; color: var(--guide-ink-muted); font-size: 11px; line-height: 1.45; overflow-wrap: anywhere; }
.context-empty { color: var(--guide-ink-muted); font-size: 12px; }

.concept-block h4 { margin-top: 6px; color: var(--guide-gold); }
.concept-block p { margin: 8px 0 0; color: var(--guide-ink-soft); font-size: 12px; line-height: 1.62; }

.chronicler-box {
  margin-top: 16px;
  padding: 16px;
  border: 1px solid var(--guide-rule);
  border-radius: 10px;
  background: var(--guide-paper-raised);
}
.chronicler-box > header { display: flex; align-items: end; justify-content: space-between; gap: 12px; }
.chronicler-box h4 { margin-top: 4px; }
.grounded-note { color: var(--guide-ink-muted); font-size: 10px; text-align: right; }
.chronicler-box form { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; margin-top: 13px; }
.chronicler-box input {
  min-width: 0;
  min-height: 46px;
  padding: 0 13px;
  border: 1px solid var(--guide-rule);
  border-radius: 7px;
  outline: 0;
  background: var(--guide-paper);
  color: var(--guide-ink);
}
.chronicler-box form button {
  min-height: 46px;
  padding: 0 17px;
  border: 1px solid var(--guide-gold);
  border-radius: 7px;
  background: var(--guide-gold-soft);
  color: var(--guide-gold-text);
  white-space: nowrap;
}
.question-suggestions { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 9px; }
.question-suggestions button {
  min-height: 34px;
  padding: 4px 9px;
  border: 1px solid var(--guide-rule);
  border-radius: 999px;
  background: var(--guide-paper-soft);
  color: var(--guide-ink-muted);
  white-space: nowrap;
}

.guide-answer { margin-top: 13px; padding: 13px; border-left: 3px solid var(--guide-teal); background: var(--guide-paper); }
.guide-answer > p { margin: 0; color: var(--guide-ink); font-size: 13px; line-height: 1.65; }
.answer-sources { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 10px; color: var(--guide-ink-muted); font-size: 10px; }
.answer-sources button { min-height: 32px; border: 0; border-bottom: 1px solid var(--guide-gold); background: transparent; color: var(--guide-gold); }
.answer-state { margin: 12px 0 0; }

button { font: inherit; cursor: pointer; transition: background-color 120ms var(--guide-ease-out), color 120ms var(--guide-ease-out), border-color 120ms var(--guide-ease-out); }
button:hover:not(:disabled) { color: var(--guide-focus); }
button:active:not(:disabled) { opacity: 0.78; }
button:focus-visible,
input:focus-visible { outline: 2px solid var(--guide-focus); outline-offset: 2px; }
button:disabled,
input:disabled { cursor: not-allowed; opacity: 0.48; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }

@media (max-width: 760px) {
  .live-guide { padding: 14px; }
  .guide-lede { padding-right: 0; }
  .source-link { position: static; margin-top: 12px; min-height: 48px; }
  .guide-layout { display: flex; flex-direction: column; }
  .guide-main { padding: 20px 0 0; }
  .guide-context { padding: 22px 0 0; border-top: 1px solid var(--guide-rule); border-left: 0; }
  .thread-copy h5 { font-size: 17px; }
  .thread-copy > p,
  .concept-block p,
  .guide-answer > p { font-size: 16px; }
  .why-link,
  .thread-subjects button,
  .person-row,
  .question-suggestions button { min-height: 48px; }
  .chronicler-box > header { align-items: flex-start; flex-direction: column; }
  .grounded-note { text-align: left; }
  .chronicler-box form { grid-template-columns: minmax(0, 1fr); }
  .chronicler-box form button { width: 100%; }
}

@media (prefers-reduced-motion: reduce) {
  button { transition-duration: 0ms; }
}
</style>
