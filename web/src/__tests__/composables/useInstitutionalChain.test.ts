import { describe, expect, it, vi } from 'vitest'
import { defineComponent, nextTick, ref } from 'vue'
import { mount } from '@vue/test-utils'
import { institutionalChainApi } from '@/api'
import { useInstitutionalChain } from '@/composables/useInstitutionalChain'

vi.mock('@/api', () => ({ institutionalChainApi: { fetch: vi.fn() } }))
const page = (tag: string, commitmentNext: string | null = null, eventNext: string | null = null) => ({ owner: { kind: 'city', id: '1', institutionId: 'i', name: tag, regionId: '1' }, currentMonth: 1, institutions: [], commitments: [{ id: `c-${tag}` }], events: [{ event_id: `e-${tag}` }], memories: [], commitmentCursor: { next: commitmentNext, hasMore: Boolean(commitmentNext) }, eventCursor: { next: eventNext, hasMore: Boolean(eventNext) } }) as any

describe('useInstitutionalChain', () => {
  it('drops stale owner responses and preserves the other independent cursor while paging', async () => {
    let firstResolve!: (value: any) => void
    vi.mocked(institutionalChainApi.fetch).mockImplementationOnce(() => new Promise(resolve => { firstResolve = resolve }) as any)
      .mockResolvedValueOnce(page('new', 'c2', 'e2')).mockResolvedValueOnce(page('events', 'c3', null))
    const owner = ref<string | null>('old'); const revision = ref(1)
    let state!: ReturnType<typeof useInstitutionalChain>
    const harness = mount(defineComponent({
      setup() {
        state = useInstitutionalChain(() => 'region', owner, revision)
        return () => null
      },
    }))
    owner.value = 'new'; await nextTick(); firstResolve(page('old')); await Promise.resolve(); await Promise.resolve()
    expect(state.chain.value?.owner.name).toBe('new')
    await state.loadMoreEvents()
    expect(state.chain.value?.commitmentCursor.next).toBe('c2')
    vi.mocked(institutionalChainApi.fetch).mockResolvedValueOnce(page('new-world'))
    revision.value = 2; await nextTick(); await Promise.resolve()
    expect(institutionalChainApi.fetch).toHaveBeenLastCalledWith('region', 'new', expect.objectContaining({ limit: 12 }))
    harness.unmount()
  })
})
