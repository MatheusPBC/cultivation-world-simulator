<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useInspection } from '../composables/useInspection'
import { formatNumber as n } from '../mappers'
import SupplyPlans from './SupplyPlans.vue'
import IncomePanel from './IncomePanel.vue'
import ResearchPanel from './ResearchPanel.vue'
const {t,te}=useI18n()
const {tab,data,settlement,character,site,route,groups,stocks,market,localSites,localRoutes,resourceName,polityName,placeName,select,source,entityName}=useInspection()
const label=(key:string)=>te('kinds.'+key)?t('kinds.'+key):key
</script>
<template>
  <aside class="inspector panel" data-testid="inspector">
    <nav class="inspector-tabs" :aria-label="t('inspection')"><button v-for="key in (['inspection','people','governments','reserves','finances','research'] as const)" :key="key" :aria-pressed="tab===key" @click="tab=key">{{t(key)}}</button></nav>
    <div class="inspector-body">
      <SupplyPlans v-if="tab==='reserves'" />
      <IncomePanel v-if="tab==='finances'" />
      <ResearchPanel v-if="tab==='research'" />
      <template v-if="tab==='inspection'">
        <template v-if="settlement">
          <p class="eyebrow">{{label(settlement.kind)}} · {{polityName(settlement.administrator_id)}}</p><h2>{{settlement.name}}</h2>
          <p class="population-number">{{n(settlement.population)}} <small>{{t('inhabitants')}}</small></p>
          <div class="stat-pair"><div><span>{{t('health')}}</span><strong>{{n(settlement.health/10)}}%</strong><meter :value="settlement.health" min="0" max="1000" :aria-label="t('health')"/></div><div><span>{{t('unrest')}}</span><strong>{{n(settlement.unrest/10)}}%</strong><meter :value="settlement.unrest" min="0" max="1000" :aria-label="t('unrest')"/></div></div>
          <p v-if="settlement.missing_food" class="notice warning">{{t('missing')}}: {{n(settlement.missing_food)}}</p>
          <dl><dt>{{t('administrator')}}</dt><dd>{{polityName(settlement.administrator_id)}}</dd><dt>{{t('occupier')}}</dt><dd>{{polityName(settlement.occupier_id)}}</dd><dt>{{t('claimants')}}</dt><dd>{{settlement.claimant_ids.map(polityName).join(', ')||t('none')}}</dd><dt>{{t('capacity')}}</dt><dd>{{n(settlement.housing_capacity)}} {{t('inhabitants')}}</dd></dl>
          <button v-if="data.economy.needs.find(x=>x.id===settlement!.id)?.last_event_id" class="text-button" @click="source(data.economy.needs.find(x=>x.id===settlement!.id)?.last_event_id)">{{t('source')}} →</button>
          <h3>{{t('stocks')}}</h3><p class="muted">{{t('privateStock')}}</p>
          <article v-for="stock in stocks" :key="stock.id" class="stock-card"><h4>{{entityName(data,stock.owner_ref)}}</h4>
            <table><thead><tr><th>{{t('resource')}}</th><th>{{t('quantity')}}</th><th>{{t('price')}}</th></tr></thead><tbody><tr v-for="(quantity,id) in stock.goods" :key="id"><td>{{resourceName(id)}}</td><td>{{n(quantity)}}</td><td>{{market?.prices[id]??'—'}}</td></tr></tbody></table>
          </article>
          <h3>{{t('groups')}}</h3><div v-for="g in groups" :key="g.id" class="list-row"><span>{{label(g.people)}} · {{label(g.occupation)}}</span><strong>{{n(g.count)}}</strong></div>
          <h3>{{t('sites')}}</h3><button v-for="s in localSites" :key="s.id" class="link-row" @click="select('site',s.id)">{{s.name}} <span>→</span></button>
          <h3>{{t('routes')}}</h3><button v-for="r in localRoutes" :key="r.route.id" class="link-row" @click="select('route',r.route.id)">{{label(r.route.mode)}} · {{n(r.operational_capacity)}} {{t('bulkDay')}} <span>→</span></button>
        </template>
        <template v-else-if="character">
          <p class="eyebrow">{{label(character.people)}} · {{character.death_day===null?t('living'):t('deceased')}}</p><h2>{{character.name}}</h2><p>{{character.age_years}} {{t('years')}}</p>
          <button class="link-row" @click="select('settlement',character.location_id)">{{placeName(character.location_id)}} →</button>
          <h3>{{t('motivations')}}</h3><p v-for="m in character.motivations" :key="m">{{m}}</p>
          <h3>{{t('skills')}}</h3><div v-for="(v,k) in character.skills" :key="k" class="list-row"><span>{{label(k)}}</span><strong>{{v}} / 100</strong></div>
          <h3>{{t('organizations')}}</h3><p v-for="o in data.society.organizations.filter(o=>o.member_ids.includes(character!.id))" :key="o.id">{{o.name}}</p>
          <h3>{{t('activity')}}</h3><p v-if="!data.society.activities.some(a=>a.character_id===character!.id)" class="muted">{{t('noActivities')}}</p>
          <p v-for="a in data.society.activities.filter(a=>a.character_id===character!.id)" :key="a.id">{{label(a.kind)}} <button @click="source(a.decision_event_id)">{{t('source')}}</button></p>
        </template>
        <template v-else-if="site">
          <p class="eyebrow">{{t('sites')}}</p><h2>{{site.name}}</h2><dl><dt>{{t('owner')}}</dt><dd>{{entityName(data,site.owner_ref)}}</dd><dt>{{t('integrity')}}</dt><dd>{{n(site.integrity*100)}}%</dd><dt>{{t('activity')}}</dt><dd>{{site.enabled?t('enabled'):t('disabled')}}</dd></dl>
          <button v-if="site.last_event_id" @click="source(site.last_event_id)">{{t('source')}}</button>
          <h3>{{t('production')}}</h3><div v-for="f in data.economy.facilities.filter(f=>f.site_id===site!.id)" :key="f.id"><p>{{t('batches')}}: {{f.last_batches}} / {{f.max_batches}}</p><p>{{t('limitations')}}: {{f.last_limitations.join(', ')||t('none')}}</p><button v-if="f.last_event_id" @click="source(f.last_event_id)">{{t('source')}}</button></div>
          <h3>{{t('routes')}}</h3><button v-for="id in site.route_ids" :key="id" class="link-row" @click="select('route',id)">{{id}} →</button>
        </template>
        <template v-else-if="route">
          <p class="eyebrow">{{t('routes')}} · {{label(route.route.mode)}}</p><h2>{{route.route.endpoint_region_ids.map(id=>data.society.settlements.find(s=>s.region_id===id)?.name).join(' — ')}}</h2>
          <dl><dt>{{t('nominal')}}</dt><dd>{{n(route.route.capacity)}} {{t('bulkDay')}}</dd><dt>{{t('operational')}}</dt><dd>{{n(route.operational_capacity)}} {{t('bulkDay')}}</dd></dl><p class="muted">{{t('routesHelp')}}</p>
          <h3>{{t('sites')}}</h3><button v-for="s in data.map.sites.filter(s=>s.route_ids.includes(route!.route.id))" :key="s.id" class="link-row" @click="select('site',s.id)">{{s.name}} →</button>
        </template>
        <div v-else class="empty-inspector"><p class="eyebrow">{{t('inspection')}}</p><h2>{{t('select')}}</h2><p class="muted">{{t('selectionHelp')}}</p></div>
      </template>
      <template v-if="tab==='people'"><h2>{{t('people')}}</h2><button v-for="c in data.society.characters" :key="c.id" class="person-row" @click="select('character',c.id)"><span class="initial">{{c.name.charAt(0)}}</span><span><strong>{{c.name}}</strong><small>{{label(c.people)}} · {{placeName(c.location_id)}}</small></span><span>→</span></button></template>
      <template v-if="tab==='governments'"><h2>{{t('governments')}}</h2><article v-for="p in data.society.polities" :key="p.id" class="stock-card"><h3>{{p.name}}</h3><p>{{label(p.government)}}</p><button class="link-row" @click="select('settlement',p.capital_id)">{{t('capital')}}: {{placeName(p.capital_id)}} →</button><p v-for="i in p.interests" :key="i" class="muted">{{i}}</p></article><h2>{{t('organizations')}}</h2><article v-for="o in data.society.organizations" :key="o.id" class="stock-card"><h3>{{o.name}}</h3><p>{{label(o.kind)}}</p><p v-for="i in o.interests" :key="i" class="muted">{{i}}</p><button @click="select('settlement',o.seat_id)">{{placeName(o.seat_id)}} →</button></article></template>
      <template v-if="tab==='reserves'"><h2>{{t('reserves')}}</h2><button v-for="s in data.society.settlements" :key="s.id" class="link-row" @click="select('settlement',s.id)"><span>{{s.name}}<small>{{t('missing')}}: {{n(s.missing_food)}}</small></span><strong>{{n(s.health/10)}}%</strong></button><h3>{{t('treasury')}}</h3><div v-for="a in data.economy.accounts.filter(a=>a.owner_ref.kind!=='population_group')" :key="a.id" class="list-row"><span>{{entityName(data,a.owner_ref)}}</span><strong>{{n(a.balance)}}</strong></div><h3>{{t('cargos')}}</h3><p v-if="!data.economy.parcels.length" class="muted">{{t('noCargo')}}</p><article v-for="p in data.economy.parcels" :key="p.id" class="stock-card"><h4>{{resourceName(data.economy.pending_orders.find(o=>o.id===p.order_id)?.resource_id??'')}} · {{n(p.quantity)}}</h4><p>{{label(p.stage)}} · {{t('due')}}: {{p.due_day}}</p><button @click="source(p.last_event_id)">{{t('source')}}</button></article></template>
    </div>
  </aside>
</template>
