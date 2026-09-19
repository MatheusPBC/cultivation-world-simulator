<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useInspection } from '../composables/useInspection'
import { formatNumber as n, calendar } from '../mappers'
import SupplyPlans from './SupplyPlans.vue'
import IncomePanel from './IncomePanel.vue'
import ResearchPanel from './ResearchPanel.vue'
import DiplomacyPanel from './DiplomacyPanel.vue'
import MigrationPanel from './MigrationPanel.vue'
import WorkforcePanel from './WorkforcePanel.vue'
const {t,te}=useI18n()
const {tab,data,settlement,character,site,route,routeReports,fiscalRouteReports,siteReports,groups,stocks,market,localSites,localRoutes,resourceName,polityName,placeName,select,source,entityName}=useInspection()
const label=(key:string)=>te('kinds.'+key)?t('kinds.'+key):key
const repairInputs=(inputs:Record<string,number> = {}) => Object.entries(inputs).map(([id,amount])=>`${resourceName(id)}: ${n(amount)}`).join(', ')
const checkpointsForSite=(siteId:string)=>data.value.economy.customs_checkpoints.filter(checkpoint=>checkpoint.site_id===siteId)
const checkpointName=(checkpointId:string)=>data.value.economy.customs_checkpoints.find(checkpoint=>checkpoint.id===checkpointId)?.id??checkpointId
const noticeForParcel=(parcelId:string)=>data.value.governance.customs_notices.find(notice=>notice.parcel_id===parcelId)
const manifestForParcel=(parcelId:string)=>data.value.economy.cargo_manifests.find(manifest=>manifest.parcel_id===parcelId)
const feeLabel=(fee:number|null)=>fee===null?'—':n(fee)
const checkpointLabel=(checkpointId:string)=>{
  const checkpoint=data.value.economy.customs_checkpoints.find(item=>item.id===checkpointId)
  const site=checkpoint&&data.value.map.sites.find(item=>item.id===checkpoint.site_id)
  return site ? site.name + ' (' + checkpointId + ')' : checkpointId
}
</script>
<template>
  <aside class="inspector panel" data-testid="inspector">
    <nav class="inspector-tabs" :aria-label="t('inspection')"><button v-for="key in (['inspection','people','governments','reserves','finances','research','diplomacy','migrations','workforce'] as const)" :key="key" :aria-pressed="tab===key" @click="tab=key">{{t(key)}}</button></nav>
    <div class="inspector-body">
      <SupplyPlans v-if="tab==='reserves'" />
      <IncomePanel v-if="tab==='finances'" />
      <ResearchPanel v-if="tab==='research'" />
      <DiplomacyPanel v-if="tab==='diplomacy'" />
      <MigrationPanel v-if="tab==='migrations'" />
      <WorkforcePanel v-if="tab==='workforce'" />
      <template v-if="tab==='inspection'">
        <template v-if="settlement">
          <p class="eyebrow">{{label(settlement.kind)}} · {{polityName(settlement.administrator_id)}}</p><h2>{{settlement.name}}</h2>
          <p class="population-number">{{n(settlement.population)}} <small>{{t('inhabitants')}} ({{t('residents')}})</small></p>
          <p class="muted">{{t('presentPopulation')}}: {{n(settlement.present_population)}}</p>
          <div class="stat-pair"><div><span>{{t('health')}}</span><strong>{{n(settlement.health/10)}}%</strong><meter :value="settlement.health" min="0" max="1000" :aria-label="t('health')"/></div><div><span>{{t('unrest')}}</span><strong>{{n(settlement.unrest/10)}}%</strong><meter :value="settlement.unrest" min="0" max="1000" :aria-label="t('unrest')"/></div></div>
          <p v-if="settlement.missing_food" class="notice warning">{{t('missing')}}: {{n(settlement.missing_food)}}</p>
          <dl><dt>{{t('administrator')}}</dt><dd>{{polityName(settlement.administrator_id)}}</dd><dt>{{t('occupier')}}</dt><dd>{{polityName(settlement.occupier_id)}}</dd><dt>{{t('claimants')}}</dt><dd>{{settlement.claimant_ids.map(polityName).join(', ')||t('none')}}</dd><dt>{{t('capacity')}}</dt><dd>{{n(settlement.housing_capacity)}} {{t('inhabitants')}}</dd></dl>
          <button v-if="data.economy.needs.find(x=>x.id===settlement!.id)?.last_event_id" class="text-button" @click="source(data.economy.needs.find(x=>x.id===settlement!.id)?.last_event_id)">{{t('source')}} →</button>
          <h3>{{t('stocks')}}</h3><p class="muted">{{t('privateStock')}}</p>
          <article v-for="stock in stocks" :key="stock.id" class="stock-card"><h4>{{entityName(data,stock.owner_ref)}}</h4>
            <table><thead><tr><th>{{t('resource')}}</th><th>{{t('quantity')}}</th><th>{{t('price')}}</th></tr></thead><tbody><tr v-for="(quantity,id) in stock.goods" :key="id"><td>{{resourceName(id)}}</td><td>{{n(quantity)}}</td><td>{{market?.prices[id]??'—'}}</td></tr></tbody></table>
          </article>
          <template v-if="market">
            <h3>{{t('localMarket')}} <small class="muted">· {{calendar(market.updated_day)}}</small></h3>
            <table><thead><tr><th>{{t('resource')}}</th><th>{{t('observedSupply')}}</th><th>{{t('observedDemand')}}</th><th>{{t('price')}}</th></tr></thead>
              <tbody><tr v-for="id in Object.keys(market.prices)" :key="id"><td>{{resourceName(id)}}</td><td>{{n(market.observed_supply?.[id]??0)}}</td><td>{{n(market.observed_demand?.[id]??0)}}</td><td>{{n(market.prices[id])}}</td></tr></tbody>
            </table>
          </template>
          <h3>{{t('groups')}}</h3><div v-for="g in groups" :key="g.id" class="list-row"><span>{{label(g.people)}} · {{label(g.occupation)}}</span><strong>{{n(g.count)}}</strong></div>
          <h3>{{t('civicProtests')}}</h3>
          <p v-if="!data.society.civic_protests.some(p=>p.settlement_id===settlement!.id)" class="muted">{{t('noCivicProtests')}}</p>
          <article v-for="protest in data.society.civic_protests.filter(p=>p.settlement_id===settlement!.id)" :key="protest.id" class="stock-card" :data-protest="protest.id">
            <h4>{{t('protestDemands.' + protest.demand_kind)}}</h4>
            <p>{{t('protestStages.' + protest.stage)}} · {{n(protest.participants)}} {{t('protestParticipants')}}</p>
            <p class="muted">{{t('protestDue')}}: {{calendar(protest.due_day)}}</p>
            <button @click="source(protest.last_event_id)">{{t('source')}}</button>
          </article>
          <h3>{{t('civicMovements')}}</h3>
          <p v-if="!data.society.civic_movements.some(m=>m.settlement_id===settlement!.id)" class="muted">{{t('noCivicMovements')}}</p>
          <article v-for="movement in data.society.civic_movements.filter(m=>m.settlement_id===settlement!.id)" :key="movement.id" class="stock-card" :data-movement="movement.id">
            <h4>{{t('movementStages.' + movement.stage)}}</h4>
            <p>{{n(movement.member_group_ids.length)}} {{t('movementGroups')}} · {{t('movementLeader')}}: {{data.society.characters.find(c=>c.id===movement.leader_character_id)?.name||movement.leader_character_id}}</p>
            <button @click="source(movement.last_event_id)">{{t('source')}}</button>
          </article>
          <h3>{{t('civicStrikes')}}</h3>
          <p v-if="!data.society.civic_strikes.some(s=>s.settlement_id===settlement!.id)" class="muted">{{t('noCivicStrikes')}}</p>
          <article v-for="strike in data.society.civic_strikes.filter(s=>s.settlement_id===settlement!.id)" :key="strike.id" class="stock-card" :data-strike="strike.id">
            <h4>{{t('strikeStages.' + strike.stage)}}</h4>
            <p>{{t('strikeParticipants')}}: {{n(Object.values(strike.participants_by_group).reduce((total, count)=>total+count, 0))}} · {{t('strikeDue')}}: {{calendar(strike.due_day)}}</p>
            <button @click="source(strike.last_event_id)">{{t('source')}}</button>
          </article>
          <h3>{{t('civicAmnesties')}}</h3>
          <p v-if="!data.society.civic_amnesties.some(a=>a.settlement_id===settlement!.id)" class="muted">{{t('noCivicAmnesties')}}</p>
          <article v-for="amnesty in data.society.civic_amnesties.filter(a=>a.settlement_id===settlement!.id)" :key="amnesty.id" class="stock-card" :data-amnesty="amnesty.id">
            <h4>{{t('amnestyGranted')}}</h4>
            <p>{{t('amnestyAdministrator')}}: {{entityName(data, amnesty.administrator_ref)}}</p>
            <button @click="source(amnesty.last_event_id)">{{t('source')}}</button>
          </article>
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
          <p class="eyebrow">{{t('sites')}}</p><h2>{{site.name}}</h2><dl><dt>{{t('owner')}}</dt><dd>{{entityName(data,site.owner_ref)}}</dd><dt>{{t('maintainer')}}</dt><dd>{{entityName(data,site.maintainer_ref)}}</dd><dt>{{t('integrity')}}</dt><dd>{{n(site.integrity*100)}}%</dd><dt>{{t('activity')}}</dt><dd>{{site.enabled?t('enabled'):t('disabled')}}</dd><dt>{{t('serviceSuspended')}}</dt><dd>{{site.service_suspended?t('serviceSuspended'):t('serviceOperating')}}</dd></dl>
          <button v-if="site.last_event_id" @click="source(site.last_event_id)">{{t('source')}}</button>
          <h3>{{t('production')}}</h3><div v-for="f in data.economy.facilities.filter(f=>f.site_id===site!.id)" :key="f.id"><p>{{t('batches')}}: {{f.last_batches}} / {{f.max_batches}}</p><p>{{t('limitations')}}: {{f.last_limitations.join(', ')||t('none')}}</p><button v-if="f.last_event_id" @click="source(f.last_event_id)">{{t('source')}}</button></div>
          <template v-if="data.economy.repairs.some(r=>r.site_id===site!.id)">
            <h3>{{t('repairs')}}</h3>
            <article v-for="r in data.economy.repairs.filter(r=>r.site_id===site!.id)" :key="r.id" :data-repair="r.id" class="stock-card">
              <p>{{t('repairStages.' + r.stage)}}</p>
              <p>{{t('accumulatedRepairWork')}}: {{r.restored_permille}}‰</p>
              <p class="muted">{{t('repairRatePerBatch')}}: {{data.economy.repair_blueprints.find(b=>b.id===r.blueprint_id)?.restored_permille}}‰</p>
              <p class="muted">{{t('repairInputsPerBatch')}}: {{repairInputs(data.economy.repair_blueprints.find(b=>b.id===r.blueprint_id)?.inputs)}}</p>
              <p v-if="r.blocker" class="notice warning">{{r.blocker}}</p>
              <p class="muted">{{t('lastReview')}}: {{r.last_work_day ?? r.started_day}}</p>
              <button @click="source(r.last_event_id)">{{t('source')}}</button>
            </article>
          </template>
          <template v-if="checkpointsForSite(site!.id).length">
            <h3>{{t('customsCheckpoints')}}</h3>
            <article v-for="checkpoint in checkpointsForSite(site!.id)" :key="checkpoint.id" class="stock-card" :data-checkpoint="checkpoint.id">
              <h4>{{t('civilCheckpoint')}} · {{checkpointName(checkpoint.id)}}</h4>
              <dl>
                <dt>{{t('checkpointState')}}</dt><dd>{{checkpoint.staff_count > 0 ? t('checkpointStaffed') : t('checkpointUnstaffed')}}</dd>
                <dt>{{t('operator')}}</dt><dd>{{entityName(data,checkpoint.operator_ref)}}</dd>
                <dt>{{t('checkpointStaff')}}</dt><dd>{{n(checkpoint.staff_count)}}</dd>
                <dt>{{t('checkpointFee')}}</dt><dd>{{n(checkpoint.fee_per_bulk)}} / {{t('bulkDay')}}</dd>
                <dt>{{t('lastStaffed')}}</dt><dd>{{calendar(checkpoint.last_staffed_day)}}</dd>
                <dt>{{t('inspectionDay')}}</dt><dd>{{calendar(checkpoint.inspection_day)}}</dd>
                <dt>{{t('inspectionSlots')}}</dt><dd>{{n(checkpoint.inspection_slots_used)}}</dd>
              </dl>
              <button v-if="checkpoint.last_event_id" @click="source(checkpoint.last_event_id)">{{t('source')}}</button>
            </article>
          </template>
          <details class="route-knowledge">
            <summary>{{t('siteKnowledge')}} ({{siteReports.length}})</summary>
            <p class="muted">{{t('siteKnowledgeHelp')}}</p>
            <p v-if="!siteReports.length" class="muted">{{t('noSiteKnowledge')}}</p>
            <article v-for="report in siteReports" :key="report.id" :data-site-report="report.id" class="stock-card">
              <h4>{{t('observer')}}: {{report.observerName}}</h4>
              <dl>
                <dt>{{t('observedIntegrity')}}</dt><dd>{{n(report.integrity*100)}}%</dd>
                <dt>{{t('observedActivity')}}</dt><dd>{{report.enabled?t('enabled'):t('disabled')}}</dd>
                <dt>{{t('serviceSuspended')}}</dt><dd>{{report.service_suspended?t('serviceSuspended'):t('serviceOperating')}}</dd>
              </dl>
              <p class="muted">{{t('observedOn')}}: {{calendar(report.observed_day)}}</p>
              <p v-if="report.stale" class="notice warning">{{t('staleRouteKnowledge')}}</p>
              <button @click="source(report.event_id)">{{t('source')}}</button>
            </article>
          </details>
          <h3>{{t('routes')}}</h3><button v-for="id in site.route_ids" :key="id" class="link-row" @click="select('route',id)">{{id}} →</button>
        </template>
        <template v-else-if="route">
          <p class="eyebrow">{{t('routes')}} · {{label(route.route.mode)}}</p><h2>{{route.route.endpoint_region_ids.map(id=>data.society.settlements.find(s=>s.region_id===id)?.name).join(' — ')}}</h2>
          <dl><dt>{{t('nominal')}}</dt><dd>{{n(route.route.capacity)}} {{t('bulkDay')}}</dd><dt>{{t('operational')}}</dt><dd>{{n(route.operational_capacity)}} {{t('bulkDay')}}</dd></dl><p class="muted">{{t('routesHelp')}}</p>
          <details class="route-knowledge">
            <summary>{{t('routeKnowledge')}} ({{routeReports.length}})</summary>
            <p class="muted">{{t('routeKnowledgeHelp')}}</p>
            <p v-if="!routeReports.length" class="muted">{{t('noRouteKnowledge')}}</p>
            <article v-for="report in routeReports" :key="report.id" :data-route-report="report.id" class="stock-card">
              <h4>{{report.recipientName}}</h4>
              <p class="muted">{{t('publisher')}}: {{report.publisherName}} · {{t('routeReportChannels.' + report.channel)}}</p>
              <dl>
                <dt>{{t('observedCapacity')}}</dt><dd>{{n(report.operational_capacity)}} {{t('bulkDay')}}</dd><dt>{{t('observedTraffic')}}</dt><dd>{{n(report.daily_flow_bulk ?? 0)}} {{t('bulkDay')}}</dd>
                <dt>{{t('observedTravelDays')}}</dt><dd>{{report.travel_days!==null?`${report.travel_days} ${t('days')}`:t('impassable')}}</dd>
              </dl>
              <p class="muted">{{t('observedOn')}}: {{calendar(report.observed_day)}}</p>
              <p v-if="report.stale" class="notice warning">{{t('staleRouteKnowledge')}}</p>
              <button @click="source(report.event_id)">{{t('source')}}</button>
            </article>
          </details>
          <details class="route-knowledge" v-if="fiscalRouteReports.length">
            <summary>{{t('fiscalRouteKnowledge')}} ({{fiscalRouteReports.length}})</summary>
            <p class="muted">{{t('fiscalRouteKnowledgeHelp')}}</p>
            <article v-for="report in fiscalRouteReports" :key="report.id" :data-fiscal-route-report="report.id" class="stock-card">
              <h4>{{checkpointLabel(report.checkpoint_id)}}</h4>
              <p class="muted">{{t('observer')}}: {{report.recipientName}} · {{t('publisher')}}: {{report.publisherName}} · {{t('routeReportChannels.' + report.channel)}}</p>
              <dl><dt>{{t('checkpointFee')}}</dt><dd>{{n(report.fee_per_bulk)}} / {{t('bulkDay')}}</dd></dl>
              <p class="muted">{{t('observedOn')}}: {{calendar(report.observed_day)}}</p>
              <p v-if="report.stale" class="notice warning">{{t('staleRouteKnowledge')}}</p>
              <button @click="source(report.event_id)">{{t('source')}}</button>
            </article>
          </details>
          <h3>{{t('sites')}}</h3><button v-for="s in data.map.sites.filter(s=>s.route_ids.includes(route!.route.id))" :key="s.id" class="link-row" @click="select('site',s.id)">{{s.name}} →</button>
        </template>
        <div v-else class="empty-inspector"><p class="eyebrow">{{t('inspection')}}</p><h2>{{t('select')}}</h2><p class="muted">{{t('selectionHelp')}}</p></div>
      </template>
      <template v-if="tab==='people'"><h2>{{t('people')}}</h2><button v-for="c in data.society.characters" :key="c.id" class="person-row" @click="select('character',c.id)"><span class="initial">{{c.name.charAt(0)}}</span><span><strong>{{c.name}}</strong><small>{{label(c.people)}} · {{placeName(c.location_id)}}</small></span><span>→</span></button></template>
      <template v-if="tab==='governments'"><h2>{{t('governments')}}</h2><article v-for="p in data.society.polities" :key="p.id" class="stock-card"><h3>{{p.name}}</h3><p>{{label(p.government)}}</p><button class="link-row" @click="select('settlement',p.capital_id)">{{t('capital')}}: {{placeName(p.capital_id)}} →</button><p v-for="i in p.interests" :key="i" class="muted">{{i}}</p></article><h2>{{t('organizations')}}</h2><article v-for="o in data.society.organizations" :key="o.id" class="stock-card"><h3>{{o.name}}</h3><p>{{label(o.kind)}}</p><p v-for="i in o.interests" :key="i" class="muted">{{i}}</p><button @click="select('settlement',o.seat_id)">{{placeName(o.seat_id)}} →</button></article></template>
      <template v-if="tab==='reserves'"><h2>{{t('reserves')}}</h2><button v-for="s in data.society.settlements" :key="s.id" class="link-row" @click="select('settlement',s.id)"><span>{{s.name}}<small>{{t('missing')}}: {{n(s.missing_food)}}</small></span><strong>{{n(s.health/10)}}%</strong></button><h3>{{t('treasury')}}</h3><div v-for="a in data.economy.accounts.filter(a=>a.owner_ref.kind!=='population_group')" :key="a.id" class="list-row"><span>{{entityName(data,a.owner_ref)}}</span><strong>{{n(a.balance)}}</strong></div><h3>{{t('cargos')}}</h3><p v-if="!data.economy.parcels.length" class="muted">{{t('noCargo')}}</p><article v-for="p in data.economy.parcels" :key="p.id" class="stock-card"><h4>{{resourceName(data.economy.pending_orders.find(o=>o.id===p.order_id)?.resource_id??'')}} · {{n(p.quantity)}}</h4><p>{{label(p.stage)}} · {{t('due')}}: {{p.due_day}}</p><p v-if="p.stage==='held'" class="notice warning">{{t('cargoHeldAtCheckpoint')}}: {{checkpointName(p.held_checkpoint_id ?? '')}}</p><template v-if="manifestForParcel(p.id)"><p>{{t('manifestStatus')}}: <strong>{{t('manifestDeclared')}}</strong></p><p class="muted">{{resourceName(manifestForParcel(p.id)!.resource_id)}} · {{n(manifestForParcel(p.id)!.quantity)}} · {{t('declaredOn')}}: {{calendar(manifestForParcel(p.id)!.declared_day)}}</p><button @click="source(manifestForParcel(p.id)!.event_id)">{{t('source')}}</button></template><template v-if="noticeForParcel(p.id)"><p>{{t('noticeState')}}: <strong>{{t('customsNoticeStates.' + noticeForParcel(p.id)!.state)}}</strong></p><p class="muted">{{resourceName(noticeForParcel(p.id)!.resource_id)}} · {{n(noticeForParcel(p.id)!.quantity)}} · {{t('checkpointFee')}}: {{feeLabel(noticeForParcel(p.id)!.fee)}} · {{t('learnedOn')}}: {{calendar(noticeForParcel(p.id)!.learned_day)}}</p><button :data-notice-source="noticeForParcel(p.id)!.id" @click="source(noticeForParcel(p.id)!.event_id)">{{t('source')}}</button><button v-if="noticeForParcel(p.id)!.state_event_id !== noticeForParcel(p.id)!.event_id" @click="source(noticeForParcel(p.id)!.state_event_id)">{{t('source')}}</button></template><button v-if="p.last_event_id" @click="source(p.last_event_id)">{{t('source')}}</button></article></template>
    </div>
  </aside>
</template>
