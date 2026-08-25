import { useMediaQuery } from '@vueuse/core'

export function useIsMobile() {
  return useMediaQuery('(max-width: 768px)')
}
