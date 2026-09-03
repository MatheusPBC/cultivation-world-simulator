import { mount } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import MapLayer from '@/components/game/MapLayer.vue'
import SectInfluenceLayer from '@/components/game/SectInfluenceLayer.vue'
import InstitutionalPresenceLayer from '@/components/game/InstitutionalPresenceLayer.vue'
import { MAP_LAYER_Z_INDEX } from '@/components/game/composables/useMapLayerRenderer'
import { createPinia, setActivePinia } from 'pinia'
import { createTestI18n } from '@/__tests__/utils/i18n'

describe('MapLayer', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('should render successfully', () => {
    const i18n = createTestI18n({}, 'en-US')
    const wrapper = mount(MapLayer, {
      global: {
        plugins: [createPinia(), i18n],
        stubs: {
          container: { template: '<div v-bind="$attrs"><slot /></div>' },
          SectInfluenceLayer: true,
          InstitutionalPresenceLayer: true,
          sprite: true,
          graphics: true
        }
      }
    })

    expect(wrapper.exists()).toBe(true)
    const rootLayer = wrapper.get('[label="map-layers"]')
    const sectLayer = wrapper.getComponent(SectInfluenceLayer)
    const institutionalLayer = wrapper.getComponent(InstitutionalPresenceLayer)
    const labelLayer = wrapper.get('[label="region-labels"]')
    expect(rootLayer.attributes()).toHaveProperty('sortable-children')
    expect(sectLayer.element.parentElement).toBe(rootLayer.element)
    expect(labelLayer.element.parentElement).toBe(rootLayer.element)
    expect(sectLayer.props('zIndex')).toBe(MAP_LAYER_Z_INDEX.sects)
    expect(institutionalLayer.props('zIndex')).toBe(MAP_LAYER_Z_INDEX.institutionalPresence)
    expect(Number(sectLayer.props('zIndex'))).toBeLessThan(Number(institutionalLayer.props('zIndex')))
    expect(Number(sectLayer.props('zIndex'))).toBeLessThan(
      Number(labelLayer.attributes('z-index')),
    )
  })
})
