import { expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import IncomePanel from '../components/IncomePanel.vue'
import { medievalI18n } from '../i18n'
import { useObserverStore } from '../stores/world'
import { acceptSnapshot } from '../mappers'
import type { ObservatoryView } from '../../types/medieval-api'
import fixture from './world.json'

it('shows export tariff as a sale tariff and opens its policy source', async () => {
  const pinia = createPinia(); setActivePinia(pinia)
  const store = useObserverStore()
  const data = structuredClone(fixture) as unknown as ObservatoryView
  data.governance.tax_policies[0].export_rate_permille = 125
  data.governance.tax_policies[0].export_policy_event_id = 'event:export-policy'
  store.snapshot = data
  const panel = mount(IncomePanel, { global: { plugins: [pinia, medievalI18n] } })
  const policy = panel.get('.stock-card')
  expect(policy.text()).toContain('Tarifa de exportação: 12,5%')
  expect(panel.text()).toContain('não é cobrança por passagem')
  await policy.get('[data-testid="export-policy-source"]').trigger('click')
  expect(store.focusEventId).toBe('event:export-policy')
  panel.unmount()
})

it('rejects a financial snapshot without the required export rate', () => {
  const data = structuredClone(fixture)
  const policy = { ...data.governance.tax_policies[0] }
  delete (policy as { export_rate_permille?: number }).export_rate_permille
  const incomplete = { ...data, governance: { ...data.governance, tax_policies: [policy, ...data.governance.tax_policies.slice(1)] } }
  expect(() => acceptSnapshot(incomplete as unknown as ObservatoryView)).toThrow('política de exportação')
})

it('rejects a report without export policy metadata instead of dereferencing undefined', () => {
  const data = structuredClone(fixture)
  const report = {
    id: 'report:test', recipient_ref: { kind: 'polity', id: 'auren' },
    publisher_ref: { kind: 'polity', id: 'auren' }, stock_id: 'stock:pedraclara', resource_id: 'food',
    kind: 'inventory', channel: 'administrative_report', observed_day: 0, quantity: 100,
    population: 2400, unit_price: 4, quote_day: 0, event_id: 'event:test',
  }
  data.governance.reports = [report]
  expect(() => acceptSnapshot(data as unknown as ObservatoryView)).toThrow('política de exportação')
})
