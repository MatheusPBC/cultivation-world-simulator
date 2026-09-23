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
    work_kind: 'facility', work_id: data.economy.facilities[0]!.id, target_occupation: 'artisan', account_id: 'account:auren', count: 2, stipend_per_person: 7,
    observed_day: 90, source_event_id: 'event:workforce-demand', event_id: 'event:workforce-observed', channel: 'administrative_workforce_demand',
  }]
  data.governance.workforce_offer_notices = [{
    id: 'workforce-offer-1', recipient_ref: { kind: 'population_group', id: data.society.population_groups[0]!.id }, publisher_ref: { kind: 'polity', id: 'auren' }, sponsor_ref: { kind: 'polity', id: 'auren' },
    demand_id: 'workforce-demand-1', source_group_id: data.society.population_groups[0]!.id, target_occupation: 'artisan', count: 2, stipend_per_person: 7,
    observed_day: 90, event_id: 'event:workforce-offer', channel: 'direct_workforce_offer',
  }]
  data.society.workforce_transitions = [{
    id: 'workforce-transition-1', source_group_id: data.society.population_groups[0]!.id, target_group_id: data.society.population_groups.find(group => group.occupation === 'artisan')!.id,
    sponsor_ref: { kind: 'polity', id: 'auren' }, demand_id: 'workforce-demand-1', notice_id: 'workforce-offer-1', work_kind: 'facility', work_id: data.economy.facilities[0]!.id,
    target_occupation: 'artisan', destination_settlement_id: data.society.population_groups[0]!.settlement_id,
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

it('shows a military need at its settlement and accepts the current workforce kinds', async () => {
  const data = workforceSnapshot()
  const settlement = data.society.settlements[0]!
  const site = data.map.sites[0]!
  data.research.projects.push({
    id: 'research:example', owner_ref: { kind: 'polity', id: 'auren' }, technology_id: 'field_drill',
    site_id: site.id, stock_id: 'stock:example', account_id: 'account:auren', researcher_id: 'character:example',
    sponsor_decision_id: 'event:sponsor', researcher_decision_id: 'event:researcher',
    started_day: 90, completed_units: 0, last_work_day: null, stage: 'waiting', blocker: null,
    last_event_id: 'event:research',
  })
  data.economy.customs_checkpoints.push({
    id: 'checkpoint:example', site_id: site.id, operator_ref: { kind: 'polity', id: 'auren' },
    account_id: 'account:auren', staff_group_id: data.society.population_groups[0]!.id,
    staff_count: 1, fee_per_bulk: 1, started_day: 90, last_staffed_day: 90,
    inspection_day: 90, inspection_slots_used: 0, last_event_id: null,
  })
  const base = data.governance.workforce_demand_reports[0]!
  data.governance.workforce_demand_reports = [
    { ...base, id: 'military-need', work_kind: 'military_recruitment', work_id: settlement.id,
      target_occupation: 'soldier' },
    { ...base, id: 'research-need', work_kind: 'research', work_id: 'research:example' },
    { ...base, id: 'customs-need', work_kind: 'customs', work_id: 'checkpoint:example', target_occupation: 'merchant' },
  ]
  data.governance.workforce_offer_notices = []
  data.society.workforce_transitions = []
  expect(acceptSnapshot(data)).toBe(data)
  const pinia = createPinia(); setActivePinia(pinia)
  const store = useObserverStore(); store.snapshot = data
  const panel = mount(Inspector, { global: { plugins: [pinia, medievalI18n] } })
  await panel.findAll('nav button').find(button => button.text() === 'Trabalho')!.trigger('click')
  const military = panel.get('[data-workforce-demand="military-need"]')
  expect(military.text()).toContain('Recrutamento defensivo')
  expect(military.text()).toContain(settlement.name)
  expect(military.text()).toContain('Soldados')
  expect(panel.get('[data-workforce-demand="research-need"]').text()).toContain(site.name)
  expect(panel.get('[data-workforce-demand="customs-need"]').text()).toContain(site.name)
  await military.get('button').trigger('click')
  expect(store.focusEventId).toBe(base.source_event_id)
  panel.unmount()
})
