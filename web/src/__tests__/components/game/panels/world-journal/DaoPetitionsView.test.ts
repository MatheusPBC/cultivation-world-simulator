import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { describe, expect, it } from 'vitest'
import DaoPetitionsView from '@/components/game/panels/world-journal/DaoPetitionsView.vue'

describe('DaoPetitionsView', () => {
  it('renders localized tradition and initiator labels', () => {
    const i18n = createI18n({
      legacy: false,
      locale: 'zh-CN',
      messages: {
        'zh-CN': {
          game: {
            info_panel: { region: { dao_traditions: { mercy: '慈悲' } } },
            world_journal: {
              why_button: '为什么？',
              dao: {
                eyebrow: '天道意志', title: '天道请愿', description: '说明', loading: '加载', retry: '重试', empty: '空',
                silence: '沉默', sign: '征兆', favor: '赐福', history: '已回应的请愿', response_why: '查看回应缘由',
                rite_evidence: '由近一年 {count} 次仪式支撑', status: { signed: '降下征兆' }, initiator: { court: '朝廷' },
              },
            },
          },
        },
      },
    })
    const wrapper = mount(DaoPetitionsView, {
      props: {
        loading: false,
        error: false,
        respondingId: null,
        petitions: {
          pending: [{ id: 'p1', initiator_kind: 'court', initiator_id: '1', initiator_name: 'Court', region_id: 7, tradition: 'mercy', motivated_event_ids: ['e1'], rite_event_ids: ['r1', 'r2', 'r3'], content: 'Please witness.', created_month: 1, status: 'pending', response_event_id: null, response_content: '', favor_expires_month: null }],
          history: [],
        },
      },
      global: { plugins: [i18n] },
    })

    expect(wrapper.text()).toContain('慈悲')
    expect(wrapper.text()).toContain('Court')
    expect(wrapper.text()).not.toContain('mercy · court')
  })

  it('keeps resolved petitions secondary and opens their response evidence', async () => {
    const i18n = createI18n({
      legacy: false,
      locale: 'zh-CN',
      messages: { 'zh-CN': { game: { info_panel: { region: { dao_traditions: { mercy: '慈悲' } } }, world_journal: { why_button: '为什么？', dao: {
        eyebrow: '天道意志', title: '天道请愿', description: '说明', loading: '加载', retry: '重试', empty: '空', silence: '沉默', sign: '征兆', favor: '赐福', history: '已回应的请愿', response: '天道回应', response_why: '查看回应缘由', favor_until: '机会持续至第 {month} 月', rite_evidence: '由近一年 {count} 次仪式支撑', status: { favored: '赐予机会' }, initiator: { court: '朝廷' },
      } } } } },
    })
    const wrapper = mount(DaoPetitionsView, {
      props: { loading: false, error: false, respondingId: null, petitions: {
        pending: [],
        history: [{ id: 'p1', initiator_kind: 'court', initiator_id: '1', initiator_name: 'Court', region_id: 7, tradition: 'mercy', motivated_event_ids: ['cause'], rite_event_ids: ['r1', 'r2', 'r3'], content: 'Please witness.', created_month: 1, status: 'favored', response_event_id: 'answer-event', response_content: 'A sign crosses the sky.', favor_expires_month: 13 }],
      } },
      global: { plugins: [i18n] },
    })

    expect(wrapper.get('[data-testid="dao-petition-history"]').text()).toContain('已回应的请愿')
    expect(wrapper.text()).toContain('A sign crosses the sky.')
    expect(wrapper.text()).toContain('机会持续至第 13 月')
    await wrapper.get('button.why').trigger('click')
    expect(wrapper.emitted('why')).toEqual([['answer-event']])
  })
})
