<script setup lang="ts">
import { onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useI18n } from 'vue-i18n'

import EventPanel from '@/components/game/panels/EventPanel.vue'
import ChronicleDossierDrawer from '@/components/game/panels/world-journal/ChronicleDossierDrawer.vue'
import ChronicleView from '@/components/game/panels/world-journal/ChronicleView.vue'
import LiveGuideView from '@/components/game/panels/world-journal/LiveGuideView.vue'
import DaoPetitionsView from '@/components/game/panels/world-journal/DaoPetitionsView.vue'
import { useUiStore } from '@/stores/ui'
import { useWorldJournalStore, type WorldJournalTab } from '@/stores/worldJournal'
import type { CausalEdgeDTO, EventDTO, EventSubjectDTO, LiveGuideSubjectDTO, WorldJournalPeriodMonths } from '@/types/api'

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
      <h2>{{ t('game.world_journal.title') }}</h2>
      <div class="journal-tabs" role="tablist">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          type="button"
          class="journal-tab"
          :class="{ 'journal-tab--active': activeTab === tab.key }"
          :data-testid="`journal-tab-${tab.key}`"
          @click="selectTab(tab.key)"
        >
          <span>{{ t(tab.labelKey) }}</span>
        </button>
      </div>
    </header>

    <div v-if="activeTab === 'now'" class="journal-body" data-testid="journal-now">
      <div class="period-selector" aria-label="periodo do diario">
        <button
          v-for="period in periods"
          :key="period.months"
          type="button"
          class="period-button"
          :class="{ 'period-button--active': periodMonths === period.months }"
          :data-testid="`journal-period-${period.months}`"
          @click="journalStore.setPeriod(period.months)"
        >
          {{ t(period.labelKey) }}
        </button>
      </div>

      <p v-if="loading && !journal" class="journal-state">{{ t('game.world_journal.loading') }}</p>
      <p v-else-if="hasError" class="journal-state journal-state--error">
        {{ t('game.world_journal.error') }}
      </p>

      <template v-if="journal">
        <section class="journal-section">
          <h3>{{ t('game.world_journal.activity') }}</h3>
          <div class="activity-grid">
            <div class="activity-stat">
              <strong>{{ journal.activity.total_events }}</strong>
              <span>{{ t('game.world_journal.total_events') }}</span>
            </div>
            <div class="activity-stat activity-stat--major">
              <strong>{{ journal.activity.major_events }}</strong>
              <span>{{ t('game.world_journal.major_events') }}</span>
            </div>
            <div class="activity-stat">
              <strong>{{ journal.activity.story_events }}</strong>
              <span>{{ t('game.world_journal.story_events') }}</span>
            </div>
            <div class="activity-stat">
              <strong>{{ journal.activity.active_avatar_count }}</strong>
              <span>{{ t('game.world_journal.active_avatars') }}</span>
            </div>
          </div>
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
.world-journal-panel {
  min-height: 0;
  height: 100%;
  width: 100%;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: #111;
  color: #e8e2d4;
}

.journal-header {
  position: sticky;
  top: 0;
  z-index: 3;
  flex-shrink: 0;
  padding: 10px 10px 0;
  background: rgba(17, 17, 17, 0.97);
  border-bottom: 1px solid #303030;
}

.journal-header h2 {
  margin: 0 0 9px;
  color: #f3e9cf;
  font-size: 14px;
  letter-spacing: 0.02em;
}

.journal-tabs {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
}

.journal-tab {
  min-width: 0;
  min-height: 42px;
  padding: 6px 3px;
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: #969696;
  font-size: 11px;
  line-height: 1.1;
}

.journal-tab span {
  display: block;
}

.journal-tab--active {
  border-bottom-color: #c5a66b;
  color: #f1dfb9;
}

.journal-body {
  min-height: 0;
  min-width: 0;
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.journal-body--guide {
  padding: 0;
}

.period-selector {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 6px;
  margin-bottom: 14px;
}

.period-button {
  min-height: 34px;
  padding: 6px;
  border: 1px solid #363636;
  border-radius: 7px;
  background: #1a1a1a;
  color: #aaa;
  font-size: 11px;
}

.period-button--active {
  border-color: rgba(197, 166, 107, 0.72);
  background: rgba(85, 63, 27, 0.38);
  color: #f2dfb7;
}

.journal-section + .journal-section {
  margin-top: 18px;
}

.journal-section h3 {
  margin: 0 0 9px;
  color: #bdb6a9;
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.activity-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 7px;
}

.activity-stat {
  min-width: 0;
  padding: 10px;
  border: 1px solid #2e2e2e;
  border-radius: 9px;
  background: #181818;
}

.activity-stat strong,
.activity-stat span {
  display: block;
}

.activity-stat strong {
  color: #eee6d6;
  font-size: 18px;
}

.activity-stat span {
  margin-top: 2px;
  color: #898989;
  font-size: 10px;
}

.activity-stat--major {
  border-color: rgba(197, 166, 107, 0.46);
}

.highlight-card {
  display: block;
  width: 100%;
  margin-top: 8px;
  padding: 12px;
  border: 1px solid #303030;
  border-left: 3px solid #b99652;
  border-radius: 10px;
  background: #191919;
  text-align: left;
}

.highlight-card time {
  color: #817b71;
  font-size: 10px;
}

.event-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.why-button {
  flex-shrink: 0;
  min-height: 30px;
  padding: 4px 10px;
  border: 1px solid rgba(197, 166, 107, 0.5);
  border-radius: 999px;
  background: rgba(85, 63, 27, 0.28);
  color: #f1dfb9;
  font-size: 11px;
}

.highlight-card p {
  margin: 7px 0 0;
  color: #ded8ca;
  font-size: 13px;
  line-height: 1.55;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.subject-list {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 9px;
}

.subject-chip {
  min-height: 28px;
  padding: 4px 8px;
  border: 1px solid #3b4d47;
  border-radius: 999px;
  background: #17201d;
  color: #7dd9bd;
  font-size: 10px;
}

.ongoing-card {
  display: block;
  width: 100%;
  position: relative;
  margin-top: 8px;
  padding: 11px 78px 11px 12px;
  border: 1px solid #303030;
  border-radius: 10px;
  background: #191919;
  text-align: left;
}

.ongoing-avatar,
.ongoing-action,
.ongoing-card small {
  display: block;
}

.ongoing-avatar {
  color: #79d5b9;
  font-size: 12px;
  font-weight: 600;
}

.ongoing-action {
  margin-top: 4px;
  color: #d0cbc0;
  font-size: 12px;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.ongoing-card small {
  position: absolute;
  top: 12px;
  right: 10px;
  max-width: 65px;
  color: #777;
  font-size: 9px;
  text-align: right;
}

.journal-empty,
.journal-state {
  margin: 0;
  padding: 14px;
  border: 1px dashed #303030;
  border-radius: 9px;
  color: #777;
  font-size: 12px;
}

.journal-state--error {
  color: #d28d84;
}

.journal-note {
  margin: 10px 0 0;
  padding: 10px 12px;
  border: 1px dashed rgba(197, 166, 107, 0.4);
  border-radius: 9px;
  color: #bdb6a9;
  font-size: 11px;
  line-height: 1.5;
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
  margin-top: 8px;
  padding: 12px;
  border: 1px solid #303030;
  border-radius: 10px;
  background: #191919;
}

.focus-card-header {
  display: block;
  width: 100%;
  min-height: 48px;
  padding: 0;
  border: 0;
  background: transparent;
  text-align: left;
}

.focus-objectives {
  margin: 10px 0 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.focus-objective dt {
  color: #8a8478;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.focus-objective dd {
  margin: 3px 0 0;
  color: #ded8ca;
  font-size: 13px;
  line-height: 1.5;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.focus-card > small {
  display: block;
  margin-top: 10px;
  color: #777;
  font-size: 10px;
}

/* --- "Why" causal drill-down overlay --- */

.why-overlay {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: flex;
  align-items: flex-end;
  background: rgba(0, 0, 0, 0.6);
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
  background: #161616;
  border-top: 1px solid #383838;
  border-radius: 14px 14px 0 0;
  box-shadow: 0 -8px 24px rgba(0, 0, 0, 0.45);
}

.why-header {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-bottom: 1px solid #2c2c2c;
}

.why-header h3 {
  margin: 0;
  color: #f3e9cf;
  font-size: 14px;
}

.why-close {
  min-width: 48px;
  min-height: 48px;
  border: 0;
  background: transparent;
  color: #bbb;
  font-size: 22px;
  line-height: 1;
}

.why-body {
  min-height: 0;
  overflow-y: auto;
  padding: 14px;
}

.why-subject {
  margin: 0 0 12px;
  padding: 10px 12px;
  border-left: 3px solid #b99652;
  background: #1d1d1d;
  color: #f1dfb9;
  font-size: 14px;
  line-height: 1.55;
}

.why-section + .why-section {
  margin-top: 16px;
}

.why-section h4 {
  margin: 0 0 8px;
  color: #bdb6a9;
  font-size: 11px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.why-edge-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.why-edge {
  padding: 9px 10px;
  border: 1px solid #2e2e2e;
  border-radius: 8px;
  background: #1a1a1a;
}

.why-relation {
  display: block;
  color: #7dd9bd;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.why-edge-text {
  display: block;
  margin-top: 4px;
  color: #ded8ca;
  font-size: 13px;
  line-height: 1.5;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.why-edge-text--pruned {
  color: #8a8478;
  font-style: italic;
}

.why-decision-thinking {
  margin: 0;
  color: #ded8ca;
  font-size: 13px;
  line-height: 1.55;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.why-decision-meta {
  margin: 6px 0 0;
  color: #918b7f;
  font-size: 11px;
  line-height: 1.5;
}

.why-appraisals {
  margin-top: 8px;
  min-width: 0;
}

.why-appraisals h5 {
  margin: 0 0 6px;
  color: #9f9380;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.why-appraisal-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
  list-style: none;
  margin: 0;
  padding: 0;
}

.why-appraisal-item {
  min-width: 0;
}

.why-appraisal-button {
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 100%;
  min-width: 0;
  min-height: 44px;
  padding: 8px 10px;
  border: 1px solid #2e2e2e;
  border-radius: 8px;
  background: #1a1a1a;
  color: #ded8ca;
  text-align: left;
  cursor: pointer;
  font: inherit;
}

.why-appraisal-button:hover,
.why-appraisal-button:focus-visible {
  background: #222;
}

.why-appraisal-line {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  min-width: 0;
  flex-wrap: wrap;
}

.why-appraisal-focus {
  min-width: 0;
  overflow-wrap: anywhere;
  font-size: 12px;
  font-weight: 600;
  color: #ddd;
}

.why-appraisal-pruned {
  display: block;
  width: 100%;
  min-width: 0;
  padding: 8px 10px;
  border: 1px dashed #2e2e2e;
  border-radius: 8px;
  background: #161616;
}

.why-appraisal-emotion {
  flex: 0 0 auto;
  color: #7dd9bd;
  font-size: 10px;
}

.why-appraisal-date {
  flex: 0 0 auto;
  color: #918b7f;
  font-size: 10px;
}

.why-appraisal-summary {
  min-width: 0;
  overflow-wrap: anywhere;
  word-break: break-word;
  font-size: 12px;
  line-height: 1.5;
  color: #bbb;
}

.why-retry {
  margin-top: 10px;
  min-height: 44px;
  padding: 0 16px;
  border: 1px solid #3b3b3b;
  border-radius: 8px;
  background: #1f1f1f;
  color: #f1dfb9;
  font-size: 12px;
}

@media (max-width: 760px) {
  .world-journal-panel {
    min-height: 100%;
    height: auto;
  }

  .journal-header {
    padding-top: 8px;
  }

  .journal-header h2 {
    font-size: 13px;
  }

  .journal-body {
    overflow: visible;
    padding: 12px 14px 24px;
  }

  .journal-tab {
    min-height: 48px;
    font-size: 10px;
  }

  .journal-tabs {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .journal-body--guide {
    padding: 0;
  }

  .period-button {
    min-height: 48px;
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

  .why-panel {
    max-height: 92%;
  }

  .journal-timeline {
    min-height: 65vh;
  }
}
</style>
