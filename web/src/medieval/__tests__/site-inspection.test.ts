import { expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import Inspector from '../components/Inspector.vue'
import { useObserverStore } from '../stores/world'
import { medievalI18n } from '../i18n'
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
