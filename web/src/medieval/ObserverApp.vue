<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useAppShell } from './composables/useAppShell'
import Controls from './components/Controls.vue'
import Atlas from './components/Atlas.vue'
import Inspector from './components/Inspector.vue'
import Chronicle from './components/Chronicle.vue'
import StrategicCapacity from './components/StrategicCapacity.vue'
import SavePanel from './components/SavePanel.vue'
import { formatNumber } from './mappers'
const { t } = useI18n()
const { store, scene, overlay, seed, count, replace, create } = useAppShell()
</script>

<template>
  <div class="observer-shell">
    <div v-if="store.error" role="alert" class="notice error">
      <span>{{ store.error.message }} <small>{{ store.error.code }}</small></span>
      <button @click="store.snapshot ? store.refresh() : store.boot()">{{ t('refresh') }}</button>
    </div>
    <div v-if="scene === 'boot'" class="boot-screen" role="status">{{ t('boot') }}</div>
    <template v-else>
      <header class="masthead">
        <div class="brand"><span class="brand-seal" aria-hidden="true">III</span><div><p class="eyebrow">{{ t('subtitle') }}</p><h1>{{ t('title') }}</h1></div></div>
        <div class="masthead-right"><span class="edition">{{ t('construction') }}</span>
          <button data-testid="open-saves" @click="overlay = 'saves'">{{ t('saves') }}</button>
          <button v-if="scene === 'game'" :disabled="!store.status?.paused || store.busy" @click="overlay = 'create'">{{ t('newWorld') }}</button>
        </div>
      </header>
      <main v-if="scene === 'splash'" class="splash">
        <section class="intro"><p class="eyebrow">{{ t('observatory') }}</p><h2>{{ t('tagline') }}</h2><p>{{ t('description') }}</p>
          <div class="world-facts"><span>3 <small>{{ t('governments') }}</small></span><span>8 <small>{{ t('settlements') }}</small></span><span>10.900 <small>{{ t('inhabitants') }}</small></span></div>
          <p class="muted">{{ t('notYet') }}</p>
        </section>
      </main>
      <template v-if="scene === 'game' && store.snapshot">
        <Controls />
        <main class="observatory-grid">
          <section class="atlas-column">
            <div class="section-heading"><div><p class="eyebrow">{{ t('map') }}</p><h2>{{ store.snapshot.map.name }}</h2></div><span class="muted">{{ t('observatory') }}</span></div>
            <Atlas />
            <div class="world-strip"><span><strong>{{ formatNumber(store.snapshot.world.population) }}</strong> {{ t('inhabitants') }}</span><span><strong>{{ store.snapshot.world.living_characters }}</strong> {{ t('people') }}</span><span><strong>{{ store.snapshot.world.events }}</strong> {{ t('totalEvents') }}</span></div>
            <div class="decision-strip" :aria-label="t('decisionTrace')">
              <span><strong>{{ store.snapshot.world.decision_sources.provider_consultations }}</strong> {{ t('providerConsultations') }}</span>
              <span><strong>{{ store.snapshot.world.decision_sources.provider_declines }}</strong> {{ t('providerDeclines') }}</span>
              <span><strong>{{ store.snapshot.world.decision_sources.provider_failures }}</strong> {{ t('providerFailures') }}</span>
              <span><strong>{{ store.snapshot.world.decision_sources.no_affordance_receipts }}</strong> {{ t('noAffordance') }}</span>
              <span><strong>{{ store.snapshot.world.decision_sources.stale_affordance_receipts }}</strong> {{ t('staleAffordance') }}</span>
            </div>
            <StrategicCapacity />
            <Chronicle />
          </section>
          <Inspector />
        </main>
      </template>
      <section v-if="scene === 'splash' || overlay === 'create'" :class="overlay === 'create' ? 'create-overlay' : 'create-card'" :aria-label="t('create')">
        <form data-testid="create-world" @submit.prevent="create">
          <p class="eyebrow">{{ t('newWorld') }}</p><h2>{{ t('create') }}</h2>
          <label>{{ t('seed') }}<input v-model.number="seed" name="seed" type="number" min="0" max="4294967295" required /></label>
          <label>{{ t('characters') }}<input v-model.number="count" name="character_count" type="number" min="1" max="60" required /></label>
          <p class="muted">{{ t('populationHelp') }}</p>
          <p class="policy-label">{{ t('policy') }}</p><p class="muted">{{ t('aiPending') }}</p>
          <label v-if="store.snapshot" class="check"><input v-model="replace" type="checkbox" required />{{ t('replace') }}</label>
          <button class="primary" :disabled="store.busy">{{ store.busy ? t('working') : t('create') }}</button>
          <button v-if="overlay" type="button" @click="overlay = null">{{ t('cancel') }}</button>
        </form>
      </section>
      <SavePanel v-if="overlay === 'saves'" @close="overlay = null" />
      <footer class="app-footer"><span>{{ t('factsOnly') }}</span><span>{{ t('hybrid') }}</span></footer>
    </template>
  </div>
</template>
