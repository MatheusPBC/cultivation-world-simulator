import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import IncomePanel from '../components/IncomePanel.vue'
import { useObserverStore } from '../stores/world'
import { medievalI18n } from '../i18n'
import type { ObservatoryView } from '../../types/medieval-api'
import fixture from './world.json'

describe('material construction in the observatory', () => {
  it('shows real progress, current capacity and pending gain without pretending completion', async () => {
    const pinia = createPinia(); setActivePinia(pinia)
    const store = useObserverStore()
    const data = structuredClone(fixture) as unknown as ObservatoryView
    Object.assign(data.economy, {
      expansion_blueprints: [{ id: 'extension', name: 'Ampliação', inputs: { tools: 1 }, workers_per_unit: 2,
        wage_per_worker: 2, required_units: 10, monthly_units: 5, capacity_gain: 10 }],
      expansions: [{ id: 'project:1', facility_id: 'works:minas-de-ferroalto', blueprint_id: 'extension',
        owner_ref: { kind: 'polity', id: 'escarlia' }, started_day: 30, last_work_day: 60,
        completed_units: 5, stage: 'blocked', blocker: 'input:tools', decision_event_id: 'event:1', last_event_id: 'event:2' }],
      payrolls: [{ id: 'project:1', day: 60, workers_by_group: {}, gross: 20, tax: 2, wage_per_worker: 2, last_event_id: 'event:3' }],
    })
    store.snapshot = data
    const panel = mount(IncomePanel, { global: { plugins: [pinia, medievalI18n] } })
    const project = panel.get('[data-expansion="project:1"]')
    expect(project.text()).toContain('Minas de Ferroalto')
    expect(project.text()).toContain('5 / 10')
    expect(project.text()).toContain('Faltam materiais: Ferramentas')
    expect(project.text()).toContain('Ganho na conclusão')
    expect(project.get('progress').attributes('value')).toBe('5')
    expect(panel.get('[data-payroll="project:1"]').text()).toContain('Obra · Minas de Ferroalto')
    await project.get('button').trigger('click')
    expect(store.focusEventId).toBe('event:2')
    panel.unmount()
  })

  it('rejects snapshots missing construction state', async () => {
    const { acceptSnapshot } = await import('../mappers')
    const data = structuredClone(fixture) as unknown as ObservatoryView
    Object.assign(data.economy, { expansions: undefined })
    expect(() => acceptSnapshot(data)).toThrow('incompleto')
  })
})
