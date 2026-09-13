import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { it, expect } from 'vitest'
import Inspector from '../components/Inspector.vue'
import IncomePanel from '../components/IncomePanel.vue'
import { useObserverStore } from '../stores/world'
import { medievalI18n } from '../i18n'
import { acceptSnapshot } from '../mappers'
import type { ObservatoryView } from '../../types/medieval-api'
import fixture from './world.json'

it('shows institutional research, impediments, knowledge and causal navigation', async () => {
  const pinia = createPinia(); setActivePinia(pinia)
  const store = useObserverStore()
  const data = structuredClone(fixture) as unknown as ObservatoryView
  Object.assign(data.research, { projects: [{ id: 'research:1', owner_ref: { kind: 'polity', id: 'escarlia' },
    technology_id: 'metallurgy', site_id: 'minas-de-ferroalto', stock_id: 'stock:ferroalto',
    account_id: 'treasury:escarlia', researcher_id: 'character:011', sponsor_decision_id: 'event:1',
    researcher_decision_id: 'event:2', started_day: 30, last_work_day: 60, completed_units: 2,
    stage: 'blocked', blocker: 'input:tools', last_event_id: 'event:3' }],
    knowledge: [{ id: 'knowledge:1', owner_ref: { kind: 'polity', id: 'auren' }, technology_id: 'irrigation',
      channel: 'teaching', learned_day: 60, event_id: 'event:4' }] })
  store.snapshot = data
  const panel = mount(Inspector, { global: { plugins: [pinia, medievalI18n] } })
  const tab = panel.findAll('nav button').find(b => b.text() === 'Pesquisa')
  expect(tab).toBeDefined(); await tab!.trigger('click')
  const project = panel.get('[data-research="research:1"]')
  expect(project.text()).toContain('Metalurgia de alto rendimento')
  expect(project.text()).toContain('Minas de Ferroalto')
  expect(project.text()).toContain('2 / 6')
  expect(project.text()).toContain('Faltam materiais: Ferramentas')
  expect(project.get('progress').attributes('value')).toBe('2')
  await project.get('button').trigger('click'); expect(store.focusEventId).toBe('event:3')
  const knowledge = panel.get('[data-knowledge="knowledge:1"]')
  expect(knowledge.text()).toContain('Irrigação de campos')
  expect(knowledge.text()).toContain('Ensino')
  expect(panel.text()).toContain('Conhecer uma técnica não significa ter instalações adaptadas')
  await knowledge.get('button').trigger('click'); expect(store.focusEventId).toBe('event:4')
  panel.unmount()
})

it('rejects incomplete research payloads at the snapshot boundary', () => {
  const data = structuredClone(fixture) as unknown as ObservatoryView
  Object.assign(data, { research: undefined })
  expect(() => acceptSnapshot(data)).toThrow('incompleto')
})

it('shows recipe adaptation separately from capacity and identifies research wages', () => {
  const pinia = createPinia(); setActivePinia(pinia)
  const store = useObserverStore()
  const data = structuredClone(fixture) as unknown as ObservatoryView
  Object.assign(data.economy, { expansions: [{ id: 'adaptation:1', facility_id: 'works:minas-de-ferroalto',
    blueprint_id: 'efficient-furnaces', owner_ref: { kind: 'polity', id: 'escarlia' }, started_day: 90,
    last_work_day: 120, completed_units: 5, stage: 'building', blocker: null, decision_event_id: 'event:1', last_event_id: 'event:2' }],
    payrolls: [{ id: 'research:1', day: 60, workers_by_group: {}, gross: 10, tax: 1, wage_per_worker: 2, last_event_id: 'event:3' }] })
  Object.assign(data.research, { projects: [{ id: 'research:1', site_id: 'minas-de-ferroalto' }] })
  store.snapshot = data
  const panel = mount(IncomePanel, { global: { plugins: [pinia, medievalI18n] } })
  const project = panel.get('[data-expansion="adaptation:1"]')
  expect(project.text()).toContain('Ferro: 5 → 7')
  expect(project.text()).toContain('Produção por lote na conclusão')
  expect(project.text()).not.toContain('+0')
  expect(panel.get('[data-payroll="research:1"]').text()).toContain('Pesquisa · Minas de Ferroalto')
  panel.unmount()
})
