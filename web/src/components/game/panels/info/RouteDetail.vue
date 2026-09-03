<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { RouteDetail } from '@/types/core'
import { useWorldJournalStore } from '@/stores/worldJournal'
import { useUiStore } from '@/stores/ui'

const props = defineProps<{ data: RouteDetail }>()
const { t } = useI18n()
const journalStore = useWorldJournalStore()
const uiStore = useUiStore()

function openCausalDetail(eventId: string) {
  void journalStore.openCausalDetail(eventId)
}

function openSiteDetail(siteId: string) {
  void uiStore.select('site', siteId)
}
</script>

<template>
  <div class="route-detail">
    <section class="section">
      <div class="section-title">{{ t('game.info_panel.route.title') }}</div>
      <div class="kv"><span>{{ t('game.info_panel.route.id') }}</span><strong>{{ data.id }}</strong></div>
      <div class="kv"><span>{{ t('game.info_panel.route.mode') }}</span><strong>{{ data.mode }}</strong></div>
      <div class="kv"><span>{{ t('game.info_panel.route.endpoints') }}</span><strong>{{ data.endpointRegionIds.join(' ↔ ') }}</strong></div>
    </section>

    <section class="section">
      <div class="section-title">{{ t('game.info_panel.route.capacity_section') }}</div>
      <div class="kv"><span>{{ t('game.info_panel.route.capacity') }}</span><strong>{{ data.capacity }}</strong></div>
      <div class="kv"><span>{{ t('game.info_panel.route.operational_capacity') }}</span><strong>{{ data.operationalCapacity }}</strong></div>
      <div class="kv"><span>{{ t('game.info_panel.route.quality') }}</span><strong>{{ Math.round(data.quality * 100) }}%</strong></div>
      <div class="kv"><span>{{ t('game.info_panel.route.enabled') }}</span><strong>{{ data.enabled ? t('common.yes') : t('common.no') }}</strong></div>
    </section>

    <section class="section">
      <div class="section-title">{{ t('game.info_panel.route.references') }}</div>
      <div class="kv"><span>{{ t('game.info_panel.route.allowed_resources') }}</span><strong>{{ data.allowedResourceIds.join(', ') || t('common.none') }}</strong></div>
      <div class="kv">
        <span>{{ t('game.info_panel.route.dependency_sites') }}</span>
        <span v-if="data.dependencySiteIds.length" class="site-references">
          <button
            v-for="siteId in data.dependencySiteIds"
            :key="siteId"
            type="button"
            class="site-link"
            :data-testid="`route-site-${siteId}`"
            @click="openSiteDetail(siteId)"
          >
            {{ siteId }}
          </button>
        </span>
        <strong v-else>{{ t('common.none') }}</strong>
      </div>
      <div class="kv">
        <span>{{ t('game.info_panel.route.source_events') }}</span>
        <span v-if="data.sourceEventIds.length" class="event-references">
          <span v-for="eventId in data.sourceEventIds" :key="eventId" class="event-reference">
            <strong>{{ eventId }}</strong>
            <button type="button" :data-testid="`route-open-why-${eventId}`" @click="openCausalDetail(eventId)">
              {{ t('game.world_journal.why_button') }}
            </button>
          </span>
        </span>
        <strong v-else>{{ t('common.none') }}</strong>
      </div>
    </section>
  </div>
</template>

<style scoped>
.route-detail { display: flex; flex-direction: column; gap: 14px; overflow: auto; min-height: 0; padding-right: 4px; }
.section { display: flex; flex-direction: column; gap: 8px; }
.section-title { color: var(--color-text-secondary); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }
.kv { display: flex; justify-content: space-between; gap: 12px; font-size: 13px; }
.kv span { color: var(--color-text-secondary); }
.kv strong { text-align: right; overflow-wrap: anywhere; }
.event-references { display: inline-flex; flex-direction: column; align-items: flex-end; gap: 6px; }
.event-reference { display: inline-flex; align-items: center; justify-content: flex-end; gap: 6px; flex-wrap: wrap; }
.event-reference button { border: 0; color: var(--color-primary); background: transparent; cursor: pointer; }
.site-references { display: inline-flex; justify-content: flex-end; gap: 6px; flex-wrap: wrap; }
.site-link { border: 0; color: var(--color-primary); background: transparent; cursor: pointer; padding: 0; font: inherit; }
.site-link:hover { text-decoration: underline; }
</style>
