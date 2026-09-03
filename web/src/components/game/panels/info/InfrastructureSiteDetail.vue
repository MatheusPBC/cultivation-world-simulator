<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { InfrastructureSiteDetail } from '@/types/core'
import { useWorldJournalStore } from '@/stores/worldJournal'
import { useUiStore } from '@/stores/ui'

const props = defineProps<{ data: InfrastructureSiteDetail }>()
const { t } = useI18n()
const journalStore = useWorldJournalStore()
const uiStore = useUiStore()
const owner = computed(() => props.data.ownerRef)
const maintainer = computed(() => props.data.maintainerRef)
const statusLabel = computed(() => t(`game.info_panel.infrastructure_site.status_values.${props.data.status}`))

function openCausalDetail(eventId: string) {
  void journalStore.openCausalDetail(eventId)
}

function openRouteDetail(routeId: string) {
  void uiStore.select('route', routeId)
}
</script>

<template>
  <div class="infrastructure-site-detail">
    <section class="section">
      <div class="section-title">{{ t('game.info_panel.infrastructure_site.title') }}</div>
      <div class="kv"><span>{{ t('game.info_panel.infrastructure_site.kind') }}</span><strong>{{ data.kind }}</strong></div>
      <div class="kv"><span>{{ t('game.info_panel.infrastructure_site.status') }}</span><strong>{{ statusLabel }}</strong></div>
      <div class="kv"><span>{{ t('game.info_panel.infrastructure_site.integrity') }}</span><strong>{{ Math.round(data.integrity * 100) }}%</strong></div>
      <div class="kv"><span>{{ t('game.info_panel.infrastructure_site.location') }}</span><strong>({{ data.x }}, {{ data.y }})</strong></div>
      <div class="kv"><span>{{ t('game.info_panel.infrastructure_site.enabled') }}</span><strong>{{ data.enabled ? t('common.yes') : t('common.no') }}</strong></div>
    </section>

    <section class="section">
      <div class="section-title">{{ t('game.info_panel.infrastructure_site.references') }}</div>
      <div class="kv"><span>{{ t('game.info_panel.infrastructure_site.regions') }}</span><strong>{{ data.regionIds.join(', ') }}</strong></div>
      <div class="kv">
        <span>{{ t('game.info_panel.infrastructure_site.routes') }}</span>
        <span v-if="data.routeIds.length" class="route-references">
          <button
            v-for="routeId in data.routeIds"
            :key="routeId"
            type="button"
            class="route-link"
            :data-testid="`infrastructure-site-route-${routeId}`"
            @click="openRouteDetail(routeId)"
          >
            {{ routeId }}
          </button>
        </span>
        <strong v-else>{{ t('common.none') }}</strong>
      </div>
      <div class="kv"><span>{{ t('game.info_panel.infrastructure_site.capabilities') }}</span><strong>{{ data.capabilityIds.join(', ') || t('common.none') }}</strong></div>
      <div v-if="owner" class="kv"><span>{{ t('game.info_panel.infrastructure_site.owner') }}</span><strong>{{ owner.kind }}: {{ owner.id }}</strong></div>
      <div v-if="maintainer" class="kv"><span>{{ t('game.info_panel.infrastructure_site.maintainer') }}</span><strong>{{ maintainer.kind }}: {{ maintainer.id }}</strong></div>
      <div v-if="data.lastEventId" class="kv">
        <span>{{ t('game.info_panel.infrastructure_site.last_event') }}</span>
        <span class="event-reference">
          <strong>{{ data.lastEventId }}</strong>
          <button
            type="button"
            data-testid="infrastructure-site-open-why"
            @click="openCausalDetail(data.lastEventId)"
          >
            {{ t('game.world_journal.why_button') }}
          </button>
        </span>
      </div>
    </section>
  </div>
</template>

<style scoped>
.infrastructure-site-detail { display: flex; flex-direction: column; gap: 14px; overflow: auto; min-height: 0; padding-right: 4px; }
.section { display: flex; flex-direction: column; gap: 8px; }
.section-title { color: var(--color-text-secondary); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }
.kv { display: flex; justify-content: space-between; gap: 12px; font-size: 13px; }
.kv span { color: var(--color-text-secondary); }
.kv strong { text-align: right; overflow-wrap: anywhere; }
.event-reference { display: inline-flex; align-items: center; justify-content: flex-end; gap: 6px; flex-wrap: wrap; }
.event-reference button { border: 0; color: var(--color-primary); background: transparent; cursor: pointer; }
.route-references { display: inline-flex; justify-content: flex-end; gap: 6px; flex-wrap: wrap; }
.route-link { border: 0; color: var(--color-primary); background: transparent; cursor: pointer; padding: 0; font: inherit; }
.route-link:hover { text-decoration: underline; }
</style>
