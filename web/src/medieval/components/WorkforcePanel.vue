<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { calendar, formatNumber as n } from '../mappers'
import { useWorkforce } from '../composables/useWorkforce'

const { t } = useI18n()
const { demandReports, offers, transitions, source } = useWorkforce()
</script>

<template>
  <section class="workforce-panel" aria-labelledby="workforce-title">
    <h2 id="workforce-title">{{ t('workforce') }}</h2>
    <p class="muted">{{ t('workforceHelp') }}</p>

    <h3>{{ t('workforceDemands') }}</h3>
    <p v-if="!demandReports.length" class="muted">{{ t('noWorkforceDemands') }}</p>
    <article v-for="item in demandReports" :key="item.report.id" class="stock-card" :data-workforce-demand="item.report.id">
      <h4>{{ item.location.siteName }} · {{ t('workforceKinds.' + item.report.work_kind) }}</h4>
      <dl>
        <dt>{{ t('sponsor') }}</dt><dd>{{ item.sponsorName }}</dd>
        <dt>{{ t('location') }}</dt><dd>{{ item.location.settlementName }}</dd>
        <dt>{{ t('targetOccupation') }}</dt><dd>{{ t('kinds.' + item.report.target_occupation) }}</dd>
        <dt>{{ t('workforcePeople') }}</dt><dd>{{ n(item.report.count) }}</dd>
        <dt>{{ t('stipend') }}</dt><dd>{{ n(item.report.stipend_per_person) }} {{ t('perPerson') }}</dd>
      </dl>
      <p class="muted">{{ t('observedOn') }}: {{ calendar(item.report.observed_day) }}</p>
      <button @click="source(item.report.source_event_id)">{{ t('why') }}</button>
    </article>

    <h3>{{ t('workforceOffers') }}</h3>
    <p v-if="!offers.length" class="muted">{{ t('noWorkforceOffers') }}</p>
    <article v-for="item in offers" :key="item.notice.id" class="stock-card" :data-workforce-offer="item.notice.id">
      <h4>{{ item.group ? `${item.group.people} · ${item.group.occupation}` : item.notice.source_group_id }}</h4>
      <dl>
        <dt>{{ t('location') }}</dt><dd>{{ item.settlement }}</dd>
        <dt>{{ t('sponsor') }}</dt><dd>{{ item.sponsorName }}</dd>
        <dt>{{ t('workforcePeople') }}</dt><dd>{{ n(item.notice.count) }}</dd>
        <dt>{{ t('targetOccupation') }}</dt><dd>{{ t('kinds.' + item.notice.target_occupation) }}</dd>
        <dt>{{ t('stipend') }}</dt><dd>{{ n(item.notice.stipend_per_person) }} {{ t('perPerson') }}</dd>
      </dl>
      <p class="muted">{{ t('observedOn') }}: {{ calendar(item.notice.observed_day) }}</p>
      <button @click="source(item.notice.event_id)">{{ t('why') }}</button>
    </article>

    <h3>{{ t('activeWorkforceTransitions') }}</h3>
    <p v-if="!transitions.length" class="muted">{{ t('noWorkforceTransitions') }}</p>
    <article v-for="item in transitions" :key="item.transition.id" class="stock-card" :data-workforce-transition="item.transition.id">
      <h4>{{ item.location.siteName }} · {{ t('workforceKinds.' + item.transition.work_kind) }}</h4>
      <dl>
        <dt>{{ t('workers') }}</dt><dd>{{ n(item.transition.count) }}</dd>
        <dt>{{ t('from') }}</dt><dd>{{ item.source?.people }} · {{ item.sourceSettlement }}</dd>
        <dt>{{ t('to') }}</dt><dd>{{ t('kinds.' + item.transition.target_occupation) }} · {{ item.location.settlementName }}</dd>
        <dt>{{ t('sponsor') }}</dt><dd>{{ item.sponsorName }}</dd>
        <dt>{{ t('workforceDue') }}</dt><dd>{{ calendar(item.transition.due_day) }}</dd>
      </dl>
      <button @click="source(item.transition.decision_event_id)">{{ t('why') }}</button>
    </article>
  </section>
</template>

<style scoped>
.workforce-panel h3 { margin-top: 1.25rem; }
.workforce-panel dl { display: grid; grid-template-columns: max-content 1fr; gap: .25rem .75rem; }
.workforce-panel dt { color: var(--muted, #aaa); }
.workforce-panel dd { margin: 0; text-align: right; }
</style>
