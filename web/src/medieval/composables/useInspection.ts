import { computed, ref } from 'vue'
import { useObserverStore } from '../stores/world'
import { entityName } from '../mappers'
export function useInspection() {
  const store=useObserverStore(), tab=ref<'inspection'|'people'|'governments'|'reserves'|'finances'|'research'|'diplomacy'|'migrations'|'workforce'>('inspection')
  const data=computed(()=>store.snapshot!)
  const settlement=computed(()=>data.value.society.settlements.find(s=>store.selection?.kind==='settlement' && s.id===store.selection.id))
  const character=computed(()=>data.value.society.characters.find(s=>store.selection?.kind==='character' && s.id===store.selection.id))
  const site=computed(()=>data.value.map.sites.find(s=>store.selection?.kind==='site' && s.id===store.selection.id))
  const route=computed(()=>data.value.map.routes.find(s=>store.selection?.kind==='route' && s.route.id===store.selection.id))
  const routeReports=computed(()=>{
    const current=route.value
    if(!current)return []
    const day=data.value.world.day
    return data.value.governance.route_reports.filter(r=>r.route_id===current.route.id)
      .map(r=>({...r,recipientName:entityName(data.value,r.recipient_ref),publisherName:entityName(data.value,r.publisher_ref),
        stale:day-r.observed_day>=30}))
      .sort((a,b)=>b.observed_day-a.observed_day || a.id.localeCompare(b.id))
  })
  const fiscalRouteReports=computed(()=>{
    const current=route.value
    if(!current)return []
    const day=data.value.world.day
    return data.value.governance.fiscal_route_reports.filter(r=>r.route_id===current.route.id)
      .map(r=>({...r,recipientName:entityName(data.value,r.recipient_ref),publisherName:entityName(data.value,r.publisher_ref),
        stale:day-r.observed_day>=30}))
      .sort((a,b)=>b.observed_day-a.observed_day || a.id.localeCompare(b.id))
  })
  const siteReports=computed(()=>{
    const current=site.value
    if(!current)return []
    const day=data.value.world.day
    return data.value.governance.site_reports.filter(r=>r.site_id===current.id)
      .map(r=>({...r,observerName:entityName(data.value,r.recipient_ref),stale:day-r.observed_day>=30}))
      .sort((a,b)=>b.observed_day-a.observed_day || a.id.localeCompare(b.id))
  })
  const groups=computed(()=>data.value.society.population_groups.filter(g=>g.settlement_id===settlement.value?.id))
  const stocks=computed(()=>data.value.economy.stocks.filter(s=>s.location_id===settlement.value?.id))
  const market=computed(()=>data.value.economy.markets.find(s=>s.id===settlement.value?.id))
  const localSites=computed(()=>data.value.map.sites.filter(s=>s.region_ids.includes(settlement.value?.region_id??-1)))
  const localRoutes=computed(()=>data.value.map.routes.filter(s=>s.route.endpoint_region_ids.includes(settlement.value?.region_id??-1)))
  const resourceName=(id:string)=>data.value.economy.resources.find(r=>r.id===id)?.name??id
  const polityName=(id:string|null)=>id?entityName(data.value,{kind:'polity',id}):'—'
  const placeName=(id:string)=>data.value.society.settlements.find(s=>s.id===id)?.name??id
  const select=(kind:'settlement'|'character'|'site'|'route',id:string)=>{store.selection={kind,id};tab.value='inspection'}
  const source=(id:string|null|undefined)=>{if(id)store.focusEventId=id}
  return {store,tab,data,settlement,character,site,route,routeReports,fiscalRouteReports,siteReports,groups,stocks,market,localSites,localRoutes,resourceName,polityName,placeName,select,source,entityName}
}
