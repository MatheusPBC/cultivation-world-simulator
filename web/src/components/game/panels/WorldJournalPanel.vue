<script setup lang="ts">
import { onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useI18n } from 'vue-i18n'

import EventPanel from '@/components/game/panels/EventPanel.vue'
import { useUiStore } from '@/stores/ui'
import { useWorldJournalStore, type WorldJournalTab } from '@/stores/worldJournal'
import type { EventDTO, EventSubjectDTO, WorldJournalPeriodMonths } from '@/types/api'

const { t } = useI18n()
const uiStore = useUiStore()
const journalStore = useWorldJournalStore()
const { activeTab, periodMonths, journal, loading, hasError } = storeToRefs(journalStore)

const tabs: Array<{
  key: 'now' | 'focus' | 'stories' | 'timeline'
  labelKey: string
  disabled?: boolean
}> = [
  { key: 'now', labelKey: 'game.world_journal.tabs.now' },
  { key: 'focus', labelKey: 'game.world_journal.tabs.focus', disabled: true },
  { key: 'stories', labelKey: 'game.world_journal.tabs.stories', disabled: true },
  { key: 'timeline', labelKey: 'game.world_journal.tabs.timeline' },
]

const periods: Array<{ months: WorldJournalPeriodMonths; labelKey: string }> = [
  { months: 1, labelKey: 'game.world_journal.periods.one' },
  { months: 3, labelKey: 'game.world_journal.periods.three' },
  { months: 12, labelKey: 'game.world_journal.periods.twelve' },
]

function selectTab(tab: string, disabled = false) {
  if (disabled || (tab !== 'now' && tab !== 'timeline')) return
  journalStore.selectTab(tab as WorldJournalTab)
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

onMounted(() => {
  void journalStore.refresh()
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
          :disabled="tab.disabled"
          :data-testid="`journal-tab-${tab.key}`"
          @click="selectTab(tab.key, tab.disabled)"
        >
          <span>{{ t(tab.labelKey) }}</span>
          <small v-if="tab.disabled">{{ t('game.world_journal.coming_soon') }}</small>
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
            <time>{{ formatEventDate(event) }}</time>
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

    <div v-else class="journal-timeline" data-testid="journal-timeline">
      <EventPanel />
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
  grid-template-columns: repeat(4, minmax(0, 1fr));
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

.journal-tab span,
.journal-tab small {
  display: block;
}

.journal-tab small {
  margin-top: 3px;
  color: #626262;
  font-size: 8px;
}

.journal-tab--active {
  border-bottom-color: #c5a66b;
  color: #f1dfb9;
}

.journal-tab:disabled {
  cursor: not-allowed;
  opacity: 0.58;
}

.journal-body {
  min-height: 0;
  min-width: 0;
  flex: 1;
  overflow-y: auto;
  padding: 12px;
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

.highlight-card,
.ongoing-card {
  display: block;
  width: 100%;
  margin-top: 8px;
  border: 1px solid #303030;
  border-radius: 10px;
  background: #191919;
  text-align: left;
}

.highlight-card {
  padding: 12px;
  border-left: 3px solid #b99652;
}

.highlight-card time {
  color: #817b71;
  font-size: 10px;
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
  position: relative;
  padding: 11px 78px 11px 12px;
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

.journal-timeline {
  min-height: 0;
  min-width: 0;
  width: 100%;
  flex: 1;
  display: flex;
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
    min-height: 44px;
    font-size: 10px;
  }

  .period-button {
    min-height: 42px;
  }

  .journal-timeline {
    min-height: 65vh;
  }
}
</style>
