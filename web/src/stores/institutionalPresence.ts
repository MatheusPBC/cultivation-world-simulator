import { defineStore } from 'pinia'
import { ref, shallowRef } from 'vue'
import type { InstitutionalPresenceRegion } from '@/types/core'
import { institutionalPresenceApi } from '@/api'
import { logWarn } from '@/utils/appError'

export const useInstitutionalPresenceStore = defineStore('institutionalPresence', () => {
  const regions = shallowRef<InstitutionalPresenceRegion[]>([])
  const isLoaded = ref(false)
  const isLoading = ref(false)
  let refreshRequestId = 0

  async function refresh() {
    const requestId = ++refreshRequestId
    isLoading.value = true
    try {
      const nextRegions = await institutionalPresenceApi.fetch()
      if (requestId !== refreshRequestId) return
      regions.value = nextRegions
      isLoaded.value = true
    } catch (error) {
      if (requestId !== refreshRequestId) return
      // A projection failure must not leave stale institutional colors on the map.
      regions.value = []
      isLoaded.value = false
      logWarn('InstitutionalPresenceStore refresh', error)
    } finally {
      if (requestId === refreshRequestId) isLoading.value = false
    }
  }

  function reset() {
    refreshRequestId += 1
    regions.value = []
    isLoaded.value = false
    isLoading.value = false
  }

  return {
    regions,
    isLoaded,
    isLoading,
    refresh,
    reset,
  }
})
