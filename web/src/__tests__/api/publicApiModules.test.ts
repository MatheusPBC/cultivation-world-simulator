import { beforeEach, describe, expect, it, vi } from 'vitest'

const getMock = vi.fn()
const postMock = vi.fn()
const deleteMock = vi.fn()

vi.mock('@/api/http', () => ({
  httpClient: {
    get: getMock,
    post: postMock,
    delete: deleteMock,
  },
}))

describe('public api module migration', () => {
  beforeEach(() => {
    getMock.mockReset()
    postMock.mockReset()
    deleteMock.mockReset()
  })

  it('worldApi fetches world state and map from /api/v1', async () => {
    const { worldApi } = await import('@/api/modules/world')
    getMock.mockResolvedValueOnce({ status: 'ok', year: 100, month: 1 })
    getMock.mockResolvedValueOnce({ data: [], regions: [], render_config: {} })

    const state = await worldApi.fetchInitialState()
    const map = await worldApi.fetchMap()

    expect(getMock).toHaveBeenNthCalledWith(1, '/api/v1/query/world/state')
    expect(getMock).toHaveBeenNthCalledWith(2, '/api/v1/query/world/map')
    expect(state.avatars).toEqual([])
    expect(state.events).toEqual([])
    expect(map.renderConfig).toEqual({ water_speed: 'high', cloud_frequency: 'none' })
  })

  it('eventApi fetches events from /api/v1 query endpoint', async () => {
    const { eventApi } = await import('@/api/modules/event')
    getMock.mockResolvedValue({ events: [], next_cursor: null, has_more: false })

    const page = await eventApi.fetchEvents({ avatar_id: 'a1', limit: 20 })

    expect(getMock).toHaveBeenCalledWith('/api/v1/query/events?avatar_id=a1&limit=20')
    expect(page).toEqual({ events: [], nextCursor: null, hasMore: false })
  })

  it('eventApi fetches the deterministic world journal period', async () => {
    const { eventApi } = await import('@/api/modules/event')
    const journal = {
      period: { months: 3, start_month_stamp: 1202, end_month_stamp: 1204 },
      activity: {
        total_events: 3,
        major_events: 1,
        story_events: 1,
        routine_events: 1,
        active_avatar_count: 2,
      },
      highlights: [],
      ongoing: [],
    }
    getMock.mockResolvedValue(journal)

    const result = await eventApi.fetchWorldJournal(3)

    expect(getMock).toHaveBeenCalledWith('/api/v1/query/world/journal?period_months=3')
    expect(result).toEqual(journal)
  })

  it('eventApi reads the Live Guide and asks its grounded query endpoint', async () => {
    const { eventApi } = await import('@/api/modules/event')
    getMock.mockResolvedValue({ threads: [] })
    postMock.mockResolvedValue({ answer: 'Fato', source_event_ids: ['e1'], mode: 'generated' })

    await eventApi.fetchLiveGuide()
    await eventApi.askLiveGuide('O que mudou?')

    expect(getMock).toHaveBeenCalledWith('/api/v1/query/world/live-guide')
    expect(postMock).toHaveBeenCalledWith(
      '/api/v1/query/world/live-guide/ask',
      { question: 'O que mudou?' },
      { timeoutMs: 120_000 },
    )
  })

  it('eventApi fetches the first Chronicle page from the exact endpoint', async () => {
    const { eventApi } = await import('@/api/modules/event')
    getMock.mockResolvedValue({ chapters: [], next_cursor: null, has_more: false })

    await eventApi.fetchWorldChronicle({ limit: 20 })

    expect(getMock).toHaveBeenCalledWith('/api/v1/query/world/chronicle?limit=20')
  })

  it('eventApi fetches a Chronicle dossier with encoded identifiers and bounds', async () => {
    const { eventApi } = await import('@/api/modules/event')
    getMock.mockResolvedValue({ chapter_id: 'chapter/a', anchor: {}, focal_event: null, sequence: [], pruned_source_ids: [], truncated: false })

    await eventApi.fetchChronicleDossier('chapter/a', 'anchor 1', { depth: 3, limit: 40 })

    expect(getMock).toHaveBeenCalledWith('/api/v1/query/world/chronicle/chapter%2Fa/anchors/anchor%201/dossier?depth=3&limit=40')
  })

  it('eventApi fetches the causal detail for one event with depth/limit params', async () => {
    const { eventApi } = await import('@/api/modules/event')
    const detail = {
      event: {
        id: 'e1',
        text: 'e1',
        content: 'e1',
        year: 100,
        month: 1,
        month_stamp: 1200,
        related_avatar_ids: [],
        is_major: false,
        is_story: false,
        created_at: 0,
      },
      causes: [],
      effects: [],
      deltas: [],
      decision: null,
      decision_appraisals: [],
      truncated: false,
    }
    getMock.mockResolvedValue(detail)

    const result = await eventApi.fetchEventCausalDetail('e1', { depth: 2, limit: 10 })

    expect(getMock).toHaveBeenCalledWith('/api/v1/query/events/e1/causal?depth=2&limit=10')
    expect(result).toEqual(detail)
  })

  it('eventApi normalizes a missing causal detail response to null', async () => {
    const { eventApi } = await import('@/api/modules/event')
    getMock.mockResolvedValue(null)

    const result = await eventApi.fetchEventCausalDetail('e1')

    expect(getMock).toHaveBeenCalledWith('/api/v1/query/events/e1/causal')
    expect(result).toBeNull()
  })

  it('eventApi cleans up events through /api/v1 command endpoint', async () => {
    const { eventApi } = await import('@/api/modules/event')
    deleteMock.mockResolvedValue({ deleted: 12 })

    await eventApi.cleanupEvents(false, 1200)

    expect(deleteMock).toHaveBeenCalledWith('/api/v1/command/events/cleanup?keep_major=false&before_month_stamp=1200')
  })

  it('worldApi fetches sect territories from /api/v1', async () => {
    const { worldApi } = await import('@/api/modules/world')
    getMock.mockResolvedValue({ sects: [] })

    await worldApi.fetchSectTerritories()

    expect(getMock).toHaveBeenCalledWith('/api/v1/query/sects/territories')
  })

  it('systemApi uses /api/v1 lifecycle and save endpoints', async () => {
    const { systemApi } = await import('@/api/modules/system')
    getMock.mockResolvedValue({ status: 'idle' })
    postMock.mockResolvedValue({ status: 'ok' })

    await systemApi.fetchInitStatus()
    await systemApi.fetchSaves()
    await systemApi.saveGame('存档A')
    await systemApi.loadGame('save.json')

    expect(getMock).toHaveBeenNthCalledWith(1, '/api/v1/query/runtime/status')
    expect(getMock).toHaveBeenNthCalledWith(2, '/api/v1/query/saves')
    expect(postMock).toHaveBeenNthCalledWith(1, '/api/v1/command/game/save', { custom_name: '存档A' })
    expect(postMock).toHaveBeenNthCalledWith(2, '/api/v1/command/game/load', { filename: 'save.json' })
  })

  it('systemApi startNewGame and shutdown use /api/v1 endpoints', async () => {
    const { systemApi } = await import('@/api/modules/system')
    postMock.mockResolvedValue({ status: 'ok' })

    await systemApi.startNewGame()
    await systemApi.shutdown()

    expect(postMock).toHaveBeenNthCalledWith(1, '/api/v1/command/game/reinit', {})
    expect(postMock).toHaveBeenNthCalledWith(2, '/api/v1/command/system/shutdown', {})
  })

  it('systemApi exposes pause-and-drain for edit panels', async () => {
    const { systemApi } = await import('@/api/modules/system')
    postMock.mockResolvedValue({ status: 'ok' })

    await systemApi.pauseGameAndDrain()

    expect(postMock).toHaveBeenCalledWith('/api/v1/command/game/pause-and-drain', {})
  })
})
