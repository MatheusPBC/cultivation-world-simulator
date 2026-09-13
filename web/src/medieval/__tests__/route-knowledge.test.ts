import { expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import Inspector from '../components/Inspector.vue'
import { useObserverStore } from '../stores/world'
import { medievalI18n } from '../i18n'
import type { ObservatoryView } from '../../types/medieval-api'
import fixture from './world.json'

const ROUTE = 'road-campomanso-pedraclara'

function inspectRoute(data: ObservatoryView) {
  const pinia = createPinia(); setActivePinia(pinia)
  const store = useObserverStore()
  store.snapshot = data
  store.selection = { kind: 'route', id: ROUTE }
  const wrapper = mount(Inspector, { global: { plugins: [pinia, medievalI18n] } })
  return { wrapper, store }
}

it('keeps the observed route capacity separate from the current canonical capacity', () => {
  const data = structuredClone(fixture) as unknown as ObservatoryView
  data.world.day = 10
  data.governance.route_reports = [{ id: 'route_report:polity:auren:' + ROUTE, recipient_ref: { kind: 'polity', id: 'auren' },
    publisher_ref: { kind: 'polity', id: 'auren' }, route_id: ROUTE, observed_day: 5, operational_capacity: 90,
    travel_days: 3, channel: 'administrative_route_report', event_id: 'event:1' }]
  const { wrapper } = inspectRoute(data)
  const canonical = wrapper.get('dl')
  expect(canonical.text()).toContain('162') // canonical operational_capacity from the map, untouched
  const report = wrapper.get('[data-route-report="route_report:polity:auren:' + ROUTE + '"]')
  expect(report.text()).toContain('90') // observed capacity, distinct from the canonical figure above
  expect(report.text()).toContain('Coroa de Auren')
  expect(report.text()).toContain('3')
  wrapper.unmount()
})

it('does not mix reports from another route or another recipient into the selected route', () => {
  const data = structuredClone(fixture) as unknown as ObservatoryView
  data.world.day = 10
  data.governance.route_reports = [
    { id: 'route_report:polity:auren:' + ROUTE, recipient_ref: { kind: 'polity', id: 'auren' },
      publisher_ref: { kind: 'polity', id: 'auren' }, route_id: ROUTE, observed_day: 8, operational_capacity: 100,
      travel_days: 2, channel: 'administrative_route_report', event_id: 'event:1' },
    { id: 'route_report:polity:escarlia:' + ROUTE, recipient_ref: { kind: 'polity', id: 'escarlia' },
      publisher_ref: { kind: 'polity', id: 'valedouro' }, route_id: 'road-brumafria-ferroalto', observed_day: 8,
      operational_capacity: 40, travel_days: 1, channel: 'route_bulletin', event_id: 'event:2' },
  ]
  const { wrapper } = inspectRoute(data)
  expect(wrapper.findAll('[data-route-report]')).toHaveLength(1)
  expect(wrapper.get('[data-route-report="route_report:polity:auren:' + ROUTE + '"]').text()).toContain('Coroa de Auren')
  wrapper.unmount()
})

it('marks an observation of 30 days or more as stale', () => {
  const data = structuredClone(fixture) as unknown as ObservatoryView
  data.world.day = 40
  data.governance.route_reports = [{ id: 'route_report:polity:auren:' + ROUTE, recipient_ref: { kind: 'polity', id: 'auren' },
    publisher_ref: { kind: 'polity', id: 'auren' }, route_id: ROUTE, observed_day: 10, operational_capacity: 90,
    travel_days: 3, channel: 'administrative_route_report', event_id: 'event:1' }]
  const { wrapper } = inspectRoute(data)
  const report = wrapper.get('[data-route-report="route_report:polity:auren:' + ROUTE + '"]')
  expect(report.text()).toContain('desatualizada')
  wrapper.unmount()
})

it('leaves an absent report as unknown, never inferring institutional knowledge from the canonical map', () => {
  const data = structuredClone(fixture) as unknown as ObservatoryView
  data.world.day = 40
  data.governance.route_reports = [] // no institution observed or was told about this route
  const { wrapper } = inspectRoute(data)
  expect(wrapper.findAll('[data-route-report]')).toHaveLength(0)
  expect(wrapper.text()).toContain('Nenhuma instituição observou ou recebeu boletim sobre esta rota.')
  expect(wrapper.text()).not.toContain('90') // no observed value invented from the canonical 162
  wrapper.unmount()
})

it('opens the canonical receipt event when a report source is clicked', async () => {
  const data = structuredClone(fixture) as unknown as ObservatoryView
  data.world.day = 10
  data.governance.route_reports = [{ id: 'route_report:polity:auren:' + ROUTE, recipient_ref: { kind: 'polity', id: 'auren' },
    publisher_ref: { kind: 'polity', id: 'auren' }, route_id: ROUTE, observed_day: 5, operational_capacity: 90,
    travel_days: 3, channel: 'administrative_route_report', event_id: 'event:77' }]
  const { wrapper, store } = inspectRoute(data)
  const report = wrapper.get('[data-route-report="route_report:polity:auren:' + ROUTE + '"]')
  await report.get('button').trigger('click')
  expect(store.focusEventId).toBe('event:77')
  wrapper.unmount()
})

it('shows dated fiscal route knowledge separately from the canonical route state', async () => {
  const data = structuredClone(fixture) as unknown as ObservatoryView
  data.world.day = 40
  data.economy.customs_checkpoints = [{ id: 'customs:passagem-negra', site_id: 'passagem-negra',
    operator_ref: { kind: 'polity', id: 'auren' }, account_id: 'account:auren', staff_group_id: 'staff:auren',
    staff_count: 2, fee_per_bulk: 7, started_day: 1, last_staffed_day: 40, inspection_day: 40,
    inspection_slots_used: 0, last_event_id: 'event:checkpoint' }]
  data.governance.fiscal_route_reports = [{ id: 'fiscal_route_report:polity:auren:' + ROUTE,
    recipient_ref: { kind: 'polity', id: 'auren' }, publisher_ref: { kind: 'polity', id: 'auren' }, route_id: ROUTE,
    observed_day: 10, checkpoint_id: 'customs:passagem-negra', fee_per_bulk: 7,
    channel: 'administrative_fiscal_route_report', event_id: 'event:fiscal-1' }]
  const { wrapper, store } = inspectRoute(data)
  const report = wrapper.get('[data-fiscal-route-report="fiscal_route_report:polity:auren:' + ROUTE + '"]')
  expect(report.text()).toContain('Passagem Negra')
  expect(report.text()).toContain('7')
  expect(report.text()).toContain('desatualizada')
  await report.get('button').trigger('click')
  expect(store.focusEventId).toBe('event:fiscal-1')
  wrapper.unmount()
})
