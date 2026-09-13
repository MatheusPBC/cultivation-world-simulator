import { computed, ref } from 'vue'
import { useObserverStore } from '../stores/world'
import { entityName } from '../mappers'
export function useInspection() {
  const store=useObserverStore(), tab=ref<'inspection'|'people'|'governments'|'reserves'|'finances'|'research'>('inspection')
  const data=computed(()=>store.snapshot!)
  const settlement=computed(()=>data.value.society.settlements.find(s=>store.selection?.kind==='settlement' && s.id===store.selection.id))
  const character=computed(()=>data.value.society.characters.find(s=>store.selection?.kind==='character' && s.id===store.selection.id))
  const site=computed(()=>data.value.map.sites.find(s=>store.selection?.kind==='site' && s.id===store.selection.id))
  const route=computed(()=>data.value.map.routes.find(s=>store.selection?.kind==='route' && s.route.id===store.selection.id))
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
  return {store,tab,data,settlement,character,site,route,groups,stocks,market,localSites,localRoutes,resourceName,polityName,placeName,select,source,entityName}
}
