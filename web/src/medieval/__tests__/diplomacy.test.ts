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
    clauses: [{ kind: 'payment', debtor_ref: buyer, creditor_ref: seller, due_day: 100, depends_on: [],
      source_account_id: 'treasury:auren', target_account_id: 'treasury:escarlia', amount: 80 },
    { kind: 'teaching', debtor_ref: seller, creditor_ref: buyer, due_day: 105, depends_on: [0], technology_id: 'metallurgy' }] }
  data.diplomacy = { proposals: [p], obligations: [
    { id: `${p.id}:term:0`, proposal_id: p.id, clause_index: 0, status: 'fulfilled', material_event_id: 'event:4', last_event_id: 'event:5' },
    { id: `${p.id}:term:1`, proposal_id: p.id, clause_index: 1, status: 'active', material_event_id: null, last_event_id: 'event:3' },
  ], notices: [seller, buyer].flatMap(ref => ['event:3', 'event:5'].map(event_id => ({
    id: `notice:${event_id}:${ref.id}`, proposal_id: p.id, recipient_ref: ref, event_id, learned_day: 90, channel: 'direct_diplomacy' as const,
  }))) }
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

it('rejects a snapshot without its diplomatic state', () => {
  const data = negotiation()
  Object.assign(data, { diplomacy: undefined })
  expect(() => acceptSnapshot(data)).toThrow('incompleto')
})
