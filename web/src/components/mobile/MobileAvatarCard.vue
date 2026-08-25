<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { AvatarSummary } from '@/types/core'
import { formatCultivationText, formatRealmLabel, humanizeIdentifier } from '@/utils/cultivationText'

const props = defineProps<{
  avatar: AvatarSummary
}>()

const emit = defineEmits<{
  roleplay: [avatarId: string]
}>()

const { t } = useI18n()

const statusLabel = computed(() => (
  props.avatar.is_dead ? t('game.deceased.status_dead') : t('game.deceased.status_alive')
))
const cultivationLabel = computed(() => {
  const cultivation = props.avatar.cultivation
  if (cultivation?.display_full_name) {
    return formatCultivationText(cultivation.display_full_name, t)
  }
  if (cultivation?.realm_id && cultivation?.stage_id) {
    return formatCultivationText(`${cultivation.realm_id} ${cultivation.stage_id}`, t)
  }
  return formatCultivationText(props.avatar.cultivation_display, t)
    || formatRealmLabel(props.avatar.realm, t)
    || '—'
})
const actionLabel = computed(() => humanizeIdentifier(props.avatar.action))
</script>

<template>
  <div class="avatar-card" :class="{ 'avatar-card--dead': avatar.is_dead }">
    <div class="avatar-card-main">
      <div class="avatar-card-name-row">
        <span class="avatar-card-name">{{ avatar.name }}</span>
        <span class="avatar-card-status">{{ statusLabel }}</span>
      </div>
      <div class="avatar-card-meta">
        {{ cultivationLabel }}
      </div>
      <div v-if="avatar.action" class="avatar-card-action">
        <span v-if="avatar.action_emoji">{{ avatar.action_emoji }}</span>
        {{ actionLabel }}
      </div>
    </div>

    <button
      type="button"
      class="avatar-card-roleplay-btn"
      :disabled="avatar.is_dead"
      @click="emit('roleplay', avatar.id)"
    >
      {{ t('game.roleplay.panel.start') }}
    </button>
  </div>
</template>

<style scoped>
.avatar-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  background: #181818;
  border: 1px solid #2c2c2c;
  border-radius: 10px;
  padding: 12px 14px;
}

.avatar-card--dead {
  opacity: 0.6;
}

.avatar-card-main {
  min-width: 0;
  flex: 1;
}

.avatar-card-name-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.avatar-card-name {
  font-size: 15px;
  font-weight: 600;
  color: #f0e6cc;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.avatar-card-status {
  font-size: 11px;
  color: #999;
  flex-shrink: 0;
}

.avatar-card-meta {
  font-size: 13px;
  color: #aaa;
  margin-top: 2px;
}

.avatar-card-action {
  font-size: 12px;
  color: #888;
  margin-top: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.avatar-card-roleplay-btn {
  flex-shrink: 0;
  min-height: 44px;
  padding: 0 16px;
  border-radius: 8px;
  border: 1px solid rgba(232, 202, 143, 0.4);
  background: rgba(232, 202, 143, 0.12);
  color: #f6ecd2;
  font-size: 13px;
  font-weight: 600;
}

.avatar-card-roleplay-btn:disabled {
  opacity: 0.4;
}
</style>
