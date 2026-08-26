import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { describe, expect, it, vi } from 'vitest'

import ChronicleDossierDrawer from '@/components/game/panels/world-journal/ChronicleDossierDrawer.vue'

const openWhyMock = vi.fn()

function mountDrawer() {
  return mount(ChronicleDossierDrawer, {
    props: {
      open: true,
      dossier: {
        chapter_id: 'c1',
        anchor: { id: 'anchor-1', kind: 'event', label: 'Claim', target_id: 'e2', claim_kind: 'fact', source_event_ids: ['e1'] },
        focal_event: null,
        sequence: [{ id: 'e1', text: 'first', content: 'first', year: 1, month: 1, month_stamp: 1, related_avatar_ids: [], is_major: false, is_story: false, created_at: 1 }],
        pruned_source_ids: ['gone'],
        truncated: true,
      },
      loading: false,
      error: false,
      onClose: vi.fn(),
      onOpenWhy: openWhyMock,
    },
    global: { plugins: [createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': { common: { year: '年', month: '月' }, game: { world_journal: { chronicle: { dossier: '因果档案', close: '关闭', sequence: '因果序列', sequence_empty: '没有事件', loading: '加载中', dossier_error: '加载失败', pruned: '来源已清理', truncated: '序列已截断', why: '为什么？' } } } } } })] },
  })
}

describe('ChronicleDossierDrawer', () => {
  it('shows pruned and truncated states and delegates Why per event', async () => {
    const wrapper = mountDrawer()

    expect(wrapper.text()).toContain('来源已清理')
    expect(wrapper.text()).toContain('序列已截断')
    await wrapper.get('[data-testid="dossier-why-e1"]').trigger('click')
    expect(openWhyMock).toHaveBeenCalledWith('e1')
  })
})
