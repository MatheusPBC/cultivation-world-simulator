import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { h, defineComponent, nextTick, ref } from 'vue'
import { setActivePinia, createPinia } from 'pinia'

// Use vi.hoisted to define mock functions that will be used by vi.mock.
const { mockGetPhenomenaList, mockChangePhenomenon, mockSuccess, mockError } = vi.hoisted(() => ({
  mockGetPhenomenaList: vi.fn(),
  mockChangePhenomenon: vi.fn(),
  mockSuccess: vi.fn(),
  mockError: vi.fn(),
}))

const refreshDynastyOverviewMock = vi.hoisted(() => vi.fn())
const refreshAvatarOverviewMock = vi.hoisted(() => vi.fn())

// Mutable store state that can be modified in tests.
let mockYear = 100
let mockMonth = 5
let mockCurrentPhenomenon: any = { id: 1, name: 'Test Phenomenon', rarity: 'R' }
let mockActiveDomains: any[] = []
let mockPhenomenaList: any[] = [
  { id: 1, name: 'Phenomenon 1', rarity: 'N', desc: 'Desc 1', effect_desc: 'Effect 1' },
  { id: 2, name: 'Phenomenon 2', rarity: 'R', desc: 'Desc 2', effect_desc: 'Effect 2' },
  { id: 3, name: 'Phenomenon 3', rarity: 'SSR', desc: 'Desc 3', effect_desc: 'Effect 3' },
]
let mockIsConnected = true
let mockAvatarOverview: any = {
  summary: {
    totalCount: 0,
    aliveCount: 0,
    deadCount: 0,
    sectMemberCount: 0,
    rogueCount: 0,
  },
  realmDistribution: [],
}
let mockAvatarOverviewLoaded = false
const mockFetch = vi.fn()

async function settleAsyncPanels() {
  await nextTick()
}

// Mock vue-i18n.
vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    locale: ref('zh-CN'),
    t: (key: string, params?: any) => {
      if (params) return `${key}:${JSON.stringify(params)}`
      return key
    },
  }),
}))

// Mock stores.
vi.mock('@/stores/world', () => ({
  useWorldStore: () => ({
    get year() { return mockYear },
    get month() { return mockMonth },
    get currentPhenomenon() { return mockCurrentPhenomenon },
    get activeDomains() { return mockActiveDomains },
    get phenomenaList() { return mockPhenomenaList },
    getPhenomenaList: mockGetPhenomenaList,
    changePhenomenon: mockChangePhenomenon,
  }),
}))

vi.mock('@/stores/socket', () => ({
  useSocketStore: () => ({
    get isConnected() { return mockIsConnected },
  }),
}))

vi.mock('@/stores/dynasty', () => ({
  useDynastyStore: () => ({
    overview: {
      name: '晋',
      title: '晋朝',
      royal_surname: '司马',
      royal_house_name: '司马氏',
      desc: '门第森然。',
      effect_desc: '',
      is_low_magic: true,
    },
    isLoading: false,
    isLoaded: true,
    refreshOverview: refreshDynastyOverviewMock,
  }),
}))

vi.mock('@/stores/avatarOverview', () => ({
  useAvatarOverviewStore: () => ({
    get overview() { return mockAvatarOverview },
    get isLoaded() { return mockAvatarOverviewLoaded },
    refreshOverview: refreshAvatarOverviewMock,
  }),
}))

// Mock naive-ui.
vi.mock('naive-ui', () => ({
  NModal: defineComponent({
    name: 'NModal',
    props: ['show', 'preset', 'title'],
    emits: ['update:show'],
    setup(props, { slots, emit }) {
      return () => props.show ? h('div', {
        class: 'n-modal-stub',
        onClick: () => emit('update:show', false),
      }, slots.default?.()) : null
    },
  }),
  NList: defineComponent({
    name: 'NList',
    props: ['hoverable', 'clickable'],
    setup(_, { slots }) {
      return () => h('div', { class: 'n-list-stub' }, slots.default?.())
    },
  }),
  NListItem: defineComponent({
    name: 'NListItem',
    emits: ['click'],
    setup(_, { slots, emit }) {
      return () => h('div', {
        class: 'n-list-item-stub',
        onClick: () => emit('click'),
      }, slots.default?.())
    },
  }),
  NTag: defineComponent({
    name: 'NTag',
    props: ['size', 'bordered', 'color'],
    setup(_, { slots }) {
      return () => h('span', { class: 'n-tag-stub' }, slots.default?.())
    },
  }),
  NEmpty: defineComponent({
    name: 'NEmpty',
    props: ['description'],
    setup(props) {
      return () => h('div', { class: 'n-empty-stub' }, props.description)
    },
  }),
  NSpin: defineComponent({
    name: 'NSpin',
    props: ['show'],
    setup(_, { slots }) {
      return () => h('div', { class: 'n-spin-stub' }, slots.default?.())
    },
  }),
  useMessage: () => ({
    success: mockSuccess,
    error: mockError,
  }),
}))

// Stub StatusWidget.
const StatusWidgetStub = defineComponent({
  name: 'StatusWidget',
  props: ['label', 'icon', 'accent', 'disablePopover'],
  emits: ['trigger-click'],
  setup(props, { emit }) {
    return () => h('div', {
      class: 'status-widget-stub',
      'data-label': props.label,
      'data-icon': props.icon,
      'data-accent': props.accent,
      onClick: () => emit('trigger-click'),
    }, props.label)
  },
})

// Stub SimClock: the clock owns date, run state and the pause control.
const SimClockStub = defineComponent({
  name: 'SimClock',
  props: ['year', 'month', 'paused', 'connected', 'compact'],
  emits: ['toggle-pause', 'open-time'],
  setup(props) {
    return () => h('div', { class: 'sim-clock-stub' }, `${props.year}/${props.month}`)
  },
})

import StatusBar from '@/components/layout/StatusBar.vue'

describe('StatusBar', () => {
  const globalConfig = {
    global: {
      directives: {
        sound: () => {}
      },
      stubs: {
        StatusWidget: StatusWidgetStub,
        SimClock: SimClockStub,
        TimeOverviewModal: true,
        AvatarOverviewModal: true,
        WorldSecretModal: true,
      },
    },
  }

  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.stubGlobal('fetch', mockFetch)

    // Reset mock values.
    mockYear = 100
    mockMonth = 5
    mockCurrentPhenomenon = { id: 1, name: 'Test Phenomenon', rarity: 'R' }
    mockActiveDomains = []
    mockIsConnected = true
    mockAvatarOverview = {
      summary: {
        totalCount: 0,
        aliveCount: 0,
        deadCount: 0,
        sectMemberCount: 0,
        rogueCount: 0,
      },
      realmDistribution: [],
    }
    mockAvatarOverviewLoaded = false

    // Setup default mock implementations.
    mockGetPhenomenaList.mockImplementation(() => Promise.resolve())
    mockChangePhenomenon.mockImplementation(() => Promise.resolve())
    mockFetch.mockResolvedValue({
      ok: true,
      text: () => Promise.resolve([
        'title,title_id,name_id,desc_id,desc',
        '标题,标题ID,名称ID,描述ID,描述',
        '简介,WORLD_INFO_INTRO_TITLE,WORLD_INFO_INTRO_NAME,WORLD_INFO_INTRO_DESC,这是一个诸多修士竞相修行的修仙世界。',
      ].join('\n')),
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows the simulation date through the clock', () => {
    mockYear = 200
    mockMonth = 12

    const wrapper = mount(StatusBar, globalConfig)

    const clock = wrapper.getComponent(SimClockStub)
    expect(clock.props('year')).toBe(200)
    expect(clock.props('month')).toBe(12)
  })

  it('binds the run/pause control to the clock rather than a detached corner button', () => {
    const wrapper = mount(StatusBar, { ...globalConfig, props: { paused: true } })

    const clock = wrapper.getComponent(SimClockStub)
    expect(clock.props('paused')).toBe(true)

    clock.vm.$emit('toggle-pause')
    expect(wrapper.emitted('toggle-pause')).toHaveLength(1)
  })

  it('passes connection state to the clock', () => {
    mockIsConnected = false

    const wrapper = mount(StatusBar, globalConfig)

    expect(wrapper.getComponent(SimClockStub).props('connected')).toBe(false)
  })

  it('opens the time panel from the clock readout', async () => {
    const wrapper = mount(StatusBar, globalConfig)

    wrapper.getComponent(SimClockStub).vm.$emit('open-time')
    await settleAsyncPanels()

    expect(wrapper.find('time-overview-modal-stub').exists()).toBe(true)
  })

  describe('navigation rail', () => {
    it('organises the panels into world, powers and records groups', () => {
      const wrapper = mount(StatusBar, globalConfig)

      const groups = wrapper.findAll('.hud__group')
      expect(groups).toHaveLength(3)

      // World: phenomenon + hidden domain + world secret + world info.
      expect(groups[0].findAll('.status-widget-stub')).toHaveLength(4)
      // Powers: sect relations + dynasty + mortals.
      expect(groups[1].findAll('.status-widget-stub')).toHaveLength(3)
      // Records: characters + rankings + tournament.
      expect(groups[2].findAll('.status-widget-stub')).toHaveLength(3)
    })

    it('drops the phenomenon entry when no phenomenon is active', () => {
      mockCurrentPhenomenon = null

      const wrapper = mount(StatusBar, globalConfig)

      expect(wrapper.findAll('.status-widget-stub')).toHaveLength(9)
    })

    it('spends colour only on the phenomenon, whose rarity is real state', () => {
      const wrapper = mount(StatusBar, globalConfig)

      const widgets = wrapper.findAll('.status-widget-stub')
      const accented = widgets.filter(widget => widget.attributes('data-accent'))
      expect(accented).toHaveLength(1)
      // R rarity -> jade from the shared palette.
      expect(accented[0].attributes('data-accent')).toBe('#6fb3a3')
    })

    it('names the phenomenon without decorative brackets', () => {
      mockCurrentPhenomenon = { id: 1, name: 'Ano da Hostilidade', rarity: 'SSR' }

      const wrapper = mount(StatusBar, globalConfig)

      const widget = wrapper.findAll('.status-widget-stub')[0]
      expect(widget.attributes('data-label')).toBe('Ano da Hostilidade')
      expect(widget.attributes('data-accent')).toBe('#d9b877')
    })

    it('gives every entry an icon so the rail stays readable when labels collapse', () => {
      const wrapper = mount(StatusBar, globalConfig)

      for (const widget of wrapper.findAll('.status-widget-stub')) {
        expect(widget.attributes('data-icon')).toBeTruthy()
      }
    })

    it('opens the phenomenon selector after loading the list', async () => {
      const wrapper = mount(StatusBar, globalConfig)

      await wrapper.findAll('.status-widget-stub')[0].trigger('click')
      await settleAsyncPanels()

      expect(mockGetPhenomenaList).toHaveBeenCalled()
      expect(wrapper.find('.n-modal-stub').exists()).toBe(true)
    })

    it('fetches the avatar overview before opening its panel', async () => {
      const wrapper = mount(StatusBar, globalConfig)

      const records = wrapper.findAll('.hud__group')[2]
      await records.findAll('.status-widget-stub')[0].trigger('click')
      await nextTick()

      expect(refreshAvatarOverviewMock).toHaveBeenCalled()
    })
  })

  describe('changePhenomenon', () => {
    it('should call changePhenomenon on selection', async () => {
      const wrapper = mount(StatusBar, globalConfig)

      await wrapper.findAll('.status-widget-stub')[0].trigger('click')
      await settleAsyncPanels()

      const listItems = wrapper.findAll('.n-list-item-stub')
      expect(listItems.length).toBeGreaterThan(0)

      await listItems[0].trigger('click')
      await settleAsyncPanels()

      expect(mockChangePhenomenon).toHaveBeenCalled()
    })

    it('should show success message on successful change', async () => {
      mockChangePhenomenon.mockImplementation(() => Promise.resolve())

      const wrapper = mount(StatusBar, globalConfig)

      await wrapper.findAll('.status-widget-stub')[0].trigger('click')
      await settleAsyncPanels()

      await wrapper.findAll('.n-list-item-stub')[0].trigger('click')
      await settleAsyncPanels()

      expect(mockSuccess).toHaveBeenCalled()
    })

    it('should show error message on failed change', async () => {
      mockChangePhenomenon.mockImplementation(() => Promise.reject(new Error('Failed')))

      const wrapper = mount(StatusBar, globalConfig)

      await wrapper.findAll('.status-widget-stub')[0].trigger('click')
      await settleAsyncPanels()

      await wrapper.findAll('.n-list-item-stub')[0].trigger('click')
      await settleAsyncPanels()

      expect(mockError).toHaveBeenCalled()
    })
  })

  it('exposes the system menu from the bar instead of a floating map button', async () => {
    const wrapper = mount(StatusBar, globalConfig)

    await wrapper.get('.hud__menu').trigger('click')

    expect(wrapper.emitted('open-menu')).toHaveLength(1)
  })
})
