import { mount } from '@vue/test-utils'
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import InfoPanelContainer from '@/components/game/panels/info/InfoPanelContainer.vue'
import { createPinia, setActivePinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import { useUiStore } from '@/stores/ui'

function createInfoPanelI18n() {
  return createI18n({
    legacy: false,
    locale: 'zh-CN',
    messages: {
      'zh-CN': {
        ui: {
          close: '关闭',
        },
      },
    },
  })
}

describe('InfoPanelContainer', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('should render successfully', () => {
    const i18n = createInfoPanelI18n()

    const wrapper = mount(InfoPanelContainer, {
      global: {
        plugins: [createPinia(), i18n],
        stubs: {
          AvatarDetail: true,
          SectDetail: true,
          RegionDetail: true,
          InfrastructureSiteDetail: true,
          RouteDetail: true,
        }
      }
    })

    expect(wrapper.exists()).toBe(true)
  })

  it('should not close when pointerdown happens inside portrait panel', async () => {
    const i18n = createInfoPanelI18n()

    const wrapper = mount(InfoPanelContainer, {
      attachTo: document.body,
      global: {
        plugins: [createPinia(), i18n],
        stubs: {
          AvatarDetail: true,
          SectDetail: true,
          RegionDetail: true,
          InfrastructureSiteDetail: true,
          RouteDetail: true,
        }
      }
    })

    const uiStore = useUiStore()
    uiStore.selectedTarget = { type: 'avatar', id: 'avatar-1' }
    uiStore.detailData = { id: 'avatar-1', name: 'Test Avatar' } as any
    await wrapper.vm.$nextTick()

    const closeSpy = vi.spyOn(uiStore, 'clearSelection')
    const portraitPanel = document.createElement('div')
    portraitPanel.className = 'portrait-panel'
    const inner = document.createElement('button')
    portraitPanel.appendChild(inner)
    document.body.appendChild(portraitPanel)

    Object.defineProperty(performance, 'now', {
      configurable: true,
      value: vi.fn(() => 1000),
    })

    inner.dispatchEvent(new Event('pointerdown', { bubbles: true }))
    await wrapper.vm.$nextTick()

    expect(closeSpy).not.toHaveBeenCalled()
  })

  it('should not render region subtitle in header', async () => {
    const i18n = createInfoPanelI18n()

    const wrapper = mount(InfoPanelContainer, {
      global: {
        plugins: [createPinia(), i18n],
        stubs: {
          AvatarDetail: true,
          SectDetail: true,
          RegionDetail: true,
          InfrastructureSiteDetail: true,
          RouteDetail: true,
        },
      },
    })

    const uiStore = useUiStore()
    uiStore.selectedTarget = { type: 'region', id: 'region-1' }
    uiStore.detailData = {
      id: 'region-1',
      name: '千机谷',
      type_name: '宗门驻地',
    } as any
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('千机谷')
    expect(wrapper.text()).not.toContain('宗门驻地')
    expect(wrapper.text()).not.toContain('固有地名')
  })

  it('resolves the infrastructure site detail panel', async () => {
    const i18n = createInfoPanelI18n()
    const siteStub = { template: '<div data-testid="infrastructure-site-detail" />' }
    const wrapper = mount(InfoPanelContainer, {
      global: {
        plugins: [createPinia(), i18n],
        stubs: { InfrastructureSiteDetail: siteStub },
      },
    })
    const uiStore = useUiStore()
    uiStore.selectedTarget = { type: 'site', id: 'bridge-1' }
    uiStore.detailData = {
      id: 'bridge-1', name: 'Ponte', kind: 'bridge', cellRefs: [[0, 0]], regionIds: [1, 2],
      routeIds: [], waterBodyIds: [], capabilityIds: [], ownerRef: null, maintainerRef: null,
      integrity: 0.8, enabled: true, status: 'impaired', x: 0, y: 0, clickable: true, lastEventId: null,
    }
    await wrapper.vm.$nextTick()

    expect(wrapper.find('[data-testid="infrastructure-site-detail"]').exists()).toBe(true)
  })

  it('resolves the route detail panel and uses its id as the title', async () => {
    const i18n = createInfoPanelI18n()
    const routeStub = { template: '<div data-testid="route-detail" />' }
    const wrapper = mount(InfoPanelContainer, {
      global: {
        plugins: [createPinia(), i18n],
        stubs: { RouteDetail: routeStub },
      },
    })
    const uiStore = useUiStore()
    uiStore.selectedTarget = { type: 'route', id: 'route-1' }
    uiStore.detailData = {
      id: 'route-1', endpointRegionIds: [1, 2], mode: 'land', capacity: 100,
      operationalCapacity: 80, quality: 0.8, enabled: true, allowedResourceIds: [],
      dependencySiteIds: [], sourceEventIds: [],
    } as any
    await wrapper.vm.$nextTick()

    expect(wrapper.find('[data-testid="route-detail"]').exists()).toBe(true)
    expect(wrapper.find('.main-title').text()).toBe('route-1')
  })
})
