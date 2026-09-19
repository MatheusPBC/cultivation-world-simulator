<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useChronicle } from '../composables/useChronicle'
import { calendar, decisionTraceKind } from '../mappers'
const {t,te}=useI18n(), {store,after,loading,filter,items,page,causal,error,go,latest,open,setDetail}=useChronicle()
const label=(key:string)=>te('kinds.'+key)?t('kinds.'+key):key
</script>
<template>
  <section class="chronicle panel" :aria-label="t('chronicle')">
    <div class="section-heading"><div><p class="eyebrow">{{t('allFacts')}}</p><h2>{{t('chronicle')}}</h2></div><button @click="latest">{{t('follow')}}</button></div>
    <nav class="chronicle-filters segmented" :aria-label="t('chronicleFilter')">
      <button :aria-pressed="filter==='all'" @click="filter='all'">{{t('allEvents')}}</button>
      <button :aria-pressed="filter==='decisions'" @click="filter='decisions'">{{t('decisionsAndConsultations')}}</button>
    </nav>
    <p v-if="error" role="alert" class="notice error">{{error.message}}</p>
    <p v-if="!items.length" class="muted">{{loading?t('working'):filter==='decisions'?t('noDecisionEvents'):t('noEvents')}}</p>
    <div class="event-list"><button v-for="e in items" :key="e.id" :data-event="e.id" class="event-row" :aria-pressed="store.focusEventId===e.id" @click="store.focusEventId=e.id">
      <span class="event-date">{{calendar(e.day)}}<small>#{{e.sequence}} · {{label(e.fact_kind)}}</small></span>
      <span class="event-copy">
        <span class="event-meta">
          <span class="origin-badge" :class="'origin-'+e.causal_origin" :data-origin="e.causal_origin">{{t('causalOrigins.'+e.causal_origin)}}</span>
          <span v-if="decisionTraceKind(e)" class="trace-badge" :class="'trace-'+decisionTraceKind(e)" :data-trace="decisionTraceKind(e)">{{t('decisionTraces.'+decisionTraceKind(e))}}</span>
        </span>
        <span>{{e.content}}</span>
      </span>
      <span aria-hidden="true">↗</span>
    </button></div>
    <nav class="pagination" :aria-label="t('page')"><button :disabled="loading||after===0" @click="go(-1)">{{t('previous')}}</button><span>{{after+1}}–{{page?.next_after??0}}</span><button :disabled="loading||!page?.has_more" @click="go(1)">{{t('next')}}</button></nav>
    <article v-if="causal" :ref="setDetail" tabindex="-1" class="causal-detail" data-testid="causal-detail">
      <div class="section-heading"><div><p class="eyebrow">{{t('causal')}}</p><h3>#{{causal.event.sequence}} · {{label(causal.event.fact_kind)}}</h3></div><button @click="store.focusEventId=null">{{t('close')}}</button></div>
      <p>{{causal.event.content}}</p>
      <h4>{{t('causes')}}</h4><p v-if="!causal.causes.length" class="muted">{{t('noCauses')}}</p>
      <button v-for="e in causal.causes" :key="e.id" class="link-row" @click="store.focusEventId=e.id">#{{e.sequence}} · {{e.content}} →</button>
      <h4 v-if="causal.event.deltas.length">{{t('changes')}}</h4>
      <div v-for="d in causal.event.deltas" :key="d.id" class="delta-row"><span>{{d.owner_id}} · {{d.aspect}}</span><span><small>{{t('before')}} </small>{{d.before??'—'}} → <small>{{t('after')}} </small>{{d.after??'—'}}</span></div>
      <template v-if="decisionTraceKind(causal.event)==='deliberate_inaction' && Array.isArray(causal.event.decision?.declined_option_ids)">
        <h4>{{t('declinedOptions')}}</h4>
        <p class="muted">{{t('declinedOptionsHelp')}}</p>
        <ul class="declined-options"><li v-for="optionId in (causal.event.decision!.declined_option_ids as string[])" :key="optionId">{{optionId}}</li></ul>
      </template>
      <details v-if="causal.event.decision"><summary>{{t('decision')}}</summary><pre>{{JSON.stringify(causal.event.decision,null,2)}}</pre></details>
      <details v-if="causal.event.causal_payload"><summary>{{t('engineEvidence')}}</summary><pre>{{JSON.stringify(causal.event.causal_payload,null,2)}}</pre></details>
      <h4>{{t('effects')}}</h4><p v-if="!causal.effects.length" class="muted">{{t('noEffects')}}</p>
      <button v-for="e in causal.effects" :key="e.id" class="link-row" @click="store.focusEventId=e.id">#{{e.sequence}} · {{e.content}} →</button>
      <button v-if="causal.has_more" @click="open(causal.event.id,true)">{{t('showMore')}}</button>
    </article>
  </section>
</template>
