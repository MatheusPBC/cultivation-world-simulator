import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia } from 'pinia'
import App from '../ObserverApp.vue'
import { medievalI18n } from '../i18n'
import fixture from './world.json'

let wrapper: VueWrapper | undefined
let data = structuredClone(fixture)
let ready = false
let saved: typeof data | null = null
const posts: { name: string; body: Record<string, unknown> }[] = []
beforeEach(() => {
  vi.useRealTimers(); ready = false; saved = null; data = structuredClone(fixture); posts.length = 0
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const path = url.split('?')[0].split('/').pop()
    if (init?.method === 'POST') {
      const body = JSON.parse(init.body as string)
      posts.push({ name: path!, body })
      if (path === 'create') ready = true
      if (path === 'step') { data.world.day += 30; data.status.day = data.world.day }
      if (path === 'save') saved = structuredClone(data)
      if (path === 'load' && saved) data = structuredClone(saved)
      return reply({ ...data.status, ready })
    }
    if (path === 'status') return reply({ ...data.status, ready })
    if (path === 'options') return reply({ defaults: data.world.config, map_id: data.map.map_id, map_name: data.map.name, ai_available: false })
    if (path === 'observatory') return reply({ ...data, status: { ...data.status, ready } })
    if (path === 'events') return reply({ items: [], next_after: 0, has_more: false })
    if (path === 'saves') return reply(saved ? [{ save_id: 'teste', day: saved.world.day, compatible: true, size_bytes: 4000, modified_at: '2026-09-13T00:00:00Z' }] : [])
    throw new Error('Unexpected API request: ' + url)
  }))
})
afterEach(() => { wrapper?.unmount(); vi.unstubAllGlobals() })
const reply = (value: unknown) => new Response(JSON.stringify({ ok: true, revision: 1, data: value }))
async function open() {
  wrapper = mount(App, { global: { plugins: [createPinia(), medievalI18n] } })
  await flushPromises(); return wrapper
}
it('creates twelve relevant characters and advances the displayed canonical date', async () => {
  const app = await open()
  expect(app.find('input[name="character_count"]').element).toHaveProperty('value', '12')
  await app.get('form[data-testid="create-world"]').trigger('submit')
  await flushPromises()
  expect(posts[0]).toEqual({ name: 'create', body: { seed: 73, character_count: 12, replace: false } })
  expect(app.text()).toContain('10.900')
  await app.get('[data-testid="step"]').trigger('click'); await flushPromises()
  expect(app.get('[data-testid="absolute-day"]').text()).toContain('30')
})
it('opens a settlement from the accessible map list and shows material state', async () => {
  ready = true
  const app = await open()
  await app.get('[data-settlement="pedraclara"]').trigger('click')
  expect(app.get('[data-testid="inspector"]').text()).toContain('Pedraclara')
  expect(app.get('[data-testid="inspector"]').text()).toContain('2.400')
  expect(app.get('[data-testid="inspector"]').text()).toContain('Saúde')
})
it('loads the saved date through the real save panel workflow', async () => {
  ready = true
  const app = await open()
  await app.get('[data-testid="open-saves"]').trigger('click'); await flushPromises()
  await app.get('input[name="save_id"]').setValue('teste')
  await app.get('form[data-testid="save-world"]').trigger('submit'); await flushPromises()
  expect(posts.at(-1)).toEqual({ name: 'save', body: { save_id: 'teste', overwrite: false } })
  await app.get('[data-testid="close-saves"]').trigger('click')
  await app.get('[data-testid="step"]').trigger('click'); await flushPromises()
  await app.get('[data-testid="open-saves"]').trigger('click'); await flushPromises()
  await app.get('[data-load="teste"]').trigger('click'); await flushPromises()
  await app.get('[data-testid="confirm-load"]').trigger('click'); await flushPromises()
  expect(app.get('[data-testid="absolute-day"]').text()).toContain('0')
})
it('shows connection failure and keeps the last date, not a fake successful step', async () => {
  ready = true
  const app = await open()
  vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('offline') }))
  await app.get('[data-testid="step"]').trigger('click'); await flushPromises()
  expect(app.get('[role="alert"]').text()).toContain('Sem conexão')
  expect(app.get('[data-testid="absolute-day"]').text()).toContain('0')
})
