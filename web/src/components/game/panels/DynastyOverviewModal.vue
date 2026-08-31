<script setup lang="ts">
import { NModal, NSpin, NTag } from 'naive-ui'
import { useI18n } from 'vue-i18n'
import { useDynastyOverviewModal } from '@/composables/useDynastyOverviewModal'
import { formatCultivationText } from '@/utils/cultivationText'
import buildingIcon from '@/assets/icons/ui/lucide/building-2.svg'
import crownIcon from '@/assets/icons/ui/lucide/crown.svg'
import landmarkIcon from '@/assets/icons/ui/lucide/landmark.svg'
import scaleIcon from '@/assets/icons/ui/lucide/scale.svg'
import usersIcon from '@/assets/icons/ui/lucide/users.svg'

const props = defineProps<{
  show: boolean;
}>()

const emit = defineEmits<{
  (e: 'update:show', value: boolean): void;
}>()

const { t } = useI18n()
const {
  dynastyStore,
  panelStyleVars,
  overview,
  officials,
  summary,
  hasOverview,
  emperor,
  imperialCrisis,
  effectLines,
  jumpToAvatar,
  openCrisisEvidence,
} = useDynastyOverviewModal(() => props.show)

function handleShowChange(value: boolean) {
  emit('update:show', value)
}
</script>

<template>
  <n-modal
    :show="show"
    @update:show="handleShowChange"
    preset="card"
    :title="t('game.dynasty.title')"
    style="width: 760px; max-height: 80vh; overflow-y: auto;"
  >
    <n-spin :show="dynastyStore.isLoading">
      <div class="dynasty-overview" :style="panelStyleVars">
        <template v-if="hasOverview">
          <section class="hero-card">
            <div class="hero-header">
              <div class="hero-title-wrap">
                <span class="hero-icon" :style="{ '--icon-url': `url(${landmarkIcon})` }" aria-hidden="true"></span>
                <div>
                <div class="hero-title">{{ overview.title || overview.name }}</div>
                <div class="hero-subtitle">{{ t('game.dynasty.royal_house') }}：{{ overview.royal_house_name || overview.royal_surname }}</div>
                </div>
              </div>
              <n-tag size="small" :bordered="false" type="success">
                {{ t('game.dynasty.low_magic') }}
              </n-tag>
            </div>
            <div class="hero-desc">{{ overview.desc }}</div>
          </section>

        <section class="section">
            <div class="section-title">
              <span class="section-title-icon" :style="{ '--icon-url': `url(${buildingIcon})` }" aria-hidden="true"></span>
              {{ t('game.dynasty.summary.title') }}
            </div>
            <div class="info-grid">
              <div class="info-card">
                <div class="info-label">{{ t('game.dynasty.name') }}</div>
                <div class="info-value">{{ overview.name }}</div>
              </div>
              <div class="info-card">
                <div class="info-label">{{ t('game.dynasty.royal_house') }}</div>
                <div class="info-value">{{ overview.royal_house_name || overview.royal_surname }}</div>
              </div>
              <div class="info-card">
                <div class="info-label">{{ t('game.dynasty.style_tag') }}</div>
                <div class="info-value">{{ overview.style_tag || t('common.none') }}</div>
              </div>
              <div class="info-card">
                <div class="info-label">{{ t('game.dynasty.official_preference') }}</div>
                <div class="info-value">{{ overview.official_preference_label || t('common.none') }}</div>
              </div>
            </div>
        </section>

        <section v-if="imperialCrisis" class="section crisis-section">
          <div class="section-title">
            <span class="section-title-icon" :style="{ '--icon-url': `url(${scaleIcon})` }" aria-hidden="true"></span>
            {{ t('game.dynasty.crisis.title') }}
          </div>
          <div class="crisis-status">{{ t(`game.dynasty.crisis.status.${imperialCrisis.status}`) }}</div>
          <div class="crisis-contenders">
            <button type="button" class="contender" @click="jumpToAvatar(imperialCrisis.emperor.id)">
              <span>{{ t('game.dynasty.crisis.emperor') }}</span><strong>{{ imperialCrisis.emperor.name }}</strong>
            </button>
            <span class="crisis-versus" aria-hidden="true">↔</span>
            <button type="button" class="contender" @click="jumpToAvatar(imperialCrisis.claimant.id)">
              <span>{{ t('game.dynasty.crisis.claimant') }}</span><strong>{{ imperialCrisis.claimant.name }}</strong>
            </button>
          </div>
          <p class="crisis-meta">{{ t('game.dynasty.crisis.support', { count: imperialCrisis.supportCount }) }}</p>
          <div v-if="imperialCrisis.supporters.length" class="crisis-supporters">
            <span class="crisis-supporters-label">{{ t('game.dynasty.crisis.supporters') }}</span>
            <button
              v-for="supporter in imperialCrisis.supporters"
              :key="supporter.id"
              type="button"
              class="supporter"
              @click="jumpToAvatar(supporter.id)"
            >
              {{ supporter.name }}
            </button>
          </div>
          <div v-if="Object.keys(imperialCrisis.legitimacyFactors).length" class="legitimacy-factors">
            <span v-for="factor in ['office', 'reputation', 'cultivation', 'support', 'celestial', 'worldly_total', 'total']" :key="factor" v-show="factor in imperialCrisis.legitimacyFactors">
              {{ t(`game.dynasty.crisis.factors.${factor}`) }}: {{ imperialCrisis.legitimacyFactors[factor] > 0 ? '+' : '' }}{{ imperialCrisis.legitimacyFactors[factor] }}
            </span>
          </div>
          <div v-if="imperialCrisis.evidenceEventIds.length" class="crisis-evidence">
            <button v-for="eventId in imperialCrisis.evidenceEventIds" :key="eventId" type="button" @click="openCrisisEvidence(eventId)">{{ t('game.dynasty.crisis.evidence') }}</button>
          </div>
        </section>

        <section class="section">
            <div class="section-title">
              <span class="section-title-icon" :style="{ '--icon-url': `url(${crownIcon})` }" aria-hidden="true"></span>
              {{ t('game.dynasty.emperor.title') }}
            </div>
            <div v-if="emperor" class="info-grid">
              <button class="info-card emperor-row" type="button" @click="jumpToAvatar(emperor.id)">
                <div class="info-label">{{ t('game.dynasty.emperor.name') }}</div>
                <div class="info-value">{{ emperor.name }}</div>
              </button>
              <div class="info-card">
                <div class="info-label">{{ t('game.dynasty.emperor.age') }}</div>
                <div class="info-value">{{ emperor.age }}</div>
              </div>
              <div class="info-card">
                <div class="info-label">{{ t('game.dynasty.emperor.lifespan') }}</div>
                <div class="info-value">{{ emperor.max_age }}</div>
              </div>
              <div class="info-card">
                <div class="info-label">{{ t('game.dynasty.emperor.identity') }}</div>
                <div class="info-value emperor-tag">{{ t('game.dynasty.emperor.mortal') }}</div>
              </div>
            </div>
            <div v-else class="empty-state section-empty">
              {{ t('game.dynasty.emperor.empty') }}
            </div>
          </section>

        <section class="section">
            <div class="section-title">
              <span class="section-title-icon" :style="{ '--icon-url': `url(${scaleIcon})` }" aria-hidden="true"></span>
              {{ t('game.dynasty.effect') }}
            </div>
            <div v-if="effectLines.length" class="effect-card">
              <div class="effects-grid">
                <template v-for="(line, idx) in effectLines" :key="idx">
                  <div class="effect-source">{{ t('game.dynasty.effect_source') }}</div>
                  <div class="effect-content">{{ line }}</div>
                </template>
              </div>
            </div>
            <div v-else class="effect-card">
              {{ t('game.dynasty.effect_empty') }}
            </div>
          </section>

          <section class="section">
            <div class="section-header">
              <div class="section-title">
                <span class="section-title-icon" :style="{ '--icon-url': `url(${usersIcon})` }" aria-hidden="true"></span>
                {{ t('game.dynasty.officials.title') }}
              </div>
              <div class="section-meta">{{ t('game.dynasty.officials.count', { count: summary.officialCount }) }}</div>
            </div>
            <div v-if="officials.length" class="official-list">
              <button
                v-for="official in officials"
                :key="official.id"
                class="official-row"
                type="button"
                @click="jumpToAvatar(official.id)"
              >
                <div class="official-main">
                  <div class="official-name">{{ official.name }}</div>
                  <div class="official-rank">{{ official.officialRankName }}</div>
                </div>
                <div class="official-side">
                  <div class="official-meta">
                    {{ t('game.dynasty.officials.realm') }}：{{ formatCultivationText(official.realm, t) || t('common.none') }}
                  </div>
                  <div class="official-meta">
                    {{ t('game.dynasty.officials.court_reputation') }}：{{ official.courtReputation }}
                  </div>
                  <div class="official-meta">
                    {{ t('game.dynasty.officials.sect') }}：{{ official.sectName || t('game.dynasty.officials.rogue') }}
                  </div>
                </div>
              </button>
            </div>
            <div v-else class="empty-state section-empty">
              {{ t('game.dynasty.officials.empty') }}
            </div>
          </section>
        </template>

        <div v-else class="empty-state">
          {{ t('game.dynasty.empty') }}
        </div>
      </div>
    </n-spin>
  </n-modal>
</template>

<style scoped>
.dynasty-overview {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.hero-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px;
  border: 1px solid var(--panel-border);
  border-radius: 8px;
  background:
    linear-gradient(135deg, rgba(184, 121, 59, 0.34), rgba(69, 48, 30, 0.14)),
    rgba(255, 255, 255, 0.03);
}

.hero-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.hero-title-wrap {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.hero-icon {
  width: 28px;
  height: 28px;
  color: var(--panel-accent-strong);
  margin-top: 2px;
}

.hero-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--panel-text-primary);
}

.hero-subtitle {
  font-size: 13px;
  color: var(--panel-text-secondary);
  margin-top: 4px;
}

.hero-desc {
  color: var(--panel-text-secondary);
  line-height: 1.7;
}

.section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 700;
  color: var(--panel-title);
  border-bottom: 1px solid var(--panel-border);
  padding-bottom: 6px;
}

.hero-icon,
.section-title-icon {
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
  flex-shrink: 0;
}

.section-title-icon {
  width: 1em;
  height: 1em;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
}

.section-meta {
  font-size: 12px;
  color: var(--panel-text-secondary);
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
}

.info-card,
.effect-card {
  padding: 10px 12px;
  border: 1px solid var(--panel-border);
  border-radius: 6px;
  background: var(--panel-accent-soft);
}

.info-label {
  font-size: 12px;
  color: var(--panel-text-secondary);
  margin-bottom: 6px;
}

.info-value {
  font-size: 18px;
  font-weight: 700;
  color: var(--panel-text-primary);
}

.effect-card {
  color: var(--panel-text-secondary);
  line-height: 1.7;
}

.effects-grid {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 4px 12px;
  align-items: baseline;
}

.effect-source {
  color: var(--panel-text-secondary);
  white-space: nowrap;
}

.effect-content {
  color: var(--panel-text-primary);
}

.emperor-tag {
  color: var(--panel-accent-strong);
}

.crisis-section { border-color: color-mix(in srgb, var(--panel-accent) 62%, var(--panel-border)); }
.crisis-status { margin: 8px 0 12px; color: var(--panel-accent-strong); font-weight: 700; }
.crisis-contenders { display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); gap: 10px; align-items: center; }
.contender { min-height: 64px; padding: 10px; border: 1px solid var(--panel-border); border-radius: 6px; background: var(--panel-accent-soft); color: var(--panel-text-primary); text-align: left; cursor: pointer; }
.contender span { display: block; margin-bottom: 5px; color: var(--panel-text-secondary); font-size: 12px; }
.contender strong { display: block; overflow-wrap: anywhere; }
.crisis-versus { color: var(--panel-accent-strong); }
.crisis-meta { margin: 12px 0 0; color: var(--panel-text-secondary); font-size: 12px; }
.crisis-supporters { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 8px; }
.crisis-supporters-label { margin-right: 2px; color: var(--panel-text-secondary); font-size: 12px; }
.supporter { min-height: 32px; padding: 4px 8px; border: 1px solid var(--panel-border); border-radius: 999px; background: var(--panel-accent-soft); color: var(--panel-text-primary); cursor: pointer; }
.supporter:hover { border-color: var(--panel-accent); background: rgba(255, 255, 255, 0.06); }
.supporter:focus-visible { outline: 2px solid var(--panel-accent-strong); outline-offset: 2px; }
.legitimacy-factors { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.legitimacy-factors span { padding: 4px 7px; border: 1px solid var(--panel-border); border-radius: 999px; color: var(--panel-text-secondary); font-size: 11px; }
.crisis-evidence { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
.crisis-evidence button { min-height: 40px; border: 0; border-bottom: 1px solid var(--panel-accent-strong); background: transparent; color: var(--panel-accent-strong); cursor: pointer; }
.contender:focus-visible { outline: 2px solid var(--panel-accent-strong); outline-offset: 2px; }

.official-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.official-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  width: 100%;
  padding: 12px;
  border: 1px solid var(--panel-border);
  border-radius: 6px;
  background: var(--panel-accent-soft);
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease;
}

.emperor-row { width: 100%; color: inherit; text-align: left; cursor: pointer; }
.emperor-row:hover { border-color: var(--panel-accent); background: rgba(255, 255, 255, 0.06); }
.emperor-row:focus-visible { outline: 2px solid var(--panel-accent-strong); outline-offset: 2px; }

.official-row:hover {
  background: rgba(255, 255, 255, 0.06);
  border-color: var(--panel-accent);
}

.official-main {
  min-width: 0;
}

.official-name {
  font-size: 16px;
  font-weight: 700;
  color: var(--panel-text-primary);
}

.official-rank {
  margin-top: 4px;
  font-size: 12px;
  color: var(--panel-accent-strong);
}

.official-side {
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: flex-end;
}

.official-meta {
  font-size: 12px;
  color: var(--panel-text-secondary);
  white-space: nowrap;
}

.empty-state {
  text-align: center;
  color: var(--panel-empty);
  padding: 20px 0;
}

.section-empty {
  padding: 10px 0;
}

@media (max-width: 640px) {
  .official-row {
    grid-template-columns: 1fr;
  }

  .official-side {
    align-items: flex-start;
  }
}
</style>
