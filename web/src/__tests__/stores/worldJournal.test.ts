import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const fetchChronicleMock = vi.fn()
const fetchDossierMock = vi.fn()

vi.mock('@/api', () => ({
  eventApi: {
    fetchWorldChronicle: fetchChronicleMock,
    fetchChronicleDossier: fetchDossierMock,
    fetchWorldJournal: vi.fn(),
    fetchEventCausalDetail: vi.fn(),
  },
}))

const page = (chapters: Array<{ id: string }>, next_cursor: string | null = null, has_more = false) => ({
  chapters,
  next_cursor,
  has_more,
})

describe('worldJournal Chronicle state', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    fetchChronicleMock.mockReset()
    fetchDossierMock.mockReset()
  })

  it('appends Chronicle pages without duplicate chapters', async () => {
    fetchChronicleMock.mockResolvedValueOnce(page([{ id: 'c2' }, { id: 'c1' }], 'c1', true))
      .mockResolvedValueOnce(page([{ id: 'c1' }, { id: 'c0' }]))
    const { useWorldJournalStore } = await import('@/stores/worldJournal')
    const store = useWorldJournalStore()

    await store.refreshChronicle()
    await store.loadMoreChronicle()

    expect(store.chronicle?.chapters.map((chapter) => chapter.id)).toEqual(['c2', 'c1', 'c0'])
    expect(fetchChronicleMock).toHaveBeenNthCalledWith(2, { cursor: 'c1', limit: 20 })
  })

  it('ignores a stale Chronicle response after a newer refresh', async () => {
    let resolveOld: ((value: unknown) => void) | undefined
    const oldRequest = new Promise((resolve) => { resolveOld = resolve })
    fetchChronicleMock.mockReturnValueOnce(oldRequest).mockResolvedValueOnce(page([{ id: 'new' }]))
    const { useWorldJournalStore } = await import('@/stores/worldJournal')
    const store = useWorldJournalStore()

    const first = store.refreshChronicle()
    const second = store.refreshChronicle()
    await second
    resolveOld?.(page([{ id: 'old' }]))
    await first

    expect(store.chronicle?.chapters.map((chapter) => chapter.id)).toEqual(['new'])
  })
})
