import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import DynastyOverviewModal from '@/components/game/panels/DynastyOverviewModal.vue'

const refreshDetailMock = vi.fn()
const selectMock = vi.fn()

vi.mock('naive-ui', () => ({
  NModal: {
    name: 'NModal',
    template: '<div v-if="show" class="n-modal"><slot /></div>',
    props: ['show', 'title', 'preset'],
  },
  NTag: {
    name: 'NTag',
    template: '<span class="n-tag"><slot /></span>',
    props: ['bordered', 'type', 'size'],
  },
  NSpin: {
    name: 'NSpin',
    template: '<div class="n-spin"><slot /></div>',
    props: ['show'],
  },
}))

vi.mock('@/stores/dynasty', () => ({
  useDynastyStore: () => ({
    detail: {
      overview: {
        name: '晋',
        title: '晋朝',
        royal_surname: '司马',
        royal_house_name: '司马氏',
        desc: '门第森然，士族清谈，朝野重礼而尚名教。',
        effect_desc: '',
        is_low_magic: true,
        current_emperor: {
          name: '司马承安',
          surname: '司马',
          given_name: '承安',
          age: 34,
          max_age: 67,
          is_mortal: true,
        },
      },
      summary: {
        officialCount: 2,
        topOfficialRankName: '州牧',
      },
      officials: [
        {
          id: 'a-1',
          name: '王玄策',
          realm: '金丹',
          officialRankName: '州牧',
          officialRankKey: 'PROVINCE',
          courtReputation: 520,
          sectName: '太一门',
        },
        {
          id: 'a-2',
          name: '李观澜',
          realm: '筑基',
          officialRankName: '县令',
          officialRankKey: 'COUNTY',
          courtReputation: 120,
          sectName: '',
        },
      ],
      imperialCrisis: {
        status: 'active',
        openedMonth: 12,
        emperor: { id: 'emperor-1', name: '司马承安' },
        claimant: { id: 'claimant-1', name: '桓温' },
        supportCount: 1,
        supporters: [{ id: 'supporter-1', name: '王玄策' }],
        evidenceEventIds: [],
        legitimacyFactors: { support: 75, worldly_total: 75, total: 75 },
      },
    },
    overview: {
      name: '晋',
      title: '晋朝',
      royal_surname: '司马',
      royal_house_name: '司马氏',
      desc: '门第森然，士族清谈，朝野重礼而尚名教。',
      effect_desc: '',
      is_low_magic: true,
      current_emperor: {
        name: '司马承安',
        surname: '司马',
        given_name: '承安',
        age: 34,
        max_age: 67,
        is_mortal: true,
      },
    },
    officials: [
      {
        id: 'a-1',
        name: '王玄策',
        realm: '金丹',
        officialRankName: '州牧',
        officialRankKey: 'PROVINCE',
        courtReputation: 520,
        sectName: '太一门',
      },
      {
        id: 'a-2',
        name: '李观澜',
        realm: '筑基',
        officialRankName: '县令',
        officialRankKey: 'COUNTY',
        courtReputation: 120,
        sectName: '',
      },
    ],
    summary: {
      officialCount: 2,
      topOfficialRankName: '州牧',
    },
    imperialCrisis: {
      status: 'active',
      openedMonth: 12,
      emperor: { id: 'emperor-1', name: '司马承安' },
      claimant: { id: 'claimant-1', name: '桓温' },
      supportCount: 1,
      supporters: [{ id: 'supporter-1', name: '王玄策' }],
      evidenceEventIds: [],
      legitimacyFactors: { support: 75, worldly_total: 75, total: 75 },
    },
    isLoading: false,
    isLoaded: true,
    refreshDetail: refreshDetailMock,
    refreshOverview: refreshDetailMock,
  }),
}))

vi.mock('@/stores/ui', () => ({
  useUiStore: () => ({
    select: selectMock,
  }),
}))

describe('DynastyOverviewModal', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  function createWrapper(show = true) {
    const i18n = createI18n({
      legacy: false,
      locale: 'zh-CN',
      messages: {
        'zh-CN': {
          game: {
            dynasty: {
              title: '王朝',
              name: '王朝名',
              royal_house: '皇族',
              style_tag: '王朝风气',
              official_preference: '仕途偏好',
              effect: '王朝效果',
              effect_empty: '当前暂无王朝效果。待官职系统与后续逻辑接入后补充。',
              low_magic: '凡人王朝',
              empty: '暂无王朝数据',
              emperor: {
                title: '当朝皇帝',
                name: '姓名',
                age: '年龄',
                lifespan: '寿元',
                identity: '身份',
                mortal: '凡人',
                empty: '暂无皇帝数据',
              },
              summary: {
                title: '王朝概览',
              },
              officials: {
                title: '在朝修士',
                count: '共 {count} 人',
                empty: '当前暂无有品阶修士',
                realm: '境界',
                court_reputation: '朝廷威望',
                sect: '所属',
                rogue: '散修',
              },
              crisis: {
                title: '正统危机', emperor: '皇帝', claimant: '觊觎者', support: '已获 {count} 人公开支持', supporters: '公开支持者', evidence: '查看因果凭据',
                factors: { office: '官职', reputation: '朝廷威望', cultivation: '修为', support: '支持', celestial: '天道征兆', worldly_total: '世俗根基', total: '正统差额' },
                status: { active: '政治危机正在发酵' },
              },
            },
          },
          common: {
            none: '无',
          },
          realms: {
            FOUNDATION_ESTABLISHMENT: '筑基',
            CORE_FORMATION: '金丹',
          },
        },
      },
    })

    return mount(DynastyOverviewModal, {
      props: { show },
      global: {
        plugins: [i18n],
      },
    })
  }

  it('fetches overview when opened', async () => {
    const wrapper = createWrapper(false)
    await wrapper.setProps({ show: true })
    expect(refreshDetailMock).toHaveBeenCalled()
  })

  it('fetches overview when initially mounted open', () => {
    createWrapper(true)
    expect(refreshDetailMock).toHaveBeenCalled()
  })

  it('renders dynasty summary', () => {
    const wrapper = createWrapper(true)
    const text = wrapper.text()
    expect(text).toContain('晋朝')
    expect(text).toContain('司马氏')
    expect(text).toContain('司马承安')
    expect(text).toContain('34')
    expect(text).toContain('67')
    expect(text).toContain('门第森然')
    expect(text).toContain('凡人王朝')
    expect(text).toContain('当前暂无王朝效果')
    expect(text).toContain('在朝修士')
    expect(text).toContain('王玄策')
    expect(text).toContain('李观澜')
    expect(text).toContain('太一门')
    expect(text).toContain('散修')
    expect(text).toContain('世俗根基')
  })

  it('jumps to avatar detail when clicking an official row', async () => {
    const wrapper = createWrapper(true)
    await wrapper.get('.official-row').trigger('click')
    expect(selectMock).toHaveBeenCalledWith('avatar', 'a-1')
  })

  it('shows declared supporters and opens their avatar detail', async () => {
    const wrapper = createWrapper(true)
    expect(wrapper.text()).toContain('公开支持者')
    expect(wrapper.text()).toContain('王玄策')
    await wrapper.get('.supporter').trigger('click')
    expect(selectMock).toHaveBeenCalledWith('avatar', 'supporter-1')
  })
})
