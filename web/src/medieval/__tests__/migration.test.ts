import { expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import App from '../ObserverApp.vue'
import { medievalI18n } from '../i18n'
import { acceptSnapshot } from '../mappers'
import fixture from './world.json'

const reply = (value: unknown) => new Response(JSON.stringify({ ok: true, revision: 1, data: value }))
async function open(data = structuredClone(fixture)) {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const path = url.split('?')[0].split('/').pop()
    if (path === 'status') return reply(data.status)
    if (path === 'options') return reply({ defaults: data.world.config, map_id: data.map.map_id, map_name: data.map.name, ai_available: false })
    if (path === 'observatory') return reply(data)
    if (path === 'events') return reply({ items: [], next_after: 0, has_more: false })
    throw new Error('Unexpected API request: ' + url)
  }))
  const wrapper = mount(App, { global: { plugins: [createPinia(), medievalI18n] } })
  await flushPromises()
  return wrapper
}

it('projects active migration with named people, provision and account balance', async () => {
  const wrapper = await open()
  await wrapper.findAll('nav.inspector-tabs button').find(button => button.text() === 'Migrações')!.trigger('click')
  const panel = wrapper.get('[data-migration="migration:brumafria:pedraclara:1"]')
  expect(panel.text()).toContain('Brumafria → Pedraclara')
  expect(panel.text()).toContain('Kaela Valverde')
  expect(panel.text()).toContain('Saldo da viagem')
  expect(panel.text()).toContain('20.000')
  await wrapper.unmount()
  vi.unstubAllGlobals()
})

it('states explicitly when no migration is active', async () => {
  const data = structuredClone(fixture)
  data.society.migrations = []
  const wrapper = await open(data)
  await wrapper.findAll('nav.inspector-tabs button').find(button => button.text() === 'Migrações')!.trigger('click')
  expect(wrapper.text()).toContain('Nenhuma migração em curso')
  await wrapper.unmount()
  vi.unstubAllGlobals()
})

it('rejects snapshots that omit migration projection fields', () => {
  const data = structuredClone(fixture)
  delete (data.society as { migrations?: unknown }).migrations
  expect(() => acceptSnapshot(data)).toThrow('incompleto')
})

it('labels a returning journey by its current destination', async () => {
  const data = structuredClone(fixture)
  data.society.migrations[0].returning = true
  data.society.migrations[0].destination_id = 'brumafria'
  const wrapper = await open(data)
  await wrapper.findAll('nav.inspector-tabs button').find(button => button.text() === 'Migrações')!.trigger('click')
  expect(wrapper.get('[data-migration="migration:brumafria:pedraclara:1"] h3').text()).toBe('Retorno a Brumafria')
  await wrapper.unmount()
  vi.unstubAllGlobals()
})
