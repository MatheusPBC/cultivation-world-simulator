import { defineStore } from 'pinia'
import { ref, shallowRef } from 'vue'

import { eventApi } from '@/api'
import type { EventCausalDetailDTO, WorldJournalPeriodMonths, WorldJournalResponseDTO } from '@/types/api'
import { logError } from '@/utils/appError'

export type WorldJournalTab = 'now' | 'focus' | 'stories' | 'timeline'

export const useWorldJournalStore = defineStore('worldJournal', () => {
  const activeTab = ref<WorldJournalTab>('now')
  const periodMonths = ref<WorldJournalPeriodMonths>(1)
  const journal = shallowRef<WorldJournalResponseDTO | null>(null)
  const loading = ref(false)
  const hasError = ref(false)
  let requestId = 0

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
    selectTab,
    causalEventId,
    causalDetail,
    causalLoading,
    causalError,
    openCausalDetail,
    closeCausalDetail,
  }
})
