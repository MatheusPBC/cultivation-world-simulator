import { expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import Chronicle from '../components/Chronicle.vue'
import { useObserverStore } from '../stores/world'
import { medievalI18n } from '../i18n'
import type { ObservatoryView, WorldEvent } from '../../types/medieval-api'
import fixture from './world.json'

const event = (overrides: Partial<WorldEvent> & Pick<WorldEvent, 'id' | 'sequence' | 'event_type' | 'content' | 'causal_origin'>): WorldEvent => ({
  day: 30, fact_kind: 'occurrence', decision: null, causal_links: [], deltas: [], ...overrides,
})

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

it('shows structured engine evidence in the causal detail', async () => {
  vi.useRealTimers()
  const pinia=createPinia(); setActivePinia(pinia)
  const store=useObserverStore()
  store.snapshot=structuredClone(fixture) as ObservatoryView
  store.snapshot.world.events=1
  const ecologyEvent = event({id:'event:ecology',sequence:1,event_type:'creature_ecology_tick',content:'O habitat perdeu capacidade.',causal_origin:'deterministic',causal_payload:{ ecology: { species: 'river_drake', habitat_stress: 3 } }})
  vi.stubGlobal('fetch', vi.fn(async (url: string) => url.includes('/causal/')
    ? new Response(JSON.stringify({ ok:true, revision:1, data: { event: ecologyEvent, causes: [], effects: [], next_after: 0, has_more: false } }), { headers: { 'content-type': 'application/json' } })
    : new Response(JSON.stringify({ ok:true, revision:1, data: { items: [ecologyEvent], next_after: 1, has_more: false } }), { headers: { 'content-type': 'application/json' } })))
  const app = mount(Chronicle,{attachTo:document.body,global:{plugins:[pinia,medievalI18n]}})
  await flushPromises()
  await app.get('[data-event="event:ecology"]').trigger('click')
  await flushPromises()
  expect(app.get('[data-testid="causal-detail"]').text()).toContain('Evidência estruturada do motor')
  expect(app.get('[data-testid="causal-detail"]').text()).toContain('river_drake')
  app.unmount(); vi.unstubAllGlobals()
})

it('separates actor choice, explicit refusal and technical failure and filters decision traces', async () => {
  vi.useRealTimers()
  const pinia=createPinia(); setActivePinia(pinia)
  const store=useObserverStore()
  store.snapshot=structuredClone(fixture) as ObservatoryView
  store.snapshot.world.events=5
  const events: WorldEvent[]=[
    event({id:'event:routine',sequence:1,event_type:'production_completed',content:'O moinho produziu farinha.',causal_origin:'deterministic'}),
    event({id:'event:choice',sequence:2,event_type:'institutional_decision_turn_decided',content:'O ator escolheu entre opções institucionais concorrentes.',causal_origin:'actor_decision',fact_kind:'decision',decision:{selected_id:'buy:grain'}}),
    event({id:'event:refusal',sequence:3,event_type:'ai_decision_declined',content:'Copy de recusa alterada sem mudar o contrato.',causal_origin:'llm_interpretation'}),
    event({id:'event:consultation',sequence:4,event_type:'ai_decision_interpreted',content:'Copy de escolha alterada sem mudar o contrato.',causal_origin:'llm_interpretation'}),
    event({id:'event:failure',sequence:5,event_type:'ai_decision_failed',content:'Copy de falha alterada sem mudar o contrato.',causal_origin:'llm_interpretation'}),
  ]
  vi.stubGlobal('fetch',vi.fn(async ()=>new Response(JSON.stringify({ok:true,revision:1,data:{items:events,next_after:4,has_more:false}}))))
  const app=mount(Chronicle,{global:{plugins:[pinia,medievalI18n]}})
  await flushPromises()

  expect(app.get('[data-event="event:choice"] [data-origin="actor_decision"]').text()).toBe('Decisão do ator')
  expect(app.get('[data-event="event:choice"] [data-trace="actor_choice"]').text()).toBe('Ação escolhida')
  expect(app.get('[data-event="event:refusal"] [data-trace="explicit_refusal"]').text()).toBe('Recusa explícita')
  expect(app.get('[data-event="event:consultation"] [data-trace="consultation_completed"]').text()).toBe('Consulta concluída')
  expect(app.get('[data-event="event:failure"] [data-trace="technical_failure"]').text()).toBe('Sem decisão · falha técnica')
  expect(app.get('[data-event="event:routine"] [data-origin="deterministic"]').text()).toBe('Mundo determinístico')

  await app.get('.chronicle-filters button:last-child').trigger('click')
  expect(app.find('[data-event="event:routine"]').exists()).toBe(false)
  expect(app.findAll('.event-row')).toHaveLength(4)
  app.unmount();vi.unstubAllGlobals()
})

it('marks a declined institutional decision turn as deliberate inaction, not as an action, and shows what was declined and why', async () => {
  vi.useRealTimers()
  const pinia=createPinia(); setActivePinia(pinia)
  const store=useObserverStore()
  store.snapshot=structuredClone(fixture) as ObservatoryView
  store.snapshot.world.events=2
  const cause: WorldEvent=event({id:'event:report',sequence:1,event_type:'settlement_report',
    content:'Relatório: fome em Pedraclara.',causal_origin:'deterministic'})
  const decided: WorldEvent=event({id:'event:choice',sequence:2,event_type:'institutional_decision_turn_decided',
    content:'O ator escolheu entre opções institucionais concorrentes.',causal_origin:'actor_decision',
    fact_kind:'decision',decision:{selected_id:'buy:grain'}})
  const declined: WorldEvent=event({id:'event:declined',sequence:3,event_type:'institutional_decision_turn_declined',
    content:'O ator foi consultado e optou por não agir entre as opções institucionais concorrentes.',
    causal_origin:'actor_decision',fact_kind:'decision',
    decision:{action:'no_action',declined_option_ids:['distribute_food:pedraclara','request_aid:coroa']}})
  const events=[decided,declined]
  vi.stubGlobal('fetch',vi.fn(async (url:string)=>new Response(JSON.stringify({ok:true,revision:1,data:
    url.includes('/causal/') ? {event:declined,causes:[cause],effects:[],next_after:0,has_more:false} :
    {items:events,next_after:2,has_more:false}}))))
  const app=mount(Chronicle,{attachTo:document.body,global:{plugins:[pinia,medievalI18n]}})
  await flushPromises()

  expect(app.get('[data-event="event:choice"] [data-trace="actor_choice"]').text()).toBe('Ação escolhida')
  expect(app.get('[data-event="event:declined"] [data-trace="deliberate_inaction"]').text()).toBe('Inação deliberada')
  expect(app.find('[data-event="event:declined"] [data-trace="actor_choice"]').exists()).toBe(false)

  await app.get('[data-event="event:declined"]').trigger('click');await flushPromises()
  const detail=app.get('[data-testid="causal-detail"]')
  expect(detail.text()).toContain('Relatório: fome em Pedraclara.')
  expect(detail.text()).toContain('distribute_food:pedraclara')
  expect(detail.text()).toContain('request_aid:coroa')
  app.unmount();vi.unstubAllGlobals()
})
