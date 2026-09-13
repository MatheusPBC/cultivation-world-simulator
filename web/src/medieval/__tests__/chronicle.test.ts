import { expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import Chronicle from '../components/Chronicle.vue'
import { useObserverStore } from '../stores/world'
import { medievalI18n } from '../i18n'
import type { ObservatoryView, WorldEvent } from '../../types/medieval-api'
import fixture from './world.json'

it('opens real causal evidence and preserves before/after without interpreting it as state', async () => {
  vi.useRealTimers()
  const pinia=createPinia(); setActivePinia(pinia)
  const store=useObserverStore()
  store.snapshot=structuredClone(fixture) as ObservatoryView
  store.snapshot.world.events=1
  const event: WorldEvent={id:'event:1',sequence:1,day:30,event_type:'subsistence',content:'Faltaram 200 rações.',
    fact_kind:'state_transition',causal_origin:'deterministic',decision:null,causal_links:[],
    deltas:[{id:'event:1:delta:0',event_id:'event:1',owner_kind:'settlement_needs',owner_id:'pedraclara',aspect:'health',before:'1000',after:'900',magnitude:null}]}
  vi.stubGlobal('fetch',vi.fn(async (url:string)=>new Response(JSON.stringify({ok:true,revision:1,data:
    url.includes('/causal/') ? {event,causes:[],effects:[],next_after:0,has_more:false} :
    {items:[event],next_after:1,has_more:false}}))))
  const app=mount(Chronicle,{attachTo:document.body,global:{plugins:[pinia,medievalI18n]}})
  await flushPromises()
  await app.get('[data-event="event:1"]').trigger('click');await flushPromises()
  expect(app.get('[data-testid="causal-detail"]').text()).toContain('1000')
  expect(app.get('[data-testid="causal-detail"]').text()).toContain('900')
  expect(document.activeElement).toBe(app.get('[data-testid="causal-detail"]').element)
  expect(store.snapshot.society.settlements.find(s=>s.id==='pedraclara')?.health).toBe(1000)
  app.unmount();vi.unstubAllGlobals()
})
