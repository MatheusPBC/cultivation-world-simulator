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
