import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { it, expect } from 'vitest'
import IncomePanel from '../components/IncomePanel.vue'
import ResearchPanel from '../components/ResearchPanel.vue'
import { useObserverStore } from '../stores/world'
import { medievalI18n } from '../i18n'
import type { ObservatoryView } from '../../types/medieval-api'
import fixture from './world.json'

it('distinguishes a new production line from its anchor and follows commissioning', async () => {
  const pinia=createPinia(); setActivePinia(pinia)
  const store=useObserverStore()
  const data=structuredClone(fixture) as unknown as ObservatoryView
  data.economy.expansions=[{id:'construction:1',facility_id:'works:minas-de-ferroalto',blueprint_id:'charcoal-kilns',
    owner_ref:{kind:'polity',id:'escarlia'},decision_event_id:'event:1',started_day:90,last_work_day:120,
    completed_units:3,stage:'building',blocker:null,last_event_id:'event:2'}]
  store.snapshot=data
  const panel=mount(IncomePanel,{global:{plugins:[pinia,medievalI18n]}})
  let card=panel.get('[data-expansion="construction:1"]')
  expect(card.text()).toContain('Capacidade da nova linha0 Lotes')
  expect(card.text()).toContain('Capacidade prevista10 Lotes')
  expect(card.text()).toContain('Carvão: 1 por lote')
  expect(card.text()).not.toContain('60 Lotes')
  const next=structuredClone(data)
  next.economy.expansions[0]={...next.economy.expansions[0],completed_units:6,stage:'completed',last_work_day:150,last_event_id:'event:3'}
  next.economy.facilities.push({...next.economy.facilities.find(f=>f.id==='works:minas-de-ferroalto')!,
    id:'line:minas-de-ferroalto:charcoal',recipe_id:'charcoal',max_batches:10,last_event_id:'event:3'})
  store.snapshot=next
  await panel.vm.$nextTick()
  card=panel.get('[data-expansion="construction:1"]')
  expect(card.text()).toContain('Capacidade da nova linha10 Lotes')
  expect(card.text()).not.toContain('Capacidade prevista')
  await card.get('button').trigger('click'); expect(store.focusEventId).toBe('event:3')
  panel.unmount()
})

it('shows the actual prerequisite chain for steel and steam', async () => {
  const pinia=createPinia(); setActivePinia(pinia)
  useObserverStore().snapshot=structuredClone(fixture) as unknown as ObservatoryView
  const panel=mount(ResearchPanel,{global:{plugins:[pinia,medievalI18n]}})
  const catalog=panel.get('details')
  expect(catalog.text()).toContain('Fabricação de açoPré-requisitos: Metalurgia de alto rendimento')
  expect(catalog.text()).toContain('Engenharia a vaporPré-requisitos: Fabricação de aço')
  panel.unmount()
})

it('identifies payrolls from distinct production lines at the same site', async () => {
  const pinia = createPinia(); setActivePinia(pinia)
  const store = useObserverStore()
  const data = structuredClone(fixture) as unknown as ObservatoryView
  const parent = data.economy.facilities.find(f => f.id === 'works:minas-de-ferroalto')!
  for (const recipe of ['charcoal', 'engine_assembly']) {
    const id = `line:${parent.site_id}:${recipe}`
    data.economy.facilities.push({ ...parent, id, recipe_id: recipe, max_batches: 10 })
    data.economy.payrolls.push({ id, day: 450, wage_per_worker: 1,
      workers_by_group: {}, gross: 0, tax: 0, last_event_id: `event:${recipe}` })
  }
  store.snapshot = data
  const panel = mount(IncomePanel, { global: { plugins: [pinia, medievalI18n] } })
  const coal = panel.get('[data-payroll="line:minas-de-ferroalto:charcoal"]')
  const engines = panel.get('[data-payroll="line:minas-de-ferroalto:engine_assembly"]')
  expect(coal.text()).toContain('Minas de Ferroalto')
  expect(coal.text()).toContain('Carvão')
  expect(engines.text()).toContain('Motores a vapor')
  expect(coal.text()).not.toContain('Motores a vapor')
  await engines.get('button').trigger('click')
  expect(store.focusEventId).toBe('event:engine_assembly')
  panel.unmount()
})
