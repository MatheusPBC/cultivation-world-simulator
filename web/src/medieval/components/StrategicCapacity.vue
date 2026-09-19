<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useObserverStore } from '../stores/world'
import { entityName } from '../mappers'

const store = useObserverStore()
const {t} = useI18n()
const capacities = computed(() => store.snapshot?.governance.strategic_capacity ?? [])
const label = (key: string) => t(`strategicCapacityLabels.${key}`)
const statusLabel = (status: string) => t(`strategicCapacityStatuses.${status}`)
</script>

<template>
  <section v-if="capacities.length" class="panel strategic-capacity" aria-labelledby="strategic-capacity-title">
    <div class="section-heading"><div><p class="eyebrow">{{t('institutionalAgency')}}</p><h3 id="strategic-capacity-title">{{t('activeCapacities')}}</h3></div><span class="muted">{{t('derivedFromFacts')}}</span></div>
    <article v-for="item in capacities" :key="`${item.actor_ref.kind}:${item.actor_ref.id}`" class="capacity-actor">
      <h4>{{ entityName(store.snapshot!, item.actor_ref) }}</h4>
      <div class="capacity-grid">
        <div v-for="(dimension, key) in item.dimensions" :key="key" class="capacity-item">
          <span>{{ label(key) }}</span>
          <strong :data-status="dimension.status">{{ statusLabel(dimension.status) }}</strong>
          <small v-if="dimension.source_ids.length">{{ dimension.source_ids.length }} registro(s)</small>
        </div>
      </div>
    </article>
  </section>
</template>
