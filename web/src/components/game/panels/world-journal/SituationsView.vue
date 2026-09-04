<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import type { WorldSituationDTO, WorldSituationSubjectDTO } from '@/types/api'

defineProps<{
  situations: WorldSituationDTO[]
  loading: boolean
  error: boolean
}>()

const emit = defineEmits<{
  why: [eventId: string]
  subject: [subject: WorldSituationSubjectDTO]
  dao: []
}>()

const { t } = useI18n()

function title(situation: WorldSituationDTO): string {
  return situation.title || t(
    `game.world_journal.situations.${situation.title_key}`,
    situation.title_params,
  )
}

function summary(situation: WorldSituationDTO): string {
  return situation.summary || t(
    `game.world_journal.situations.${situation.summary_key}`,
    situation.summary_params,
  )
}

function latestEventDate(situation: WorldSituationDTO): string {
  const event = situation.latest_event
  if (!event) return ''
  return t('game.world_journal.situations.event_date', {
    year: event.year,
    month: event.month,
  })
}

function responseDecision(situation: WorldSituationDTO): string {
  const decision = situation.latest_response?.decision
  return decision
    ? t(`game.world_journal.situations.response_${decision}`)
    : ''
}
</script>

<template>
  <section class="situations-view" data-testid="world-situations">
    <header class="situations-intro">
      <span>{{ t('game.world_journal.situations.eyebrow') }}</span>
      <h3>{{ t('game.world_journal.situations.title') }}</h3>
      <p>{{ t('game.world_journal.situations.description') }}</p>
    </header>

    <p v-if="loading && situations.length === 0" class="situations-state">
      {{ t('game.world_journal.loading') }}
    </p>
    <p v-else-if="error" class="situations-state situations-state--error">
      {{ t('game.world_journal.error') }}
    </p>
    <p v-else-if="situations.length === 0" class="situations-state">
      {{ t('game.world_journal.situations.empty') }}
    </p>

    <article
      v-for="situation in situations"
      v-else
      :key="situation.id"
      class="situation"
      :class="`situation--${situation.severity}`"
      :data-testid="`situation-${situation.id}`"
    >
      <header class="situation__header">
        <span class="situation__marker" aria-hidden="true"></span>
        <div>
          <div class="situation__meta">
            <span>{{ t(`game.world_journal.situations.kind.${situation.kind}`) }}</span>
            <span>{{ t('game.world_journal.situations.open_for', { count: situation.age_months }) }}</span>
          </div>
          <h4>{{ title(situation) }}</h4>
        </div>
      </header>

      <p class="situation__summary">{{ summary(situation) }}</p>

      <div v-if="situation.subjects.length" class="situation__subjects">
        <span>{{ t('game.world_journal.situations.involved') }}</span>
        <div>
          <button
            v-for="subject in situation.subjects.slice(0, 5)"
            :key="`${subject.kind}-${subject.id}`"
            type="button"
            @click="emit('subject', subject)"
          >
            {{ subject.name }}
          </button>
          <small v-if="situation.subjects.length > 5">
            +{{ situation.subjects.length - 5 }}
          </small>
        </div>
      </div>

      <section v-if="situation.latest_event" class="situation__fact">
        <div class="situation__section-label">
          <span>{{ t('game.world_journal.situations.latest_fact') }}</span>
          <time>{{ latestEventDate(situation) }}</time>
        </div>
        <p>{{ situation.latest_event.content || situation.latest_event.text }}</p>
      </section>

      <section v-if="situation.latest_response" class="situation__response">
        <div class="situation__section-label">
          <span>{{ t('game.world_journal.situations.latest_response') }}</span>
          <strong>{{ responseDecision(situation) }}</strong>
        </div>
        <p v-if="situation.latest_response.actor" class="situation__actor">
          {{ situation.latest_response.actor.name }}
        </p>
        <p>{{ situation.latest_response.reason }}</p>
        <ul v-if="situation.latest_response.rejected.length">
          <li v-for="rejected in situation.latest_response.rejected" :key="`${rejected.action_name}-${rejected.reason}`">
            <strong>{{ rejected.action_name }}</strong>
            <span>{{ rejected.reason }}</span>
          </li>
        </ul>
      </section>

      <footer class="situation__paths">
        <span>{{ t('game.world_journal.situations.paths') }}</span>
        <div>
          <button
            v-if="situation.primary_event_id"
            type="button"
            class="path-button"
            @click="emit('why', situation.primary_event_id)"
          >
            {{ t('game.world_journal.situations.understand') }}
          </button>
          <button
            v-for="subject in situation.subjects.slice(0, 2)"
            :key="`path-${subject.kind}-${subject.id}`"
            type="button"
            class="path-button"
            @click="emit('subject', subject)"
          >
            {{ t('game.world_journal.situations.open_subject', { name: subject.name }) }}
          </button>
          <button
            v-if="situation.direct_action === 'dao_petition'"
            type="button"
            class="path-button path-button--primary"
            @click="emit('dao')"
          >
            {{ t('game.world_journal.situations.answer_dao') }}
          </button>
        </div>
      </footer>
    </article>
  </section>
</template>

<style scoped>
.situations-view {
  min-width: 0;
  padding: var(--s-5);
  color: var(--text-secondary);
  font-family: var(--font-ui);
}

.situations-intro {
  padding-bottom: var(--s-5);
  border-bottom: 1px solid var(--rule);
}

.situations-intro > span,
.situation__section-label,
.situation__paths > span,
.situation__subjects > span {
  color: var(--text-muted);
  font-size: 10px;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
}

.situations-intro h3 {
  margin: var(--s-2) 0 var(--s-2);
  color: var(--text-primary);
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 500;
}

.situations-intro p,
.situations-state {
  margin: 0;
  color: var(--text-muted);
  font-size: var(--t-sm);
  line-height: 1.55;
}

.situations-state {
  padding: var(--s-7) 0;
  font-style: italic;
}

.situations-state--error {
  color: var(--state-alert);
}

.situation {
  --situation-color: var(--jade-400);
  position: relative;
  padding: var(--s-6) 0;
  border-bottom: 1px solid var(--rule);
}

.situation--major {
  --situation-color: var(--gold-400);
}

.situation--critical {
  --situation-color: var(--cinnabar-400);
}

.situation__header {
  display: grid;
  grid-template-columns: 3px minmax(0, 1fr);
  gap: var(--s-3);
}

.situation__marker {
  width: 3px;
  min-height: 42px;
  background: var(--situation-color);
}

.situation__meta {
  display: flex;
  justify-content: space-between;
  gap: var(--s-3);
  color: var(--situation-color);
  font-size: 10px;
  letter-spacing: var(--tracking-wide);
  text-transform: uppercase;
}

.situation h4 {
  margin: var(--s-2) 0 0;
  color: var(--text-primary);
  font-family: var(--font-display);
  font-size: 17px;
  font-weight: 500;
  line-height: 1.35;
}

.situation__summary {
  margin: var(--s-4) 0 0;
  color: var(--text-secondary);
  font-size: var(--t-md);
  line-height: 1.6;
}

.situation__subjects {
  margin-top: var(--s-4);
}

.situation__subjects > div,
.situation__paths > div {
  display: flex;
  flex-wrap: wrap;
  gap: var(--s-2);
  margin-top: var(--s-2);
}

.situation__subjects button {
  min-height: 28px;
  padding: 0 var(--s-3);
  border: 0;
  border-bottom: 1px solid var(--jade-600);
  background: transparent;
  color: var(--jade-300);
  font: inherit;
  font-size: var(--t-sm);
  cursor: pointer;
}

.situation__subjects small {
  align-self: center;
  color: var(--text-muted);
}

.situation__fact,
.situation__response {
  margin-top: var(--s-5);
  padding: var(--s-4) 0 var(--s-1) var(--s-4);
  border-left: 1px solid var(--rule-strong);
}

.situation__section-label {
  display: flex;
  justify-content: space-between;
  gap: var(--s-3);
}

.situation__section-label time,
.situation__section-label strong {
  color: var(--text-muted);
  font-family: var(--font-numeric);
  font-weight: 400;
}

.situation__fact p,
.situation__response p {
  margin: var(--s-2) 0 0;
  color: var(--text-primary);
  font-size: var(--t-sm);
  line-height: 1.55;
}

.situation__response .situation__actor {
  color: var(--jade-300);
  font-weight: 600;
}

.situation__response ul {
  margin: var(--s-3) 0 0;
  padding: 0;
  list-style: none;
}

.situation__response li {
  display: grid;
  gap: 2px;
  padding: var(--s-2) 0;
  color: var(--text-muted);
  font-size: var(--t-xs);
}

.situation__response li strong {
  color: var(--text-secondary);
  font-weight: 500;
}

.situation__paths {
  margin-top: var(--s-5);
}

.path-button {
  min-height: 34px;
  padding: 0 var(--s-3);
  border: 1px solid var(--rule-strong);
  border-radius: var(--r-1);
  background: transparent;
  color: var(--text-secondary);
  font: inherit;
  font-size: var(--t-sm);
  cursor: pointer;
}

.path-button:hover,
.situation__subjects button:hover {
  color: var(--text-primary);
  background: var(--surface-raised);
}

.path-button--primary {
  border-color: var(--gold-600);
  color: var(--accent-strong);
}

button:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring);
}

@media (max-width: 600px) {
  .situations-view {
    padding: var(--s-5);
  }

  .path-button,
  .situation__subjects button {
    min-height: 44px;
  }
}
</style>
