<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useWorldJournalStore } from '@/stores/worldJournal'
import { useWorldStore } from '@/stores/world'
import { useInstitutionalChain } from '@/composables/useInstitutionalChain'
import type { InstitutionalOwnerKindDTO } from '@/types/api'
const props = defineProps<{ ownerKind: InstitutionalOwnerKindDTO; ownerId: string | number | null | undefined }>()
const { t } = useI18n()
const journal = useWorldJournalStore()
const world = useWorldStore()
const { chain, loading, error, refresh, loadMoreCommitments, loadMoreEvents } = useInstitutionalChain(() => props.ownerKind, () => props.ownerId, () => world.lastWorldRevision)
const names = computed(() => new Map(chain.value?.institutions.map((item) => [item.id, item.name]) ?? []))
function institutionName(id: string) {
  return names.value.get(id) ?? t('game.institutional_chain.unknown_institution')
}
function actorInstitutionId(actorKind: string, actorId: string) {
  return actorKind === 'region' ? `inst:city:${actorId}` : `inst:${actorKind}:${actorId}`
}
function decisionActor(decision: { actor_kind: string; actor_id: string }) {
  return institutionName(actorInstitutionId(decision.actor_kind, decision.actor_id))
}
function why(id: string) { void journal.openCausalDetail(id) }
function amount(term: { parameters: Record<string, string | number | boolean | null> }) {
  const value = term.parameters.amount
  return typeof value === 'number' ? String(value) : '—'
}
function label(value: string) {
  return t(`game.institutional_chain.${value}`, value.replaceAll('_', ' '))
}
function controlScope(value: string) {
  return t(`game.institutional_chain.scope.${value}`, value)
}
function decisionAction(value: string) {
  return t(`game.institutional_chain.action.${value}`, value)
}
function resourceLabel(term: { subject: { id: string } }) {
  return t(`game.info_panel.region.economy.resources.${term.subject.id}`, term.subject.id)
}
function subject(term: { subject: { id: string } }) { return resourceLabel(term) }
function formatMonthStamp(monthStamp: number) {
  const year = Math.floor(monthStamp / 12)
  const month = (monthStamp % 12) + 1
  return t('game.institutional_chain.month', { month: `${year}A ${month}M` })
}
</script>
<template>
  <section class="institutional-chain" data-testid="institutional-chain">
    <header>
      <strong>{{ t('game.institutional_chain.title') }}</strong>
      <button type="button" @click="refresh">{{ t('game.institutional_chain.refresh') }}</button>
    </header>
    <p v-if="loading && !chain">{{ t('game.institutional_chain.loading') }}</p>
    <p v-else-if="error">{{ t('game.institutional_chain.error') }}</p>
    <template v-else-if="chain">
      <p class="owner">{{ chain.owner.name }} · {{ formatMonthStamp(chain.currentMonth) }}</p>
      <article v-for="commitment in chain.commitments" :key="commitment.id" class="commitment">
        <div class="commitment-header">
          <strong>{{ label(commitment.aggregate_status) }}</strong>
          <span>{{ institutionName(commitment.owner_institution_id) }} · {{ controlScope(commitment.control_scope) }}</span>
          <button type="button" @click="why(commitment.origin_event_id)">{{ t('game.world_journal.why_button') }}</button>
        </div>
        <div v-for="term in commitment.terms" :key="term.id" class="term">
          <strong>{{ institutionName(term.obligor_institution_id) }}</strong>
          <span aria-hidden="true">→</span>
          <strong>{{ institutionName(term.beneficiary_institution_id) }}</strong>
          <span>{{ label(term.kind) }} · {{ label(term.status) }}</span>
          <span v-if="term.due_month !== null">{{ t('game.institutional_chain.due') }} {{ formatMonthStamp(term.due_month) }}</span>
          <span v-if="term.kind === 'resource_transfer'">
            {{ t('game.institutional_chain.promised') }}: {{ amount(term) }} {{ subject(term) }} ·
            {{ t('game.institutional_chain.delivered') }}: {{ term.status === 'fulfilled' || term.status === 'remediated' ? amount(term) : '0' }} {{ subject(term) }}
          </span>
          <span v-if="term.breach_event_ids.length">
            {{ t('game.institutional_chain.breaches') }}:
            <button v-for="eventId in term.breach_event_ids" :key="eventId" type="button" @click="why(eventId)">{{ t('game.institutional_chain.evidence') }}</button>
          </span>
        </div>
      </article>
      <p v-if="!chain.commitments.length && !chain.events.length">{{ t('game.institutional_chain.empty') }}</p>
      <button v-if="chain.commitmentCursor.hasMore" type="button" :disabled="loading" @click="loadMoreCommitments">{{ t('game.institutional_chain.more_commitments') }}</button>
      <div class="timeline">
        <article v-for="event in chain.events" :key="event.event_id">
          <strong>{{ label(event.event_type) }}</strong>
          <p>{{ event.content }}</p>
          <p v-if="event.decision">
            {{ t('game.institutional_chain.decision') }}:
            {{ decisionActor(event.decision) }} · {{ decisionAction(event.decision.action) }} · {{ event.decision.reason }}
          </p>
          <button type="button" @click="why(event.event_id)">{{ t('game.world_journal.why_button') }}</button>
          <button v-for="source in event.source_event_ids" :key="source" type="button" @click="why(source)">{{ t('game.institutional_chain.evidence') }}</button>
        </article>
      </div>
      <button v-if="chain.eventCursor.hasMore" type="button" :disabled="loading" @click="loadMoreEvents">{{ t('game.institutional_chain.more_events') }}</button>
      <div v-for="memory in chain.memories" :key="memory.id" class="memory">
        {{ t('game.institutional_chain.relevance') }}: {{ institutionName(memory.institution_id) }} · {{ Math.round(memory.effective_salience * 100) }}%
        <button type="button" @click="why(memory.event_id)">{{ t('game.world_journal.why_button') }}</button>
      </div>
    </template>
  </section>
</template>
<style scoped>
.institutional-chain { display: grid; gap: 8px; padding: 10px; border: 1px solid var(--panel-border, rgba(175, 148, 105, .32)); border-radius: 6px; color: var(--panel-text-primary, #ccc); font-size: 14px; }
.institutional-chain header, .commitment-header, .term { display: flex; gap: 8px; align-items: center; justify-content: space-between; }
.owner { margin: 0; color: var(--panel-text-secondary, #9f9380); }
.commitment, .timeline article { display: grid; gap: 8px; padding: 10px; background: rgba(255, 255, 255, .03); border-radius: 4px; }
.term { align-items: flex-start; flex-wrap: wrap; }
.term span { color: var(--panel-text-secondary, #aaa); }
button { border: 0; background: transparent; color: var(--panel-accent, #d6b270); text-decoration: underline; cursor: pointer; padding: 2px 0; }
.timeline p { margin: 0; line-height: 1.4; }
</style>
