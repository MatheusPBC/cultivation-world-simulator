<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useMigration } from '../composables/useMigration'
import { calendar, formatNumber as n } from '../mappers'
const { t } = useI18n()
const { migrations, source } = useMigration()
const label = (key: string) => t('kinds.' + key)
</script>
<template>
  <section aria-labelledby="migration-title">
    <h2 id="migration-title">{{ t('migrations') }}</h2>
    <p v-if="!migrations.length" class="muted">{{ t('noMigrations') }}</p>
    <article v-for="item in migrations" :key="item.journey.id" class="stock-card" :data-migration="item.journey.id">
      <h3>{{ item.returnLabel }}</h3>
      <p>{{ n(item.journey.count) }} {{ t('migrants') }} · {{ label(item.group.people) }} · {{ label(item.group.occupation) }}</p>
      <p v-if="item.people.length" class="muted">{{ item.people.join(', ') }}</p>
      <dl>
        <dt>{{ t('migrationStage') }}</dt><dd>{{ t('migrationStages.' + item.journey.stage) }}</dd>
        <dt>{{ t('migrationRoute') }}</dt><dd>{{ item.routeId }}</dd>
        <dt>{{ t('migrationDue') }}</dt><dd>{{ calendar(item.journey.due_day) }}</dd>
        <dt>{{ t('migrationFood') }}</dt><dd>{{ n(item.provision.food) }} · {{ t('missing') }}: {{ n(item.provision.missing_food) }}</dd>
        <dt>{{ t('health') }}</dt><dd>{{ n(item.provision.health / 10) }}%</dd>
        <dt>{{ t('migrationBalance') }}</dt><dd>{{ n(item.balance) }} <small>({{ item.provision.account_id }})</small></dd>
      </dl>
      <button @click="source(item.journey.last_event_id)">{{ t('source') }}</button>
      <button class="text-button" @click="source(item.journey.decision_event_id)">{{ t('why') }}</button>
    </article>
  </section>
</template>
