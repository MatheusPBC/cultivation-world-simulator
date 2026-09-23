import { computed, ref, shallowRef } from 'vue'
import { defineStore } from 'pinia'
import type { ObservatoryView, StatusView } from '../../types/medieval-api'
import { api, asError, type ApiError } from '../api'
import { acceptSnapshot } from '../mappers'

export const useObserverStore = defineStore('medieval-observer', () => {
  const snapshot = shallowRef<ObservatoryView | null>(null)
  const status = shallowRef<StatusView | null>(null)
  const error = shallowRef<ApiError | null>(null)
  const busy = ref(false)
  const updatedAt = ref<number | null>(null)
  const revision = ref(-1)
  const focusEventId = ref<string | null>(null)
  const selection = ref<{ kind: 'settlement' | 'character' | 'polity' | 'organization' | 'site' | 'route' | 'detachment'; id: string } | null>(null)
  let requestId = 0
  const selectedSettlement = computed(() => snapshot.value?.society.settlements.find(s => s.id === selection.value?.id))
  async function refresh() {
    const id = ++requestId
    try {
      const reply = await api.query('observatory')
      const next = acceptSnapshot(reply.data)
      if (id !== requestId) return
      if (snapshot.value?.status.run_id !== next.status.run_id) { selection.value = null; focusEventId.value = null }
      snapshot.value = next; status.value = next.status; revision.value = reply.revision
      error.value = null; updatedAt.value = Date.now()
    } catch (e) { if (id === requestId) error.value = asError(e) }
  }
  async function boot() {
    try {
      status.value = (await api.query('status')).data
      if (status.value.ready) await refresh()
      else error.value = null
    } catch (e) { error.value = asError(e) }
  }
  async function perform(operation: () => Promise<unknown>) {
    if (busy.value) return false
    busy.value = true; error.value = null; requestId++
    try { await operation(); await refresh(); return error.value === null }
    catch (e) { error.value = asError(e); return false }
    finally { busy.value = false }
  }
  return { snapshot, status, error, busy, updatedAt, revision, selection, focusEventId, selectedSettlement, refresh, boot, perform }
})
