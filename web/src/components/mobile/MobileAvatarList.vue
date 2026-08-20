<script setup lang="ts">
import { ref } from 'vue'
import { useAvatarStore } from '@/stores/avatar'
import { useRoleplayStore } from '@/stores/roleplay'
import { useMobileNav } from '@/composables/useMobileNav'
import { logError } from '@/utils/appError'
import MobileAvatarCard from './MobileAvatarCard.vue'

const avatarStore = useAvatarStore()
const roleplayStore = useRoleplayStore()
const { goTo } = useMobileNav()

const startingAvatarId = ref<string | null>(null)

async function handleRoleplay(avatarId: string) {
  startingAvatarId.value = avatarId
  try {
    await roleplayStore.startRoleplay(avatarId)
    goTo('roleplay')
  } catch (e) {
    logError('MobileAvatarList start roleplay', e)
  } finally {
    startingAvatarId.value = null
  }
}
</script>

<template>
  <div class="avatar-list-screen">
    <h2 class="avatar-list-title">Avatares ({{ avatarStore.avatarList.length }})</h2>

    <p v-if="avatarStore.avatarList.length === 0" class="avatar-list-empty">
      Nenhum avatar carregado ainda.
    </p>

    <ul v-else class="avatar-list">
      <li v-for="avatar in avatarStore.avatarList" :key="avatar.id">
        <MobileAvatarCard :avatar="avatar" @roleplay="handleRoleplay" />
      </li>
    </ul>
  </div>
</template>

<style scoped>
.avatar-list-screen {
  padding: 16px;
  padding-bottom: 24px;
}

.avatar-list-title {
  font-size: 14px;
  font-weight: 600;
  color: #ccc;
  margin: 0 0 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.avatar-list-empty {
  color: #888;
  font-size: 14px;
}

.avatar-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
</style>
