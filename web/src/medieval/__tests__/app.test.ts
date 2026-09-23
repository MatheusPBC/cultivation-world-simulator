import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia } from 'pinia'
import App from '../ObserverApp.vue'
import { medievalI18n } from '../i18n'
import { useObserverStore } from '../stores/world'
import fixture from './world.json'

let wrapper: VueWrapper | undefined
let data = structuredClone(fixture)
let ready = false
let saved: typeof data | null = null
const posts: { name: string; body: Record<string, unknown> }[] = []
beforeEach(() => {
  vi.useRealTimers(); ready = false; saved = null; data = structuredClone(fixture); posts.length = 0
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const path = url.split('?')[0].split('/').pop()
    if (init?.method === 'POST') {
      const body = JSON.parse(init.body as string)
      posts.push({ name: path!, body })
      if (path === 'create') ready = true
      if (path === 'step') { data.world.day += 30; data.status.day = data.world.day }
      if (path === 'save') saved = structuredClone(data)
      if (path === 'load' && saved) data = structuredClone(saved)
      return reply({ ...data.status, ready })
    }
    if (path === 'status') return reply({ ...data.status, ready })
    if (path === 'options') return reply({ defaults: data.world.config, map_id: data.map.map_id, map_name: data.map.name, ai_available: false })
    if (path === 'observatory') return reply({ ...data, status: { ...data.status, ready } })
    if (path === 'events') return reply({ items: [], next_after: 0, has_more: false })
    if (path === 'saves') return reply(saved ? [{ save_id: 'teste', day: saved.world.day, compatible: true, size_bytes: 4000, modified_at: '2026-09-13T00:00:00Z' }] : [])
    throw new Error('Unexpected API request: ' + url)
  }))
})
afterEach(() => { wrapper?.unmount(); vi.unstubAllGlobals() })
const reply = (value: unknown) => new Response(JSON.stringify({ ok: true, revision: 1, data: value }))
async function open() {
  wrapper = mount(App, { global: { plugins: [createPinia(), medievalI18n] } })
  await flushPromises(); return wrapper
}
it('creates twelve relevant characters and advances the displayed canonical date', async () => {
  const app = await open()
  expect(app.find('input[name="character_count"]').element).toHaveProperty('value', '12')
  await app.get('form[data-testid="create-world"]').trigger('submit')
  await flushPromises()
  expect(posts[0]).toEqual({ name: 'create', body: { seed: 73, character_count: 12, replace: false } })
  expect(app.text()).toContain('10.900')
  await app.get('[data-testid="step"]').trigger('click'); await flushPromises()
  expect(app.get('[data-testid="absolute-day"]').text()).toContain('30')
})
it('opens a settlement from the accessible map list and shows material state', async () => {
  ready = true
  const app = await open()
  await app.get('[data-settlement="pedraclara"]').trigger('click')
  expect(app.get('[data-testid="inspector"]').text()).toContain('Pedraclara')
  expect(app.get('[data-testid="inspector"]').text()).toContain('2.400')
  expect(app.get('[data-testid="inspector"]').text()).toContain('Saúde')
})
it('exposes the canonical campaign layer in the atlas', async () => {
  ready = true
  const app = await open()
  expect(app.text()).toContain('Campanhas')
})
it('shows active canonical threats with a navigable source', async () => {
  ready = true
  data.campaigns.threats = [{ id: 'siege:1', kind: 'siege', settlement_id: 'pedraclara', route_id: null, site_id: null,
    severity: 'high', status: 'breached', source_event_id: 'event:88' }]
  const app = await open()
  expect(app.get('[aria-label="Ameaças ativas"]').text()).toContain('Cerco')
  expect(app.get('[data-threat="siege:1"]').text()).toContain('Alta urgência')
  expect(app.get('[data-threat="siege:1"]').text()).toContain('Pedraclara')
  await app.get('[data-threat="siege:1"] button').trigger('click')
  expect(useObserverStore().focusEventId).toBe('event:88')
})
it('shows live political settlements with their canonical source', async () => {
  ready = true
  data.campaigns.political_settlements = [{ id: 'proposal:concession', proposal_kind: 'administration_concession',
    settlement_id: 'pedraclara',
    proposer_ref: { kind: 'polity', id: 'escarlia' }, counterparty_ref: { kind: 'polity', id: 'auren' },
    status: 'accepted', offered_day: 30, expires_day: 33, clause_kinds: ['administration_transfer', 'withdrawal'],
    decision_event_id: 'event:90', last_event_id: 'event:91' }]
  const app = await open()
  const row = app.get('[data-political-settlement="proposal:concession"]')
  expect(row.text()).toContain('Concessão administrativa')
  expect(row.text()).toContain('Aceita; aguardando execução')
  await row.get('button').trigger('click')
  expect(useObserverStore().focusEventId).toBe('event:91')
})
it('selects a canonical detachment and exposes its military chain and sources', async () => {
  ready = true
  const commander = data.society.characters[0].id
  data.campaigns.detachments = [{ id: 'detachment:auren:1', owner_ref: { kind: 'polity', id: 'auren' }, source_group_id: 'pop:pedraclara:human:soldier', count: 120, location_id: 'pedraclara', destination_id: 'portovelho', route_ids: ['road:pedraclara-portovelho'], route_index: 0, provisions: 18, stage: 'marching', started_day: 12, due_day: 28, decision_event_id: 'event:detachment-decision', last_event_id: 'event:detachment-last' }]
  data.campaigns.commands = [{ id: 'command:1', detachment_id: 'detachment:auren:1', character_id: commander, institution_ref: { kind: 'polity', id: 'auren' }, office_id: 'office:marshal', doctrine: 'hold', doctrine_effective_day: 12, previous_doctrine: null, appointed_day: 12, last_event_id: 'event:command' }]
  data.campaigns.positions = [{ id: 'position:1', detachment_id: 'detachment:auren:1', stage: 'prepared', settlement_id: 'pedraclara', anchor_site_id: null, started_day: 12, ready_day: 20, last_event_id: 'event:position' }]
  data.campaigns.standoffs = [{ id: 'standoff:1', detachment_ids: ['detachment:auren:1', 'detachment:enemy:1'], settlement_id: 'pedraclara', started_day: 20, started_event_id: 'event:standoff-start', stage: 'active', resolved_day: null, last_event_id: 'event:standoff-last' }]
  data.campaigns.route_interdictions = [{ id: 'interdiction:1', actor_ref: { kind: 'polity', id: 'auren' }, detachment_id: 'detachment:auren:1', route_id: 'road:pedraclara-portovelho', settlement_id: 'pedraclara', investment_id: null, started_day: 20, decision_event_id: 'event:interdiction-decision', stage: 'active', lifted_day: null, last_event_id: 'event:interdiction-last' }]
  const app = await open()
  await app.get('[data-detachment="detachment:auren:1"]').trigger('click')
  const inspector = app.get('[data-testid="inspector"]')
  expect(inspector.text()).toContain('Destacamentos')
  expect(inspector.text()).toContain('120')
  expect(inspector.text()).toContain('Em marcha')
  expect(inspector.text()).toContain('Manter posição')
  expect(inspector.text()).toContain('Confronto')
  expect(inspector.text()).toContain('Interdição de rota')
  await inspector.get('[data-testid="detachment-decision-source"]').trigger('click')
  expect(useObserverStore().focusEventId).toBe('event:detachment-decision')
})
it('shows institutional capacity as a derived Dao read model', async () => {
  ready = true
  ;(data.governance as any).strategic_capacity = [{
    actor_ref: { kind: 'polity', id: 'auren' },
    dimensions: {
      diplomatic_bandwidth: { status: 'committed', objective_ids: [], plan_ids: [], source_ids: ['proposal:1'] },
      logistics_capacity: { status: 'unavailable', objective_ids: [], plan_ids: [], source_ids: [] },
    },
  }]
  const app = await open()
  expect(app.text()).toContain('Capacidades em curso')
  expect(app.text()).toContain('Diplomacia')
  expect(app.text()).toContain('em curso')
})
it('keeps provider outcomes, missing affordances and stale affordances visibly distinct', async () => {
  ready = true
  data.world.decision_sources = {
    provider_consultations: 2,
    provider_declines: 3,
    provider_failures: 4,
    no_affordance_receipts: 5,
    stale_affordance_receipts: 6,
    ai_enabled: false,
  }
  const app = await open()
  const strip = app.get('[aria-label="Rastro das decisões"]')
  expect(strip.text()).toContain('2 consultas concluídas')
  expect(strip.text()).toContain('3 recusas')
  expect(strip.text()).toContain('4 falhas técnicas')
  expect(strip.text()).toContain('5 sem affordance')
  expect(strip.text()).toContain('6 affordances obsoletas')
})
it('loads the saved date through the real save panel workflow', async () => {
  ready = true
  const app = await open()
  await app.get('[data-testid="open-saves"]').trigger('click'); await flushPromises()
  await app.get('input[name="save_id"]').setValue('teste')
  await app.get('form[data-testid="save-world"]').trigger('submit'); await flushPromises()
  expect(posts.at(-1)).toEqual({ name: 'save', body: { save_id: 'teste', overwrite: false } })
  await app.get('[data-testid="close-saves"]').trigger('click')
  await app.get('[data-testid="step"]').trigger('click'); await flushPromises()
  await app.get('[data-testid="open-saves"]').trigger('click'); await flushPromises()
  await app.get('[data-load="teste"]').trigger('click'); await flushPromises()
  await app.get('[data-testid="confirm-load"]').trigger('click'); await flushPromises()
  expect(app.get('[data-testid="absolute-day"]').text()).toContain('0')
})
it('shows connection failure and keeps the last date, not a fake successful step', async () => {
  ready = true
  const app = await open()
  vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('offline') }))
  await app.get('[data-testid="step"]').trigger('click'); await flushPromises()
  expect(app.get('[role="alert"]').text()).toContain('Sem conexão')
  expect(app.get('[data-testid="absolute-day"]').text()).toContain('0')
})
