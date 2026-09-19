<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useSupplyPlans } from '../composables/useSupplyPlans'
import { formatNumber as n, calendar } from '../mappers'
const { t } = useI18n()
const { plans, source } = useSupplyPlans()
</script>
<template>
  <section aria-labelledby="supply-plans-title">
    <h3 id="supply-plans-title">{{ t('supplyPlans') }}</h3>
    <p class="muted">{{ t('supplyPlansHelp') }}</p>
    <article v-for="item in plans" :key="item.objective.id" class="stock-card" :data-plan="item.plan?.id">
      <h4>{{ item.settlement.name }} · {{ item.owner }}</h4>
      <p><strong>{{ item.resource.name }}</strong> · {{ t('objectiveKinds.' + item.objective.kind) }}</p>
      <p class="muted">{{ item.stockId }} · {{ item.resource.unit }}</p>
      <p>{{ t('planStages.' + (item.plan?.stage ?? 'unreviewed')) }}</p>
      <dl><dt>{{ t('reserveTarget') }}</dt><dd>{{ n(item.target) }}</dd>
        <dt>{{ t('storedResource') }}</dt><dd>{{ n(item.stored) }}</dd>
        <dt>{{ t('inTransitResource') }}</dt><dd>{{ n(item.transit) }}</dd></dl>
      <p v-if="item.plan?.blocker" class="notice warning">{{ item.plan.blocker }}</p>
      <p v-if="item.plan" class="muted">{{ t('lastReview') }}: {{ item.plan.last_review_day }}</p>
      <button v-if="item.plan" @click="source(item.plan.last_event_id)">{{ t('source') }}</button>
      <details v-if="item.orders.length" class="supply-orders">
        <summary>{{ t('plannedOrders') }} ({{ item.orders.length }})</summary>
        <article v-for="order in item.orders" :key="order.order.id" class="stock-card" :data-order="order.order.id">
          <h4>{{ order.sourceName }} → {{ order.destinationName }}</h4>
          <p>{{ n(order.order.quantity) }} {{ item.resource.unit }} · {{ t('orderCreatedOn') }} {{ calendar(order.order.created_day) }}</p>
          <button v-if="order.firstDecisionId" class="text-button" @click="source(order.firstDecisionId)">{{ t('why') }}</button>
          <div v-if="order.routeSegments.length" class="route-segments">
            <p class="muted">{{ t('plannedRoute') }}</p>
            <div v-for="segment in order.routeSegments" :key="segment.id" class="route-segment" :data-route-segment="segment.id">
              <strong>{{ segment.name }}</strong>
              <details v-if="segment.reports.length">
                <summary>{{ t('knownRouteReports') }} ({{ segment.reports.length }})</summary>
                <p v-for="report in segment.reports" :key="report.id" class="muted">
                  {{ t('observedOn') }} {{ report.observedOn }} · {{ t('observedCapacity') }} {{ n(report.operational_capacity) }} {{ t('bulkDay') }} · {{ t('observedTraffic') }} {{ n(report.daily_flow_bulk ?? 0) }} {{ t('bulkDay') }} · {{ report.travel_days !== null ? `${report.travel_days} ${t('days')}` : t('impassable') }}
                </p>
              </details>
              <p v-else class="muted">{{ t('noKnownRouteReport') }}</p>
            </div>
          </div>
        </article>
      </details>
      <details v-if="item.reports.length">
        <summary>{{ t('knownOffers') }} ({{ item.reports.length }})</summary>
        <p class="muted">{{ t('knownOffersHelp') }}</p>
        <div v-for="report in item.reports" :key="report.id" class="stock-card">
          <p>{{ report.publisherName }} · {{ n(report.quantity) }} · {{ item.resource.unit }}</p>
          <p>{{ t('price') }}: {{ report.unit_price }} · {{ t('absoluteDay') }} {{ report.observed_day }}</p>
          <button @click="source(report.event_id)">{{ t('source') }}</button>
        </div>
      </details>
    </article>
  </section>
</template>
