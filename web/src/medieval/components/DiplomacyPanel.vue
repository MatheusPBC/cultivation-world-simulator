<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useDiplomacy } from '../composables/useDiplomacy'
import { calendar, formatNumber } from '../mappers'
const { t } = useI18n()
const { proposals, source } = useDiplomacy()
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
          <strong v-else>{{ t('teachingTerm', { technology: term.technology }) }}</strong>
          <p>{{ term.debtor }} → {{ term.creditor }}</p>
          <p class="muted">{{ t('fulfillmentDue') }}: {{ calendar(term.clause.due_day) }}</p>
          <p v-if="term.clause.depends_on.length" class="muted">{{ t('dependsOnTerms') }}: {{ term.clause.depends_on.map(i => i + 1).join(', ') }}</p>
          <p>{{ term.obligation ? t('obligationStatuses.' + term.obligation.status) : t('noBoundObligation') }}</p>
          <template v-if="term.obligation">
            <div class="diplomacy-actions">
              <button @click="source(term.obligation.last_event_id)">{{ t('obligationEvidence') }}</button>
              <button v-if="term.obligation.material_event_id" @click="source(term.obligation.material_event_id)">{{ t('materialEvidence') }}</button>
            </div>
            <p class="muted">{{ t('informedOfStatus') }}: {{ term.informed.map(n => n.name).join(', ') || t('noNotice') }}</p>
          </template>
        </li>
      </ol>
    </article>
  </section>
</template>

<style scoped>
.diplomacy-actions { display: flex; flex-wrap: wrap; gap: .5rem; }
.diplomacy-terms { padding-inline-start: 1.25rem; }
.diplomacy-terms li { margin-block: 1rem; padding-inline-start: .25rem; }
</style>
