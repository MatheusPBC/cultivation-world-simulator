import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import MapLayerControls from '@/components/game/MapLayerControls.vue'

describe('MapLayerControls', () => {
  it('starts with the requested visible layers and exposes accessible toggles in PT-BR', () => {
    const wrapper = mount(MapLayerControls, {
      props: {
        modelValue: {
          terrain: true,
          elevation: false,
          water: true,
          borders: true,
          routes: true,
          sects: true,
          names: true,
          infrastructure: false,
          institutionalPresence: true,
        },
      },
    })

    expect(wrapper.get('button[aria-label="Terreno"]').attributes('aria-pressed')).toBe('true')
    expect(wrapper.get('button[aria-label="Elevação"]').attributes('aria-pressed')).toBe('false')
    expect(wrapper.get('button[aria-label="Corpos d\'água"]').attributes('aria-pressed')).toBe('true')
  })

  it('emits a visibility update when a layer is toggled', async () => {
    const wrapper = mount(MapLayerControls, {
      props: {
        modelValue: {
          terrain: true,
          elevation: false,
          water: true,
          borders: true,
          routes: true,
          sects: true,
          names: true,
          infrastructure: false,
          institutionalPresence: true,
        },
      },
    })

    await wrapper.get('button[aria-label="Elevação"]').trigger('click')

    expect(wrapper.emitted('update:modelValue')?.[0]?.[0]).toEqual(expect.objectContaining({ elevation: true }))
  })

  it('exposes the infrastructure toggle in PT-BR', () => {
    const wrapper = mount(MapLayerControls, {
      props: {
        modelValue: {
          terrain: true,
          elevation: false,
          water: true,
          borders: true,
          routes: true,
          sects: true,
          names: true,
          infrastructure: true,
          institutionalPresence: true,
        },
      },
    })

    expect(wrapper.get('button[aria-label="Infraestrutura"]').attributes('aria-pressed')).toBe('true')
  })

  it('exposes the institutional presence toggle in PT-BR', () => {
    const wrapper = mount(MapLayerControls, {
      props: {
        modelValue: {
          terrain: true,
          elevation: false,
          water: true,
          borders: true,
          routes: true,
          sects: true,
          names: true,
          infrastructure: true,
          institutionalPresence: false,
        },
      },
    })

    expect(wrapper.get('button[aria-label="Presença institucional"]').attributes('aria-pressed')).toBe('false')
  })
})
