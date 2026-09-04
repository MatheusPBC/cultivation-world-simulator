<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useWorldStore } from '@/stores/world'
import { useSystemStore } from '@/stores/system'
import { useSocketStore } from '@/stores/socket'
import { useUiStore } from '@/stores/ui'
import { useMobileNav } from '@/composables/useMobileNav'

import GameCanvas from '@/components/game/GameCanvas.vue'
import InfoPanelContainer from '@/components/game/panels/info/InfoPanelContainer.vue'
import SimClock from '@/components/layout/SimClock.vue'
import MobileDashboard from './MobileDashboard.vue'
import MobileAvatarList from './MobileAvatarList.vue'
import MobileRoleplay from './MobileRoleplay.vue'

import mapIcon from '@/assets/icons/ui/lucide/map.svg'
import houseIcon from '@/assets/icons/ui/lucide/house.svg'
import usersIcon from '@/assets/icons/ui/lucide/users.svg'
import chatIcon from '@/assets/icons/ui/lucide/message-circle.svg'
import chevronIcon from '@/assets/icons/ui/lucide/chevron-down.svg'

const { t } = useI18n()
const worldStore = useWorldStore()
const systemStore = useSystemStore()
const socketStore = useSocketStore()
const uiStore = useUiStore()
const { activeTab, goTo } = useMobileNav()

/*
 * Mobile used to replace the map with a list app: the canvas was never
 * mounted, so the world simply did not exist on a phone. The map is now the
 * persistent surface and every panel is a sheet drawn over it, so the same
 * world is legible on both form factors.
 */
type SheetKey = 'dashboard' | 'avatars' | 'roleplay'

const openSheet = ref<SheetKey | null>(null)

const tabs = computed<Array<{ key: 'map' | SheetKey; label: string; icon: string }>>(() => [
  { key: 'map', label: t('game.map.tab'), icon: mapIcon },
  { key: 'dashboard', label: t('game.world_journal.title_short'), icon: houseIcon },
  { key: 'avatars', label: t('game.status_bar.avatar_overview.label'), icon: usersIcon },
  { key: 'roleplay', label: t('game.roleplay.title_short'), icon: chatIcon },
])

const activeKey = computed<'map' | SheetKey>(() => openSheet.value ?? 'map')

function selectTab(key: 'map' | SheetKey) {
  if (key === 'map') {
    openSheet.value = null
    return
  }
  openSheet.value = openSheet.value === key ? null : key
  goTo(key)
}

function closeSheet() {
  openSheet.value = null
}

function handleSelection(target: { type: 'avatar' | 'region' | 'poi' | 'site'; id: string; name?: string }) {
  // Selecting on the map dismisses the sheet so the detail panel is visible.
  openSheet.value = null
  uiStore.select(target.type, target.id)
}

const sheetTitle = computed(() => {
  const tab = tabs.value.find(entry => entry.key === openSheet.value)
  return tab?.label ?? ''
})
</script>

<template>
  <div class="mobile-shell">
    <header class="mobile-header">
      <SimClock
        :year="worldStore.year"
        :month="worldStore.month"
        :paused="systemStore.isManualPaused"
        :connected="socketStore.isConnected"
        compact
        @toggle-pause="systemStore.togglePause()"
      />
    </header>

    <!-- The map stays mounted underneath every sheet. -->
    <main class="mobile-map">
      <GameCanvas
        compact
        @avatarSelected="handleSelection"
        @regionSelected="handleSelection"
        @poiSelected="handleSelection"
        @siteSelected="handleSelection"
      />
      <InfoPanelContainer />
    </main>

    <transition name="sheet">
      <section
        v-if="openSheet"
        class="mobile-sheet"
        role="dialog"
        :aria-label="sheetTitle"
      >
        <button
          type="button"
          class="mobile-sheet__handle"
          :aria-label="t('game.map.sheet_close')"
          @click="closeSheet"
        >
          <span class="mobile-sheet__grip" aria-hidden="true" />
          <span class="mobile-sheet__title">{{ sheetTitle }}</span>
          <span
            class="cw-icon mobile-sheet__chevron"
            :style="{ '--icon-url': `url(${chevronIcon})` }"
            aria-hidden="true"
          />
        </button>

        <div class="mobile-sheet__body">
          <MobileDashboard v-if="openSheet === 'dashboard'" />
          <MobileAvatarList v-else-if="openSheet === 'avatars'" />
          <MobileRoleplay v-else-if="openSheet === 'roleplay'" />
        </div>
      </section>
    </transition>

    <nav class="mobile-tabbar" :aria-label="t('game.status_bar.nav_label')">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        class="mobile-tab"
        :aria-current="activeKey === tab.key ? 'page' : undefined"
        @click="selectTab(tab.key)"
      >
        <span class="cw-icon mobile-tab__icon" :style="{ '--icon-url': `url(${tab.icon})` }" aria-hidden="true" />
        <span class="mobile-tab__label">{{ tab.label }}</span>
      </button>
    </nav>
  </div>
</template>

<style scoped>
.mobile-shell {
  position: fixed;
  inset: 0;
  width: 100%;
  max-width: 100vw;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: var(--ink-void);
  color: var(--text-primary);
  overflow: hidden;
}

.mobile-header {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: var(--s-4);
  padding: calc(env(safe-area-inset-top, 0px) + var(--s-3)) var(--s-4) var(--s-3);
  background: var(--surface-chrome);
  border-bottom: 1px solid var(--rule-strong);
}

.mobile-map {
  position: relative;
  flex: 1;
  min-height: 0;
  min-width: 0;
  overflow: hidden;
}

/*
 * Sheet, not a page swap: it covers part of the map and can be dismissed back
 * to it, so the player never loses spatial context.
 */
.mobile-sheet {
  position: absolute;
  left: 0;
  right: 0;
  bottom: calc(56px + env(safe-area-inset-bottom, 0px));
  z-index: 40;
  display: flex;
  flex-direction: column;
  max-height: 62%;
  background: var(--surface-panel);
  border-top: 1px solid var(--rule-strong);
  box-shadow: var(--shadow-panel);
}

.mobile-sheet__handle {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: var(--s-4);
  width: 100%;
  min-height: var(--touch-target);
  padding: 0 var(--s-5);
  border: 0;
  background: var(--surface-raised);
  color: var(--text-secondary);
  cursor: pointer;
}

.mobile-sheet__handle:focus-visible {
  outline: none;
  box-shadow: inset var(--focus-ring);
}

.mobile-sheet__grip {
  width: 28px;
  height: 3px;
  border-radius: 2px;
  background: var(--paper-700);
}

.mobile-sheet__title {
  flex: 1;
  text-align: left;
  font-family: var(--font-ui);
  font-size: var(--t-xs);
  letter-spacing: var(--tracking-wide);
  text-transform: uppercase;
}

.mobile-sheet__chevron {
  width: 16px;
  height: 16px;
}

.mobile-sheet__body {
  flex: 1;
  min-height: 0;
  min-width: 0;
  overflow-y: auto;
  overflow-x: hidden;
  -webkit-overflow-scrolling: touch;
  overscroll-behavior-y: contain;
}

.sheet-enter-active,
.sheet-leave-active {
  transition: transform var(--motion), opacity var(--motion);
}

.sheet-enter-from,
.sheet-leave-to {
  transform: translateY(12px);
  opacity: 0;
}

.mobile-tabbar {
  flex-shrink: 0;
  display: flex;
  background: var(--surface-chrome);
  border-top: 1px solid var(--rule-strong);
  padding-bottom: env(safe-area-inset-bottom, 0px);
  z-index: 50;
}

.mobile-tab {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--s-2);
  /* Comfortably above the 44px minimum. */
  min-height: 56px;
  padding: var(--s-4) var(--s-2);
  border: 0;
  color: var(--text-muted);
  background: transparent;
  cursor: pointer;
  transition: color var(--motion-fast);
}

.mobile-tab:focus-visible {
  outline: none;
  box-shadow: inset var(--focus-ring);
}

/* Active tab: gold rule on top plus full-contrast text. */
.mobile-tab[aria-current='page'] {
  color: var(--accent-strong);
  box-shadow: inset 0 2px 0 0 var(--accent);
}

.mobile-tab__icon {
  width: 20px;
  height: 20px;
}

.mobile-tab__label {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-ui);
  font-size: 10px;
  letter-spacing: 0.02em;
}
</style>
