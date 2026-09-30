<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useResearch } from '../composables/useResearch'
import { calendar } from '../mappers'
import type { EntityRef } from '../../types/medieval-api'

const props=defineProps<{siteId?:string;settlementId?:string}>()
const emit=defineEmits<{inspect:[kind:'character'|'organization'|'polity'|'site',id:string]}>()
const {t}=useI18n()
const {executions,source}=useResearch()
const localExecutions=computed(()=>executions.value.filter(rite=>
  (!props.siteId||rite.site_id===props.siteId)&&(!props.settlementId||rite.settlement_id===props.settlementId)))
function inspect(ref:EntityRef){
  if(ref.kind==='character'||ref.kind==='organization'||ref.kind==='polity'||ref.kind==='site')emit('inspect',ref.kind,ref.id)
}
</script>
<template>
  <section v-if="localExecutions.length" :aria-label="t('riteExecutions')">
    <h3>{{t('riteExecutions')}}</h3><p class="muted">{{t('riteEvidenceHelp')}}</p>
    <article v-for="rite in localExecutions" :key="rite.id" class="stock-card" :data-rite-execution="rite.id">
      <h4>{{rite.site}}</h4><p>{{rite.sponsor}} · {{rite.officiant}}</p>
      <p>{{t('riteStages.'+rite.stage)}} · {{calendar(rite.started_day)}} → {{calendar(rite.due_day)}}</p>
      <button @click="source(rite.officiant_decision_id)">{{t('riteOfferDecision')}}</button>
      <button @click="source(rite.sponsor_decision_id)">{{t('riteSponsorDecision')}}</button>
      <button @click="source(rite.last_event_id)">{{t('source')}}</button>
      <div class="button-row">
        <button :data-rite-officiant="rite.officiant_id" @click="inspect({kind:'character',id:rite.officiant_id})">{{t('riteInspectOfficiant')}}</button>
        <button @click="inspect(rite.sponsor_ref)">{{t('riteInspectSponsor')}}</button>
        <button v-if="!siteId" @click="inspect({kind:'site',id:rite.site_id})">{{t('riteInspectPlace')}}</button>
      </div>
    </article>
  </section>
</template>
