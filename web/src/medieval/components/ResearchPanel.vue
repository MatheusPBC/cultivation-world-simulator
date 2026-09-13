<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useResearch } from '../composables/useResearch'
import { formatNumber as n, calendar } from '../mappers'
const { t } = useI18n()
const { projects, knowledge, catalog, source } = useResearch()
</script>
<template>
  <section aria-labelledby="research-title">
    <h2 id="research-title">{{ t('research') }}</h2>
    <p class="muted">{{ t('researchHelp') }}</p>
    <p v-if="!projects.length" class="muted">{{ t('noResearch') }}</p>
    <article v-for="p in projects" :key="p.id" :data-research="p.id" class="stock-card">
      <h3>{{ p.technology.name }}</h3><p>{{ p.owner }} · {{ p.site }}</p>
      <p>{{ t('researcher') }}: {{ p.researcher }}</p>
      <p>{{ t('researchStages.' + p.stage) }} · {{ n(p.completed_units) }} / {{ n(p.technology.required_units) }}</p>
      <progress :value="p.completed_units" :max="p.technology.required_units" :aria-label="t('workProgress') + ' · ' + p.technology.name" />
      <p v-if="p.blocker" class="notice warning">{{ p.blocker }}</p>
      <p class="muted">{{ calendar(p.last_work_day ?? p.started_day) }}</p>
      <button @click="source(p.last_event_id)">{{ t('source') }}</button>
    </article>
    <h3>{{ t('technicalKnowledge') }}</h3><p class="muted">{{ t('knowledgeHelp') }}</p>
    <p v-if="!knowledge.length" class="muted">{{ t('noKnowledge') }}</p>
    <article v-for="k in knowledge" :key="k.id" :data-knowledge="k.id" class="stock-card">
      <h4>{{ k.technology.name }}</h4><p>{{ k.owner }} · {{ t('knowledgeChannels.' + k.channel) }}</p>
      <p class="muted">{{ calendar(k.learned_day) }}</p><button @click="source(k.event_id)">{{ t('source') }}</button>
    </article>
    <details><summary>{{ t('researchCatalog') }}</summary><p class="muted">{{ t('catalogHelp') }}</p>
      <article v-for="tech in catalog" :key="tech.id" class="stock-card"><h4>{{ tech.name }}</h4>
        <p>{{ t('prerequisites') }}: {{ tech.requirements || t('none') }}</p>
        <p>{{ t('skills') }}: {{ t('kinds.' + tech.skill) }} ≥ {{ tech.min_skill }}</p>
      </article>
    </details>
  </section>
</template>
