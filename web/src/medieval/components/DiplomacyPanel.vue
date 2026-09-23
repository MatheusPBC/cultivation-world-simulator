<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useDiplomacy } from '../composables/useDiplomacy'
import { calendar, formatNumber } from '../mappers'
const { t } = useI18n()
const { proposals, aidTrail, memories, readings, strategicEvidence, source } = useDiplomacy()
</script>

<template>
  <section aria-labelledby="diplomacy-title">
    <h2 id="diplomacy-title">{{ t('diplomacy') }}</h2>
    <p class="muted">{{ t('diplomacyHelp') }}</p>
    <p v-if="!proposals.length" class="muted">{{ t('noDiplomacy') }}</p>
    <article v-for="p in proposals" :key="p.id" :data-proposal="p.id" class="stock-card">
      <h3>{{ p.proposer }} → {{ p.counterparty }}</h3>
      <p>{{ t('proposalStatuses.' + p.status) }}</p>
      <p class="muted">{{ t('offeredOn') }}: {{ calendar(p.offered_day) }}<br>
        {{ t('offerExpires') }}: {{ calendar(p.expires_day) }}</p>
      <button v-if="p.parentEventId" class="text-button" @click="source(p.parentEventId)">{{ t('previousOffer') }}</button>
      <div class="diplomacy-actions">
        <button @click="source(p.decision_event_id)">{{ t('proposalDecision') }}</button>
        <button @click="source(p.last_event_id)">{{ t('source') }}</button>
      </div>
      <p class="muted">{{ t('informedOfStatus') }}: {{ p.informed.map(n => n.name).join(', ') || t('noNotice') }}</p>
      <ol class="diplomacy-terms">
        <li v-for="term in p.terms" :key="term.number" :data-term="`${p.id}:${term.number}`">
          <strong v-if="term.clause.kind === 'payment'">{{ t('paymentTerm', { amount: formatNumber(term.clause.amount) }) }}</strong>
          <strong v-else-if="term.clause.kind === 'resource_transfer'">{{ t('resourceTransferTerm', { quantity: formatNumber(term.clause.quantity), resource: term.resource }) }}</strong>
          <strong v-else-if="term.clause.kind === 'teaching'">{{ t('teachingTerm', { technology: term.technology }) }}</strong>
          <strong v-else-if="term.clause.kind === 'withdrawal'">{{ t('withdrawalTerm', { detachment: term.clause.detachment_id }) }}</strong>
          <strong v-else-if="term.clause.kind === 'campaign_withdrawal'">{{ t('campaignWithdrawalTerm', { campaign: term.clause.campaign_id, detachment: term.clause.detachment_id }) }}</strong>
          <strong v-else>{{ t('administrationTransferTerm', { settlement: term.clause.settlement_id }) }}</strong>
          <p>{{ term.debtor }} → {{ term.creditor }}</p>
          <p class="muted">{{ t('fulfillmentDue') }}: {{ calendar(term.clause.due_day) }}</p>
          <p v-if="term.clause.depends_on.length" class="muted">{{ t('dependsOnTerms') }}: {{ term.clause.depends_on.map(i => i + 1).join(', ') }}</p>
          <p>{{ term.obligation ? t('obligationStatuses.' + term.obligation.status) : t('noBoundObligation') }}</p>
          <template v-if="term.obligation">
            <div class="diplomacy-actions">
              <button @click="source(term.obligation.last_event_id)">{{ t('obligationEvidence') }}</button>
              <button v-if="term.obligation.material_event_id" @click="source(term.obligation.material_event_id)">{{ t('materialEvidence') }}</button>
              <button v-if="term.obligation.breach_event_id" @click="source(term.obligation.breach_event_id)">{{ t('breachEvidence') }}</button>
              <button v-if="term.obligation.remediation_material_event_id" @click="source(term.obligation.remediation_material_event_id)">{{ t('remediationEvidence') }}</button>
            </div>
            <p class="muted">{{ t('informedOfStatus') }}: {{ term.informed.map(n => n.name).join(', ') || t('noNotice') }}</p>
          </template>
        </li>
      </ol>
    </article>

    <h3 id="aid-trail-title">{{ t('aidTrail') }}</h3>
    <p class="muted">{{ t('aidTrailHelp') }}</p>
    <p v-if="!aidTrail.length" class="muted">{{ t('noAidTrail') }}</p>
    <ul v-else class="diplomacy-trail">
      <li v-for="notice in aidTrail" :key="notice.id" :data-aid-notice="notice.id">
        <strong>{{ notice.kind === 'request' ? t('aidRequested') : t('aidAnswered.' + notice.response_status) }}</strong>
        <p>{{ notice.requester }} → {{ notice.recipient }}</p>
        <p class="muted">{{ t('aidRequestedFood', { quantity: formatNumber(notice.requested_food) }) }}<br>
          {{ t('learnedOn') }}: {{ calendar(notice.learned_day) }}</p>
        <div class="diplomacy-actions">
          <button @click="source(notice.request_event_id)">{{ t('aidRequestEvidence') }}</button>
          <button v-if="notice.event_id !== notice.request_event_id" @click="source(notice.event_id)">{{ t('source') }}</button>
        </div>
      </li>
    </ul>

    <h3 id="memory-title">{{ t('rememberedFacts') }}</h3>
    <p class="muted">{{ t('rememberedFactsHelp') }}</p>
    <p v-if="!memories.length" class="muted">{{ t('noRememberedFacts') }}</p>
    <ul v-else class="diplomacy-trail">
      <li v-for="memory in memories" :key="memory.id" :data-memory="memory.id">
        <strong>{{ memory.institution }}</strong>
        <p class="muted">{{ t('memoryKinds.' + (memory.kind ?? 'unknown')) }}<br>
          {{ t('recordedOn') }}: {{ calendar(memory.recorded_day) }}<br>
          {{ t('reinforcedOn') }}: {{ calendar(memory.last_reinforced_day) }}<br>
          {{ t('effectiveSalience') }}: {{ formatNumber(memory.effective_salience) }}</p>
        <button @click="source(memory.event_id)">{{ t('rememberedEvidence') }}</button>
      </li>
    </ul>

    <h3 id="reading-title">{{ t('institutionalReading') }}</h3>
    <p class="muted">{{ t('institutionalReadingHelp') }}</p>
    <p v-if="!readings.length" class="muted">{{ t('noInstitutionalReading') }}</p>
    <ul v-else class="diplomacy-trail">
      <li v-for="reading in readings" :key="`${reading.observer_ref.id}:${reading.subject_ref.id}`"
          :data-reading="`${reading.observer_ref.id}:${reading.subject_ref.id}`">
        <strong>{{ t('readingOf', { observer: reading.observer, subject: reading.subject }) }}: {{ formatNumber(reading.value) }}</strong>
        <div class="diplomacy-actions">
          <button v-for="eventId in reading.evidence_event_ids" :key="eventId" @click="source(eventId)">{{ t('readingEvidence') }}</button>
        </div>
      </li>
    </ul>

    <h3 id="evidence-title">{{ t('strategicEvidence') }}</h3>
    <p class="muted">{{ t('strategicEvidenceHelp') }}</p>
    <p v-if="!strategicEvidence.length" class="muted">{{ t('noStrategicEvidence') }}</p>
    <ul v-else class="diplomacy-trail">
      <li v-for="item in strategicEvidence" :key="item.finding_id || item.notice_id" :data-finding="item.finding_id || item.notice_id">
        <strong>{{ t('strategicEvidenceKinds.' + item.kind) }} · {{ item.result }}</strong>
        <p class="muted">{{ t('recipient') }}: {{ item.recipient }}<br>{{ t('recordedOn') }}: {{ item.event_id }}</p>
        <button @click="source(item.event_id)">{{ t('source') }}</button>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.diplomacy-actions { display: flex; flex-wrap: wrap; gap: .5rem; }
.diplomacy-terms { padding-inline-start: 1.25rem; }
.diplomacy-terms li { margin-block: 1rem; padding-inline-start: .25rem; }
.diplomacy-trail { list-style: none; margin: 0; padding: 0; }
.diplomacy-trail li { margin-block: .75rem; }
</style>
