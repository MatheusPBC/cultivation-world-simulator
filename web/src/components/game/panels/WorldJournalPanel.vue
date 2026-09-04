<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useI18n } from 'vue-i18n'

import EventPanel from '@/components/game/panels/EventPanel.vue'
import ChronicleDossierDrawer from '@/components/game/panels/world-journal/ChronicleDossierDrawer.vue'
import ChronicleView from '@/components/game/panels/world-journal/ChronicleView.vue'
import LiveGuideView from '@/components/game/panels/world-journal/LiveGuideView.vue'
import DaoPetitionsView from '@/components/game/panels/world-journal/DaoPetitionsView.vue'
import { useUiStore } from '@/stores/ui'
import { useWorldJournalStore, type WorldJournalTab } from '@/stores/worldJournal'
import type { CausalEdgeDTO, EventDTO, EventSubjectDTO, LiveGuideSubjectDTO, MetricReadingDTO, WorldJournalPeriodMonths } from '@/types/api'

const { t } = useI18n()
const uiStore = useUiStore()
const journalStore = useWorldJournalStore()
const {
  activeTab,
  periodMonths,
  journal,
  loading,
  hasError,
  chronicle,
  chronicleLoading,
  chronicleError,
  liveGuide,
  liveGuideLoading,
  liveGuideError,
  liveGuideAnswer,
  liveGuideAnswerLoading,
  liveGuideAnswerError,
  daoPetitions,
  daoLoading,
  daoError,
  respondingPetitionId,
  chronicleDossier,
  chronicleDossierChapterId,
  chronicleDossierLoading,
  chronicleDossierError,
  causalEventId,
  causalDetail,
  causalLoading,
  causalError,
} =
  storeToRefs(journalStore)

const tabs: Array<{
  key: WorldJournalTab
  labelKey: string
}> = [
  { key: 'now', labelKey: 'game.world_journal.tabs.now' },
  { key: 'focus', labelKey: 'game.world_journal.tabs.focus' },
  { key: 'stories', labelKey: 'game.world_journal.tabs.stories' },
  { key: 'timeline', labelKey: 'game.world_journal.tabs.timeline' },
  { key: 'chronicle', labelKey: 'game.world_journal.tabs.chronicle' },
  { key: 'guide', labelKey: 'game.world_journal.tabs.guide' },
  { key: 'dao', labelKey: 'game.world_journal.tabs.dao' },
]

const periods: Array<{ months: WorldJournalPeriodMonths; labelKey: string }> = [
  { months: 1, labelKey: 'game.world_journal.periods.one' },
  { months: 3, labelKey: 'game.world_journal.periods.three' },
  { months: 12, labelKey: 'game.world_journal.periods.twelve' },
]

const tabButtons = ref<HTMLButtonElement[]>([])

/**
 * Roving tabindex: a tablist must be reachable with one Tab stop and traversed
 * with the arrow keys. The tabs were plain buttons with no role, so a keyboard
 * user had to step through all seven.
 */
function onTabKeydown(event: KeyboardEvent) {
  const direction = event.key === 'ArrowRight' || event.key === 'ArrowDown'
    ? 1
    : event.key === 'ArrowLeft' || event.key === 'ArrowUp'
      ? -1
      : 0
  if (direction === 0 && event.key !== 'Home' && event.key !== 'End') return

  event.preventDefault()
  const current = Math.max(0, tabs.findIndex(tab => tab.key === activeTab.value))
  const next = event.key === 'Home'
    ? 0
    : event.key === 'End'
      ? tabs.length - 1
      : (current + direction + tabs.length) % tabs.length
  selectTab(tabs[next].key)
  tabButtons.value[next]?.focus()
}

function selectTab(tab: WorldJournalTab) {
  journalStore.selectTab(tab)
  if (tab === 'chronicle' && !chronicle.value) void journalStore.refreshChronicle()
  if (tab === 'guide') void journalStore.refreshLiveGuide()
  if (tab === 'dao') void journalStore.refreshDaoPetitions()
}

function renderEventText(event: EventDTO) {
  if (event.render_key) {
    return t(`game.event_templates.${event.render_key}`, event.render_params ?? {})
  }
  return event.content || event.text || ''
}

function formatEventDate(event: EventDTO) {
  return `${event.year}${t('common.year')} ${event.month}${t('common.month')}`
}

function selectSubject(subject: EventSubjectDTO) {
  if (subject.type === 'avatar') {
    uiStore.select('avatar', subject.id)
    return
  }
  uiStore.select('sect', String(subject.id))
}

function selectGuideSubject(subject: LiveGuideSubjectDTO) {
  if (subject.kind === 'avatar') {
    void uiStore.select('avatar', subject.id)
    return
  }
  void uiStore.select('sect', subject.id)
}

function openWhy(eventId: string) {
  void journalStore.openCausalDetail(eventId)
}

function closeWhy() {
  journalStore.closeCausalDetail()
}

function retryWhy() {
  if (causalEventId.value) openWhy(causalEventId.value)
}

function relationLabel(edge: CausalEdgeDTO) {
  return t(`game.world_journal.why_relation.${edge.relation}`)
}

function edgeEventText(edge: CausalEdgeDTO) {
  if (edge.pruned || !edge.event) return t('game.world_journal.why_pruned')
  return renderEventText(edge.event)
}

function measurementValue(reading: MetricReadingDTO): string {
  if (reading.value === null || reading.reading_kind === 'unknown') {
    return t('game.world_journal.why_measurement_unknown')
  }
  return `${reading.value} ${reading.unit}`
}

function measurementKeyText(key: MetricReadingDTO['key']): string {
  return `${key.dimension}(${key.concept_id}) · ${key.subject_kind}:${key.subject_id}`
}

function openChronicleDossier(chapterId: string, anchorId: string) {
  void journalStore.openChronicleDossier(chapterId, anchorId)
}

function closeChronicleDossier() {
  journalStore.closeChronicleDossier()
}

onMounted(() => {
  void journalStore.refresh()
  if (activeTab.value === 'chronicle' && !chronicle.value) void journalStore.refreshChronicle()
  if (activeTab.value === 'guide' && !liveGuide.value) void journalStore.refreshLiveGuide()
})
</script>

<template>
  <section class="world-journal-panel">
    <header class="journal-header">
      <h2 class="journal-title">{{ t('game.world_journal.title') }}</h2>
      <div
        class="journal-tabs"
        role="tablist"
        :aria-label="t('game.world_journal.title')"
        @keydown="onTabKeydown"
      >
        <button
          v-for="tab in tabs"
          :key="tab.key"
          ref="tabButtons"
          type="button"
          role="tab"
          class="journal-tab"
          :class="{ 'journal-tab--active': activeTab === tab.key }"
          :aria-selected="activeTab === tab.key"
          :tabindex="activeTab === tab.key ? 0 : -1"
          :data-testid="`journal-tab-${tab.key}`"
          @click="selectTab(tab.key)"
        >
          <span>{{ t(tab.labelKey) }}</span>
        </button>
      </div>
    </header>

    <div v-if="activeTab === 'now'" class="journal-body" data-testid="journal-now">
      <p v-if="loading && !journal" class="journal-state">{{ t('game.world_journal.loading') }}</p>
      <p v-else-if="hasError" class="journal-state journal-state--error">
        {{ t('game.world_journal.error') }}
      </p>

      <template v-if="journal">
        <section class="journal-section journal-section--activity">
          <div class="journal-section-head">
            <h3>{{ t('game.world_journal.activity') }}</h3>
            <div
              class="period-selector"
              role="group"
              :aria-label="t('game.world_journal.activity')"
            >
              <button
                v-for="period in periods"
                :key="period.months"
                type="button"
                class="period-button"
                :class="{ 'period-button--active': periodMonths === period.months }"
                :aria-pressed="periodMonths === period.months"
                :data-testid="`journal-period-${period.months}`"
                @click="journalStore.setPeriod(period.months)"
              >
                {{ t(period.labelKey) }}
              </button>
            </div>
          </div>

          <!--
            Four stat cards in a 2x2 grid spent ~180px of the most valuable
            column in the game on four zeroes. The same four canonical counts
            now read as one dateline, with zero values de-emphasised so a quiet
            month looks quiet instead of looking broken.
          -->
          <dl class="activity-line">
            <div
              class="activity-metric"
              :class="{ 'activity-metric--zero': journal.activity.total_events === 0 }"
            >
              <dt>{{ t('game.world_journal.total_events') }}</dt>
              <dd>{{ journal.activity.total_events }}</dd>
            </div>
            <div
              class="activity-metric activity-metric--major"
              :class="{ 'activity-metric--zero': journal.activity.major_events === 0 }"
            >
              <dt>{{ t('game.world_journal.major_events') }}</dt>
              <dd>{{ journal.activity.major_events }}</dd>
            </div>
            <div
              class="activity-metric"
              :class="{ 'activity-metric--zero': journal.activity.story_events === 0 }"
            >
              <dt>{{ t('game.world_journal.story_events') }}</dt>
              <dd>{{ journal.activity.story_events }}</dd>
            </div>
            <div
              class="activity-metric"
              :class="{ 'activity-metric--zero': journal.activity.active_avatar_count === 0 }"
            >
              <dt>{{ t('game.world_journal.active_avatars') }}</dt>
              <dd>{{ journal.activity.active_avatar_count }}</dd>
            </div>
          </dl>
        </section>

        <section class="journal-section">
          <h3>{{ t('game.world_journal.important_changes') }}</h3>
          <p v-if="journal.highlights.length === 0" class="journal-empty">
            {{ t('game.world_journal.important_empty') }}
          </p>
          <article
            v-for="event in journal.highlights"
            v-else
            :key="event.id"
            class="highlight-card"
          >
            <div class="event-card-header">
              <time>{{ formatEventDate(event) }}</time>
              <button type="button" class="why-button" @click="openWhy(event.id)">
                {{ t('game.world_journal.why_button') }}
              </button>
            </div>
            <p>{{ renderEventText(event) }}</p>
            <div v-if="event.subjects?.length" class="subject-list">
              <button
                v-for="subject in event.subjects"
                :key="`${subject.type}-${subject.id}`"
                type="button"
                class="subject-chip"
                @click="selectSubject(subject)"
              >
                {{ subject.name }}
              </button>
            </div>
          </article>
        </section>

        <section class="journal-section">
          <h3>{{ t('game.world_journal.ongoing') }}</h3>
          <p v-if="journal.ongoing.length === 0" class="journal-empty">
            {{ t('game.world_journal.ongoing_empty') }}
          </p>
          <button
            v-for="item in journal.ongoing"
            v-else
            :key="item.avatar_id"
            type="button"
            class="ongoing-card"
            @click="uiStore.select('avatar', item.avatar_id)"
          >
            <span class="ongoing-avatar">{{ item.avatar_name }}</span>
            <span class="ongoing-action">{{ item.action }}</span>
            <small>{{ t('game.world_journal.event_count', { count: item.event_count }) }}</small>
          </button>
        </section>
      </template>
    </div>

    <div v-else-if="activeTab === 'focus'" class="journal-body" data-testid="journal-focus">
      <p v-if="loading && !journal" class="journal-state">{{ t('game.world_journal.loading') }}</p>
      <p v-else-if="hasError" class="journal-state journal-state--error">
        {{ t('game.world_journal.error') }}
      </p>
      <template v-else-if="journal">
        <p v-if="journal.ongoing.length === 0" class="journal-empty">
          {{ t('game.world_journal.focus_empty') }}
        </p>
        <article v-for="item in journal.ongoing" v-else :key="item.avatar_id" class="focus-card">
          <button type="button" class="focus-card-header" @click="uiStore.select('avatar', item.avatar_id)">
            <span class="ongoing-avatar">{{ item.avatar_name }}</span>
            <span class="ongoing-action">{{ item.action }}</span>
          </button>
          <dl class="focus-objectives">
            <div class="focus-objective">
              <dt>{{ t('game.world_journal.focus_short_term') }}</dt>
              <dd>{{ item.short_term_objective || t('game.world_journal.focus_no_objective') }}</dd>
            </div>
            <div class="focus-objective">
              <dt>{{ t('game.world_journal.focus_long_term') }}</dt>
              <dd>{{ item.long_term_objective || t('game.world_journal.focus_no_objective') }}</dd>
            </div>
          </dl>
          <small>{{ t('game.world_journal.event_count', { count: item.event_count }) }}</small>
        </article>
      </template>
    </div>

    <div v-else-if="activeTab === 'stories'" class="journal-body" data-testid="journal-stories">
      <p v-if="loading && !journal" class="journal-state">{{ t('game.world_journal.loading') }}</p>
      <p v-else-if="hasError" class="journal-state journal-state--error">
        {{ t('game.world_journal.error') }}
      </p>
      <template v-else-if="journal">
        <p v-if="journal.stories.length === 0" class="journal-empty">
          {{ t('game.world_journal.stories_empty') }}
        </p>
        <template v-else>
          <p v-if="journal.stories_truncated" class="journal-note">
            {{ t('game.world_journal.stories_truncated', { count: journal.stories.length }) }}
          </p>
          <article v-for="event in journal.stories" :key="event.id" class="highlight-card">
            <div class="event-card-header">
              <time>{{ formatEventDate(event) }}</time>
              <button type="button" class="why-button" @click="openWhy(event.id)">
                {{ t('game.world_journal.why_button') }}
              </button>
            </div>
            <p>{{ renderEventText(event) }}</p>
          </article>
        </template>
      </template>
    </div>

    <div v-else-if="activeTab === 'guide'" class="journal-body journal-body--guide" data-testid="journal-guide">
      <LiveGuideView
        :guide="liveGuide"
        :answer="liveGuideAnswer"
        :loading="liveGuideLoading"
        :error="liveGuideError"
        :answer-loading="liveGuideAnswerLoading"
        :answer-error="liveGuideAnswerError"
        @ask="journalStore.askLiveGuide"
        @retry="journalStore.refreshLiveGuide"
        @open-why="openWhy"
        @open-subject="selectGuideSubject"
        @open-avatar="uiStore.select('avatar', $event)"
      />
    </div>

    <div v-else-if="activeTab === 'dao'" class="journal-body journal-body--guide">
      <DaoPetitionsView :petitions="daoPetitions" :loading="daoLoading" :error="daoError" :responding-id="respondingPetitionId" @retry="journalStore.refreshDaoPetitions" @answer="journalStore.answerDaoPetition" @why="openWhy" />
    </div>

    <div v-else-if="activeTab === 'chronicle'" class="journal-body journal-body--chronicle" data-testid="journal-chronicle">
      <ChronicleView
        :chapters="chronicle?.chapters ?? []"
        :has-more="chronicle?.has_more ?? false"
        :loading="chronicleLoading"
        :error="chronicleError"
        @load-more="journalStore.loadMoreChronicle()"
        @open-dossier="openChronicleDossier"
      />
    </div>

    <div v-else class="journal-timeline" data-testid="journal-timeline">
      <EventPanel />
    </div>

    <ChronicleDossierDrawer
      :open="chronicleDossierChapterId !== null"
      :dossier="chronicleDossier"
      :loading="chronicleDossierLoading"
      :error="chronicleDossierError"
      :on-close="closeChronicleDossier"
      :on-open-why="journalStore.openCausalDetail"
    />

    <div v-if="causalEventId" class="why-overlay why-overlay--above-dossier" data-testid="why-overlay" role="dialog" aria-modal="true">
      <div class="why-panel">
        <header class="why-header">
          <h3>{{ t('game.world_journal.why_title') }}</h3>
          <button type="button" class="why-close" :aria-label="t('game.world_journal.why_close')" @click="closeWhy">
            &times;
          </button>
        </header>
        <div class="why-body">
          <p v-if="causalLoading" class="journal-state">{{ t('game.world_journal.why_loading') }}</p>
          <template v-else-if="causalError">
            <p class="journal-state journal-state--error">{{ t('game.world_journal.why_error') }}</p>
            <button type="button" class="why-retry" @click="retryWhy">{{ t('game.world_journal.why_retry') }}</button>
          </template>
          <template v-else-if="causalDetail">
            <p class="why-subject">{{ renderEventText(causalDetail.event) }}</p>

            <section class="why-section">
              <h4>{{ t('game.world_journal.why_causes') }}</h4>
              <p v-if="causalDetail.causes.length === 0" class="journal-empty">
                {{ t('game.world_journal.why_no_causes') }}
              </p>
              <ul v-else class="why-edge-list">
                <li v-for="(edge, index) in causalDetail.causes" :key="`cause-${index}`" class="why-edge">
                  <span class="why-relation">{{ relationLabel(edge) }}</span>
                  <span class="why-edge-text" :class="{ 'why-edge-text--pruned': edge.pruned }">
                    {{ edgeEventText(edge) }}
                  </span>
                </li>
              </ul>
            </section>

            <section class="why-section">
              <h4>{{ t('game.world_journal.why_effects') }}</h4>
              <p v-if="causalDetail.effects.length === 0" class="journal-empty">
                {{ t('game.world_journal.why_no_effects') }}
              </p>
              <ul v-else class="why-edge-list">
                <li v-for="(edge, index) in causalDetail.effects" :key="`effect-${index}`" class="why-edge">
                  <span class="why-relation">{{ relationLabel(edge) }}</span>
                  <span class="why-edge-text" :class="{ 'why-edge-text--pruned': edge.pruned }">
                    {{ edgeEventText(edge) }}
                  </span>
                </li>
              </ul>
            </section>

            <section class="why-section">
              <h4>{{ t('game.world_journal.why_deltas') }}</h4>
              <p v-if="causalDetail.deltas.length === 0" class="journal-empty">
                {{ t('game.world_journal.why_no_deltas') }}
              </p>
              <ul v-else class="why-edge-list">
                <li v-for="delta in causalDetail.deltas" :key="delta.id" class="why-edge">
                  <span class="why-relation">{{ delta.aspect }}</span>
                  <span class="why-edge-text">{{ delta.before }} &rarr; {{ delta.after }}</span>
                </li>
              </ul>
            </section>

            <section class="why-section" data-testid="why-measurements">
              <h4>{{ t('game.world_journal.why_measurements') }}</h4>
              <p v-if="causalDetail.measurements.length === 0" class="journal-empty">
                {{ t('game.world_journal.why_no_measurements') }}
              </p>
              <ul v-else class="why-measurement-list">
                <li
                  v-for="(reading, index) in causalDetail.measurements"
                  :key="`measurement-${index}`"
                  class="why-measurement"
                >
                  <div class="why-measurement__header">
                    <strong>{{ reading.key.dimension }}({{ reading.key.concept_id }})</strong>
                    <span>{{ measurementValue(reading) }}</span>
                  </div>
                  <div class="why-measurement__meta">
                    {{ t(`game.world_journal.why_measurement_availability.${reading.availability}`) }}
                    · {{ t(`game.world_journal.why_measurement_kind.${reading.reading_kind}`) }}
                  </div>
                  <div class="why-measurement__refs">
                    <span>{{ t('game.world_journal.why_measurement_state_refs') }}:</span>
                    <span>{{ reading.state_refs.length ? reading.state_refs.join(', ') : t('game.world_journal.why_measurement_none') }}</span>
                  </div>
                  <div v-if="reading.derived_from.length" class="why-measurement__derived-from">
                    <span class="why-measurement__derived-from-label">
                      {{ t('game.world_journal.why_measurement_derived_from') }}:
                    </span>
                    <ul>
                      <li v-for="input in reading.derived_from" :key="measurementKeyText(input)">
                        {{ measurementKeyText(input) }}
                      </li>
                    </ul>
                  </div>
                  <div v-if="reading.source_event_ids.length" class="why-measurement__sources">
                    <span class="why-measurement__sources-label">{{ t('game.world_journal.why_measurement_source_events') }}:</span>
                    <div v-for="eventId in reading.source_event_ids" :key="eventId" class="why-measurement__source">
                      <span>{{ eventId }}</span>
                      <button
                        type="button"
                        class="why-button"
                        :data-testid="`why-measurement-source-event-${eventId}`"
                        @click="openWhy(eventId)"
                      >
                        {{ t('game.world_journal.why_button') }}
                      </button>
                    </div>
                  </div>
                </li>
              </ul>
            </section>

            <section v-if="causalDetail.decision" class="why-section">
              <h4>{{ t('game.world_journal.why_decision') }}</h4>
              <p class="why-decision-thinking">{{ causalDetail.decision.thinking }}</p>
              <p class="why-decision-meta">
                {{ t('game.world_journal.why_considered_count', { count: causalDetail.decision.considered_count }) }}
              </p>
              <p v-if="causalDetail.decision.rejected.length" class="why-decision-meta">
                {{ t('game.world_journal.why_rejected') }}:
                {{ causalDetail.decision.rejected.map((r) => r.action_name).join(', ') }}
              </p>

              <div v-if="causalDetail.decision_appraisals.length" class="why-appraisals">
                <h5>{{ t('game.world_journal.why_decision_appraisals') }}</h5>
                <ul class="why-appraisal-list">
                  <li
                    v-for="entry in causalDetail.decision_appraisals"
                    :key="entry.appraisal_id"
                    class="why-appraisal-item"
                  >
                    <span v-if="entry.pruned" class="why-appraisal-pruned">
                      <span class="why-appraisal-summary why-edge-text--pruned">
                        {{ t('game.world_journal.why_pruned') }}
                      </span>
                    </span>
                    <button
                      v-else
                      type="button"
                      class="why-appraisal-button"
                      @click="openWhy(entry.source_event_id)"
                    >
                      <span class="why-appraisal-line">
                        <span class="why-appraisal-focus">{{ entry.focus_avatar_name }}</span>
                        <span v-if="entry.emotion" class="why-appraisal-emotion">
                          <span aria-hidden="true">{{ entry.emotion.emoji }}</span>
                          {{ entry.emotion.name }}
                        </span>
                        <span class="why-appraisal-date">{{ entry.source_event_date }}</span>
                      </span>
                      <span class="why-appraisal-summary">{{ entry.summary }}</span>
                    </button>
                  </li>
                </ul>
              </div>
            </section>

            <p v-if="causalDetail.truncated" class="journal-note">
              {{ t('game.world_journal.why_truncated') }}
            </p>
          </template>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
/*
 * World Journal — editorial column in "Tinta e Jade".
 *
 * Read as a printed gazette rather than a dashboard: one narrow measure, a
 * tracked eyebrow per section, hairline rules instead of card borders, and
 * numerals in a tabular face. Rounded 9-10px cards with their own background
 * are gone — a stack of them inside a 380px column produced nested boxes and
 * no hierarchy.
 */

.world-journal-panel {
  min-height: 0;
  height: 100%;
  width: 100%;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: var(--surface-panel);
  color: var(--text-secondary);
  font-family: var(--font-ui);
  /*
   * The sidebar is user-resizable, so its children must respond to the column
   * width rather than to the window. `LiveGuideView` keys its two-column split
   * off this container; a viewport media query cannot see a 380px sidebar
   * inside a 1680px window.
   */
  container-type: inline-size;
  container-name: journal;
}

.journal-header {
  position: sticky;
  top: 0;
  z-index: 3;
  flex-shrink: 0;
  padding: var(--s-5) var(--s-5) 0;
  background: var(--surface-panel);
  border-bottom: 1px solid var(--rule);
}

/* The panel title is an eyebrow, not a heading competing with the content. */
.journal-title {
  margin: 0 0 var(--s-4);
  color: var(--text-muted);
  font-size: 10px;
  font-weight: 400;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
}

/*
 * One wrapping row of text tabs. The old `repeat(6)` grid put seven tabs into
 * a rigid six-column grid, so the seventh dropped to a second row of one and
 * every label was clipped to ~55px.
 */
.journal-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0 var(--s-2);
}

.journal-tab {
  min-width: 0;
  /* 40px keeps a comfortable target while fitting two rows in the header. */
  min-height: 40px;
  padding: 0 var(--s-3);
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: var(--text-muted);
  font-family: var(--font-ui);
  font-size: var(--t-sm);
  line-height: 1.1;
  cursor: pointer;
  transition: color var(--motion-fast), border-color var(--motion-fast);
}

.journal-tab span {
  display: block;
}

.journal-tab:hover {
  color: var(--text-primary);
}

.journal-tab:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring);
}

.journal-tab--active {
  border-bottom-color: var(--accent);
  color: var(--accent-strong);
}

.journal-body {
  min-height: 0;
  min-width: 0;
  flex: 1;
  overflow-y: auto;
  padding: var(--s-5);
}

.journal-body--guide {
  padding: 0;
}

/* Section header carries its own inline controls, so the period selector no
   longer occupies a navigation row of its own. */
.journal-section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--s-4);
  flex-wrap: wrap;
}

.period-selector {
  display: inline-flex;
  align-items: stretch;
  border: 1px solid var(--rule);
  border-radius: var(--r-1);
  overflow: hidden;
}

.period-button {
  min-height: 26px;
  padding: 0 var(--s-4);
  border: 0;
  background: transparent;
  color: var(--text-muted);
  font-family: var(--font-numeric);
  font-size: 10px;
  font-variant-numeric: tabular-nums;
  cursor: pointer;
  transition: color var(--motion-fast), background var(--motion-fast);
}

.period-button + .period-button {
  border-left: 1px solid var(--rule-soft);
}

.period-button:hover {
  color: var(--text-primary);
  background: var(--surface-raised);
}

.period-button:focus-visible {
  outline: none;
  box-shadow: inset var(--focus-ring);
}

.period-button--active {
  color: var(--ink-900);
  background: var(--accent);
}

.journal-section + .journal-section {
  margin-top: var(--s-7);
}

.journal-section h3 {
  margin: 0 0 var(--s-4);
  color: var(--text-muted);
  font-size: 10px;
  font-weight: 400;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
}

.journal-section-head h3 {
  margin-bottom: 0;
}

.journal-section--activity {
  padding-bottom: var(--s-5);
  border-bottom: 1px solid var(--rule-soft);
}

/*
 * Activity dateline: four counts on one line. Replaces a 2x2 grid of bordered
 * cards that reserved ~180px to show four zeroes.
 */
.activity-line {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0 var(--s-5);
  margin: var(--s-4) 0 0;
}

.activity-metric {
  display: inline-flex;
  align-items: baseline;
  gap: var(--s-3);
  min-width: 0;
}

/* Own gap so the drawn separator is evenly spaced from both neighbours. */
.activity-metric + .activity-metric {
  gap: var(--s-3);
  padding-left: 0;
}

/*
 * Separator is drawn, not typed, so it never lands in copied text. The flex
 * gap supplies the space on both sides, keeping it optically centred.
 */
.activity-metric + .activity-metric::before {
  content: '';
  align-self: center;
  width: 1px;
  height: 9px;
  background: var(--rule-strong);
}

.activity-metric dd {
  order: -1;
  margin: 0;
  color: var(--text-primary);
  font-family: var(--font-numeric);
  font-size: var(--t-lg);
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}

.activity-metric dt {
  color: var(--text-muted);
  font-size: var(--t-xs);
}

/* Major events keep the gold accent the old card border carried. */
.activity-metric--major dd {
  color: var(--accent-strong);
}

/*
 * A quiet month should look quiet, not broken. A zero drops to the decorative
 * ink value — including for major events, because "no important changes" is
 * not something to accent.
 */
.activity-metric--zero dd,
.activity-metric--zero.activity-metric--major dd {
  color: var(--paper-700);
}

.activity-metric--zero dt {
  color: var(--paper-700);
}

/*
 * Entries are separated by a rule and a gold ledger mark, not by a card. This
 * is what lets a stack of them read as a column of copy.
 */
.highlight-card {
  display: block;
  width: 100%;
  padding: var(--s-5) 0 var(--s-5) var(--s-5);
  border: 0;
  border-left: 2px solid var(--gold-600);
  background: transparent;
  text-align: left;
}

.highlight-card + .highlight-card {
  border-top: 1px solid var(--rule-soft);
}

.highlight-card time {
  color: var(--text-muted);
  font-family: var(--font-numeric);
  font-size: 10px;
  font-variant-numeric: tabular-nums;
}

.event-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--s-4);
}

/* "Why" is the panel's primary verb: a quiet text action, not a gold pill. */
.why-button {
  flex-shrink: 0;
  min-height: 28px;
  padding: 0 var(--s-3);
  border: 0;
  border-bottom: 1px solid var(--gold-600);
  border-radius: 0;
  background: transparent;
  color: var(--accent);
  font-family: var(--font-ui);
  font-size: var(--t-xs);
  cursor: pointer;
  transition: color var(--motion-fast), border-color var(--motion-fast);
}

.why-button:hover {
  color: var(--accent-strong);
  border-bottom-color: var(--accent);
}

.why-button:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring);
}

/* Body copy: the one place in the panel that gets a generous measure. */
.highlight-card p {
  margin: var(--s-3) 0 0;
  color: var(--text-primary);
  font-size: var(--t-md);
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.subject-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--s-2);
  margin-top: var(--s-4);
}

.subject-chip {
  min-height: 26px;
  padding: 0 var(--s-3);
  border: 1px solid var(--jade-600);
  border-radius: var(--r-1);
  background: transparent;
  color: var(--jade-300);
  font-family: var(--font-ui);
  font-size: 10px;
  cursor: pointer;
  transition: color var(--motion-fast), background var(--motion-fast);
}

.subject-chip:hover {
  color: var(--paper-100);
  background: var(--jade-wash);
}

.subject-chip:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring);
}

.ongoing-card {
  display: block;
  width: 100%;
  position: relative;
  padding: var(--s-4) 72px var(--s-4) 0;
  border: 0;
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition: background var(--motion-fast);
}

.ongoing-card + .ongoing-card {
  border-top: 1px solid var(--rule-soft);
}

.ongoing-card:hover {
  background: var(--surface-raised);
}

.ongoing-card:focus-visible {
  outline: none;
  box-shadow: inset var(--focus-ring);
}

.ongoing-avatar,
.ongoing-action,
.ongoing-card small {
  display: block;
}

.ongoing-avatar {
  color: var(--jade-300);
  font-size: var(--t-sm);
  font-weight: 600;
}

.ongoing-action {
  margin-top: var(--s-1);
  color: var(--text-secondary);
  font-size: var(--t-sm);
  overflow-wrap: anywhere;
  word-break: break-word;
}

.ongoing-card small {
  position: absolute;
  top: var(--s-4);
  right: 0;
  max-width: 64px;
  color: var(--text-muted);
  font-family: var(--font-numeric);
  font-size: 9px;
  font-variant-numeric: tabular-nums;
  text-align: right;
}

/* Empty and loading states: a hairline rule and quiet copy, no dashed box. */
.journal-empty,
.journal-state {
  margin: 0;
  padding: var(--s-5) 0;
  border: 0;
  border-top: 1px solid var(--rule-soft);
  color: var(--text-muted);
  font-size: var(--t-sm);
  font-style: italic;
}

.journal-state--error {
  color: var(--state-alert);
  font-style: normal;
}

.journal-note {
  margin: var(--s-5) 0 0;
  padding: 0 0 0 var(--s-4);
  border: 0;
  border-left: 2px solid var(--gold-600);
  color: var(--text-muted);
  font-size: var(--t-xs);
  line-height: 1.55;
}

.journal-timeline {
  min-height: 0;
  min-width: 0;
  width: 100%;
  flex: 1;
  display: flex;
}

/* --- Focus tab: people and objectives --- */

.focus-card {
  padding: var(--s-5) 0;
  border: 0;
  background: transparent;
}

.focus-card + .focus-card {
  border-top: 1px solid var(--rule-soft);
}

.focus-card-header {
  display: block;
  width: 100%;
  min-height: 40px;
  padding: 0;
  border: 0;
  background: transparent;
  text-align: left;
  cursor: pointer;
}

.focus-card-header:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring);
}

.focus-objectives {
  margin: var(--s-4) 0 0;
  display: flex;
  flex-direction: column;
  gap: var(--s-4);
}

/* Objectives read as a definition list: tracked term, indented answer. */
.focus-objective dt {
  color: var(--text-muted);
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: var(--tracking-wide);
}

.focus-objective dd {
  margin: var(--s-1) 0 0;
  color: var(--text-primary);
  font-size: var(--t-md);
  line-height: 1.55;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.focus-card > small {
  display: block;
  margin-top: var(--s-4);
  color: var(--text-muted);
  font-family: var(--font-numeric);
  font-size: 10px;
  font-variant-numeric: tabular-nums;
}

/* --- "Why" causal drill-down overlay --- */

.why-overlay {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: flex;
  align-items: flex-end;
  background: var(--surface-scrim);
  padding-bottom: env(safe-area-inset-bottom, 0px);
}

.why-overlay--above-dossier {
  z-index: 70;
}

.why-panel {
  width: 100%;
  max-height: 88%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: var(--surface-panel);
  border-top: 1px solid var(--rule-strong);
  /* Lacquered panel, not a rounded mobile sheet. */
  border-radius: 0;
  box-shadow: var(--shadow-panel);
}

.why-header {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--s-5) var(--s-6);
  border-bottom: 1px solid var(--rule);
}

.why-header h3 {
  margin: 0;
  color: var(--text-muted);
  font-size: 10px;
  font-weight: 400;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
}

.why-close {
  min-width: var(--touch-target);
  min-height: var(--touch-target);
  border: 0;
  background: transparent;
  color: var(--text-secondary);
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
  transition: color var(--motion-fast);
}

.why-close:hover {
  color: var(--text-primary);
}

.why-close:focus-visible {
  outline: none;
  box-shadow: inset var(--focus-ring);
}

.why-body {
  min-height: 0;
  overflow-y: auto;
  padding: var(--s-6);
}

/* The event under investigation: the drill-down's dateline. */
.why-subject {
  margin: 0 0 var(--s-6);
  padding: 0 0 var(--s-5) var(--s-5);
  border-left: 2px solid var(--accent);
  border-bottom: 1px solid var(--rule);
  background: transparent;
  color: var(--text-primary);
  font-family: var(--font-display);
  font-size: 15px;
  line-height: 1.55;
}

.why-section + .why-section {
  margin-top: var(--s-7);
}

.why-section h4 {
  margin: 0 0 var(--s-4);
  color: var(--text-muted);
  font-size: 10px;
  font-weight: 400;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
}

/*
 * Causal edges are a ledger: a tracked relation term over the event text,
 * separated by rules. Each edge used to be its own bordered, rounded box, so a
 * chain of five causes produced five nested boxes inside the overlay.
 */
.why-edge-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}

.why-edge {
  padding: var(--s-4) 0;
  border: 0;
  border-radius: 0;
  background: transparent;
}

.why-edge + .why-edge {
  border-top: 1px solid var(--rule-soft);
}

.why-relation {
  display: block;
  color: var(--jade-300);
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: var(--tracking-wide);
}

.why-edge-text {
  display: block;
  margin-top: var(--s-2);
  color: var(--text-primary);
  font-size: var(--t-md);
  line-height: 1.55;
  overflow-wrap: anywhere;
  word-break: break-word;
}

/* A pruned edge is absence of evidence, and must read as such. */
.why-edge-text--pruned {
  color: var(--text-muted);
  font-style: italic;
}

.why-measurement-list {
  display: flex;
  flex-direction: column;
  list-style: none;
  margin: 0;
  padding: 0;
}

.why-measurement {
  padding: var(--s-4) 0;
  border: 0;
  border-radius: 0;
  background: transparent;
}

.why-measurement + .why-measurement {
  border-top: 1px solid var(--rule-soft);
}

.why-measurement__header,
.why-measurement__refs,
.why-measurement__source {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--s-4);
}

.why-measurement__header strong {
  color: var(--text-primary);
  font-size: var(--t-md);
  font-weight: 400;
  overflow-wrap: anywhere;
}

/* Readings are data: tabular numerals, gold so the value is findable. */
.why-measurement__header span {
  color: var(--accent-strong);
  font-family: var(--font-numeric);
  font-size: var(--t-sm);
  font-variant-numeric: tabular-nums;
  text-align: right;
  overflow-wrap: anywhere;
}

.why-measurement__meta,
.why-measurement__refs,
.why-measurement__derived-from,
.why-measurement__sources {
  margin-top: var(--s-2);
  color: var(--text-muted);
  font-size: var(--t-xs);
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.why-measurement__derived-from-label {
  display: block;
  color: var(--text-secondary);
}

.why-measurement__derived-from ul {
  margin: 3px 0 0;
  padding-left: 16px;
}

.why-measurement__derived-from li + li {
  margin-top: 3px;
}

.why-measurement__sources-label {
  display: block;
  margin-bottom: 3px;
}

.why-measurement__sources {
  color: #bdb6a9;
}

.why-measurement__source + .why-measurement__source {
  margin-top: 4px;
}

.why-measurement__source .why-button {
  min-height: 28px;
  padding: 3px 9px;
  font-size: 10px;
}

/* The agent's reasoning is a quotation, so it is set in the display serif. */
.why-decision-thinking {
  margin: 0;
  padding-left: var(--s-5);
  border-left: 2px solid var(--rule-strong);
  color: var(--text-primary);
  font-family: var(--font-display);
  font-size: var(--t-md);
  line-height: 1.6;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.why-decision-meta {
  margin: var(--s-3) 0 0;
  color: var(--text-muted);
  font-size: var(--t-xs);
  line-height: 1.5;
}

.why-appraisals {
  margin-top: var(--s-5);
  min-width: 0;
}

.why-appraisals h5 {
  margin: 0 0 var(--s-3);
  color: var(--text-muted);
  font-size: 10px;
  font-weight: 400;
  text-transform: uppercase;
  letter-spacing: var(--tracking-wide);
}

.why-appraisal-list {
  display: flex;
  flex-direction: column;
  min-width: 0;
  list-style: none;
  margin: 0;
  padding: 0;
}

.why-appraisal-item {
  min-width: 0;
}

.why-appraisal-item + .why-appraisal-item {
  border-top: 1px solid var(--rule-soft);
}

.why-appraisal-button {
  display: flex;
  flex-direction: column;
  gap: var(--s-2);
  width: 100%;
  min-width: 0;
  min-height: var(--touch-target);
  padding: var(--s-4) var(--s-3);
  border: 0;
  border-radius: 0;
  background: transparent;
  color: var(--text-secondary);
  text-align: left;
  cursor: pointer;
  font: inherit;
  font-family: var(--font-ui);
  transition: background var(--motion-fast);
}

.why-appraisal-button:hover {
  background: var(--surface-raised);
}

.why-appraisal-button:focus-visible {
  outline: none;
  box-shadow: inset var(--focus-ring);
}

.why-appraisal-line {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--s-4);
  min-width: 0;
  flex-wrap: wrap;
}

.why-appraisal-focus {
  min-width: 0;
  overflow-wrap: anywhere;
  font-size: var(--t-sm);
  font-weight: 600;
  color: var(--text-primary);
}

.why-appraisal-pruned {
  display: block;
  width: 100%;
  min-width: 0;
  padding: var(--s-4) var(--s-3);
  border: 0;
  border-radius: 0;
  background: transparent;
}

.why-appraisal-emotion {
  flex: 0 0 auto;
  color: var(--jade-300);
  font-size: 10px;
}

.why-appraisal-date {
  flex: 0 0 auto;
  color: var(--text-muted);
  font-family: var(--font-numeric);
  font-size: 10px;
  font-variant-numeric: tabular-nums;
}

.why-appraisal-summary {
  min-width: 0;
  overflow-wrap: anywhere;
  word-break: break-word;
  font-size: var(--t-sm);
  line-height: 1.5;
  color: var(--text-secondary);
}

.why-retry {
  margin-top: var(--s-5);
  min-height: 36px;
  padding: 0 var(--s-6);
  border: 1px solid var(--gold-600);
  border-radius: var(--r-1);
  background: transparent;
  color: var(--accent-strong);
  font-family: var(--font-ui);
  font-size: var(--t-sm);
  cursor: pointer;
  transition: background var(--motion-fast), border-color var(--motion-fast);
}

.why-retry:hover {
  background: var(--accent-wash);
  border-color: var(--accent);
}

.why-retry:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring);
}

/*
 * Touch: the same editorial column, with every target lifted to 48px and body
 * copy at 16px. The panel is shared with the mobile sheet, so these rules stay.
 */
@media (max-width: 760px) {
  .world-journal-panel {
    min-height: 100%;
    height: auto;
  }

  .journal-header {
    padding-top: var(--s-4);
  }

  .journal-body {
    overflow: visible;
    padding: var(--s-5) var(--s-6) var(--s-7);
  }

  .journal-tab {
    min-height: 48px;
    padding: 0 var(--s-4);
    font-size: var(--t-sm);
  }

  .journal-body--guide {
    padding: 0;
  }

  .period-button {
    min-height: 40px;
    font-size: var(--t-xs);
  }

  .why-button,
  .subject-chip,
  .why-retry,
  .why-appraisal-button,
  .focus-card-header {
    min-height: 48px;
  }

  .highlight-card p,
  .why-edge-text,
  .why-subject,
  .why-decision-thinking,
  .focus-objective dd {
    font-size: 16px;
    line-height: 1.6;
  }

  .activity-metric dd {
    font-size: var(--t-display);
  }

  .why-panel {
    max-height: 92%;
  }

  .journal-timeline {
    min-height: 65vh;
  }
}
</style>
