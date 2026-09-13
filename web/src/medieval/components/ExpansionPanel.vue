<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useObserverStore } from '../stores/world'
import { formatNumber as n } from '../mappers'
const { t } = useI18n()
const store = useObserverStore()
const projects = computed(() => {
  const data = store.snapshot!
  return data.economy.expansions.map(p => {
    const facility = data.economy.facilities.find(f => f.id === p.facility_id)!
    const blueprint = data.economy.expansion_blueprints.find(b => b.id === p.blueprint_id)!
    const previous = data.economy.recipes.find(r => r.id === blueprint.from_recipe_id)
    const next = data.economy.recipes.find(r => r.id === (blueprint.additional_recipe_id ?? blueprint.to_recipe_id))
    const line = data.economy.facilities.find(f => f.id === `line:${facility.site_id}:${blueprint.additional_recipe_id}`)
    const yields = next ? Object.entries(next.outputs).map(([id, amount]) => ({ id,
      name: data.economy.resources.find(r => r.id === id)?.name ?? id, before: previous?.outputs[id] ?? 0, after: amount })) : []
    const blocker = p.blocker?.startsWith('input:')
      ? t('missingMaterial') + ': ' + (data.economy.resources.find(r => r.id === p.blocker!.slice(6))?.name ?? p.blocker.slice(6))
      : p.blocker ? t('expansionBlockers.' + p.blocker) : null
    return { ...p, blueprint, facility, line, blocker, yields, name: data.map.sites.find(s => s.id === facility.site_id)?.name ?? facility.id }
  })
})
</script>
<template>
  <section aria-labelledby="expansion-title">
    <h3 id="expansion-title">{{ t('expansionTitle') }}</h3>
    <p class="muted">{{ t('expansionHelp') }}</p>
    <p v-if="!projects.length" class="muted">{{ t('noExpansions') }}</p>
    <article v-for="p in projects" :key="p.id" :data-expansion="p.id" class="stock-card">
      <h4>{{ p.name }}</h4><p>{{ p.blueprint.name }} · {{ t('expansionStages.' + p.stage) }}</p>
      <p>{{ t('workProgress') }}: {{ n(p.completed_units) }} / {{ n(p.blueprint.required_units) }}</p>
      <progress :value="p.completed_units" :max="p.blueprint.required_units" :aria-label="t('workProgress') + ' · ' + p.name" />
      <dl v-if="p.blueprint.additional_recipe_id"><dt>{{ t('newLineCapacity') }}</dt><dd>{{ n(p.line?.max_batches ?? 0) }} {{ t('batches') }}</dd>
        <template v-if="p.stage !== 'completed'"><dt>{{ t('plannedCapacity') }}</dt><dd>{{ n(p.blueprint.new_capacity!) }} {{ t('batches') }}</dd></template></dl>
      <dl v-else><dt>{{ t('capacity') }}</dt><dd>{{ n(p.facility.max_batches) }} {{ t('batches') }}</dd>
        <template v-if="p.blueprint.capacity_gain"><dt>{{ t(p.stage === 'completed' ? 'capacityGainApplied' : 'completionGain') }}</dt><dd>+{{ n(p.blueprint.capacity_gain) }} {{ t('batches') }}</dd></template></dl>
      <template v-if="p.yields.length"><p>{{ t(p.blueprint.additional_recipe_id ? 'newLineOutput' : p.stage === 'completed' ? 'recipeApplied' : 'recipePending') }}</p>
        <p v-for="y in p.yields" :key="y.id">{{ y.name }}: <template v-if="!p.blueprint.additional_recipe_id">{{ n(y.before) }} → </template>{{ n(y.after) }}{{ p.blueprint.additional_recipe_id ? ' ' + t('perBatch') : '' }}</p></template>
      <p v-if="p.blocker" class="notice warning">{{ p.blocker }}</p>
      <p class="muted">{{ t('lastReview') }}: {{ p.last_work_day ?? p.started_day }}</p>
      <button @click="store.focusEventId = p.last_event_id">{{ t('source') }}</button>
    </article>
  </section>
</template>
