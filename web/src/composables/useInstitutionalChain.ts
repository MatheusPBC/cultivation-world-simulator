import { onBeforeUnmount, shallowRef, ref, watch, type MaybeRefOrGetter, toValue } from 'vue'
import { institutionalChainApi } from '@/api'
import type { InstitutionalOwnerKindDTO } from '@/types/api'
import type { InstitutionalChain } from '@/api/mappers/institutionalChain'

export function useInstitutionalChain(ownerKind: MaybeRefOrGetter<InstitutionalOwnerKindDTO>, ownerId: MaybeRefOrGetter<string | number | null | undefined>, worldRevision: MaybeRefOrGetter<number> = 0) {
  const chain = shallowRef<InstitutionalChain | null>(null)
  const loading = ref(false)
  const error = ref(false)
  let controller: AbortController | null = null
  let request = 0
  async function load(more: 'commitments' | 'events' | null = null) {
    const id = toValue(ownerId)
    controller?.abort()
    const token = ++request
    if (id == null || id === '') { chain.value = null; loading.value = false; return }
    controller = new AbortController(); loading.value = true; error.value = false
    try {
      const current = chain.value
      const next = await institutionalChainApi.fetch(toValue(ownerKind), String(id), {
        commitmentCursor: more === 'commitments' ? current?.commitmentCursor.next : undefined,
        eventCursor: more === 'events' ? current?.eventCursor.next : undefined,
        limit: 12,
        signal: controller.signal,
      })
      if (token !== request) return
      chain.value = more && current ? {
        ...next,
        commitments: more === 'commitments' ? [...current.commitments, ...next.commitments] : current.commitments,
        events: more === 'events' ? [...current.events, ...next.events] : current.events,
        commitmentCursor: more === 'events' ? current.commitmentCursor : next.commitmentCursor,
        eventCursor: more === 'commitments' ? current.eventCursor : next.eventCursor,
      } : next
    } catch (cause) { if (token === request && !(cause instanceof DOMException && cause.name === 'AbortError')) error.value = true } finally { if (token === request) loading.value = false }
  }
  watch([() => toValue(ownerKind), () => toValue(ownerId), () => toValue(worldRevision)], () => { chain.value = null; void load() }, { immediate: true })
  onBeforeUnmount(() => { controller?.abort(); request += 1 })
  return { chain, loading, error, refresh: () => load(), loadMoreCommitments: () => load('commitments'), loadMoreEvents: () => load('events') }
}
