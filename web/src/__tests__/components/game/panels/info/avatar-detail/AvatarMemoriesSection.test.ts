import { mount } from '@vue/test-utils'
import { describe, it, expect, vi } from 'vitest'
import AvatarMemoriesSection from '@/components/game/panels/info/avatar-detail/AvatarMemoriesSection.vue'
import type { PersonalAppraisalEntry } from '@/types/core'

function makeEntry(overrides: Partial<PersonalAppraisalEntry> = {}): PersonalAppraisalEntry {
  return {
    appraisal_id: 'ap-1',
    focus_avatar_id: 'a2',
    focus_avatar_name: 'Beta',
    emotion: { name: 'Anger', emoji: '😡', desc: 'Anger' },
    summary: 'He humiliated me before the whole sect.',
    source_event_id: 'ev-1',
    source_event_date: '100年1月',
    valence: -0.8,
    effective_weight: 0.72,
    ...overrides,
  }
}

describe('AvatarMemoriesSection', () => {
  it('renders required fields for each appraisal: focus, emoji, summary, emotion name, date', () => {
    const wrapper = mount(AvatarMemoriesSection, {
      props: {
        appraisals: [makeEntry()],
        title: 'Memorable Moments',
        emptyText: 'No memorable moments yet.',
        strengthLabelFor: () => 'Vivid memory',
      },
    })

    expect(wrapper.text()).toContain('Beta')
    expect(wrapper.text()).toContain('😡')
    expect(wrapper.text()).toContain('He humiliated me before the whole sect.')
    expect(wrapper.text()).toContain('Anger')
    expect(wrapper.text()).toContain('100年1月')
  })

  it('calls strengthLabelFor with the entry effective_weight and renders its returned label', () => {
    const strengthLabelFor = vi.fn((weight: number) => (weight >= 0.65 ? 'Vivid memory' : 'Fading memory'))
    const wrapper = mount(AvatarMemoriesSection, {
      props: {
        appraisals: [makeEntry({ effective_weight: 0.72 })],
        title: 'Memorable Moments',
        emptyText: 'No memorable moments yet.',
        strengthLabelFor,
      },
    })

    expect(strengthLabelFor).toHaveBeenCalledWith(0.72)
    expect(wrapper.text()).toContain('Vivid memory')
  })

  it('emits open-source with the source_event_id when the full-row button is tapped', async () => {
    const wrapper = mount(AvatarMemoriesSection, {
      props: {
        appraisals: [makeEntry({ source_event_id: 'ev-42' })],
        title: 'Memorable Moments',
        emptyText: 'No memorable moments yet.',
        strengthLabelFor: () => 'Vivid memory',
      },
    })

    const button = wrapper.get('button.memory-item')
    await button.trigger('click')

    expect(wrapper.emitted('open-source')).toEqual([['ev-42']])
  })

  it('renders the full row as a single tappable button (no separate nested control)', () => {
    const wrapper = mount(AvatarMemoriesSection, {
      props: {
        appraisals: [makeEntry()],
        title: 'Memorable Moments',
        emptyText: 'No memorable moments yet.',
        strengthLabelFor: () => 'Vivid memory',
      },
    })

    const buttons = wrapper.findAll('button')
    expect(buttons).toHaveLength(1)
    expect(buttons[0]!.classes()).toContain('memory-item')
  })

  it('shows the empty text and no list when there are no appraisals', () => {
    const wrapper = mount(AvatarMemoriesSection, {
      props: {
        appraisals: [],
        title: 'Memorable Moments',
        emptyText: 'No memorable moments yet.',
        strengthLabelFor: () => 'Vivid memory',
      },
    })

    expect(wrapper.text()).toContain('No memorable moments yet.')
    expect(wrapper.findAll('button.memory-item')).toHaveLength(0)
  })

  it('renders the empty state instead of throwing when appraisals is missing entirely', () => {
    // A cached or partial detail payload can omit the field; the panel must
    // degrade to the empty state rather than crash on undefined.length.
    const wrapper = mount(AvatarMemoriesSection, {
      props: {
        appraisals: undefined as unknown as PersonalAppraisalEntry[],
        title: 'Memorable Moments',
        emptyText: 'No memorable moments yet.',
        strengthLabelFor: () => 'Vivid memory',
      },
    })

    expect(wrapper.text()).toContain('No memorable moments yet.')
    expect(wrapper.findAll('button.memory-item')).toHaveLength(0)
  })

  it('applies the strength class from the shared classifier, matching the label bucket', () => {
    const wrapper = mount(AvatarMemoriesSection, {
      props: {
        appraisals: [
          makeEntry({ appraisal_id: 'ap-strong', effective_weight: 0.65 }),
          makeEntry({ appraisal_id: 'ap-moderate', effective_weight: 0.35 }),
          makeEntry({ appraisal_id: 'ap-weak', effective_weight: 0.2 }),
        ],
        title: 'Memorable Moments',
        emptyText: 'No memorable moments yet.',
        strengthLabelFor: () => 'label',
      },
    })

    const badges = wrapper.findAll('.memory-strength')
    expect(badges[0]!.classes()).toContain('is-strong')
    expect(badges[1]!.classes()).toContain('is-moderate')
    expect(badges[2]!.classes()).toContain('is-weak')
  })
})
