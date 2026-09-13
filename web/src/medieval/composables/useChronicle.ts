import { nextTick, onUnmounted, ref, shallowRef, watch } from 'vue'
import { api, asError, type ApiError } from '../api'
import type { CausalView, EventsView } from '../../types/medieval-api'
import { useObserverStore } from '../stores/world'
export function useChronicle() {
  const store=useObserverStore(), after=ref(0), following=ref(true), loading=ref(false)
  const page=shallowRef<EventsView|null>(null), causal=shallowRef<CausalView|null>(null), error=shallowRef<ApiError|null>(null)
  const detailElement=ref<HTMLElement|null>(null)
  const setDetail=(el:unknown)=>{detailElement.value=el as HTMLElement|null}
  let pageRequest=0, causeRequest=0
  async function loadPage() {
    const request=++pageRequest
    loading.value=true
    try { const reply=await api.query('events','?after='+after.value+'&limit=25')
      if(request===pageRequest) {page.value=reply.data;error.value=null}
    } catch(e) {if(request===pageRequest)error.value=asError(e)}
    finally {if(request===pageRequest)loading.value=false}
  }
  async function open(id:string|null, more=false) {
    const request=++causeRequest
    if(!id){causal.value=null;return}
    const previous=more?causal.value:null
    if(!more)causal.value=null
    try {const reply=await api.causal(id,previous?.next_after??0)
      if(request!==causeRequest)return
      causal.value=previous?{...reply.data,effects:[...previous.effects,...reply.data.effects]}:reply.data
      error.value=null
    }catch(e){if(request===causeRequest)error.value=asError(e)}
  }
  function go(delta:number) {following.value=false;after.value=Math.max(0,after.value+delta*25);void loadPage()}
  function latest(){following.value=true;after.value=Math.max(0,(store.snapshot?.world.events??0)-25);void loadPage()}
  watch(()=>store.snapshot?.status.run_id,()=>{pageRequest++;causeRequest++;page.value=null;causal.value=null;following.value=true;latest()})
  watch(()=>store.snapshot?.world.events,()=>{if(following.value)latest()},{immediate:true})
  watch(()=>store.focusEventId,id=>{void open(id)},{immediate:true})
  watch(()=>causal.value?.event.id,async id=>{
    if(!id)return
    await nextTick()
    detailElement.value?.focus({preventScroll:true})
    detailElement.value?.scrollIntoView?.({block:'nearest'})
  })
  onUnmounted(()=>{pageRequest++;causeRequest++})
  return {store,after,following,loading,page,causal,error,go,latest,open,setDetail}
}
