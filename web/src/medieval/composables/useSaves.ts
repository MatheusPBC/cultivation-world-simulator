import { onMounted, onUnmounted, ref, shallowRef } from 'vue'
import type { SaveView } from '../../types/medieval-api'
import { api, asError, type ApiError } from '../api'
import { useObserverStore } from '../stores/world'
export function useSaves(close:()=>void) {
  const store=useObserverStore(), files=shallowRef<SaveView[]>([]), error=shallowRef<ApiError|null>(null)
  const name=ref(''),overwrite=ref(false),confirmation=ref<SaveView|null>(null),saved=ref(false)
  const container=ref<HTMLElement|null>(null)
  const previousFocus=document.activeElement as HTMLElement|null
  let disposed=false
  async function refresh() {try{const reply=await api.query('saves');if(!disposed)files.value=reply.data}catch(e){if(!disposed)error.value=asError(e)}}
  async function save() {
    saved.value=false
    const ok=await store.perform(()=>api.command('save',{save_id:name.value,overwrite:overwrite.value}))
    if(ok){saved.value=true;overwrite.value=false;await refresh()}
  }
  async function load() {if(!confirmation.value)return
    if(await store.perform(()=>api.command('load',{save_id:confirmation.value!.save_id})))close()
  }
  function keyboard(e:KeyboardEvent) {
    if(e.key==='Escape'&&!store.busy){e.preventDefault();close()}
    if(e.key==='Tab'){
      const list=container.value?.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled),[tabindex="0"]')
      if(!list?.length)return
      const first=list[0],last=list[list.length-1]
      if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus()}
      else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus()}
    }
  }
  onMounted(()=>{void refresh();container.value?.querySelector<HTMLElement>('button')?.focus()})
  onUnmounted(()=>{disposed=true;previousFocus?.focus()})
  return {store,files,error,name,overwrite,confirmation,saved,container,refresh,save,load,keyboard}
}
