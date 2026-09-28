import { expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import IncomePanel from '../components/IncomePanel.vue'
import { useObserverStore } from '../stores/world'
import { medievalI18n } from '../i18n'
import type { ObservatoryView } from '../../types/medieval-api'
import fixture from './world.json'

it('opens the causal source for an employer staffing-target decision', async () => {
  const pinia = createPinia(); setActivePinia(pinia)
  const store = useObserverStore()
  const data = structuredClone(fixture) as unknown as ObservatoryView
  data.economy.employment_contracts = [{ id: 'employment:1', employer_ref: { kind: 'polity', id: 'auren' },
    settlement_id: 'campomanso', cohort_id: 'population:artisan', work_site_id: 'site:1', occupation: 'artisan',
    stock_id: 'stock:campomanso', account_id: 'account:auren', workforce_limit: 20, staffing_target: 10,
    staffing_event_id: 'event:staffing-target', wage_per_worker: 2, created_day: 1,
    decision_event_id: 'event:decision', selected_affordance_id: 'affordance:1', created_event_id: 'event:created',
    last_reviewed_day: 30, last_outcome: 'paid', last_event_id: 'event:payroll' }]
  store.snapshot = data
  const panel = mount(IncomePanel, { global: { plugins: [pinia, medievalI18n] } })
  await panel.get('[data-testid="staffing-source"]').trigger('click')
  expect(store.focusEventId).toBe('event:staffing-target')
  panel.unmount()
})

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

it('shows local food beside artisan purchasing money without treating stock as income', async () => {
  const pinia = createPinia(); setActivePinia(pinia)
  const store = useObserverStore()
  const data = structuredClone(fixture) as unknown as ObservatoryView
  const artisan = data.society.population_groups.find(group => group.occupation === 'artisan')!
  const account = data.economy.accounts.find(item => item.owner_ref.kind === 'population_group'
    && item.owner_ref.id === artisan.id)!
  account.balance = 3
  account.last_event_id = 'event:artisan-wage'
  const need = data.economy.needs.find(item => item.id === artisan.settlement_id)!
  need.health = 250
  need.missing_food = 14
  const stock = data.economy.stocks.find(item => item.id === need.stock_id)!
  stock.goods.food = 500
  store.snapshot = data

  const panel = mount(IncomePanel, { global: { plugins: [pinia, medievalI18n] } })
  const city = panel.get(`[data-income-settlement="${artisan.settlement_id}"]`)
  expect(city.get('[data-testid="local-food-stock"]').text()).toBe('500')
  expect(city.text()).toContain('14')
  expect(city.text()).toContain('250 / 1.000')
  const expectedCash = data.society.population_groups
    .filter(group => group.settlement_id === artisan.settlement_id && group.occupation === 'artisan')
    .reduce((total, group) => total + (data.economy.accounts.find(item =>
      item.owner_ref.kind === 'population_group' && item.owner_ref.id === group.id)?.balance ?? 0), 0)
  expect(city.get('[data-testid="artisan-savings"]').text()).toBe(String(expectedCash))
  await city.get('[data-testid="artisan-source"]').trigger('click')
  expect(store.focusEventId).toBe('event:artisan-wage')
  panel.unmount()
})

it('shows the current public-food affordability projection and lets the Dao inspect its inputs', async () => {
  const pinia = createPinia(); setActivePinia(pinia)
  const store = useObserverStore()
  const data = structuredClone(fixture) as unknown as ObservatoryView
  const settlement = data.society.settlements[0]
  settlement.food_price = 2
  settlement.household_cash_by_occupation = { artisan: 9, farmer: 40 }
  settlement.estimated_unaffordable_public_rations = 17
  settlement.estimated_unaffordable_public_rations_by_occupation = { artisan: 12, farmer: 5 }
  settlement.food_access_evidence_event_ids = ['event:food-stock', 'event:food-price', 'event:household-balance']
  store.snapshot = data

  const panel = mount(IncomePanel, { global: { plugins: [pinia, medievalI18n] } })
  const city = panel.findAll('[data-income-settlement]')
    .find(item => item.attributes('data-income-settlement') === settlement.id)!
  expect(city.get('[data-testid="unaffordable-rations"]').text()).toBe('17')
  expect(city.text()).toContain('Artesãos')
  expect(city.text()).toContain('12')
  const source = city.findAll('button').find(button => button.text().includes('event:food-price'))!
  await source.trigger('click')
  expect(store.focusEventId).toBe('event:food-price')
  panel.unmount()
})

it('rejects snapshots that omit financial registries instead of breaking the panel later', async () => {
  const { acceptSnapshot } = await import('../mappers')
  const data = structuredClone(fixture)
  const { payrolls, ...incomplete } = data.economy
  expect(payrolls).toEqual([])
  expect(() => acceptSnapshot({ ...data, economy: incomplete } as unknown as ObservatoryView)).toThrow('incompleto')
})
