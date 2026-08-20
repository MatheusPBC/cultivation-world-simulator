<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoleplayStore } from '@/stores/roleplay'
import { useAvatarStore } from '@/stores/avatar'
import { logError } from '@/utils/appError'

// Same poll interval as desktop's useRoleplayDockState.ts, so a pending
// decision/choice surfaces on mobile without the user having to leave and
// re-enter the tab.
const POLL_INTERVAL_MS = 2500

const roleplayStore = useRoleplayStore()
const avatarStore = useAvatarStore()

const commandText = ref('')

const controlledAvatar = computed(() => {
  const id = roleplayStore.session.controlled_avatar_id
  if (!id) return null
  return avatarStore.avatars.get(id) ?? null
})

const pendingRequest = computed(() => roleplayStore.session.pending_request)
const isChoicePrompt = computed(() => pendingRequest.value?.type === 'choice')
const interactionHistory = computed(() => roleplayStore.session.interaction_history ?? [])
const hasActiveRoleplay = computed(() => roleplayStore.hasActiveRoleplay)

let pollTimer: ReturnType<typeof setInterval> | null = null

function startPolling() {
  if (pollTimer) return
  pollTimer = setInterval(() => {
    roleplayStore.fetchSession().catch(e => logError('MobileRoleplay poll session', e))
  }, POLL_INTERVAL_MS)
}

function stopPolling() {
  if (!pollTimer) return
  clearInterval(pollTimer)
  pollTimer = null
}

watch(hasActiveRoleplay, active => {
  if (active) {
    startPolling()
  } else {
    stopPolling()
  }
})

onMounted(() => {
  if (roleplayStore.hasActiveRoleplay) {
    roleplayStore.fetchSession().catch(e => logError('MobileRoleplay fetch session', e))
    startPolling()
  }
})

onUnmounted(() => {
  stopPolling()
})

async function handleSend() {
  const request = pendingRequest.value
  const avatarId = roleplayStore.session.controlled_avatar_id
  const text = commandText.value.trim()
  if (!request || !avatarId || !text) return

  try {
    await roleplayStore.submitDecision({
      avatar_id: avatarId,
      request_id: request.request_id,
      command_text: text,
    })
    commandText.value = ''
  } catch (e) {
    logError('MobileRoleplay submit decision', e)
  }
}

async function handleChoice(optionKey: string) {
  const request = pendingRequest.value
  const avatarId = roleplayStore.session.controlled_avatar_id
  if (!request || !avatarId) return

  try {
    await roleplayStore.submitChoice({
      avatar_id: avatarId,
      request_id: request.request_id,
      selected_key: optionKey,
    })
  } catch (e) {
    logError('MobileRoleplay submit choice', e)
  }
}

async function handleStop() {
  try {
    await roleplayStore.stopRoleplay(roleplayStore.session.controlled_avatar_id ?? undefined)
  } catch (e) {
    logError('MobileRoleplay stop roleplay', e)
  }
}
</script>

<template>
  <div class="roleplay-screen">
    <div v-if="!roleplayStore.hasActiveRoleplay" class="roleplay-empty">
      <p>Nenhum roleplay ativo.</p>
      <p class="roleplay-empty-hint">Escolha um avatar na aba "Avatares" e toque em "Roleplay" para comecar.</p>
    </div>

    <template v-else>
      <header class="roleplay-header">
        <div class="roleplay-header-name">{{ controlledAvatar?.name || 'Avatar' }}</div>
        <button type="button" class="roleplay-stop-btn" @click="handleStop">Encerrar</button>
      </header>

      <div class="roleplay-history">
        <div
          v-for="(record, index) in interactionHistory"
          :key="index"
          class="roleplay-record"
          :class="`roleplay-record--${record.type}`"
        >
          <p v-if="record.text" class="roleplay-record-text">{{ record.text }}</p>
        </div>

        <p v-if="interactionHistory.length === 0 && !pendingRequest" class="roleplay-empty-hint">
          Aguardando o proximo momento de decisao de {{ controlledAvatar?.name || 'avatar' }}...
        </p>
      </div>

      <div v-if="isChoicePrompt && pendingRequest?.options?.length" class="roleplay-choices">
        <p class="roleplay-prompt-title">{{ pendingRequest.title }}</p>
        <p class="roleplay-prompt-desc">{{ pendingRequest.description }}</p>
        <button
          v-for="option in pendingRequest.options"
          :key="option.key"
          type="button"
          class="roleplay-choice-btn"
          :class="`roleplay-choice-btn--${option.variant || 'default'}`"
          :disabled="roleplayStore.isSubmitting"
          @click="handleChoice(option.key)"
        >
          {{ option.title }}
        </button>
      </div>

      <div v-else-if="pendingRequest" class="roleplay-input-bar">
        <input
          v-model="commandText"
          type="text"
          class="roleplay-input"
          placeholder="Digite uma acao ou mensagem..."
          :disabled="roleplayStore.isSubmitting"
          @keyup.enter="handleSend"
        />
        <button
          type="button"
          class="roleplay-send-btn"
          :disabled="roleplayStore.isSubmitting || !commandText.trim()"
          @click="handleSend"
        >
          Enviar
        </button>
      </div>

      <p v-if="roleplayStore.error" class="roleplay-error">{{ roleplayStore.error }}</p>
    </template>
  </div>
</template>

<style scoped>
.roleplay-screen {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 100%;
}

.roleplay-empty {
  padding: 32px 20px;
  text-align: center;
  color: #999;
}

.roleplay-empty-hint {
  font-size: 13px;
  color: #777;
  margin-top: 8px;
}

.roleplay-header {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid #2c2c2c;
  background: #181818;
}

.roleplay-header-name {
  font-size: 15px;
  font-weight: 600;
  color: #f6ecd2;
}

.roleplay-stop-btn {
  min-height: 36px;
  padding: 0 12px;
  border-radius: 6px;
  border: 1px solid #533;
  background: rgba(120, 30, 30, 0.25);
  color: #e6b0b0;
  font-size: 12px;
}

.roleplay-history {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.roleplay-record {
  background: #181818;
  border: 1px solid #2c2c2c;
  border-radius: 10px;
  padding: 10px 12px;
}

.roleplay-record--conversation_player,
.roleplay-record--command {
  align-self: flex-end;
  background: rgba(232, 202, 143, 0.14);
  border-color: rgba(232, 202, 143, 0.3);
  max-width: 85%;
}

.roleplay-record--conversation_assistant,
.roleplay-record--action_chain {
  align-self: flex-start;
  max-width: 85%;
}

.roleplay-record-text {
  margin: 0;
  font-size: 14px;
  line-height: 1.4;
  color: #ddd;
  white-space: pre-wrap;
}

.roleplay-choices {
  position: sticky;
  bottom: 0;
  z-index: 3;
  flex-shrink: 0;
  padding: 12px 16px calc(env(safe-area-inset-bottom, 0px) + 12px);
  border-top: 1px solid #2c2c2c;
  background: #181818;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.roleplay-prompt-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #f0e6cc;
}

.roleplay-prompt-desc {
  margin: 0 0 4px;
  font-size: 13px;
  color: #999;
}

.roleplay-choice-btn {
  min-height: 44px;
  border-radius: 8px;
  border: 1px solid #444;
  background: rgba(255, 255, 255, 0.04);
  color: #eee;
  font-size: 14px;
  padding: 0 12px;
  text-align: left;
}

.roleplay-choice-btn--accept {
  border-color: rgba(120, 200, 130, 0.5);
  background: rgba(60, 130, 70, 0.15);
}

.roleplay-choice-btn--reject {
  border-color: rgba(200, 100, 100, 0.5);
  background: rgba(130, 60, 60, 0.15);
}

.roleplay-input-bar {
  position: sticky;
  bottom: 0;
  z-index: 3;
  flex-shrink: 0;
  display: flex;
  gap: 8px;
  padding: 12px 16px calc(env(safe-area-inset-bottom, 0px) + 12px);
  border-top: 1px solid #2c2c2c;
  background: #181818;
}

.roleplay-input {
  flex: 1;
  min-height: 44px;
  border-radius: 8px;
  border: 1px solid #444;
  background: rgba(0, 0, 0, 0.3);
  color: #eee;
  padding: 0 12px;
  font-size: 14px;
}

.roleplay-send-btn {
  min-height: 44px;
  padding: 0 16px;
  border-radius: 8px;
  border: 1px solid rgba(232, 202, 143, 0.4);
  background: rgba(232, 202, 143, 0.12);
  color: #f6ecd2;
  font-size: 14px;
  font-weight: 600;
}

.roleplay-send-btn:disabled,
.roleplay-choice-btn:disabled {
  opacity: 0.4;
}

.roleplay-error {
  flex-shrink: 0;
  margin: 0;
  padding: 8px 16px;
  font-size: 12px;
  color: #e6b0b0;
  background: rgba(120, 30, 30, 0.15);
}
</style>
