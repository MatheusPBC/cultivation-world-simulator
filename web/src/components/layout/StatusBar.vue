<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useWorldStore } from '../../stores/world'
import { useSocketStore } from '../../stores/socket'
import StatusWidget from './StatusWidget.vue'
import StatusBarPanels from './StatusBarPanels.vue'
import SimClock from './SimClock.vue'
import { PHENOMENON_RARITY_COLORS } from '@/constants/uiColors'
import bookOpenIcon from '@/assets/icons/ui/lucide/book-open.svg'
import sparklesIcon from '@/assets/icons/ui/lucide/sparkles.svg'
import shieldIcon from '@/assets/icons/ui/lucide/shield.svg'
import trophyIcon from '@/assets/icons/ui/lucide/trophy.svg'
import swordsIcon from '@/assets/icons/ui/lucide/swords.svg'
import usersIcon from '@/assets/icons/ui/lucide/users.svg'
import landmarkIcon from '@/assets/icons/ui/lucide/landmark.svg'
import mountainIcon from '@/assets/icons/ui/lucide/mountain.svg'
import scrollTextIcon from '@/assets/icons/ui/lucide/scroll-text.svg'
import menuIcon from '@/assets/icons/ui/lucide/menu.svg'

const { t } = useI18n()
const store = useWorldStore()
const socketStore = useSocketStore()
const panelsRef = ref<InstanceType<typeof StatusBarPanels> | null>(null)

const props = withDefaults(defineProps<{
  paused?: boolean
}>(), {
  paused: false,
})

const emit = defineEmits<{
  (e: 'toggle-pause'): void
  (e: 'open-menu'): void
}>()

type StatusBarPanelKey =
  | 'time'
  | 'worldInfo'
  | 'ranking'
  | 'tournament'
  | 'sectRelations'
  | 'mortalOverview'
  | 'dynastyOverview'
  | 'hiddenDomain'
  | 'phenomenonSelector'
  | 'avatarOverview'
  | 'worldSecret'

/*
 * Eleven equally-weighted, differently-coloured entries separated by `|` gave
 * the player no map of the interface. The same eleven destinations are now one
 * clock plus three semantic groups — the world itself, the powers acting in it,
 * and the records kept about it — separated by hairlines instead of glyphs.
 */
interface NavEntry {
  key: StatusBarPanelKey
  label: string
  icon: string
  accent?: string
  onSelect?: () => void
}

const phenomenonAccent = computed(() => {
  const phenomenon = store.currentPhenomenon
  if (!phenomenon) return undefined
  // Rarity is genuine live state, so this is the one entry that keeps a hue.
  return PHENOMENON_RARITY_COLORS[phenomenon.rarity] ?? undefined
})

const worldGroup = computed<NavEntry[]>(() => {
  const entries: NavEntry[] = []
  if (store.currentPhenomenon) {
    entries.push({
      key: 'phenomenonSelector',
      label: store.currentPhenomenon.name,
      icon: sparklesIcon,
      accent: phenomenonAccent.value,
      onSelect: openPhenomenonSelector,
    })
  }
  entries.push(
    { key: 'hiddenDomain', label: t('game.status_bar.hidden_domain.label'), icon: mountainIcon },
    { key: 'worldSecret', label: t('game.status_bar.world_secret.label'), icon: scrollTextIcon },
    { key: 'worldInfo', label: t('game.status_bar.world_info.label'), icon: bookOpenIcon },
  )
  return entries
})

const powerGroup = computed<NavEntry[]>(() => ([
  { key: 'sectRelations', label: t('game.sect_relations.title_short'), icon: shieldIcon },
  { key: 'dynastyOverview', label: t('game.dynasty.title_short'), icon: landmarkIcon },
  { key: 'mortalOverview', label: t('game.mortal_system.title_short'), icon: usersIcon },
]))

const recordGroup = computed<NavEntry[]>(() => ([
  { key: 'avatarOverview', label: t('game.status_bar.avatar_overview.label'), icon: usersIcon },
  { key: 'ranking', label: t('game.ranking.title_short'), icon: trophyIcon },
  { key: 'tournament', label: t('game.ranking.tournament_short'), icon: swordsIcon },
]))

const navGroups = computed(() => ([
  { key: 'world', entries: worldGroup.value },
  { key: 'powers', entries: powerGroup.value },
  { key: 'records', entries: recordGroup.value },
]))

async function openPhenomenonSelector() {
  await store.getPhenomenaList()
  void openPanel('phenomenonSelector')
}

function openPanel(panel: StatusBarPanelKey) {
  void panelsRef.value?.open(panel)
}

function selectEntry(entry: NavEntry) {
  if (entry.onSelect) {
    void entry.onSelect()
    return
  }
  openPanel(entry.key)
}
</script>

<template>
  <header class="hud">
    <SimClock
      :year="store.year"
      :month="store.month"
      :paused="props.paused"
      :connected="socketStore.isConnected"
      @toggle-pause="emit('toggle-pause')"
      @open-time="openPanel('time')"
    />

    <nav class="hud__rail" :aria-label="t('game.status_bar.nav_label')">
      <div
        v-for="group in navGroups"
        :key="group.key"
        class="hud__group"
        role="group"
        :aria-label="t(`game.status_bar.groups.${group.key}`)"
      >
        <StatusWidget
          v-for="entry in group.entries"
          :key="entry.key"
          :label="entry.label"
          :icon="entry.icon"
          :accent="entry.accent"
          :disable-popover="true"
          @trigger-click="selectEntry(entry)"
        />
      </div>
    </nav>

    <StatusBarPanels ref="panelsRef" />

    <div class="hud__end">
      <button
        type="button"
        class="hud__menu"
        :title="t('game.status_bar.menu')"
        :aria-label="t('game.status_bar.menu')"
        @click="emit('open-menu')"
      >
        <span class="cw-icon" :style="{ '--icon-url': `url(${menuIcon})` }" aria-hidden="true" />
      </button>
    </div>
  </header>
</template>

<style scoped>
.hud {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: var(--s-5);
  height: var(--hud-height);
  padding: 0 var(--s-5);
  /* Lacquered iron: one opaque surface, one engraved rule. No gradient stack. */
  background: var(--surface-chrome);
  border-bottom: 1px solid var(--rule-strong);
  z-index: 10;
  min-width: 0;
}

.hud__rail {
  flex: 1 1 auto;
  display: flex;
  align-items: center;
  min-width: 0;
  overflow: hidden;
}

.hud__group {
  display: flex;
  align-items: center;
  gap: var(--s-1);
  padding: 0 var(--s-4);
  min-width: 0;
}

/* Hairline separators replace the literal `|` characters. */
.hud__group + .hud__group {
  border-left: 1px solid var(--rule);
}

.hud__end {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: var(--s-3);
}

.hud__menu {
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--touch-target);
  height: 36px;
  border: 1px solid var(--rule);
  border-radius: var(--r-2);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: color var(--motion-fast), background var(--motion-fast),
    border-color var(--motion-fast);
}

.hud__menu:hover {
  color: var(--text-primary);
  background: var(--surface-raised);
  border-color: var(--rule-strong);
}

.hud__menu:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring);
}

@media (max-width: 720px) {
  .hud {
    gap: var(--s-3);
    padding: 0 var(--s-4);
  }

  .hud__group {
    padding: 0 var(--s-2);
  }
}
</style>
