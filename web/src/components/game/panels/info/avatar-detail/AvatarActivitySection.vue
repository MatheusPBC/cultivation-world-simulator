<script setup lang="ts">
import type { AvatarActivity } from '@/types/core'

defineProps<{
  activity: AvatarActivity
  title: string
  nowLabel: string
  idleLabel: string
  queueLabel: string
  factsLabel: string
  decisionLabel: string
  factLabel: string
  whyLabel: string
  emptyLabel: string
  objectiveLabel: string
  consideredLabel: (count: number) => string
  rejectedLabel: string
}>()

const emit = defineEmits<{
  (e: 'open-source', eventId: string): void
}>()

function eventDate(event: AvatarActivity['events'][number]): string {
  return `${event.year} · ${event.month}`
}
</script>

<template>
  <section class="activity-section" data-testid="avatar-activity">
    <div class="section-title">{{ title }}</div>

    <div class="activity-now">
      <span>{{ nowLabel }}</span>
      <strong>{{ activity.current_action.label || idleLabel }}</strong>
    </div>

    <div v-if="activity.current_action.queued_actions.length" class="activity-queue">
      <span>{{ queueLabel }}</span>
      <ol>
        <li v-for="action in activity.current_action.queued_actions" :key="action">{{ action }}</li>
      </ol>
    </div>

    <div class="activity-facts">
      <span class="activity-label">{{ factsLabel }}</span>
      <p v-if="activity.events.length === 0" class="activity-empty">{{ emptyLabel }}</p>
      <ol v-else class="activity-list">
        <li v-for="event in activity.events" :key="event.event_id" class="activity-event">
          <div class="activity-event__meta">
            <time>{{ eventDate(event) }}</time>
            <span :class="event.decision ? 'activity-kind activity-kind--decision' : 'activity-kind'">
              {{ event.decision ? decisionLabel : factLabel }}
            </span>
          </div>
          <p class="activity-event__content">{{ event.content }}</p>

          <div v-if="event.decision" class="activity-decision">
            <p v-if="event.decision.short_term_objective">
              <span>{{ objectiveLabel }}</span>
              {{ event.decision.short_term_objective }}
            </p>
            <p v-if="event.decision.thinking">{{ event.decision.thinking }}</p>
            <p v-if="event.decision.chosen_actions.length" class="activity-chosen">
              {{ event.decision.chosen_actions.join(' → ') }}
            </p>
            <p v-if="event.decision.considered_count" class="activity-considered">
              {{ consideredLabel(event.decision.considered_count) }}
            </p>
            <div v-if="event.decision.rejected.length" class="activity-rejections">
              <span>{{ rejectedLabel }}</span>
              <ul class="activity-rejected">
                <li v-for="rejected in event.decision.rejected" :key="`${rejected.action_name}-${rejected.reason}`">
                  <strong>{{ rejected.action_name }}</strong>
                  <span>{{ rejected.reason }}</span>
                </li>
              </ul>
            </div>
          </div>

          <button type="button" class="activity-why" @click="emit('open-source', event.event_id)">
            {{ whyLabel }}
          </button>
        </li>
      </ol>
    </div>
  </section>
</template>

<style scoped>
.activity-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  border: 1px solid rgba(103, 180, 220, 0.25);
  border-left: 3px solid rgba(86, 183, 225, 0.8);
  background: linear-gradient(135deg, rgba(30, 103, 139, 0.16), rgba(255, 255, 255, 0.025));
}

.section-title,
.activity-label,
.activity-now > span,
.activity-queue > span {
  color: #9fcae0;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.section-title { border: 0; margin: 0; padding: 0; }

.activity-now {
  display: grid;
  gap: 3px;
}

.activity-now strong { color: #edf7fb; font-size: 15px; font-weight: 600; }

.activity-queue { display: grid; gap: 4px; }
.activity-queue ol { display: flex; flex-wrap: wrap; gap: 5px; margin: 0; padding: 0; list-style: none; }
.activity-queue li { padding: 3px 7px; border: 1px solid rgba(133, 203, 234, 0.25); background: rgba(47, 122, 158, 0.17); color: #d6edf8; font-size: 11px; }

.activity-facts { display: grid; gap: 7px; }
.activity-empty { margin: 0; color: #9a9a9a; font-size: 12px; font-style: italic; }
.activity-list { display: grid; gap: 8px; margin: 0; padding: 0; list-style: none; }
.activity-event { padding-top: 8px; border-top: 1px solid rgba(255, 255, 255, 0.09); }
.activity-event__meta { display: flex; justify-content: space-between; gap: 8px; color: #8e9da6; font-size: 10px; }
.activity-kind { color: #d1d8d4; }
.activity-kind--decision { color: #e5c57a; }
.activity-event__content { margin: 5px 0 0; color: #e3e6e4; font-size: 12px; line-height: 1.5; }
.activity-decision { display: grid; gap: 5px; margin-top: 7px; padding-left: 9px; border-left: 1px solid rgba(229, 197, 122, 0.5); }
.activity-decision p { margin: 0; color: #bac7ca; font-size: 12px; line-height: 1.45; }
.activity-decision p span { color: #e5c57a; font-size: 10px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; }
.activity-chosen { color: #a9dfc8 !important; }
.activity-considered { color: #819097 !important; font-size: 11px !important; }
.activity-rejected { display: grid; gap: 4px; margin: 0; padding: 0; list-style: none; }
.activity-rejections { display: grid; gap: 4px; }
.activity-rejections > span { color: #d8b5a8; font-size: 10px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; }
.activity-rejected li { display: grid; gap: 1px; color: #9ca5a5; font-size: 11px; }
.activity-rejected strong { color: #d8b5a8; font-weight: 600; }
.activity-why { min-height: 32px; width: fit-content; margin-top: 5px; padding: 0; border: 0; border-bottom: 1px solid rgba(136, 207, 237, 0.62); background: transparent; color: #a9daf0; font: inherit; font-size: 11px; cursor: pointer; }
.activity-why:hover { color: #eff9ff; }
.activity-why:focus-visible { outline: none; box-shadow: var(--focus-ring); }

@media (hover: none) {
  .activity-why { min-height: 44px; }
}
</style>
