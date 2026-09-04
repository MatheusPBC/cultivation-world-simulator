import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import MapLayerControls from '@/components/game/MapLayerControls.vue'
import { createTestI18n } from '@/__tests__/utils/i18n'
import ptGame from '@/locales/pt-BR/game.json'

const ALL_ON = {
  terrain: true,
  elevation: true,
  water: true,
  borders: true,
  routes: true,
  sects: true,
  names: true,
  infrastructure: true,
  institutionalPresence: true,
}

function mountControls(modelValue = { ...ALL_ON, elevation: false, infrastructure: false }) {
  return mount(MapLayerControls, {
    props: { modelValue },
    global: {
      plugins: [createTestI18n({ game: ptGame }, 'pt-BR')],
    },
  })
}

describe('MapLayerControls', () => {
  it('labels every toggle from the locale instead of hard-coded strings', () => {
    const wrapper = mountControls()

    // Labels resolve through i18n, so the panel follows the UI language.
    expect(wrapper.text()).toContain(ptGame.map.layers.terrain.label)
    expect(wrapper.text()).toContain(ptGame.map.layers.elevation.label)
    expect(wrapper.text()).toContain(ptGame.map.layers.institutionalPresence.label)
    expect(wrapper.text()).toContain(ptGame.map.layers.title)
  })

  it('groups layers by the kind of information they describe', () => {
    const wrapper = mountControls()

    const groupTitles = wrapper.findAll('.map-layers__group-title').map(node => node.text())
    expect(groupTitles).toEqual([
      ptGame.map.layers.groups.physical,
      ptGame.map.layers.groups.territorial,
      ptGame.map.layers.groups.organizational,
    ])
  })

  it('exposes each toggle as a switch with a readable on/off state', () => {
    const wrapper = mountControls()

    const terrain = wrapper.get(`[title="${ptGame.map.layers.terrain.label}"]`)
    const elevation = wrapper.get(`[title="${ptGame.map.layers.elevation.label}"]`)

    expect(terrain.attributes('role')).toBe('switch')
    expect(terrain.attributes('aria-checked')).toBe('true')
    expect(elevation.attributes('aria-checked')).toBe('false')
  })

  it('surfaces the route caveat as the toggle hint', () => {
    const wrapper = mountControls()

    expect(wrapper.get(`[title="${ptGame.map.layers.routes.hint}"]`).exists()).toBe(true)
  })

  it('reports how many layers are currently on', () => {
    const wrapper = mountControls()

    // 9 layers, two of them off in the fixture.
    expect(wrapper.get('.map-layers__count').text()).toBe('7/9')
  })

  it('emits a visibility update when a layer is toggled', async () => {
    const wrapper = mountControls()

    await wrapper.get(`[title="${ptGame.map.layers.elevation.label}"]`).trigger('click')

    expect(wrapper.emitted('update:modelValue')?.[0]?.[0]).toEqual(
      expect.objectContaining({ elevation: true }),
    )
  })

  it('starts collapsed so the map surface is clear on entry', async () => {
    const wrapper = mountControls()
    const handle = wrapper.get('.map-layers__handle')

    expect(handle.attributes('aria-expanded')).toBe('false')
    await handle.trigger('click')
    expect(handle.attributes('aria-expanded')).toBe('true')
  })

  it('keeps the active-layer count visible while collapsed', () => {
    const wrapper = mountControls()

    expect(wrapper.get('.map-layers__handle').attributes('aria-expanded')).toBe('false')
    expect(wrapper.get('.map-layers__count').text()).toBe('7/9')
  })
})
