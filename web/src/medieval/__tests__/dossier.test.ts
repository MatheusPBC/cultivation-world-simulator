import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import Inspector from '../components/Inspector.vue'
import { medievalI18n } from '../i18n'
import { useObserverStore } from '../stores/world'
import type { ObservatoryView } from '../../types/medieval-api'
import fixture from './world.json'

it('loads the selected character dossier and navigates to its source event', async () => {
  const pinia = createPinia(); setActivePinia(pinia)
  const store = useObserverStore()
  store.snapshot = structuredClone(fixture) as unknown as ObservatoryView
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    expect(url).toContain('/api/v2/query/dossier/character/')
    return new Response(JSON.stringify({ ok: true, revision: 4, data: {
      actor_ref: { kind: 'character', id: 'character:001' },
      entries: [{ category: 'known_fact', id: 'fact:event:42', event_id: 'event:42', learned_day: 30,
        cause_event_ids: [], causal_depth: 0, payload: { content: 'A ponte foi danificada.' } }],
    } }))
  }))
  const panel = mount(Inspector, { global: { plugins: [pinia, medievalI18n] } })
  store.selection = { kind: 'character', id: 'character:001' }
  await flushPromises()
  const entry = panel.get('[data-dossier-entry="fact:event:42"]')
  expect(entry.text()).toContain('A ponte foi danificada.')
  await entry.get('button').trigger('click')
  expect(store.focusEventId).toBe('event:42')
  panel.unmount(); vi.unstubAllGlobals()
})

it('selects a polity from governments, loads its dossier, and navigates to a source event', async () => {
  const pinia = createPinia(); setActivePinia(pinia)
  const store = useObserverStore()
  store.snapshot = structuredClone(fixture) as unknown as ObservatoryView
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    expect(url).toContain('/api/v2/query/dossier/polity/auren')
    return new Response(JSON.stringify({ ok: true, revision: 5, data: {
      actor_ref: { kind: 'polity', id: 'auren' },
      entries: [
        { category: 'strategic_objective', id: 'objective:auren:food', event_id: 'event:objective', learned_day: null,
          cause_event_ids: [], causal_depth: 0, payload: { kind: 'maintain_food_reserve', resource_id: 'food' } },
        { category: 'strategic_plan', id: 'plan:auren:food', event_id: 'event:plan', learned_day: null,
          cause_event_ids: [], causal_depth: 0, payload: { stage: 'acquire', objective_id: 'objective:auren:food' } },
        { category: 'institutional_memory', id: 'memory:auren:event:42', event_id: 'event:42', learned_day: 42,
          cause_event_ids: [], causal_depth: 1, payload: { content: 'Escarlia recusou ajuda.' } },
      ],
    } }))
  }))
  const panel = mount(Inspector, { global: { plugins: [pinia, medievalI18n] } })
  await panel.findAll('.inspector-tabs button')[2]!.trigger('click')
  await panel.get('[data-polity="auren"] button').trigger('click')
  await flushPromises()
  expect(panel.text()).toContain('Coroa de Auren')
  expect(panel.text()).toContain('Objetivo estratégico')
  expect(panel.text()).toContain('Plano estratégico')
  expect(panel.text()).toContain('Memória institucional')
  const entry = panel.get('[data-dossier-entry="memory:auren:event:42"]')
  expect(entry.text()).toContain('Escarlia recusou ajuda.')
  await entry.get('button').trigger('click')
  expect(store.focusEventId).toBe('event:42')
  panel.unmount(); vi.unstubAllGlobals()
})

it('selects an organization from governments, loads its dossier, and navigates to a source event', async () => {
  const pinia = createPinia(); setActivePinia(pinia)
  const store = useObserverStore()
  store.snapshot = structuredClone(fixture) as unknown as ObservatoryView
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    expect(url).toContain('/api/v2/query/dossier/organization/casa-alvor')
    return new Response(JSON.stringify({ ok: true, revision: 6, data: {
      actor_ref: { kind: 'organization', id: 'casa-alvor' },
      entries: [{ category: 'known_fact', id: 'fact:event:organization', event_id: 'event:organization', learned_day: 12,
        cause_event_ids: [], causal_depth: 0, payload: { content: 'A Casa Alvor recebeu um pedido de proteção.' } }],
    } }))
  }))
  const panel = mount(Inspector, { global: { plugins: [pinia, medievalI18n] } })
  await panel.findAll('.inspector-tabs button')[2]!.trigger('click')
  await panel.get('[data-organization="casa-alvor"] button').trigger('click')
  await flushPromises()
  expect(panel.text()).toContain('Casa Alvor')
  const entry = panel.get('[data-dossier-entry="fact:event:organization"]')
  expect(entry.text()).toContain('pedido de proteção')
  await entry.get('button').trigger('click')
  expect(store.focusEventId).toBe('event:organization')
  panel.unmount(); vi.unstubAllGlobals()
})
