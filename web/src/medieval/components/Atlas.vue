<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useObserverStore } from '../stores/world'
import { useAtlas } from '../composables/useAtlas'
const { t }=useI18n(), store=useObserverStore(), host=ref<HTMLElement|null>(null)
const {layer,showRoutes,showSites,unavailable,fit,zoomBy,down,move,up}=useAtlas(host)
const threats = computed(() => store.snapshot?.campaigns.threats ?? [])
const politicalSettlements = computed(() => store.snapshot?.campaigns.political_settlements ?? [])
function threatTarget(threat: (typeof threats.value)[number]) {
  const snapshot = store.snapshot
  if (threat.settlement_id) return snapshot?.society.settlements.find(item => item.id === threat.settlement_id)?.name ?? threat.settlement_id
  if (threat.site_id) return snapshot?.map.sites.find(item => item.id === threat.site_id)?.name ?? threat.site_id
  return threat.route_id ?? '—'
}
</script>
<template>
  <section class="atlas" :aria-label="t('map')">
    <div class="map-toolbar">
      <div class="segmented"><button v-for="key in (['political','terrain','food','campaign'] as const)" :key="key" :aria-pressed="layer===key" @click="layer=key">{{ t(key) }}</button></div>
      <label class="check"><input v-model="showRoutes" type="checkbox" />{{t('routes')}}</label>
      <label class="check"><input v-model="showSites" type="checkbox" />{{t('sites')}}</label>
    </div>
    <div ref="host" class="map-canvas" @pointerdown="down" @pointermove="move" @pointerup="up" @pointercancel="up">
      <p v-if="unavailable" role="status" class="map-fallback">{{t('mapUnavailable')}}</p>
    </div>
    <div class="map-bottom"><span>{{t('topology')}}</span><div class="zoom-controls"><button :aria-label="t('zoomOut')" @click="zoomBy(-.25)">−</button><button @click="fit">{{t('fit')}}</button><button :aria-label="t('zoomIn')" @click="zoomBy(.25)">+</button></div></div>
    <div class="legend"><span class="auren">Auren</span><span class="valedouro">Valedouro</span><span class="escarlia">Escárlia</span></div>
  </section>
  <section v-if="threats.length" class="threat-list" :aria-label="t('activeThreats')">
    <h3>{{t('activeThreats')}}</h3>
    <article v-for="threat in threats" :key="threat.id" class="threat-row" :data-threat="threat.id">
      <strong>{{t('threatKinds.' + threat.kind)}}</strong>
      <span :data-target="threatTarget(threat)">{{threatTarget(threat)}} · {{t('threatSeverities.' + threat.severity)}} · {{t('threatStatuses.' + threat.status)}}</span>
      <button class="text-button" @click="store.focusEventId=threat.source_event_id">{{t('source')}}</button>
    </article>
  </section>
  <section v-if="politicalSettlements.length" class="threat-list" :aria-label="t('politicalSettlements')">
    <h3>{{t('politicalSettlements')}}</h3>
    <article v-for="proposal in politicalSettlements" :key="proposal.id" class="threat-row" :data-political-settlement="proposal.id">
      <strong>{{t('politicalSettlementKinds.' + proposal.proposal_kind)}}</strong>
      <span>{{proposal.proposer_ref.id}} → {{proposal.counterparty_ref.id}} · {{proposal.settlement_id ?? '—'}} · {{t('politicalSettlementStatuses.' + proposal.status)}}</span>
      <button class="text-button" @click="store.focusEventId=proposal.last_event_id">{{t('source')}}</button>
    </article>
  </section>
  <nav class="settlement-list" :aria-label="t('settlements')"><button v-for="s in store.snapshot!.society.settlements" :key="s.id" :data-settlement="s.id" :aria-pressed="store.selection?.id===s.id" @click="store.selection={kind:'settlement',id:s.id}">{{s.name}}<span v-if="s.missing_food" class="shortage-mark"> · {{t('missing')}}</span></button></nav>
</template>
