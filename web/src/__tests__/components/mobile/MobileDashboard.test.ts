import { shallowMount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { describe, expect, it, vi } from 'vitest'

import MobileDashboard from '@/components/mobile/MobileDashboard.vue'
import WorldJournalPanel from '@/components/game/panels/WorldJournalPanel.vue'

vi.mock('@/stores/world', () => ({
  useWorldStore: () => ({ year: 100, month: 5 }),
}))

vi.mock('@/stores/avatarOverview', () => ({
  useAvatarOverviewStore: () => ({
    overview: {
      summary: { aliveCount: 2, sectMemberCount: 1, deadCount: 0 },
    },
    refreshOverview: vi.fn(),
  }),
}))

describe('MobileDashboard', () => {
  it('uses the shared World Journal instead of a duplicated mobile timeline', () => {
    const wrapper = shallowMount(MobileDashboard, {
      global: {
        plugins: [createI18n({ legacy: false, locale: 'pt-BR', messages: { 'pt-BR': {} } })],
      },
    })

    expect(wrapper.findComponent(WorldJournalPanel).exists()).toBe(true)
    expect(wrapper.find('.event-timeline').exists()).toBe(false)
  })
})
