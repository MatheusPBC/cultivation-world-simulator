import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import EventStreamList from '@/components/game/EventStreamList.vue'

describe('EventStreamList', () => {
  it('makes the causal detail reachable from every timeline event', async () => {
    const openWhy = vi.fn()
    const wrapper = mount(EventStreamList, {
      props: {
        events: [{
          id: 'event-1', text: 'A ponte cedeu.', content: 'A ponte cedeu.', year: 100, month: 2,
          timestamp: 1201, relatedAvatarIds: [], subjects: [], isMajor: true, isStory: false,
          factKind: 'state_transition', causalOrigin: 'deterministic',
        }],
        emptyText: 'Sem eventos',
        formatDate: () => 'Ano 100',
        whyLabel: 'Por quê?',
        onOpenWhy: openWhy,
      },
    })

    await wrapper.get('.event-stream-list__why').trigger('click')

    expect(openWhy).toHaveBeenCalledWith('event-1')
  })
})
