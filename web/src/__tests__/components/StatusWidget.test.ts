import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { h, defineComponent } from 'vue'

vi.mock('naive-ui', () => ({
  NPopover: defineComponent({
    name: 'NPopover',
    props: ['trigger', 'placement'],
    setup(_, { slots }) {
      return () => h('div', { class: 'n-popover-stub' }, [
        slots.trigger?.(),
        slots.default?.(),
      ])
    },
  }),
}))

import StatusWidget from '@/components/layout/StatusWidget.vue'

const soundDirective = {
  mounted() {},
}

describe('StatusWidget', () => {
  const defaultProps = {
    label: 'Test Label',
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the label', () => {
    const wrapper = mount(StatusWidget, {
      props: defaultProps,
      global: {
        directives: {
          sound: soundDirective,
        },
      },
    })

    expect(wrapper.text()).toContain('Test Label')
  })

  it('renders the icon when icon url is provided', () => {
    const wrapper = mount(StatusWidget, {
      props: {
        ...defaultProps,
        icon: '/icons/test.svg',
      },
      global: {
        directives: {
          sound: soundDirective,
        },
      },
    })

    const icon = wrapper.find('.widget-icon')
    expect(icon.exists()).toBe(true)
    expect(icon.attributes('style')).toContain('url(/icons/test.svg)')
  })

  it('exposes a supplied accent as a custom property', () => {
    const wrapper = mount(StatusWidget, {
      props: {
        ...defaultProps,
        accent: '#ff0000',
      },
      global: {
        directives: {
          sound: soundDirective,
        },
      },
    })

    const trigger = wrapper.find('.widget-trigger')
    expect(trigger.attributes('style')).toContain('--widget-accent: #ff0000')
  })

  it('inherits the rail colour when no accent is supplied', () => {
    const wrapper = mount(StatusWidget, {
      props: defaultProps,
      global: {
        directives: {
          sound: soundDirective,
        },
      },
    })

    // No inline colour at all: plain entries take the bar's text token, which
    // is what keeps the rail from turning back into a rainbow.
    const trigger = wrapper.find('.widget-trigger')
    expect(trigger.attributes('style')).toBeUndefined()
  })

  it('emits trigger-click when clicked', async () => {
    const wrapper = mount(StatusWidget, {
      props: defaultProps,
      global: {
        directives: {
          sound: soundDirective,
        },
      },
    })

    await wrapper.find('.widget-trigger').trigger('click')

    expect(wrapper.emitted('trigger-click')).toBeTruthy()
    expect(wrapper.emitted('trigger-click')?.length).toBe(1)
  })

  it('skips popover when disablePopover is true', () => {
    const wrapper = mount(StatusWidget, {
      props: {
        ...defaultProps,
        disablePopover: true,
      },
      global: {
        directives: {
          sound: soundDirective,
        },
      },
    })

    expect(wrapper.find('.n-popover-stub').exists()).toBe(false)
    expect(wrapper.find('.widget-trigger').exists()).toBe(true)
  })

  it('renders the single slot inside popover mode', () => {
    const wrapper = mount(StatusWidget, {
      props: defaultProps,
      slots: {
        single: '<div class="custom-single">Custom Content</div>',
      },
      global: {
        directives: {
          sound: soundDirective,
        },
      },
    })

    expect(wrapper.find('.custom-single').exists()).toBe(true)
    expect(wrapper.text()).toContain('Custom Content')
  })

  it('separates entries with chrome rather than a literal pipe glyph', () => {
    const wrapper = mount(StatusWidget, {
      props: defaultProps,
      global: {
        directives: {
          sound: soundDirective,
        },
      },
    })

    // Grouping is done by the rail's hairline borders, so the widget no longer
    // prints a `|` of its own.
    expect(wrapper.find('.divider').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('|')
  })

  it('is a real button, so it is reachable and activatable by keyboard', () => {
    const wrapper = mount(StatusWidget, {
      props: { ...defaultProps, disablePopover: true },
      global: {
        directives: {
          sound: soundDirective,
        },
      },
    })

    const trigger = wrapper.get('.widget-trigger')
    expect(trigger.element.tagName).toBe('BUTTON')
    expect(trigger.attributes('type')).toBe('button')
    expect(trigger.attributes('title')).toBe('Test Label')
  })

  it('applies an accent only when one is supplied', () => {
    const plain = mount(StatusWidget, {
      props: defaultProps,
      global: { directives: { sound: soundDirective } },
    })
    expect(plain.get('.widget-trigger').classes()).not.toContain('widget-trigger--accented')

    const accented = mount(StatusWidget, {
      props: { ...defaultProps, accent: '#d9b877' },
      global: { directives: { sound: soundDirective } },
    })
    const trigger = accented.get('.widget-trigger')
    expect(trigger.classes()).toContain('widget-trigger--accented')
    expect(trigger.attributes('style')).toContain('#d9b877')
  })
})
