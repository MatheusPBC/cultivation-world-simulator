<script setup lang="ts">
import { computed } from 'vue'
import { useWorldStore } from '@/stores/world'
import { useSystemStore } from '@/stores/system'
import { useMobileNav } from '@/composables/useMobileNav'

import MobileDashboard from './MobileDashboard.vue'
import MobileAvatarList from './MobileAvatarList.vue'
import MobileRoleplay from './MobileRoleplay.vue'

import houseIcon from '@/assets/icons/ui/lucide/house.svg'
import usersIcon from '@/assets/icons/ui/lucide/users.svg'
import chatIcon from '@/assets/icons/ui/lucide/message-circle.svg'
import playIcon from '@/assets/icons/ui/lucide/play.svg'
import pauseIcon from '@/assets/icons/ui/lucide/pause.svg'

const worldStore = useWorldStore()
const systemStore = useSystemStore()
const { activeTab, goTo } = useMobileNav()

const dateLabel = computed(() => `${worldStore.year} - ${worldStore.month}`)

const tabs: Array<{ key: 'dashboard' | 'avatars' | 'roleplay'; label: string; icon: string }> = [
  { key: 'dashboard', label: 'Diario', icon: houseIcon },
  { key: 'avatars', label: 'Avatares', icon: usersIcon },
  { key: 'roleplay', label: 'Roleplay', icon: chatIcon },
]
</script>

<template>
  <div class="mobile-shell">
    <header class="mobile-header">
      <div class="mobile-header-date">{{ dateLabel }}</div>
      <button
        class="mobile-pause-btn"
        type="button"
        :title="systemStore.isManualPaused ? 'Retomar' : 'Pausar'"
        @click="systemStore.togglePause()"
      >
        <span
          class="mobile-pause-icon"
          :style="{ '--icon-url': `url(${systemStore.isManualPaused ? playIcon : pauseIcon})` }"
          aria-hidden="true"
        ></span>
      </button>
    </header>

    <main class="mobile-content">
      <MobileDashboard v-if="activeTab === 'dashboard'" />
      <MobileAvatarList v-else-if="activeTab === 'avatars'" />
      <MobileRoleplay v-else-if="activeTab === 'roleplay'" />
    </main>

    <nav class="mobile-tabbar">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        class="mobile-tab"
        :class="{ 'mobile-tab--active': activeTab === tab.key }"
        @click="goTo(tab.key)"
      >
        <span class="mobile-tab-icon" :style="{ '--icon-url': `url(${tab.icon})` }" aria-hidden="true"></span>
        <span class="mobile-tab-label">{{ tab.label }}</span>
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
  background: #111;
  color: #eee;
  overflow: hidden;
}

.mobile-header {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: calc(env(safe-area-inset-top, 0px) + 10px) 16px 10px;
  background: #181818;
  border-bottom: 1px solid #2c2c2c;
}

.mobile-header-date {
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 0.5px;
  color: #f6ecd2;
}

.mobile-pause-btn {
  width: 44px;
  height: 44px;
  border-radius: 8px;
  border: 1px solid #444;
  background: rgba(0, 0, 0, 0.4);
  color: #ddd;
  display: flex;
  align-items: center;
  justify-content: center;
}

.mobile-pause-btn:active {
  background: rgba(20, 18, 14, 0.9);
}

.mobile-pause-icon {
  width: 20px;
  height: 20px;
  display: inline-block;
  background-color: currentColor;
  -webkit-mask-image: var(--icon-url);
  mask-image: var(--icon-url);
  -webkit-mask-repeat: no-repeat;
  mask-repeat: no-repeat;
  -webkit-mask-position: center;
  mask-position: center;
  -webkit-mask-size: contain;
  mask-size: contain;
}

.mobile-content {
  flex: 1;
  min-height: 0;
  min-width: 0;
  width: 100%;
  overflow-y: auto;
  overflow-x: hidden;
  -webkit-overflow-scrolling: touch; overscroll-behavior-y: contain;
}

.mobile-tabbar {
  flex-shrink: 0;
  display: flex;
  background: #181818;
  border-top: 1px solid #2c2c2c;
  padding-bottom: env(safe-area-inset-bottom, 0px);
}

.mobile-tab {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  min-height: 56px;
  padding: 8px 4px;
  color: #999;
  background: transparent;
}

.mobile-tab--active {
  color: #f6ecd2;
}

.mobile-tab-icon {
  width: 22px;
  height: 22px;
  display: inline-block;
  background-color: currentColor;
  -webkit-mask-image: var(--icon-url);
  mask-image: var(--icon-url);
  -webkit-mask-repeat: no-repeat;
  mask-repeat: no-repeat;
  -webkit-mask-position: center;
  mask-position: center;
  -webkit-mask-size: contain;
  mask-size: contain;
}

.mobile-tab-label {
  font-size: 11px;
}
</style>
