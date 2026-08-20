import { ref } from 'vue'

export type MobileTab = 'dashboard' | 'avatars' | 'roleplay'

// Shared across MobileGameShell and its children so any component can
// request a tab switch (e.g. "Roleplay" button on an avatar card).
const activeTab = ref<MobileTab>('dashboard')

export function useMobileNav() {
  function goTo(tab: MobileTab) {
    activeTab.value = tab
  }

  return {
    activeTab,
    goTo,
  }
}
