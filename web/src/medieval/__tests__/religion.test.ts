import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { it, expect, vi } from 'vitest'
import Inspector from '../components/Inspector.vue'
import { useObserverStore } from '../stores/world'
import { medievalI18n } from '../i18n'
import type { ObservatoryView } from '../../types/medieval-api'
import fixture from './world.json'
import { acceptSnapshot } from '../mappers'

it('distinguishes membership, chosen faith and declared doctrine with causal navigation', async () => {
  const pinia = createPinia(); setActivePinia(pinia)
  const store = useObserverStore()
  const data = structuredClone(fixture) as unknown as ObservatoryView
  data.society.organizations.find(o => o.id === 'coro-das-cinzas')!.member_ids.push('character:001')
  store.snapshot = data
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ ok: true, revision: 1,
    data: { actor_ref: { kind: 'character', id: 'character:001' }, entries: [], next_after: null, has_more: false } }))))
  const panel = mount(Inspector, { global: { plugins: [pinia, medievalI18n] } })
  try {
    store.selection = { kind: 'character', id: 'character:001' }
    await flushPromises()
    expect(panel.text()).toContain('Sem adesão religiosa declarada')
    const updated = structuredClone(data)
    updated.society.religious_adherences = [{ id: 'religious-adherence:character:character:001',
      actor_ref: { kind: 'character', id: 'character:001' }, organization_id: 'coro-das-cinzas',
      joined_day: 30, invitation_id: 'religious-invitation:event:4', last_event_id: 'event:7' }]
    store.snapshot = updated
    await flushPromises()
    const affiliation = panel.get('[data-adherence="religious-adherence:character:character:001"]')
    expect(affiliation.text()).toContain('Coro das Cinzas')
    await affiliation.get('button').trigger('click')
    expect(store.focusEventId).toBe('event:7')
    store.selection = { kind: 'organization', id: 'coro-das-cinzas' }
    await flushPromises()
    expect(panel.text()).toContain('Doutrina declarada')
    expect(panel.text()).toContain('honrar os mortos')
    expect(panel.text()).toContain('não fatos físicos confirmados')
  } finally {
    panel.unmount(); vi.unstubAllGlobals()
  }
})

it('separates declared belief, pending or interrupted ritual and recorded material protection', async () => {
  const pinia = createPinia(); setActivePinia(pinia)
  const store = useObserverStore()
  const data = structuredClone(fixture) as unknown as ObservatoryView
  data.world.day = 30
  const base = { sponsor_ref: { kind: 'organization', id: 'ordem-da-aurora' },
    blueprint_id: 'rite-of-restoration', officiant_id: 'character:001',
    site_id: data.map.sites[0]!.id, settlement_id: 'pedraclara', stock_id: 'stock:test', account_id: 'account:test',
    started_day: 20, due_day: 25, target_settlement_id: null, route_id: null,
    sponsor_decision_id: 'event:2', officiant_decision_id: 'event:1' } as const
  data.research.rites = [
    { ...base, id: 'rite:pending', stage: 'officiating', last_event_id: 'event:3' },
    { ...base, id: 'rite:interrupted', stage: 'interrupted', last_event_id: 'event:4' },
    { ...base, id: 'rite:completed', stage: 'completed', last_event_id: 'event:5' },
  ]
  data.research.wards = [{ id: 'ward:rite:completed', rite_id: 'rite:completed',
    settlement_id: 'pedraclara', sponsor_ref: base.sponsor_ref, started_day: 25, until_day: 60,
    resistance_capability_id: 'standing_ward', last_event_id: 'event:6' }]
  store.snapshot = data
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ok:true,revision:1,
    data:{actor_ref:{kind:'character',id:'character:001'},entries:[],next_after:null,has_more:false}}))))
  const panel = mount(Inspector, { global: { plugins: [pinia, medievalI18n] } })
  try {
    await panel.findAll('nav button').find(b => b.text() === 'Pesquisa')!.trigger('click')
    expect(panel.text()).toContain('Doutrina é crença declarada')
    expect(panel.get('[data-rite-execution="rite:pending"]').text()).toContain('efeito ainda não confirmado')
    expect(panel.get('[data-rite-execution="rite:interrupted"]').text()).toContain('sem efeito concluído')
    const completed = panel.get('[data-rite-execution="rite:completed"]')
    expect(completed.text()).toContain('Execução material concluída')
    await completed.findAll('button')[0]!.trigger('click'); expect(store.focusEventId).toBe('event:1')
    await completed.findAll('button')[1]!.trigger('click'); expect(store.focusEventId).toBe('event:2')
    await completed.findAll('button')[2]!.trigger('click'); expect(store.focusEventId).toBe('event:5')
    const ward = panel.get('[data-ward="ward:rite:completed"]')
    expect(ward.text()).toContain('Proteção vigente')
    await ward.get('button').trigger('click'); expect(store.focusEventId).toBe('event:6')
    const expired = structuredClone(data); expired.world.day = 60; store.snapshot = expired
    await flushPromises()
    expect(ward.text()).toContain('Prazo da proteção encerrado')
    const incomplete = structuredClone(data)
    Object.assign(incomplete.research, { rites: undefined })
    expect(() => acceptSnapshot(incomplete)).toThrow('incompleto')
    await completed.findAll('button').find(b=>b.text()==='Inspecionar local do rito')!.trigger('click')
    expect(store.selection).toEqual({kind:'site',id:base.site_id})
    expect(panel.findAll('[data-rite-execution]')).toHaveLength(3)
    store.selection={kind:'site',id:data.map.sites.find(site=>site.id!==base.site_id)!.id}
    await flushPromises();expect(panel.findAll('[data-rite-execution]')).toHaveLength(0)
    store.selection={kind:'settlement',id:'pedraclara'}
    await flushPromises();expect(panel.findAll('[data-rite-execution]')).toHaveLength(3)
    await panel.get('[data-rite-execution="rite:completed"] [data-rite-officiant]').trigger('click')
    await flushPromises();expect(store.selection).toEqual({kind:'character',id:'character:001'})
    expect(panel.text()).toContain('Dossiê conhecido')
  } finally { panel.unmount();vi.unstubAllGlobals() }
})
