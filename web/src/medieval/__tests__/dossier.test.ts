import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import Inspector from '../components/Inspector.vue'
import { medievalI18n } from '../i18n'
import { useObserverStore } from '../stores/world'
import type { ObservatoryView } from '../../types/medieval-api'
import fixture from './world.json'

it('explains own office and current work in Portuguese without inventing an appointment receipt', async () => {
  const pinia = createPinia(); setActivePinia(pinia)
  const store = useObserverStore()
  store.snapshot = structuredClone(fixture) as unknown as ObservatoryView
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ok:true,revision:1,data:{
    actor_ref:{kind:'character',id:'character:001'},next_after:null,has_more:false,entries:[
      {category:'authority_office',id:'office:own',event_id:null,learned_day:null,cause_event_ids:[],causal_depth:0,
        payload:{institution_ref:{kind:'polity',id:'auren'},holder_ref:{kind:'character',id:'character:001'},scopes:['policy'],active:false}},
      {category:'current_activity',id:'activity:own',event_id:'event:practice',learned_day:30,cause_event_ids:[],causal_depth:0,
        payload:{kind:'training',skill:'diplomacy',started_day:30,progress_days:4,due_day:null}},
    ],
  }}))))
  const panel = mount(Inspector,{global:{plugins:[pinia,medievalI18n]}})
  try {
    store.selection={kind:'character',id:'character:001'};await flushPromises()
    const office=panel.get('[data-dossier-entry="office:own"]')
    expect(office.text()).toContain('Mandato sem autoridade vigente')
    expect(office.text()).toContain('Direção política')
    expect(office.find('button').exists()).toBe(false)
    const work=panel.get('[data-dossier-entry="activity:own"]')
    expect(work.text()).toContain('Treinamento · Diplomacia')
    expect(work.text()).toContain('4 dias de prática acumulados')
    await work.get('button').trigger('click');expect(store.focusEventId).toBe('event:practice')
  } finally {panel.unmount();vi.unstubAllGlobals()}
})

it('shows actual ritual participation, planned materials and navigable outcome without inventing a thought', async () => {
  const pinia = createPinia(); setActivePinia(pinia)
  const store = useObserverStore()
  const data = structuredClone(fixture) as unknown as ObservatoryView
  store.snapshot = data
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ ok: true, revision: 1, data: {
    actor_ref: { kind: 'character', id: 'character:001' }, entries: [{
      category: 'ritual_activity', id: 'rite:event:2', event_id: 'event:completion', learned_day: 35,
      cause_event_ids: [], causal_depth: 0, payload: { site_id: data.map.sites[0]!.id, role: 'officiant',
        stage: 'completed', started_day: 30, due_day: 35, planned_cost: { reagents: 4 } },
    }], next_after: null, has_more: false,
  } }))))
  const panel = mount(Inspector, { global: { plugins: [pinia, medievalI18n] } })
  try {
    store.selection = { kind: 'character', id: 'character:001' }; await flushPromises()
    const activity = panel.get('[data-dossier-entry="rite:event:2"]')
    expect(activity.text()).toContain('Participação em rito')
    expect(activity.text()).toContain('Oficiante')
    expect(activity.text()).toContain('Execução material concluída')
    expect(activity.text()).toContain('Materiais previstos: 4')
    await activity.get('button').trigger('click'); expect(store.focusEventId).toBe('event:completion')
  } finally { panel.unmount(); vi.unstubAllGlobals() }
})

it('loads the selected character dossier and navigates to its source event', async () => {
  const pinia = createPinia(); setActivePinia(pinia)
  const store = useObserverStore()
  store.snapshot = structuredClone(fixture) as unknown as ObservatoryView
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    expect(url).toContain('/api/v2/query/dossier/character/')
    return new Response(JSON.stringify({ ok: true, revision: 4, data: {
      actor_ref: { kind: 'character', id: 'character:001' },
      entries: [
        { category: 'known_fact', id: 'fact:event:42', event_id: 'event:42', learned_day: 30,
          cause_event_ids: [], causal_depth: 0, payload: { content: 'A ponte foi danificada.', fact_kind: 'state_transition' } },
        { category: 'known_fact', id: 'fact:event:43', event_id: 'event:43', learned_day: 60,
          cause_event_ids: [], causal_depth: 0, payload: { content: 'Li Wen decidiu estudar a técnica.', fact_kind: 'decision',
            decision: { action: 'accept_religious_adherence', selected_affordance_id: 'religious-join:invitation:event:41' } } },
      ],
      next_after: null, has_more: false,
    } }))
  }))
  const panel = mount(Inspector, { global: { plugins: [pinia, medievalI18n] } })
  store.selection = { kind: 'character', id: 'character:001' }
  await flushPromises()
  expect(panel.findAll('[data-character-history]').map(item => item.text())).toEqual([
    expect.stringContaining('Li Wen decidiu estudar a técnica.'),
    expect.stringContaining('A ponte foi danificada.'),
  ])
  const entry = panel.get('[data-character-history="fact:event:42"]')
  expect(panel.get('[data-character-history="fact:event:43"]').text()).toContain('Opção canônica escolhida: religious-join:invitation:event:41')
  expect(entry.text()).toContain('A ponte foi danificada.')
  await entry.get('button').trigger('click')
  expect(store.focusEventId).toBe('event:42')
  panel.unmount(); vi.unstubAllGlobals()
})

it('selects a polity from governments, loads its dossier, and navigates to a source event', async () => {
  const pinia = createPinia(); setActivePinia(pinia)
  const store = useObserverStore()
  store.snapshot = structuredClone(fixture) as unknown as ObservatoryView
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    expect(url).toContain('/api/v2/query/dossier/polity/auren')
    return new Response(JSON.stringify({ ok: true, revision: 5, data: {
      actor_ref: { kind: 'polity', id: 'auren' },
      entries: [
        { category: 'strategic_objective', id: 'objective:auren:food', event_id: 'event:objective', learned_day: null,
          cause_event_ids: [], causal_depth: 0, payload: { kind: 'maintain_food_reserve', resource_id: 'food' } },
        { category: 'strategic_plan', id: 'plan:auren:food', event_id: 'event:plan', learned_day: null,
          cause_event_ids: [], causal_depth: 0, payload: { stage: 'acquire', objective_id: 'objective:auren:food' } },
        { category: 'institutional_memory', id: 'memory:auren:event:42', event_id: 'event:42', learned_day: 42,
          cause_event_ids: [], causal_depth: 1, payload: { content: 'Escarlia recusou ajuda.' } },
      ],
      next_after: null, has_more: false,
    } }))
  }))
  const panel = mount(Inspector, { global: { plugins: [pinia, medievalI18n] } })
  await panel.findAll('.inspector-tabs button')[2]!.trigger('click')
  await panel.get('[data-polity="auren"] button').trigger('click')
  await flushPromises()
  expect(panel.text()).toContain('Coroa de Auren')
  expect(panel.text()).toContain('Objetivo estratégico')
  expect(panel.text()).toContain('Plano estratégico')
  expect(panel.text()).toContain('Memória institucional')
  const entry = panel.get('[data-dossier-entry="memory:auren:event:42"]')
  expect(entry.text()).toContain('Escarlia recusou ajuda.')
  await entry.get('button').trigger('click')
  expect(store.focusEventId).toBe('event:42')
  panel.unmount(); vi.unstubAllGlobals()
})

it('selects an organization from governments, loads its dossier, and navigates to a source event', async () => {
  const pinia = createPinia(); setActivePinia(pinia)
  const store = useObserverStore()
  store.snapshot = structuredClone(fixture) as unknown as ObservatoryView
  store.snapshot.society.organizations.find(item => item.id === 'casa-alvor')!.member_ids = [
    'character:001', 'character:002',
  ]
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    expect(url).toContain('/api/v2/query/dossier/organization/casa-alvor')
    return new Response(JSON.stringify({ ok: true, revision: 6, data: {
      actor_ref: { kind: 'organization', id: 'casa-alvor' },
      entries: [{ category: 'known_fact', id: 'fact:event:organization', event_id: 'event:organization', learned_day: 12,
        cause_event_ids: [], causal_depth: 0, payload: { content: 'A Casa Alvor recebeu um pedido de proteção.' } }],
      next_after: null, has_more: false,
    } }))
  }))
  const panel = mount(Inspector, { global: { plugins: [pinia, medievalI18n] } })
  await panel.findAll('.inspector-tabs button')[2]!.trigger('click')
  await panel.get('[data-organization="casa-alvor"] button').trigger('click')
  await flushPromises()
  expect(panel.text()).toContain('Casa Alvor')
  const members = panel.findAll('[data-organization-member]')
  expect(members.map(item => item.text())).toEqual([
    expect.stringContaining('Kaela Valverde · Humano'),
    expect.stringContaining('Fenn Pedralume · Elfo'),
  ])
  const entry = panel.get('[data-dossier-entry="fact:event:organization"]')
  expect(entry.text()).toContain('pedido de proteção')
  await entry.get('button').trigger('click')
  expect(store.focusEventId).toBe('event:organization')
  panel.unmount(); vi.unstubAllGlobals()
})

it('explains the people-specific work-entry age in settlement population groups', async () => {
  const pinia = createPinia(); setActivePinia(pinia)
  const store = useObserverStore()
  store.snapshot = structuredClone(fixture) as unknown as ObservatoryView
  const ages = { human: 15, elf: 25, dwarf: 20, orc: 12 }
  for (const group of store.snapshot.society.population_groups) {
    group.maturity_years = ages[group.people]
  }

  const panel = mount(Inspector, { global: { plugins: [pinia, medievalI18n] } })
  await panel.findAll('.inspector-tabs button')[3]!.trigger('click')
  const settlement = panel.findAll('button.link-row').find(button => button.text().includes('Campomanso'))
  expect(settlement).toBeDefined()
  await settlement!.trigger('click')
  const group = store.snapshot.society.population_groups.find(item => item.settlement_id === 'campomanso'
    && item.people === 'elf')!
  expect(panel.get(`[data-population-group="${group.id}"]`).text()).toContain('Entrada no trabalho: 25 anos')
  panel.unmount()
})

it('renders institutional aid notices with translated categories and canonical details', async () => {
  const pinia = createPinia(); setActivePinia(pinia)
  const store = useObserverStore()
  store.snapshot = structuredClone(fixture) as unknown as ObservatoryView
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ ok: true, revision: 8, data: {
    actor_ref: { kind: 'polity', id: 'auren' },
    entries: [{ category: 'institutional_aid_notices', id: 'aid:request:1', event_id: 'event:aid:request', learned_day: 30,
      cause_event_ids: [], causal_depth: 0, payload: { kind: 'request', requester_ref: { kind: 'polity', id: 'valedouro' },
        requester_settlement_id: 'campomanso', requested_food: 75 } }],
    next_after: null, has_more: false,
  } }))))
  const panel = mount(Inspector, { global: { plugins: [pinia, medievalI18n] } })
  await panel.findAll('.inspector-tabs button')[2]!.trigger('click')
  await panel.get('[data-polity="auren"] button').trigger('click')
  await flushPromises()
  const entry = panel.get('[data-dossier-entry="aid:request:1"]')
  expect(entry.text()).toContain('Pedidos e respostas de ajuda institucional')
  expect(entry.text()).toContain('Valedouro')
  expect(entry.text()).toContain('Campomanso')
  expect(entry.text()).toContain('75 de alimento')
  expect(panel.text()).not.toContain('dossierCategories.institutional_aid_notices')
  panel.unmount(); vi.unstubAllGlobals()
})

it('loads older dossier pages without duplicating recent character history', async () => {
  const pinia = createPinia(); setActivePinia(pinia)
  const store = useObserverStore()
  store.snapshot = structuredClone(fixture) as unknown as ObservatoryView
  const calls: string[] = []
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    calls.push(url)
    const parsed = new URL(url, 'http://localhost')
    const page = parsed.searchParams.get('after') === 'older-page-cursor'
      ? { entries: [{ category: 'known_fact', id: 'fact:event:old', event_id: 'event:old', learned_day: 1,
          cause_event_ids: [], causal_depth: 0, payload: { content: 'Registro anterior.', fact_kind: 'occurrence' } }],
          next_after: null, has_more: false }
      : { entries: [
          { category: 'known_fact', id: 'fact:event:new', event_id: 'event:new', learned_day: 60,
            cause_event_ids: [], causal_depth: 0, payload: { content: 'Decisão recente.', fact_kind: 'decision' } },
          { category: 'known_fact', id: 'fact:event:older', event_id: 'event:older', learned_day: 30,
            cause_event_ids: [], causal_depth: 0, payload: { content: 'Relato conhecido.', fact_kind: 'occurrence' } },
          ...Array.from({length: 9}, (_,i)=>({category:'known_fact',id:`fact:extra:${i}`,event_id:`extra:${i}`,
            learned_day:20-i,cause_event_ids:[],causal_depth:0,payload:{content:`Fato carregado ${i}.`}})),
        ], next_after: 'older-page-cursor', has_more: true }
    return new Response(JSON.stringify({ ok: true, revision: 7, data: {
      actor_ref: { kind: 'character', id: 'character:001' }, ...page,
    } }))
  }))
  const panel = mount(Inspector, { global: { plugins: [pinia, medievalI18n] } })
  store.selection = { kind: 'character', id: 'character:001' }
  await flushPromises()
  expect(panel.findAll('[data-character-history]')).toHaveLength(11)
  const loadMore = panel.findAll('button').find(button => button.text() === 'Carregar fatos anteriores')
  expect(loadMore).toBeTruthy()
  await loadMore!.trigger('click'); await flushPromises()
  expect(panel.findAll('[data-character-history]')).toHaveLength(12)
  expect(panel.get('[data-character-history="fact:event:old"]').text()).toContain('Registro anterior.')
  const nextPage = new URL(calls[1], 'http://localhost')
  expect(nextPage.searchParams.get('after')).toBe('older-page-cursor')
  expect(nextPage.searchParams.get('limit')).toBe('50')
  panel.unmount(); vi.unstubAllGlobals()
})
