import { defineStore } from 'pinia'
import { ref, shallowRef } from 'vue'

import { eventApi, worldApi } from '@/api'
import type {
  ChronicleDossierResponseDTO,
  EventCausalDetailDTO,
  LiveGuideAnswerDTO,
  LiveGuideResponseDTO,
  DaoPetitionsResponseDTO,
  WorldChronicleResponseDTO,
  WorldJournalPeriodMonths,
  WorldJournalResponseDTO,
} from '@/types/api'
import { logError } from '@/utils/appError'

export type WorldJournalTab = 'now' | 'focus' | 'stories' | 'timeline' | 'chronicle' | 'guide' | 'dao'

export const useWorldJournalStore = defineStore('worldJournal', () => {
  const activeTab = ref<WorldJournalTab>('now')
  const periodMonths = ref<WorldJournalPeriodMonths>(1)
  const journal = shallowRef<WorldJournalResponseDTO | null>(null)
  const loading = ref(false)
  const hasError = ref(false)
  let requestId = 0

  const chronicle = shallowRef<WorldChronicleResponseDTO | null>(null)
  const chronicleLoading = ref(false)
  const chronicleError = ref(false)
  let chronicleRequestId = 0

  const liveGuide = shallowRef<LiveGuideResponseDTO | null>(null)
  const liveGuideLoading = ref(false)
  const liveGuideError = ref(false)
  const liveGuideAnswer = shallowRef<LiveGuideAnswerDTO | null>(null)
  const liveGuideAnswerLoading = ref(false)
  const liveGuideAnswerError = ref(false)
  let liveGuideRequestId = 0
  let liveGuideAnswerRequestId = 0

  const daoPetitions = shallowRef<DaoPetitionsResponseDTO | null>(null)
  const daoLoading = ref(false)
  const daoError = ref(false)
  const respondingPetitionId = ref<string | null>(null)

  const chronicleDossier = shallowRef<ChronicleDossierResponseDTO | null>(null)
  const chronicleDossierChapterId = ref<string | null>(null)
  const chronicleDossierAnchorId = ref<string | null>(null)
  const chronicleDossierLoading = ref(false)
  const chronicleDossierError = ref(false)
  let chronicleDossierRequestId = 0

  const causalEventId = ref<string | null>(null)
  const causalDetail = shallowRef<EventCausalDetailDTO | null>(null)
  const causalLoading = ref(false)
  const causalError = ref(false)
  let causalRequestId = 0

  async function refresh() {
    const currentRequestId = ++requestId
    loading.value = true
    hasError.value = false
    try {
      const result = await eventApi.fetchWorldJournal(periodMonths.value)
      if (currentRequestId === requestId) {
        journal.value = result
      }
    } catch (error) {
      if (currentRequestId === requestId) {
        hasError.value = true
        logError('WorldJournalStore refresh', error)
      }
    } finally {
      if (currentRequestId === requestId) {
        loading.value = false
      }
    }
  }

  async function setPeriod(months: WorldJournalPeriodMonths) {
    periodMonths.value = months
    await refresh()
  }

  async function refreshChronicle(limit = 20) {
    const currentRequestId = ++chronicleRequestId
    chronicleLoading.value = true
    chronicleError.value = false
    try {
      const result = await eventApi.fetchWorldChronicle({ limit })
      if (currentRequestId === chronicleRequestId) {
        chronicle.value = result
      }
    } catch (error) {
      if (currentRequestId === chronicleRequestId) {
        chronicleError.value = true
        logError('WorldJournalStore refreshChronicle', error)
      }
    } finally {
      if (currentRequestId === chronicleRequestId) chronicleLoading.value = false
    }
  }

  async function loadMoreChronicle(limit = 20) {
    if (!chronicle.value?.has_more || chronicleLoading.value || !chronicle.value.next_cursor) return
    const currentRequestId = ++chronicleRequestId
    chronicleLoading.value = true
    chronicleError.value = false
    try {
      const result = await eventApi.fetchWorldChronicle({ cursor: chronicle.value.next_cursor, limit })
      if (currentRequestId !== chronicleRequestId) return
      const knownIds = new Set(chronicle.value.chapters.map((chapter) => chapter.id))
      const chapters = chronicle.value.chapters.concat(
        result.chapters.filter((chapter) => !knownIds.has(chapter.id)),
      )
      chronicle.value = { ...result, chapters }
    } catch (error) {
      if (currentRequestId === chronicleRequestId) {
        chronicleError.value = true
        logError('WorldJournalStore loadMoreChronicle', error)
      }
    } finally {
      if (currentRequestId === chronicleRequestId) chronicleLoading.value = false
    }
  }

  async function refreshLiveGuide() {
    const currentRequestId = ++liveGuideRequestId
    liveGuideLoading.value = true
    liveGuideError.value = false
    liveGuideAnswerRequestId += 1
    liveGuideAnswer.value = null
    liveGuideAnswerLoading.value = false
    liveGuideAnswerError.value = false
    try {
      const result = await eventApi.fetchLiveGuide()
      if (currentRequestId === liveGuideRequestId) liveGuide.value = result
    } catch (error) {
      if (currentRequestId === liveGuideRequestId) {
        liveGuideError.value = true
        logError('WorldJournalStore refreshLiveGuide', error)
      }
    } finally {
      if (currentRequestId === liveGuideRequestId) liveGuideLoading.value = false
    }
  }

  async function askLiveGuide(question: string) {
    const normalized = question.trim()
    if (!normalized || liveGuideAnswerLoading.value) return
    const currentRequestId = ++liveGuideAnswerRequestId
    liveGuideAnswer.value = null
    liveGuideAnswerLoading.value = true
    liveGuideAnswerError.value = false
    try {
      const result = await eventApi.askLiveGuide(normalized)
      if (currentRequestId === liveGuideAnswerRequestId) liveGuideAnswer.value = result
    } catch (error) {
      if (currentRequestId === liveGuideAnswerRequestId) {
        liveGuideAnswerError.value = true
        logError('WorldJournalStore askLiveGuide', error)
      }
    } finally {
      if (currentRequestId === liveGuideAnswerRequestId) liveGuideAnswerLoading.value = false
    }
  }

  async function refreshDaoPetitions() {
    daoLoading.value = true; daoError.value = false
    try { daoPetitions.value = await worldApi.fetchDaoPetitions() }
    catch (error) { daoError.value = true; logError('WorldJournalStore refreshDaoPetitions', error) }
    finally { daoLoading.value = false }
  }

  async function answerDaoPetition(petitionId: string, response: 'silence' | 'sign' | 'favor') {
    if (respondingPetitionId.value) return
    respondingPetitionId.value = petitionId
    try { await worldApi.answerDaoPetition(petitionId, response); await refreshDaoPetitions() }
    finally { respondingPetitionId.value = null }
  }

  function refreshAfterTick() {
    void refresh()
    if (chronicle.value) void refreshChronicle()
    if (liveGuide.value) void refreshLiveGuide()
    if (daoPetitions.value) void refreshDaoPetitions()
  }

  async function openChronicleDossier(chapterId: string, anchorId: string) {
    const currentRequestId = ++chronicleDossierRequestId
    chronicleDossierChapterId.value = chapterId
    chronicleDossierAnchorId.value = anchorId
    chronicleDossier.value = null
    chronicleDossierLoading.value = true
    chronicleDossierError.value = false
    try {
      const result = await eventApi.fetchChronicleDossier(chapterId, anchorId)
      if (currentRequestId === chronicleDossierRequestId) chronicleDossier.value = result
    } catch (error) {
      if (currentRequestId === chronicleDossierRequestId) {
        chronicleDossierError.value = true
        logError('WorldJournalStore openChronicleDossier', error)
      }
    } finally {
      if (currentRequestId === chronicleDossierRequestId) chronicleDossierLoading.value = false
    }
  }

  function closeChronicleDossier() {
    chronicleDossierRequestId += 1
    chronicleDossierChapterId.value = null
    chronicleDossierAnchorId.value = null
    chronicleDossier.value = null
    chronicleDossierLoading.value = false
    chronicleDossierError.value = false
  }

  function selectTab(tab: WorldJournalTab) {
    activeTab.value = tab
  }

  async function openCausalDetail(eventId: string) {
    causalEventId.value = eventId
    causalDetail.value = null
    causalLoading.value = true
    causalError.value = false
    const currentRequestId = ++causalRequestId
    try {
      const result = await eventApi.fetchEventCausalDetail(eventId)
      if (currentRequestId === causalRequestId) {
        causalDetail.value = result
      }
    } catch (error) {
      if (currentRequestId === causalRequestId) {
        causalError.value = true
        logError('WorldJournalStore openCausalDetail', error)
      }
    } finally {
      if (currentRequestId === causalRequestId) {
        causalLoading.value = false
      }
    }
  }

  function closeCausalDetail() {
    causalRequestId += 1
    causalEventId.value = null
    causalDetail.value = null
    causalLoading.value = false
    causalError.value = false
  }

  return {
    activeTab,
    periodMonths,
    journal,
    loading,
    hasError,
    refresh,
    setPeriod,
    chronicle,
    chronicleLoading,
    chronicleError,
    refreshChronicle,
    loadMoreChronicle,
    liveGuide,
    liveGuideLoading,
    liveGuideError,
    liveGuideAnswer,
    liveGuideAnswerLoading,
    liveGuideAnswerError,
    refreshLiveGuide,
    askLiveGuide,
    daoPetitions,
    daoLoading,
    daoError,
    respondingPetitionId,
    refreshDaoPetitions,
    answerDaoPetition,
    refreshAfterTick,
    chronicleDossier,
    chronicleDossierChapterId,
    chronicleDossierAnchorId,
    chronicleDossierLoading,
    chronicleDossierError,
    openChronicleDossier,
    closeChronicleDossier,
    selectTab,
    causalEventId,
    causalDetail,
    causalLoading,
    causalError,
    openCausalDetail,
    closeCausalDetail,
  }
})
