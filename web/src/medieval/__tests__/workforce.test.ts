import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { expect, it } from 'vitest'
import Inspector from '../components/Inspector.vue'
import { medievalI18n } from '../i18n'
import { acceptSnapshot } from '../mappers'
import { useObserverStore } from '../stores/world'
import type { ObservatoryView } from '../../types/medieval-api'
import fixture from './world.json'

function workforceSnapshot() {
  const data = structuredClone(fixture) as unknown as ObservatoryView
  data.governance.workforce_demand_reports = [{
    id: 'workforce-demand-1', recipient_ref: { kind: 'polity', id: 'auren' }, publisher_ref: { kind: 'polity', id: 'auren' }, sponsor_ref: { kind: 'polity', id: 'auren' },
    work_kind: 'facility', work_id: data.economy.facilities[0]!.id, account_id: 'account:auren', count: 2, stipend_per_person: 7,
    observed_day: 90, source_event_id: 'event:workforce-demand', event_id: 'event:workforce-observed', channel: 'administrative_workforce_demand',
  }]
  data.governance.workforce_offer_notices = [{
    id: 'workforce-offer-1', recipient_ref: { kind: 'population_group', id: data.society.population_groups[0]!.id }, publisher_ref: { kind: 'polity', id: 'auren' }, sponsor_ref: { kind: 'polity', id: 'auren' },
    demand_id: 'workforce-demand-1', source_group_id: data.society.population_groups[0]!.id, count: 2, stipend_per_person: 7,
    observed_day: 90, event_id: 'event:workforce-offer', channel: 'direct_workforce_offer',
  }]
  data.society.workforce_transitions = [{
    id: 'workforce-transition-1', source_group_id: data.society.population_groups[0]!.id, target_group_id: data.society.population_groups.find(group => group.occupation === 'artisan')!.id,
    sponsor_ref: { kind: 'polity', id: 'auren' }, demand_id: 'workforce-demand-1', notice_id: 'workforce-offer-1', work_kind: 'facility', work_id: data.economy.facilities[0]!.id,
    count: 2, stipend_per_person: 7, started_day: 90, due_day: 120, decision_event_id: 'event:workforce-decision', last_event_id: 'event:workforce-started',
  }]
  return data
}

it('shows material workforce demand, local offer and active transition with causal focus', async () => {
  const pinia = createPinia(); setActivePinia(pinia)
  const store = useObserverStore(); store.snapshot = workforceSnapshot()
  const panel = mount(Inspector, { global: { plugins: [pinia, medievalI18n] } })
  await panel.findAll('nav button').find(button => button.text() === 'Trabalho')!.trigger('click')
  expect(panel.get('[data-workforce-demand="workforce-demand-1"]').text()).toContain('Financiador')
  expect(panel.get('[data-workforce-offer="workforce-offer-1"]').text()).toContain('Bolsa')
  expect(panel.get('[data-workforce-transition="workforce-transition-1"]').text()).toContain('Conclusão prevista')
  await panel.get('[data-workforce-demand="workforce-demand-1"] button').trigger('click')
  expect(store.focusEventId).toBe('event:workforce-demand')
  expect(panel.text()).not.toContain('account:auren')
  panel.unmount()
})

it('rejects an observatory snapshot without workforce projections', () => {
  const data = workforceSnapshot()
  delete (data.governance as { workforce_demand_reports?: unknown }).workforce_demand_reports
  expect(() => acceptSnapshot(data)).toThrow('incompleto')
})
