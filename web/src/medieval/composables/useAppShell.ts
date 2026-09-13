import { computed, onMounted, onUnmounted, ref } from 'vue'
import { api, asError } from '../api'
import { useObserverStore } from '../stores/world'

export function useAppShell() {
  const store = useObserverStore()
  const booted = ref(false)
  const overlay = ref<'saves' | 'create' | null>(null)
  const seed = ref(73), count = ref(12), replace = ref(false)
  const scene = computed(() => !booted.value ? 'boot' : store.snapshot ? 'game' : 'splash')
  let timer: ReturnType<typeof setTimeout> | undefined
  let stopped = false
  async function poll() {
    if (stopped) return
    if (!document.hidden && !store.busy) {
      if (store.snapshot) await store.refresh()
      else await store.boot()
    }
    if (!stopped) timer = setTimeout(poll, store.status?.paused ? 4000 : 1000)
  }
  onMounted(async () => {
    await store.boot()
    try { const { data } = await api.query('options'); seed.value = data.defaults.seed; count.value = data.defaults.character_count }
    catch (e) { store.error = asError(e) }
    booted.value = true
    if (!stopped) timer = setTimeout(poll, 1000)
  })
  onUnmounted(() => { stopped = true; clearTimeout(timer) })
  async function create() {
    const ok = await store.perform(() => api.command('create', { seed: seed.value, character_count: count.value, replace: replace.value }))
    if (ok) { overlay.value = null; replace.value = false }
  }
  return { store, scene, overlay, seed, count, replace, create }
}
