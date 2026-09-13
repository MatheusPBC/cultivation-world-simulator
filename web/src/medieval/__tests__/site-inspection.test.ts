import { expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import Inspector from '../components/Inspector.vue'
import { useObserverStore } from '../stores/world'
import { medievalI18n } from '../i18n'
import { acceptSnapshot } from '../mappers'
import type { ObservatoryView } from '../../types/medieval-api'
import fixture from './world.json'

const SITE = 'campos-do-lume'

function inspectSite(data: ObservatoryView) {
  const pinia = createPinia(); setActivePinia(pinia)
  const store = useObserverStore()
  store.snapshot = data
  store.selection = { kind: 'site', id: SITE }
  const wrapper = mount(Inspector, { global: { plugins: [pinia, medievalI18n] } })
  return { wrapper, store }
}

it('shows the maintainer distinctly from the owner, without inferring one from the other', () => {
  const data = structuredClone(fixture) as unknown as ObservatoryView
  const site = data.map.sites.find(s => s.id === SITE)!
  site.owner_ref = { kind: 'polity', id: 'auren' }
  site.maintainer_ref = { kind: 'organization', id: 'oficios-da-serra' }
  const { wrapper } = inspectSite(data)
  const detail = wrapper.get('dl')
  expect(detail.text()).toContain('Coroa de Auren')
  expect(detail.text()).toContain('Companhia dos Ofícios da Serra')
  wrapper.unmount()
})

it('leaves an absent maintainer unknown instead of falling back to the owner', () => {
  const data = structuredClone(fixture) as unknown as ObservatoryView
  const site = data.map.sites.find(s => s.id === SITE)!
  site.owner_ref = { kind: 'polity', id: 'auren' }
  site.maintainer_ref = null
  const { wrapper } = inspectSite(data)
  const detail = wrapper.get('dl')
  expect(detail.text()).toContain('Coroa de Auren')
  expect(detail.text()).toContain('Sem responsável')
  wrapper.unmount()
})

it('keeps the current material-change source navigable regardless of the maintainer shown', async () => {
  const data = structuredClone(fixture) as unknown as ObservatoryView
  const site = data.map.sites.find(s => s.id === SITE)!
  site.maintainer_ref = { kind: 'organization', id: 'oficios-da-serra' }
  site.last_event_id = 'event:77'
  const { wrapper, store } = inspectSite(data)
  await wrapper.get('.inspector-body button').trigger('click')
  expect(store.focusEventId).toBe('event:77')
  wrapper.unmount()
})

it('shows accumulated repair work as raw permille, never as a bounded 0-100% bar', () => {
  const data = structuredClone(fixture) as unknown as ObservatoryView
  data.economy.repair_blueprints = [{ id: 'repair:farm', name: 'Reparo de fazenda', site_kind: 'farm',
    inputs: { wood: 4, stone: 2, tools: 1 }, workers: 3, wage_per_worker: 1, restored_permille: 100 }]
  data.economy.repairs = [{ id: 'repair:event:9', site_id: SITE, blueprint_id: 'repair:farm',
    maintainer_ref: { kind: 'polity', id: 'auren' }, stock_id: 'stock:campomanso', account_id: 'treasury:auren',
    decision_event_id: 'event:9', started_day: 10, restored_permille: 1240, last_work_day: 40,
    stage: 'repairing', blocker: null, last_event_id: 'event:41' }]
  const { wrapper } = inspectSite(data)
  const card = wrapper.get('[data-repair="repair:event:9"]')
  expect(card.text()).toContain('1240') // accumulated work exceeds 1000; not clamped or read as a percentage
  expect(card.text()).toContain('100') // blueprint's own per-batch restoration rate, distinct from the total above
  expect(card.text()).toContain('Madeira')
  expect(card.text()).toContain('Madeira: 4, Pedra: 2, Ferramentas: 1')
  expect(card.find('progress').exists()).toBe(false)
  wrapper.unmount()
})

it('shows the maintainer\'s own dated observation distinct from the canonical integrity, and marks it stale after 30 days', async () => {
  const data = structuredClone(fixture) as unknown as ObservatoryView
  data.world.day = 40
  const site = data.map.sites.find(s => s.id === SITE)!
  site.integrity = 1
  site.service_suspended = true
  site.maintainer_ref = { kind: 'polity', id: 'auren' }
  data.governance.site_reports = [{ id: 'site_report:polity:auren:' + SITE, recipient_ref: { kind: 'polity', id: 'auren' },
    publisher_ref: { kind: 'polity', id: 'auren' }, site_id: SITE, observed_day: 5, integrity: 0.4, enabled: false, service_suspended: true,
    channel: 'administrative_site_report', event_id: 'event:55' }]
  const { wrapper, store } = inspectSite(data)
  expect(wrapper.get('dl').text()).toContain('100%') // canonical integrity, untouched
  expect(wrapper.get('dl').text()).toContain('Serviço suspenso pelo proprietário')
  const report = wrapper.get('[data-site-report="site_report:polity:auren:' + SITE + '"]')
  expect(report.text()).toContain('40%') // maintainer's stale observed integrity, distinct from the canonical 100% above
  expect(report.text()).toContain('desatualizada')
  await report.get('button').trigger('click')
  expect(store.focusEventId).toBe('event:55')
  wrapper.unmount()
})

it('projects a civil checkpoint separately from physical site state and exposes its causal source', async () => {
  const data = structuredClone(fixture) as unknown as ObservatoryView
  const site = data.map.sites.find(s => s.id === SITE)!
  site.integrity = 0.42
  site.enabled = false
  site.service_suspended = true
  data.economy.customs_checkpoints = [{ id: 'checkpoint:campos', site_id: SITE,
    operator_ref: { kind: 'polity', id: 'auren' }, account_id: 'treasury:auren', staff_group_id: 'pop:campomanso:human:artisan',
    staff_count: 3, fee_per_bulk: 2, started_day: 4, last_staffed_day: 30, inspection_day: 30, inspection_slots_used: 1,
    last_event_id: 'event:checkpoint' }]
  const { wrapper, store } = inspectSite(data)
  const card = wrapper.get('[data-checkpoint="checkpoint:campos"]')
  expect(wrapper.get('dl').text()).toContain('Serviço suspenso pelo proprietário')
  expect(card.text()).toContain('Com pessoal')
  expect(card.text()).toContain('2')
  await card.get('button').trigger('click')
  expect(store.focusEventId).toBe('event:checkpoint')
  wrapper.unmount()
})

it('rejects a customs record with missing required metadata before rendering', () => {
  const data = structuredClone(fixture)
  const checkpoint = { ...data.economy.customs_checkpoints, staff_count: 1 }
  const incomplete = { ...data, economy: { ...data.economy, customs_checkpoints: [checkpoint] } }
  expect(() => acceptSnapshot(incomplete as unknown as ObservatoryView)).toThrow('fiscalização')
})

it('renders a held parcel and its notice without assuming a notice exists', async () => {
  const data = structuredClone(fixture) as unknown as ObservatoryView
  data.economy.pending_orders = [{ id: 'order:held', source_id: 'campomanso', destination_id: 'portovelho', resource_id: 'food',
    quantity: 10, delivered_quantity: 0, owner_ref: { kind: 'polity', id: 'auren' }, route_ids: [], created_day: 1,
    priority: 1, decision_ids: ['event:order'], last_event_id: 'event:order' }]
  data.economy.parcels = [{ id: 'parcel:held', order_id: 'order:held', quantity: 10, route_index: 0, stage: 'held', due_day: 8,
    held_checkpoint_id: 'checkpoint:portovelho', held_notice_id: null, last_event_id: 'event:held' }]
  data.economy.cargo_manifests = [{ id: 'cargo_manifest:parcel:held', checkpoint_id: 'checkpoint:portovelho', parcel_id: 'parcel:held',
    order_id: 'order:held', owner_ref: { kind: 'polity', id: 'auren' }, resource_id: 'food', quantity: 10, declared_day: 8,
    event_id: 'event:manifest' }]
  const { wrapper, store } = inspectSite(data)
  await wrapper.findAll('.inspector-tabs button')[3]!.trigger('click')
  expect(wrapper.text()).toContain('Carga retida no posto')
  expect(wrapper.text()).toContain('checkpoint:portovelho')
  data.governance.customs_notices = [{ id: 'notice:held', parcel_id: 'parcel:held', checkpoint_id: 'checkpoint:portovelho',
    order_id: 'order:held', recipient_ref: { kind: 'polity', id: 'auren' }, resource_id: 'food', quantity: 10,
    fee: 20, event_id: 'event:notice', state_event_id: 'event:notice', learned_day: 8, state: 'fee_due', manifest_id: 'cargo_manifest:parcel:held',
    channel: 'direct_customs_notice' }]
  store.snapshot = structuredClone(data)
  await nextTick()
  expect(wrapper.text()).toContain('20')
  expect(wrapper.text()).toContain('Taxa devida')
  expect(wrapper.text()).toContain('Declaração apresentada')
  await wrapper.get('[data-notice-source="notice:held"]').trigger('click')
  expect(store.focusEventId).toBe('event:notice')
  wrapper.unmount()
})

it('requires the canonical cargo manifest collection in every snapshot', () => {
  const data = structuredClone(fixture) as unknown as ObservatoryView
  const { cargo_manifests: _ignored, ...economy } = data.economy
  expect(() => acceptSnapshot({ ...data, economy } as unknown as ObservatoryView)).toThrow('incompleto')
})

it('rejects an evasion attempt as a transient state instead of a persisted notice state', () => {
  const data = structuredClone(fixture) as unknown as ObservatoryView
  data.governance.customs_notices = [{ id: 'notice:transient', parcel_id: 'parcel:held', checkpoint_id: 'checkpoint:portovelho',
    order_id: 'order:held', recipient_ref: { kind: 'polity', id: 'auren' }, resource_id: 'food', quantity: 10,
    fee: 20, event_id: 'event:notice', learned_day: 8, state: 'evasion_attempted', cleared_event_id: null,
    channel: 'direct_customs_notice' } as never]
  expect(() => acceptSnapshot(data)).toThrow('fiscalização')
})
