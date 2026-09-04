import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import AvatarActivitySection from '@/components/game/panels/info/avatar-detail/AvatarActivitySection.vue'

const activity = {
  current_action: {
    status: 'running',
    label: 'Inspecionar rota',
    queued_actions: ['Viajar'],
  },
  events: [
    {
      event_id: 'decision-1',
      content: 'Li Wen committed to an action chain.',
      year: 12,
      month: 3,
      fact_kind: 'decision',
      is_major: false,
      is_story: false,
      decision: {
        thinking: 'A ponte precisa de atenção.',
        short_term_objective: 'Reabrir a rota.',
        considered_count: 3,
        chosen_actions: ['Inspecionar rota', 'Viajar'],
        rejected: [{ action_name: 'Atacar', reason: 'Não há inimigo.' }],
      },
    },
  ],
}

describe('AvatarActivitySection', () => {
  it('keeps the current action, decision audit, and causal drill-down together', async () => {
    const wrapper = mount(AvatarActivitySection, {
      props: {
        activity,
        title: 'Rastro de ação',
        nowLabel: 'Agora',
        idleLabel: 'Aguardando',
        queueLabel: 'Na sequência',
        factsLabel: 'Fatos recentes',
        decisionLabel: 'Decisão',
        factLabel: 'Fato',
        whyLabel: 'Ver causas',
        emptyLabel: 'Sem fatos',
        objectiveLabel: 'Objetivo',
        consideredLabel: (count: number) => `${count} ações consideradas`,
        rejectedLabel: 'Alternativas inviáveis',
      },
    })

    expect(wrapper.get('[data-testid="avatar-activity"]').text()).toContain('Inspecionar rota')
    expect(wrapper.text()).toContain('A ponte precisa de atenção.')
    expect(wrapper.text()).toContain('Atacar')
    expect(wrapper.text()).toContain('Alternativas inviáveis')

    await wrapper.get('.activity-why').trigger('click')
    expect(wrapper.emitted('open-source')).toEqual([['decision-1']])
  })
})
