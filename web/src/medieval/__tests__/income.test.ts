import { expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import IncomePanel from '../components/IncomePanel.vue'
import { useObserverStore } from '../stores/world'
import { medievalI18n } from '../i18n'
import type { ObservatoryView } from '../../types/medieval-api'
import fixture from './world.json'

it('separates accumulated savings from dated wages and opens payroll evidence', async () => {
  const pinia = createPinia(); setActivePinia(pinia)
  const store = useObserverStore()
  const data = structuredClone(fixture) as unknown as ObservatoryView
  data.economy.accounts.find(a => a.owner_ref.kind === 'population_group')!.balance = 1234
  const workers = data.society.population_groups.find(g => g.settlement_id === 'campomanso' && g.occupation === 'farmer')!
  data.economy.payrolls = [{ id: 'works:campos-do-lume', day: 30, wage_per_worker: 2,
    workers_by_group: { [workers.id]: 20 }, gross: 40, tax: 4, last_event_id: 'event:123' }]
  store.snapshot = data
  const panel = mount(IncomePanel, { global: { plugins: [pinia, medievalI18n] } })
  expect(panel.get('[data-testid="household-savings"]').text()).toContain('1.234')
  const receipt = panel.get('[data-payroll="works:campos-do-lume"]')
  expect(receipt.text()).toContain('Campos do Lume')
  expect(receipt.text()).toContain('Dia absoluto 30')
  expect(receipt.get('[data-testid="gross"]').text()).toBe('40')
  expect(receipt.get('[data-testid="tax"]').text()).toBe('4')
  expect(receipt.get('[data-testid="net"]').text()).toBe('36')
  expect(panel.text()).toContain('10%')
  await receipt.get('button').trigger('click')
  expect(store.focusEventId).toBe('event:123')
  panel.unmount()
})

it('rejects snapshots that omit financial registries instead of breaking the panel later', async () => {
  const { acceptSnapshot } = await import('../mappers')
  const data = structuredClone(fixture)
  const { payrolls, ...incomplete } = data.economy
  expect(payrolls).toEqual([])
  expect(() => acceptSnapshot({ ...data, economy: incomplete } as unknown as ObservatoryView)).toThrow('incompleto')
})
