import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { it, expect } from 'vitest'
import Inspector from '../components/Inspector.vue'
import { useObserverStore } from '../stores/world'
import { medievalI18n } from '../i18n'
import { acceptSnapshot, entityName } from '../mappers'
import type { ObservatoryView, DiplomaticProposal } from '../../types/medieval-api'
import fixture from './world.json'

function negotiation() {
  const data = structuredClone(fixture) as unknown as ObservatoryView
  const seller = { kind: 'polity', id: 'escarlia' }, buyer = { kind: 'polity', id: 'auren' }
  const p: DiplomaticProposal = { id: 'proposal:event:1', proposer_ref: seller, counterparty_ref: buyer,
    offered_day: 90, expires_day: 95, parent_id: null, decision_event_id: 'event:1', status: 'accepted', last_event_id: 'event:3',
    proposal_kind: 'negotiated', request_affordance_id: null,
    clauses: [{ kind: 'payment', debtor_ref: buyer, creditor_ref: seller, due_day: 100, depends_on: [],
      source_account_id: 'treasury:auren', target_account_id: 'treasury:escarlia', amount: 80 },
    { kind: 'teaching', debtor_ref: seller, creditor_ref: buyer, due_day: 105, depends_on: [0], technology_id: 'metallurgy' }] }
  data.diplomacy = { proposals: [p], obligations: [
    { id: `${p.id}:term:0`, proposal_id: p.id, clause_index: 0, status: 'fulfilled', material_event_id: 'event:4',
      breach_event_id: null, remediation_material_event_id: null, last_event_id: 'event:5' },
    { id: `${p.id}:term:1`, proposal_id: p.id, clause_index: 1, status: 'active', material_event_id: null,
      breach_event_id: null, remediation_material_event_id: null, last_event_id: 'event:3' },
  ], notices: [seller, buyer].flatMap(ref => ['event:3', 'event:5'].map(event_id => ({
    id: `notice:${event_id}:${ref.id}`, proposal_id: p.id, recipient_ref: ref, event_id, learned_day: 90, channel: 'direct_diplomacy' as const,
  }))), aid_notices: [], memories: [], aid_readings: [], strategic_evidence: [] }
  return data
}

it('opens diplomacy from the inspector and distinguishes acceptance, delivery, knowledge and due dates', async () => {
  const pinia = createPinia(); setActivePinia(pinia)
  const store = useObserverStore()
  store.snapshot = negotiation()
  const panel = mount(Inspector, { global: { plugins: [pinia, medievalI18n] } })
  await panel.findAll('nav button').find(b => b.text() === 'Diplomacia')!.trigger('click')
  const payment = panel.get('[data-term="proposal:event:1:1"]')
  const lesson = panel.get('[data-term="proposal:event:1:2"]')
  expect(payment.text()).toContain('Pagar 80 moedas')
  expect(payment.text()).toContain('Cumprida')
  expect(payment.text()).toContain('Ano 1 · mês 4 · dia 11')
  expect(lesson.text()).toContain('Cumprimento pendente')
  expect(lesson.text()).toContain('Metalurgia de alto rendimento')
  expect(lesson.text()).toContain('Após cumprir os termos: 1')
  expect(lesson.text()).not.toContain('Ver execução material')
  await payment.findAll('button').find(b => b.text() === 'Ver execução material')!.trigger('click')
  expect(store.focusEventId).toBe('event:4')
  await lesson.get('button').trigger('click')
  expect(store.focusEventId).toBe('event:3')
  const outsider = entityName(store.snapshot, { kind: 'polity', id: 'valedouro' })
  expect(panel.get('[data-proposal]').text()).not.toContain(outsider)
  expect(panel.text()).toContain('cada participante sabe apenas o que lhe foi comunicado')
  panel.unmount()
})

it('shows breach and dependent excuse without claiming material fulfillment', async () => {
  const pinia = createPinia(); setActivePinia(pinia)
  const store = useObserverStore(), data = negotiation()
  data.diplomacy.obligations[0]!.status = 'breached'
  data.diplomacy.obligations[0]!.material_event_id = null
  data.diplomacy.obligations[1]!.status = 'excused'
  store.snapshot = data
  const panel = mount(Inspector, { global: { plugins: [pinia, medievalI18n] } })
  await panel.findAll('nav button').find(b => b.text() === 'Diplomacia')!.trigger('click')
  expect(panel.text()).toContain('Prazo descumprido')
  expect(panel.text()).toContain('Dispensada: dependência não cumprida')
  expect(panel.text()).not.toContain('Ver execução material')
  panel.unmount()
})

it('renders campaign withdrawal terms without treating them as teaching', async () => {
  const pinia = createPinia(); setActivePinia(pinia)
  const store = useObserverStore(), data = negotiation()
  const attacker = { kind: 'polity', id: 'auren' }, defender = { kind: 'polity', id: 'escarlia' }
  const ceasefire: DiplomaticProposal = {
    id: 'proposal:ceasefire', proposer_ref: attacker, counterparty_ref: defender,
    offered_day: 90, expires_day: 91, parent_id: null, decision_event_id: 'event:ceasefire',
    status: 'accepted', last_event_id: 'event:ceasefire-accepted', proposal_kind: 'campaign_ceasefire',
    request_affordance_id: 'campaign-ceasefire:1',
    clauses: [{ kind: 'campaign_withdrawal', debtor_ref: attacker, creditor_ref: defender,
      due_day: 94, depends_on: [], campaign_id: 'siege-campaign:1', detachment_id: 'detachment:1' }],
  }
  data.diplomacy.proposals = [ceasefire]
  data.diplomacy.obligations = [{ id: `${ceasefire.id}:term:0`, proposal_id: ceasefire.id, clause_index: 0,
    status: 'active', material_event_id: null, breach_event_id: null,
    remediation_material_event_id: null, last_event_id: ceasefire.last_event_id }]
  store.snapshot = data
  const panel = mount(Inspector, { global: { plugins: [pinia, medievalI18n] } })
  await panel.findAll('nav button').find(b => b.text() === 'Diplomacia')!.trigger('click')
  const term = panel.get('[data-term="proposal:ceasefire:1"]')
  expect(term.text()).toContain('Retirar a coluna detachment:1 da campanha siege-campaign:1')
  expect(term.text()).not.toContain('Ensinar')
  panel.unmount()
})

it('reads the aid trail, remembered facts and the directional institutional reading', async () => {
  const pinia = createPinia(); setActivePinia(pinia)
  const store = useObserverStore(), data = negotiation()
  const requester = { kind: 'polity', id: 'auren' }, provider = { kind: 'polity', id: 'valedouro' }
  const aid: DiplomaticProposal = { id: 'proposal:event:10', proposer_ref: requester, counterparty_ref: provider,
    offered_day: 90, expires_day: 120, parent_id: null, decision_event_id: 'event:10', status: 'accepted',
    proposal_kind: 'institutional_aid', request_affordance_id: 'institutional-aid-request:auren', last_event_id: 'event:12',
    clauses: [{ kind: 'resource_transfer', debtor_ref: provider, creditor_ref: requester, due_day: 121, depends_on: [],
      source_stock_id: 'stock:portovelho', destination_stock_id: 'stock:pedraclara', resource_id: 'food',
      quantity: 300, route_ids: ['river-pedraclara-portovelho'] }] }
  data.diplomacy.proposals = [aid]
  data.diplomacy.obligations = [{ id: `${aid.id}:term:0`, proposal_id: aid.id, clause_index: 0, status: 'remediated',
    material_event_id: null, breach_event_id: 'event:20', remediation_material_event_id: 'event:31', last_event_id: 'event:30' }]
  data.diplomacy.aid_notices = [
    { id: 'institutional_aid_notice:event:11:polity:valedouro', request_event_id: 'event:11', recipient_ref: provider,
      requester_ref: requester, requester_settlement_id: 'pedraclara', report_id: 'settlement_report:auren:pedraclara',
      requested_food: 300, event_id: 'event:11', learned_day: 90, kind: 'request', response_status: null,
      channel: 'direct_institutional_aid' },
    { id: 'institutional_aid_notice:event:12:polity:auren', request_event_id: 'event:11', recipient_ref: requester,
      requester_ref: requester, requester_settlement_id: 'pedraclara', report_id: 'settlement_report:auren:pedraclara',
      requested_food: 300, event_id: 'event:12', learned_day: 91, kind: 'response', response_status: 'accepted',
      channel: 'direct_institutional_aid' }]
  data.diplomacy.memories = [
    { id: 'memory:polity:auren:event:20', institution_ref: requester, event_id: 'event:20', recorded_day: 121,
      last_reinforced_day: 130, effective_salience: 1000 },
    { id: 'memory:polity:auren:event:30', institution_ref: requester, event_id: 'event:30', recorded_day: 130,
      last_reinforced_day: 130, effective_salience: 1000 }]
  data.diplomacy.aid_readings = [{ observer_ref: requester, subject_ref: provider, value: -2,
    evidence_event_ids: ['event:20', 'event:30'] }]
  store.snapshot = data
  const panel = mount(Inspector, { global: { plugins: [pinia, medievalI18n] } })
  await panel.findAll('nav button').find(b => b.text() === 'Diplomacia')!.trigger('click')

  const term = panel.get('[data-term="proposal:event:10:1"]')
  expect(term.text()).toContain('Entregar 300 de Alimentos')
  expect(term.text()).not.toContain('Ensinar')
  expect(term.text()).toContain('Reparada após descumprimento')
  await term.findAll('button').find(b => b.text() === 'Ver o descumprimento')!.trigger('click')
  expect(store.focusEventId).toBe('event:20')

  const request = panel.get('[data-aid-notice="institutional_aid_notice:event:11:polity:valedouro"]')
  expect(request.text()).toContain('Ajuda pedida')
  expect(request.text()).toContain('Necessidade declarada: 300 de alimento')
  expect(panel.get('[data-aid-notice="institutional_aid_notice:event:12:polity:auren"]').text()).toContain('Ajuda aceita')
  await request.findAll('button').find(b => b.text() === 'Ver o pedido')!.trigger('click')
  expect(store.focusEventId).toBe('event:11')

  const memory = panel.get('[data-memory="memory:polity:auren:event:20"]')
  expect(memory.text()).toContain('Peso efetivo (por mil)')
  await memory.findAll('button').find(b => b.text() === 'Ver o fato lembrado')!.trigger('click')
  expect(store.focusEventId).toBe('event:20')

  const reading = panel.get('[data-reading="auren:valedouro"]')
  expect(reading.text()).toContain('-2')
  await reading.findAll('button')[1]!.trigger('click')
  expect(store.focusEventId).toBe('event:30')

  const trail = panel.get('#aid-trail-title').element.parentElement!.textContent!
  expect(trail).not.toContain('stock:portovelho')
  expect(trail).not.toContain('river-pedraclara-portovelho')
  panel.unmount()
})

it('shows strategic findings and keeps their causal event navigable', async () => {
  const pinia = createPinia(); setActivePinia(pinia)
  const store = useObserverStore(), data = negotiation()
  data.diplomacy.strategic_evidence = [{
    kind: 'espionage', finding_id: 'finding:espionage:1', result: 'success', event_id: 'event:77',
    recipient_ref: { kind: 'polity', id: 'escarlia' },
    target_ref: { kind: 'settlement', id: 'portovelho' },
    target_owner_ref: { kind: 'polity', id: 'escarlia' }, evidence_event_id: 'event:76',
  }]
  store.snapshot = data
  const panel = mount(Inspector, { global: { plugins: [pinia, medievalI18n] } })
  await panel.findAll('nav button').find(b => b.text() === 'Diplomacia')!.trigger('click')
  const finding = panel.get('[data-finding="finding:espionage:1"]')
  expect(finding.text()).toContain('Espionagem')
  expect(finding.text()).toContain('Conselho de Escárlia')
  expect(finding.text()).toContain('event:77')
  await finding.get('button').trigger('click')
  expect(store.focusEventId).toBe('event:77')
  panel.unmount()
})

it('rejects a snapshot without its diplomatic state', () => {
  const data = negotiation()
  Object.assign(data, { diplomacy: undefined })
  expect(() => acceptSnapshot(data)).toThrow('incompleto')
})
