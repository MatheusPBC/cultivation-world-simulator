import { defineStore } from 'pinia'
import { ref, shallowRef } from 'vue'

import { eventApi } from '@/api'
import type { WorldJournalPeriodMonths, WorldJournalResponseDTO } from '@/types/api'
import { logError } from '@/utils/appError'

export type WorldJournalTab = 'now' | 'timeline'

export const useWorldJournalStore = defineStore('worldJournal', () => {
  const activeTab = ref<WorldJournalTab>('now')
  const periodMonths = ref<WorldJournalPeriodMonths>(1)
  const journal = shallowRef<WorldJournalResponseDTO | null>(null)
  const loading = ref(false)
  const hasError = ref(false)
  let requestId = 0

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

  return {
    activeTab,
    periodMonths,
    journal,
    loading,
    hasError,
    refresh,
    setPeriod,
    selectTab,
  }
})
