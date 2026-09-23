<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useIncome } from '../composables/useIncome'
import { formatNumber as n } from '../mappers'
import ExpansionPanel from './ExpansionPanel.vue'
const { t } = useI18n()
const { savings, totalSavings, payrolls, employmentContracts, policies, source } = useIncome()
</script>
<template>
  <section aria-labelledby="income-title">
    <h2 id="income-title">{{ t('finances') }}</h2>
    <p class="muted">{{ t('incomeHelp') }}</p>
    <ExpansionPanel />
    <h3>{{ t('householdSavings') }}</h3>
    <p class="population-number" data-testid="household-savings">{{ n(totalSavings) }}</p>
    <details><summary>{{ t('bySettlement') }}</summary>
      <p class="muted">{{ t('incomeAccessHelp') }}</p>
      <article v-for="s in savings" :key="s.id" class="stock-card" :data-income-settlement="s.id">
        <h4>{{ s.name }}</h4>
        <dl><dt>{{ t('householdSavings') }}</dt><dd>{{ n(s.balance) }}</dd>
          <dt>{{ t('artisanPeople') }}</dt><dd>{{ n(s.artisanPeople) }}</dd>
          <dt>{{ t('artisanSavings') }}</dt><dd data-testid="artisan-savings">{{ n(s.artisanCash) }}</dd>
          <dt>{{ t('localFoodStock') }}</dt><dd data-testid="local-food-stock">{{ n(s.food) }}</dd>
          <dt>{{ t('missing') }}</dt><dd>{{ n(s.missingFood) }}</dd>
          <dt>{{ t('health') }}</dt><dd>{{ n(s.health) }} / 1.000</dd></dl>
        <button v-if="s.foodSourceId" @click="source(s.foodSourceId)">{{ t('source') }} · {{ t('localFoodStock') }}</button>
        <button v-if="s.needSourceId" @click="source(s.needSourceId)">{{ t('source') }} · {{ t('lastSubsistence') }}</button>
        <details v-if="s.artisanGroups.length"><summary>{{ t('artisanGroups') }}</summary>
          <div v-for="group in s.artisanGroups" :key="group.id" class="stock-card">
            <p>{{ t('kinds.' + group.people) }} · {{ n(group.count) }} {{ t('workers') }}</p>
            <p>{{ t('householdSavings') }}: {{ n(group.balance) }}</p>
            <button v-if="group.sourceId" data-testid="artisan-source" @click="source(group.sourceId)">{{ t('source') }}</button>
          </div>
        </details>
      </article>
    </details>
    <h3>{{ t('payrolls') }}</h3>
    <p v-if="!payrolls.length" class="muted">{{ t('noPayrolls') }}</p>
    <article v-for="p in payrolls" :key="p.id" class="stock-card" :data-payroll="p.id">
      <h4>{{ p.construction ? t('constructionWork') + ' · ' : p.research ? t('research') + ' · ' : '' }}{{ p.name }}</h4>
      <p v-if="p.products">{{ p.products }}</p><p class="muted">{{ t('absoluteDay') }} {{ p.day }}</p>
      <dl><dt>{{ t('paidWorkers') }}</dt><dd>{{ n(p.workers) }}</dd>
        <dt>{{ t('grossWages') }}</dt><dd data-testid="gross">{{ n(p.gross) }}</dd>
        <dt>{{ t('incomeTax') }}</dt><dd data-testid="tax">{{ n(p.tax) }}</dd>
        <dt>{{ t('netWages') }}</dt><dd data-testid="net">{{ n(p.net) }}</dd></dl>
      <button @click="source(p.last_event_id)">{{ t('source') }}</button>
    </article>
    <h3>{{ t('employmentContracts') }}</h3>
    <p v-if="!employmentContracts.length" class="muted">{{ t('noEmploymentContracts') }}</p>
    <article v-for="contract in employmentContracts" :key="contract.id" class="stock-card" :data-employment="contract.id">
      <h4>{{ contract.employer }} · {{ contract.cohort?.id ?? contract.cohort_id }}</h4>
      <p class="muted">{{ contract.workSite }} · {{ contract.workforce_limit }} {{ t('workers') }} · {{ n(contract.wage_per_worker) }} / {{ t('perPerson') }}</p>
      <p>{{ t('employmentOutcomes.' + contract.last_outcome) }}</p>
      <button @click="source(contract.last_event_id)">{{ t('source') }}</button>
    </article>
    <h3>{{ t('taxPolicies') }}</h3><p class="muted">{{ t('taxPoliciesHelp') }}</p>
    <article v-for="p in policies" :key="p.id" class="stock-card">
      <h4>{{ p.name }}</h4><p>{{ t('incomeTax') }}: {{ n(p.income_rate / 10) }}%</p>
      <p>{{ t('exportRate') }}: {{ n(p.export_rate_permille / 10) }}%</p>
      <p class="muted">{{ t('exportRateSource') }}: {{ p.export_policy_event_id ?? '—' }}</p>
      <button v-if="p.export_policy_event_id" data-testid="export-policy-source" @click="source(p.export_policy_event_id)">{{ t('source') }} · {{ t('exportRate') }}</button>
      <button v-if="p.last_event_id" @click="source(p.last_event_id)">{{ t('source') }}</button>
    </article>
  </section>
</template>
