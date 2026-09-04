import { mount } from '@vue/test-utils'
import { describe, it, expect, beforeEach } from 'vitest'
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

  it('mounts the physical map and the organizational overlays in draw order', () => {
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
    const physicalLayer = wrapper.get('[label="physical-map"]')
    const sectLayer = wrapper.getComponent(SectInfluenceLayer)
    const institutionalLayer = wrapper.getComponent(InstitutionalPresenceLayer)

    expect(rootLayer.attributes()).toHaveProperty('sortable-children')
    expect(physicalLayer.element.parentElement).toBe(rootLayer.element)
    expect(sectLayer.element.parentElement).toBe(rootLayer.element)
    expect(sectLayer.props('zIndex')).toBe(MAP_LAYER_Z_INDEX.sects)
    expect(institutionalLayer.props('zIndex')).toBe(MAP_LAYER_Z_INDEX.institutionalPresence)
    expect(Number(sectLayer.props('zIndex'))).toBeLessThan(Number(institutionalLayer.props('zIndex')))
  })

  it('keeps region names and selection above every territorial overlay', () => {
    // Names and the selection seal are drawn by the renderer inside
    // `physical-map`, so their ordering lives in the shared z-index table.
    expect(MAP_LAYER_Z_INDEX.labels).toBeGreaterThan(MAP_LAYER_Z_INDEX.institutionalPresence)
    expect(MAP_LAYER_Z_INDEX.labels).toBeGreaterThan(MAP_LAYER_Z_INDEX.sects)
    // Region hit areas sit below the overlays so they never eat overlay pixels,
    // but above raw terrain so the land is clickable.
    expect(MAP_LAYER_Z_INDEX.regionPick).toBeGreaterThan(MAP_LAYER_Z_INDEX.physical)
    expect(MAP_LAYER_Z_INDEX.regionPick).toBeLessThan(MAP_LAYER_Z_INDEX.sects)
    expect(MAP_LAYER_Z_INDEX.selection).toBeGreaterThan(MAP_LAYER_Z_INDEX.regionPick)
  })
})
