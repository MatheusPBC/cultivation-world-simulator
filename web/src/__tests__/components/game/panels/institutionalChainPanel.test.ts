import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import InstitutionalChainPanel from '@/components/game/panels/institution/InstitutionalChainPanel.vue'
import { institutionalChainApi, eventApi } from '@/api'

vi.mock('@/api', () => ({ institutionalChainApi: { fetch: vi.fn() }, eventApi: { fetchEventCausalDetail: vi.fn() } }))
describe('InstitutionalChainPanel', () => {
  beforeEach(() => setActivePinia(createPinia()))
  it('renders canonical parties, due resource terms, and decision actors before opening Why', async () => {
    vi.mocked(institutionalChainApi.fetch).mockResolvedValue({ owner: { name: 'Cidade Norte' }, currentMonth: 3, institutions: [{ id: 'inst:city:1', name: 'Cidade Norte' }, { id: 'inst:city:2', name: 'Cidade Sul' }], relations: [{ id: 'relation:1', institution_a_id: 'inst:city:1', institution_b_id: 'inst:city:2', kind: 'neutral', friendliness: 0, since_month: 1, evidence_event_ids: ['rel-1'] }], commitments: [{ id: 'commitment:event-accept', aggregate_status: 'active', owner_institution_id: 'inst:city:1', control_scope: 'direct', origin_event_id: 'event-accept', terms: [{ id: 'term-1', obligor_institution_id: 'inst:city:1', beneficiary_institution_id: 'inst:city:2', kind: 'resource_transfer', status: 'active', due_month: 5, subject: { id: 'grain' }, parameters: { amount: 4 }, breach_event_ids: [] }] }], events: [{ event_id: 'event-1', event_type: 'institutional_aid_refused', content: 'Ajuda recusada.', source_event_ids: [], decision: { actor_kind: 'region', actor_id: '1', action: 'refuse', reason: 'Sem estoque.' } }], memories: [], commitmentCursor: { hasMore: false }, eventCursor: { hasMore: false } } as any)
    const i18n = createI18n({ legacy: false, locale: 'pt-BR', messages: { 'pt-BR': { game: { institutional_chain: { title: 'Compromissos', refresh: 'Atualizar', loading: 'Carregando', error: 'Erro', month: 'mês {month}', empty: 'Vazio', more_commitments: 'Mais', more_events: 'Mais', evidence: 'Evidência', relevance: 'Relevância', relations_title: 'Relações institucionais', relation_climate: 'Clima da relação', neutral: 'Neutro', institutional_aid_refused: 'Ajuda recusada', active: 'Ativo', resource_transfer: 'Transferência', due: 'Prazo', promised: 'Prometido', delivered: 'Entregue', decision: 'Decisão', unknown_institution: 'Instituição desconhecida', action: { refuse: 'Recusar' }, scope: { direct: 'Direto' } }, info_panel: { region: { economy: { resources: { grain: 'Grão' } } } }, world_journal: { why_button: 'Por quê?' } } } } })
    const wrapper = mount(InstitutionalChainPanel, { props: { ownerKind: 'region', ownerId: '1' }, global: { plugins: [createPinia(), i18n] } })
    await Promise.resolve(); await Promise.resolve()
    expect(wrapper.text()).toContain('Cidade Norte')
    expect(wrapper.text()).toContain('Cidade Sul')
    expect(wrapper.text()).toContain('4 Grão')
    expect(wrapper.text()).toContain('Recusar')
    expect(wrapper.get('[data-testid="institutional-relations"]').text()).toContain('Clima da relação: 0')
    await wrapper.get('[data-testid="institutional-relations"] button').trigger('click'); expect(eventApi.fetchEventCausalDetail).toHaveBeenCalledWith('rel-1')
    await wrapper.findAll('button').at(-1)!.trigger('click'); expect(eventApi.fetchEventCausalDetail).toHaveBeenCalledWith('event-1')
  })
})
