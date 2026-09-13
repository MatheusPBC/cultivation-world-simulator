import { expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import SupplyPlans from '../components/SupplyPlans.vue'
import { useObserverStore } from '../stores/world'
import { medievalI18n } from '../i18n'
import type { ObservatoryView } from '../../types/medieval-api'
import fixture from './world.json'

it('distinguishes reserve from in-transit promises and opens the canonical plan cause', async () => {
  const pinia = createPinia(); setActivePinia(pinia)
  const store = useObserverStore()
  const data = structuredClone(fixture) as unknown as ObservatoryView
  data.governance.plans = [{ id: 'plan:supply:portovelho', objective_id: 'supply:portovelho',
    stage: 'await_delivery', blocker: 'saldo insuficiente', order_ids: [], last_review_day: 60, last_event_id: 'event:120' }]
  store.snapshot = data
  const wrapper = mount(SupplyPlans, { global: { plugins: [pinia, medievalI18n] } })
  const plan = wrapper.get('[data-plan="plan:supply:portovelho"]')
  expect(plan.text()).toContain('Portovelho')
  expect(plan.text()).toContain('Aguardando entrega')
  expect(plan.text()).toContain('saldo insuficiente')
  expect(plan.text()).toContain('4.000')
  await plan.get('button').trigger('click')
  expect(store.focusEventId).toBe('event:120')
  wrapper.unmount()
})

it('shows the workshop resource and its own stock without interpreting iron as food', () => {
  const pinia = createPinia(); setActivePinia(pinia)
  const store = useObserverStore()
  const data = structuredClone(fixture) as unknown as ObservatoryView
  data.governance.objectives = [{ id: 'inputs:stock:oficios-da-serra:iron', actor_ref: { kind: 'organization', id: 'oficios-da-serra' },
    settlement_id: 'ferroalto', stock_id: 'stock:oficios-da-serra', resource_id: 'iron', kind: 'maintain_production_inputs',
    reserve_months: 2, motivation: 'Manter produção', target_quantity: 120 }]
  data.governance.plans = [{ id: 'plan:input', objective_id: data.governance.objectives[0]!.id,
    stage: 'await_delivery', blocker: null, order_ids: [], last_review_day: 30, last_event_id: 'event:1' }]
  store.snapshot = data
  const wrapper = mount(SupplyPlans, { global: { plugins: [pinia, medievalI18n] } })
  const plan = wrapper.get('[data-plan="plan:input"]')
  expect(plan.get('strong').text()).toBe('Ferro')
  expect(plan.text()).toContain('Insumos produtivos')
  expect(plan.text()).toContain('120')
  expect(plan.text()).toContain('60') // organization inventory, not public city's50iron/5400food
  expect(plan.text()).not.toContain('Rações')
  wrapper.unmount()
})

it('reveals the chosen route and only dated reports known by the plan actor', async () => {
  const pinia = createPinia(); setActivePinia(pinia)
  const store = useObserverStore()
  const data = structuredClone(fixture) as unknown as ObservatoryView
  const objective = data.governance.objectives.find(item => item.id === 'supply:portovelho')!
  const orderId = 'order:portovelho:food'
  const routeId = 'river-pedraclara-portovelho'
  data.governance.plans = [{ id: 'plan:portovelho', objective_id: objective.id,
    stage: 'await_delivery', blocker: null, order_ids: [orderId], last_review_day: 60, last_event_id: 'event:review' }]
  data.economy.pending_orders = [{ id: orderId, source_id: 'stock:pedraclara', destination_id: objective.stock_id,
    resource_id: objective.resource_id, quantity: 480, delivered_quantity: 0,
    owner_ref: { kind: 'polity', id: 'auren' }, route_ids: [routeId], created_day: 61,
    priority: 2, decision_ids: ['event:order-decision'], last_event_id: 'event:order' }]
  data.governance.route_reports = [
    { id: 'report:known', recipient_ref: objective.actor_ref, publisher_ref: { kind: 'polity', id: 'auren' },
      route_id: routeId, observed_day: 62, operational_capacity: 324, travel_days: 3,
      channel: 'route_bulletin', event_id: 'event:report' },
    { id: 'report:hidden', recipient_ref: { kind: 'polity', id: 'auren' }, publisher_ref: { kind: 'polity', id: 'auren' },
      route_id: 'road-brumafria-ferroalto', observed_day: 62, operational_capacity: 70, travel_days: 2,
      channel: 'route_bulletin', event_id: 'event:hidden' },
  ]
  store.snapshot = data
  const wrapper = mount(SupplyPlans, { global: { plugins: [pinia, medievalI18n] } })
  const plan = wrapper.get('[data-plan="plan:portovelho"]')
  expect(plan.get('[data-order="' + orderId + '"]').text()).toContain('Pedraclara → Portovelho')
  expect(plan.get('[data-route-segment="' + routeId + '"]').text()).toContain('Pedraclara — Portovelho')
  expect(plan.get('[data-route-segment="' + routeId + '"]').text()).toContain('Capacidade observada')
  expect(plan.get('[data-route-segment="' + routeId + '"]').text()).toContain('Ano 1')
  expect(plan.text()).not.toContain('road-brumafria-ferroalto')
  await plan.get('[data-order="' + orderId + '"] .text-button').trigger('click')
  expect(store.focusEventId).toBe('event:order-decision')
  wrapper.unmount()
})
