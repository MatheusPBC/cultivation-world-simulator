import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { describe, expect, it, vi } from 'vitest'

import ChronicleView from '@/components/game/panels/world-journal/ChronicleView.vue'

const selectMock = vi.fn()
const openDossierMock = vi.fn()

vi.mock('@/stores/ui', () => ({ useUiStore: () => ({ select: selectMock }) }))

function mountView() {
  return mount(ChronicleView, {
    props: {
      chapters: [{
        id: 'chapter-1', start_month_stamp: 1, end_month_stamp: 1, trigger: 'major_event', title: 'Rise', created_at: 1,
        source_event_ids: ['event-1'],
        paragraphs: [{ source_event_ids: ['event-1'], segments: [
          { text: 'A fact ', reference: { id: 'fact-1', kind: 'event', label: 'fact', target_id: 'event-1', claim_kind: 'fact', source_event_ids: ['event-1'] } },
          { text: '<script>alert(1)</script>', reference: null },
          { text: ' and ', reference: null },
          { text: 'the sect', reference: { id: 'sect-1', kind: 'sect', label: 'Cloud Sect', target_id: '7', claim_kind: null, source_event_ids: ['event-1'] } },
        ] }],
      }],
      hasMore: true,
      loading: false,
      error: false,
      onOpenDossier: openDossierMock,
    },
    global: { plugins: [createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': { game: { world_journal: { chronicle: { fact: '事实', inference: '编年史解读', source_count: '{count} 个来源', load_more: '加载更多', loading: '加载中', empty: '暂无', error: '加载失败', trigger: { major_event: '重大事件' } } } } } } })] },
  })
}

describe('ChronicleView', () => {
  it('renders safe segments, badges and structured links', async () => {
    const wrapper = mountView()

    expect(wrapper.find('[data-testid="chronicle-fact-badge"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="chronicle-inference-badge"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('<script>alert(1)</script>')
    expect(wrapper.find('[v-html]').exists()).toBe(false)
    expect(wrapper.text()).toContain('1 个来源')

    await wrapper.get('[data-testid="chronicle-ref-fact-1"]').trigger('click')
    expect(openDossierMock).toHaveBeenCalledWith('chapter-1', 'fact-1')
    await wrapper.get('[data-testid="chronicle-ref-sect-1"]').trigger('click')
    expect(selectMock).toHaveBeenCalledWith('sect', '7')
  })
})
