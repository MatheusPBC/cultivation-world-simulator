import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useInstitutionalPresenceStore } from '@/stores/institutionalPresence'

vi.mock('@/api', () => ({
  institutionalPresenceApi: {
    fetch: vi.fn(),
  },
}))

import { institutionalPresenceApi } from '@/api'

describe('institutional presence store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('loads a projection and resets it safely', async () => {
    vi.mocked(institutionalPresenceApi.fetch).mockResolvedValue([{
      regionId: 301,
      regionName: 'Tianhe',
      regionType: 'city',
      tileCount: 2,
      governance: { controllerKind: 'dynasty', controllerId: '1', administrativeCapacity: 0.5 },
      sectInfluences: [],
      dominantSectId: null,
    }])
    const store = useInstitutionalPresenceStore()

    await store.refresh()
    expect(store.isLoaded).toBe(true)
    expect(store.regions[0].regionId).toBe(301)

    store.reset()
    expect(store.regions).toEqual([])
    expect(store.isLoaded).toBe(false)
  })

  it('clears stale projection after a failed refresh', async () => {
    vi.mocked(institutionalPresenceApi.fetch).mockResolvedValueOnce([{
      regionId: 301,
      regionName: 'Tianhe',
      regionType: 'city',
      tileCount: 2,
      governance: null,
      sectInfluences: [],
      dominantSectId: null,
    }]).mockRejectedValueOnce(new Error('projection unavailable'))
    const store = useInstitutionalPresenceStore()

    await store.refresh()
    await store.refresh()

    expect(store.regions).toEqual([])
    expect(store.isLoaded).toBe(false)
  })
})
