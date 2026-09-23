import { expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import Inspector from '../components/Inspector.vue'
import { medievalI18n } from '../i18n'
import { useObserverStore } from '../stores/world'
import type { ObservatoryView } from '../../types/medieval-api'
import fixture from './world.json'

it('links a defensive plan to its current offices, material column and causal source', async () => {
  const data = structuredClone(fixture) as unknown as ObservatoryView
  data.world.day = 12
  data.governance.offices.push(
    { id: 'office:policy', institution_ref: { kind: 'polity', id: 'auren' },
      holder_ref: { kind: 'character', id: 'character:001' }, scopes: ['policy'], starts_day: 1, ends_day: null },
    { id: 'office:hq', institution_ref: { kind: 'polity', id: 'auren' },
      holder_ref: { kind: 'character', id: 'character:002' }, scopes: ['operations'], starts_day: 1, ends_day: null },
    { id: 'office:former', institution_ref: { kind: 'polity', id: 'auren' },
      holder_ref: { kind: 'character', id: 'character:003' }, scopes: ['policy'], starts_day: 1, ends_day: 10 },
  )
  data.governance.objectives.push({ id: 'objective:defense', actor_ref: { kind: 'polity', id: 'auren' },
    settlement_id: 'campomanso', stock_id: 'stock:campomanso', resource_id: 'food',
    kind: 'defend_occupied_settlement', garrison_id: null, reserve_months: 2,
    motivation: 'Ocupação observada.', target_quantity: 0 })
  data.governance.plans.push({ id: 'plan:defense', objective_id: 'objective:defense', stage: 'mobilized',
    order_ids: [], detachment_id: 'detachment:1', blocker: null, last_review_day: 11, last_event_id: 'event:plan' })
  data.campaigns.detachments.push({ id: 'detachment:1', owner_ref: { kind: 'polity', id: 'auren' },
    source_group_id: 'pop:campomanso:human:soldier', count: 12, location_id: 'campomanso',
    destination_id: 'campomanso', route_ids: [], route_index: 0, provisions: 30,
    stage: 'present', started_day: 11, due_day: 11, decision_event_id: 'event:hq', last_event_id: 'event:force' })
  const pinia = createPinia(); setActivePinia(pinia)
  const store = useObserverStore()
  store.snapshot = data
  store.selection = { kind: 'polity', id: 'auren' }
  const wrapper = mount(Inspector, { global: { plugins: [pinia, medievalI18n] } })

  const mandate = wrapper.get('details.route-knowledge')
  expect(mandate.get('[data-military-office="office:policy"]').text()).toContain('Kaela Valverde')
  expect(mandate.get('[data-military-office="office:hq"]').text()).toContain('Fenn Pedralume')
  expect(mandate.find('[data-military-office="office:former"]').exists()).toBe(false)
  const plan = mandate.get('[data-defense-plan="plan:defense"]')
  expect(plan.text()).toContain('Coluna mobilizada')
  await plan.get('button:not(.link-row)').trigger('click')
  expect(store.focusEventId).toBe('event:plan')
  await plan.get('button.link-row').trigger('click')
  expect(store.selection).toEqual({ kind: 'detachment', id: 'detachment:1' })
  expect(wrapper.get('[data-detachment-plan="plan:defense"]').text()).toContain('Coluna mobilizada')
  wrapper.unmount()
})
