<script setup lang="ts">
import { computed, onMounted, onUnmounted, watch } from 'vue'
import { NConfigProvider, darkTheme, NMessageProvider, NDialogProvider } from 'naive-ui'
import { systemApi } from './api/modules/system'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

// Components
import SplashLayer from './components/SplashLayer.vue'
import GameCanvas from './components/game/GameCanvas.vue'
import RoleplayDock from './components/game/RoleplayDock.vue'
import InfoPanelContainer from './components/game/panels/info/InfoPanelContainer.vue'
import StatusBar from './components/layout/StatusBar.vue'
import WorldJournalPanel from './components/game/panels/WorldJournalPanel.vue'
import SystemMenu from './components/SystemMenu.vue'
import LoadingOverlay from './components/LoadingOverlay.vue'
import MobileGameShell from './components/mobile/MobileGameShell.vue'

// Composables
import { useGameInit } from './composables/useGameInit'
import { useGameControl } from './composables/useGameControl'
import { useAudio } from './composables/useAudio'
import { useBgm } from './composables/useBgm'
import { useSidebarResize } from './composables/useSidebarResize'
import { useAppShell } from './composables/useAppShell'
import { useSystemMenuFlow } from './composables/useSystemMenuFlow'
import { useIsMobile } from './composables/useIsMobile'
import { logError } from './utils/appError'

const isMobile = useIsMobile()

// Stores
import { useUiStore } from './stores/ui'
import { useSettingStore } from './stores/setting'
import { useSystemStore } from './stores/system'
import { useRoleplayStore } from './stores/roleplay'

const uiStore = useUiStore()
const settingStore = useSettingStore()
const systemStore = useSystemStore()
const roleplayStore = useRoleplayStore()

function showClosedMessage() {
  document.body.replaceChildren()
  const message = document.createElement('div')
  message.textContent = t('game.controls.closed_msg')
  Object.assign(message.style, {
    alignItems: 'center',
    background: 'black',
    color: 'white',
    display: 'flex',
    fontSize: '24px',
    height: '100vh',
    justifyContent: 'center',
  })
  document.body.appendChild(message)
}

// Sidebar resizer 状态
const { sidebarWidth, isResizing, onResizerMouseDown } = useSidebarResize()

function syncLayoutCssVars(width: number) {
  document.documentElement.style.setProperty('--cws-sidebar-width', `${width}px`)
}

// 1. 游戏初始化逻辑
const { 
  initStatus, 
  gameInitialized, 
  showLoading,
} = useGameInit({
  onIdle: () => roleplayStore.reset(),
})

const {
  showMenu,
  menuDefaultTab,
  menuContext,
  canCloseMenu,
  performStartupCheck,
  openGameMenu,
  handleLLMReady,
  handleMenuClose,
} = useSystemMenuFlow()

const {
  isManualPaused,
  handleKeydown: controlHandleKeydown,
  toggleManualPause
} = useGameControl({
  gameInitialized,
  showMenu,
  canCloseMenu,
  openGameMenu,
  closeMenu: handleMenuClose,
})

const settingsHydrated = computed(() => settingStore.hydrated)
const roleplayPauseText = computed(() => {
  const status = roleplayStore.session.status
  if (status === 'awaiting_decision') return t('game.roleplay.pause_indicator.awaiting_decision')
  if (status === 'awaiting_choice') return t('game.roleplay.pause_indicator.awaiting_choice')
  if (status === 'conversing') return t('game.roleplay.pause_indicator.conversing')
  if (status === 'submitting') return t('game.roleplay.pause_indicator.submitting')
  return ''
})

const {
  scene,
  canRenderGameShell,
  canRenderSplash,
  showLoadingOverlay,
  shouldBlockControls,
  handleSplashNavigate,
  handleMenuCloseWrapper,
  returnToSplash,
} = useAppShell({
  settingsHydrated,
  initStatus,
  gameInitialized,
  showLoading,
  showMenu,
  menuDefaultTab,
  menuContext,
  isManualPaused,
  performStartupCheck,
  handleMenuClose,
  onGameBgmStart: () => {
    // Avoid downloading a large track before mobile users ask for audio.
    if (!isMobile.value) return useBgm().play('map')
  },
  onResumeGame: () => systemStore.resume(),
})

// 事件处理
function onKeydown(e: KeyboardEvent) {
  if (shouldBlockControls.value) return
  controlHandleKeydown(e)
}

function handleSelection(target: { type: 'avatar' | 'region' | 'poi' | 'site'; id: string; name?: string }) {
  uiStore.select(target.type, target.id)
}

async function handleSplashAction(key: string) {
  if (key === 'exit') {
    const desktopBridge = window.cwsDesktop
    if (desktopBridge?.quit) {
      try {
        await desktopBridge.quit()
        return
      } catch (e) {
        logError('App desktop quit', e)
      }
    }

    showClosedMessage()
    try {
      await systemApi.shutdown()
      window.close()
    } catch (e) {
      logError('App shutdown', e)
    }
    return
  }

  if (key === 'start' || key === 'load' || key === 'settings' || key === 'about') {
    handleSplashNavigate(key)
  }
}

async function handleReturnToMain() {
  roleplayStore.reset()
  returnToSplash()

  try {
    await systemApi.resetGame()
  } catch (e) {
    logError('App reset game', e)
  }
}

function focusRoleplayDock() {
  const dock = document.querySelector<HTMLElement>('.roleplay-dock--active')
  dock?.scrollIntoView({ block: 'end', behavior: 'smooth' })
  dock?.focus()
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
  syncLayoutCssVars(sidebarWidth.value)
  settingStore.hydrate().finally(() => {
    useAudio().init()
    useBgm().init() // 确保 BGM 系统在 App 层级初始化，避免 Watcher 被子组件卸载
  })
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  document.documentElement.style.removeProperty('--cws-sidebar-width')
})

watch(sidebarWidth, width => {
  syncLayoutCssVars(width)
})
</script>

<template>
  <n-config-provider :theme="darkTheme">
    <n-dialog-provider>
      <n-message-provider>
        <div v-if="scene === 'boot'" class="app-layout app-layout--shell"></div>

        <SplashLayer 
          v-else-if="canRenderSplash" 
          @action="handleSplashAction"
        />

        <div v-else-if="scene === 'initializing'" class="app-layout app-layout--shell"></div>

        <MobileGameShell v-else-if="canRenderGameShell && isMobile" />

        <div v-else-if="canRenderGameShell" class="app-layout">
          <StatusBar
            :paused="isManualPaused"
            @toggle-pause="toggleManualPause"
            @open-menu="openGameMenu()"
          />

          <div class="main-content">
            <div class="map-container">
              <div class="map-stage">
                <!--
                  The pause state is expressed by the clock in the HUD, so the
                  map surface no longer carries a floating "paused" pill on top
                  of the band where city names sit. Only the roleplay prompt —
                  which is actionable — still surfaces over the map.
                -->
                <button
                  v-if="roleplayPauseText"
                  class="roleplay-prompt"
                  type="button"
                  @click="focusRoleplayDock"
                >
                  {{ roleplayPauseText }}
                </button>

                <GameCanvas
                  :sidebar-width="sidebarWidth"
                  @avatarSelected="handleSelection"
                  @regionSelected="handleSelection"
                  @poiSelected="handleSelection"
                  @siteSelected="handleSelection"
                />
                <InfoPanelContainer />
              </div>
              <RoleplayDock />
            </div>
            <div
              class="sidebar-resizer"
              :class="{ 'is-resizing': isResizing }"
              @mousedown="onResizerMouseDown"
            ></div>
            <aside class="sidebar" :style="{ width: sidebarWidth + 'px' }">
              <WorldJournalPanel />
            </aside>
          </div>
        </div>

        <SystemMenu 
          :visible="showMenu"
          :default-tab="menuDefaultTab"
          :game-initialized="gameInitialized"
          :closable="canCloseMenu"
          @close="handleMenuCloseWrapper"
          @llm-ready="handleLLMReady"
          @return-to-main="handleReturnToMain"
          @exit-game="() => handleSplashAction('exit')"
        />

        <LoadingOverlay 
          v-if="showLoadingOverlay"
          :status="initStatus"
        />
      </n-message-provider>
    </n-dialog-provider>
  </n-config-provider>
</template>

<style scoped>
.app-layout {
  display: flex;
  flex-direction: column;
  width: 100vw;
  height: 100vh;
  background: var(--ink-void);
  color: var(--text-primary);
  overflow: hidden;
  position: relative;
}

.app-layout--shell {
  background: var(--ink-void);
}

.main-content {
  flex: 1;
  display: flex;
  position: relative;
  overflow: hidden;
  min-height: 0;
}

.map-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--ink-void);
  overflow: hidden;
  min-width: 0;
}

.map-stage {
  flex: 1;
  position: relative;
  background: var(--ink-void);
  overflow: hidden;
  min-height: 0;
}

/*
 * The only overlay left on the map surface, because it is a call to action
 * rather than a status readout.
 */
.roleplay-prompt {
  position: absolute;
  top: var(--s-5);
  left: 50%;
  transform: translateX(-50%);
  z-index: 30;
  max-width: min(460px, calc(100% - 240px));
  min-height: 36px;
  padding: 0 var(--s-6);
  border: 1px solid var(--gold-600);
  border-radius: var(--r-2);
  color: var(--gold-200);
  background: var(--surface-chrome);
  box-shadow: var(--shadow-float);
  font-family: var(--font-ui);
  font-size: var(--t-md);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  cursor: pointer;
  transition: border-color var(--motion-fast), color var(--motion-fast);
}

.roleplay-prompt:hover {
  border-color: var(--gold-400);
  color: var(--paper-100);
}

.roleplay-prompt:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring);
}

.sidebar-resizer {
  width: 4px;
  background: transparent;
  cursor: col-resize;
  transition: background var(--motion-fast);
  flex-shrink: 0;
}

.sidebar-resizer:hover,
.sidebar-resizer.is-resizing {
  background: var(--gold-600);
}

.sidebar {
  background: var(--surface-panel);
  border-left: 1px solid var(--rule);
  display: flex;
  flex-direction: column;
  z-index: 20;
  flex-shrink: 0;
  min-width: 0;
}
</style>
