<script setup lang="ts">
import { NSelect, NSpin } from 'naive-ui'
import EventStreamList from '@/components/game/EventStreamList.vue'
import { useI18n } from 'vue-i18n'
import { useEventPanel } from '@/composables/useEventPanel'

const emit = defineEmits<{ 'open-why': [eventId: string] }>()

const { t } = useI18n()
const {
  eventStore,
  filterValue1,
  filterSectValue,
  filterMajorScope,
  eventListRef,
  roleplayLockedAvatarName,
  filterOptions,
  sectFilterOptions,
  majorFilterOptions,
  panelTitle,
  displayEvents,
  emptyEventMessage,
  renderLabel,
  handleScroll,
  formatEventDate,
  renderEventContent,
  handleAvatarClick,
  handleSectClick,
} = useEventPanel()
</script>

<template>
  <section class="sidebar-section">
    <div class="sidebar-header">
      <h3>{{ panelTitle }}</h3>
      <div class="filter-group">
        <span v-if="roleplayLockedAvatarName" class="roleplay-event-lock">
          {{ t('game.event_panel.roleplay_locked', { avatar: roleplayLockedAvatarName }) }}
        </span>
        <n-select
          v-model:value="filterSectValue"
          :options="sectFilterOptions"
          size="tiny"
          class="event-filter"
          data-testid="sect-filter"
        />
        <n-select
          v-model:value="filterValue1"
          :options="filterOptions"
          :render-label="renderLabel"
          size="tiny"
          class="event-filter"
        />
        <n-select
          v-model:value="filterMajorScope"
          :options="majorFilterOptions"
          size="tiny"
          class="event-filter event-filter--scope"
          data-testid="major-filter"
        />
      </div>
    </div>
    <div v-if="eventStore.eventsLoading && displayEvents.length === 0" class="loading">
      <n-spin size="small" />
      <span>{{ t('common.loading') }}</span>
    </div>
    <div v-else-if="displayEvents.length === 0" class="empty">{{ emptyEventMessage }}</div>
    <div v-else class="event-list" ref="eventListRef" @scroll="handleScroll">
      <!-- 顶部加载指示器 -->
      <div v-if="eventStore.eventsHasMore" class="load-more-hint">
        <span v-if="eventStore.eventsLoading">{{ t('common.loading') }}</span>
        <span v-else>{{ t('game.event_panel.load_more') }}</span>
      </div>
      <EventStreamList
        :events="displayEvents"
        :empty-text="emptyEventMessage"
        :format-date="formatEventDate"
        :render-segments="renderEventContent"
        :on-avatar-click="handleAvatarClick"
        :on-sect-click="handleSectClick"
        :on-open-why="(eventId) => emit('open-why', eventId)"
        :why-label="t('game.world_journal.why_button')"
      />
    </div>
  </section>
</template>

<style scoped>
.sidebar-section {
  flex: 1;
  width: 100%;
  min-width: 0;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

/* Timeline tab header: a hairline rule over the panel surface, not a lighter
   grey bar, so the tab does not introduce a fourth background value. */
.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--s-4);
  padding: var(--s-4) var(--s-5);
  background: var(--surface-panel);
  border-bottom: 1px solid var(--rule);
}

.sidebar-header h3 {
  margin: 0;
  color: var(--text-muted);
  font-family: var(--font-ui);
  font-size: 10px;
  font-weight: 400;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  white-space: nowrap;
}

.filter-group {
  display: flex;
  align-items: center;
  gap: var(--s-2);
}

.roleplay-event-lock {
  max-width: 160px;
  padding: 0 var(--s-3);
  border-radius: var(--r-1);
  border: 1px solid var(--gold-600);
  color: var(--accent-strong);
  background: transparent;
  font-family: var(--font-ui);
  font-size: var(--t-xs);
  line-height: 1.6;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.event-filter {
  width: 120px;
}

.event-list {
  flex: 1;
  width: 100%;
  min-width: 0;
  overflow-y: auto;
  padding: var(--s-4) var(--s-5);
}

.empty, .loading {
  padding: var(--s-7) 0;
  text-align: center;
  color: var(--text-muted);
  font-family: var(--font-ui);
  font-size: var(--t-sm);
  font-style: italic;
}

.loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--s-4);
  font-style: normal;
}

.load-more-hint {
  text-align: center;
  padding: var(--s-4);
  color: var(--text-muted);
  font-family: var(--font-ui);
  font-size: var(--t-xs);
  border-bottom: 1px solid var(--rule-soft);
}

@media (max-width: 760px) {
  .sidebar-header {
    flex-direction: column;
    align-items: stretch;
    gap: 8px;
  }

  .sidebar-header h3 {
    white-space: normal;
  }

  .filter-group {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--s-3);
    width: 100%;
  }

  .roleplay-event-lock,
  .event-filter {
    width: 100%;
    min-width: 0;
    max-width: none;
  }

  .roleplay-event-lock,
  .event-filter--scope {
    grid-column: 1 / -1;
  }

  .event-list {
    padding: 8px 10px;
  }
}
</style>
