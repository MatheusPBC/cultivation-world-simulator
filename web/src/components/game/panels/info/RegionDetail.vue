<script setup lang="ts">
import type { RegionDetail } from '@/types/core';
import EntityRow from './components/EntityRow.vue';
import RelationRow from './components/RelationRow.vue';
import SecondaryPopup from './components/SecondaryPopup.vue';
import { useI18n } from 'vue-i18n';
import { computed } from 'vue';
import { formatPopulationRatioText } from '@/utils/populationFormat';
import { useRegionDetailPanel } from '@/composables/useRegionDetailPanel';
import { useWorldJournalStore } from '@/stores/worldJournal';
import type { CollectiveHealthReading, SemanticCondition, SemanticReadingKey } from '@/types/core';
import gemIcon from '@/assets/icons/ui/lucide/gem.svg';
import leafIcon from '@/assets/icons/ui/lucide/leaf.svg';
import messageCircleIcon from '@/assets/icons/ui/lucide/message-circle.svg';
import packageIcon from '@/assets/icons/ui/lucide/package.svg';
import sparkleIcon from '@/assets/icons/ui/lucide/sparkles.svg';

const { locale, t } = useI18n();
const props = defineProps<{
  data: RegionDetail;
}>();

const {
  secondaryItem,
  getPopulationBarColor,
  formatEssenceType,
  getRegionTypeExplanation,
  getRegionTypeIcon,
  showDetail,
  closeSecondaryDetail,
  jumpToSect,
  jumpToAvatar,
} = useRegionDetailPanel(() => props.data);

const journalStore = useWorldJournalStore();
const semanticContext = computed(() => props.data.semantic_context);
const activeSemanticConditions = computed(() =>
  semanticContext.value?.conditions.filter((condition) => condition.resolved_month == null) ?? [],
);
const semanticReadings = computed(() => semanticContext.value?.readings ?? []);
const activeHazards = computed(() => semanticContext.value?.active_hazards ?? []);
const cityState = computed(() => props.data.city_state);
const economy = computed(() => props.data.economy);
const infrastructure = computed(() => props.data.infrastructure);
const economyGroups = computed(() => {
  const value = economy.value;
  if (!value) return [];
  return [
    { key: 'stocks', values: value.stocks },
    { key: 'capacities', values: value.capacities },
    { key: 'production_rates', values: value.production_rates },
    { key: 'demand_rates', values: value.demand_rates },
    { key: 'access', values: value.access },
    { key: 'dependencies', values: value.dependencies },
  ].filter((group) => Object.keys(group.values).length > 0);
});
const infrastructureGroups = computed(() => {
  const value = infrastructure.value;
  if (!value) return [];
  return [
    { key: 'capacities', values: value.capacities },
    { key: 'quality', values: value.quality },
  ].filter((group) => Object.keys(group.values).length > 0);
});
const hasEconomyFacts = computed(() => economyGroups.value.length > 0);
const hasInfrastructureFacts = computed(() => infrastructureGroups.value.length > 0);
const spiritualEcology = computed(() => semanticContext.value?.spiritual_ecology ?? null);
const collectiveHealth = computed(() => semanticContext.value?.collective_health ?? null);
const collectiveHealthReadings = computed(() => {
  const health = collectiveHealth.value;
  if (!health) return [];
  const readings: Array<{ key: string; reading: CollectiveHealthReading }> = [
    { key: 'living_avatar_count', reading: health.living_avatar_count },
    { key: 'active_wounded_count', reading: health.active_wounded_count },
    { key: 'hp_deficit', reading: health.hp_deficit },
    { key: 'healing_capacity', reading: health.healing_capacity },
  ];
  readings.push({ key: 'healing_access', reading: health.healing_access });
  return readings;
});
const hasGovernanceFacts = computed(() => {
  const governance = cityState.value?.governance;
  return Boolean(
    governance && (
      governance.controller_kind ||
      governance.controller_id ||
      governance.administrative_capacity !== 0
    ),
  );
});
const hasUrbanServiceFacts = computed(() => Boolean(
  cityState.value && (
    cityState.value.service_demands.length > 0 ||
    cityState.value.population_groups.length > 0
  ),
));
const hasCityStateFacts = computed(() => Boolean(
  cityState.value && (
    cityState.value.districts.length > 0 ||
    cityState.value.assets.length > 0 ||
    hasUrbanServiceFacts.value ||
    hasGovernanceFacts.value
  ),
));
const hasRegionalContext = computed(() => Boolean(
  props.data.dao_tradition ||
  activeHazards.value.length ||
  activeSemanticConditions.value.length ||
  semanticReadings.value.length ||
  hasCityStateFacts.value ||
  hasEconomyFacts.value ||
  hasInfrastructureFacts.value ||
  spiritualEcology.value ||
  collectiveHealth.value,
));

function openCausalDetail(eventId: string) {
  void journalStore.openCausalDetail(eventId);
}

function conditionEventIds(condition: SemanticCondition): string[] {
  return [...new Set([condition.cause_event_id, condition.resolution_event_id].filter(
    (eventId): eventId is string => Boolean(eventId),
  ))];
}

function hazardEventIds(hazard: (typeof activeHazards.value)[number]): string[] {
  return [...new Set([...hazard.source_event_ids, hazard.last_event_id].filter(Boolean))];
}

function readingValue(reading: (typeof semanticReadings.value)[number]): string {
  if (reading.value === null || reading.reading_kind === 'unknown') {
    return t('game.info_panel.region.semantic_context.unknown_value');
  }
  return String(reading.value);
}

function readingKeyText(key: SemanticReadingKey): string {
  const parts = [`${key.dimension}(${key.concept_id}) · ${key.subject_kind}:${key.subject_id}`];
  if (key.group_id) {
    parts.push(t('game.info_panel.region.semantic_context.group_id', { id: key.group_id }));
  }
  for (const [name, value] of Object.entries(key.qualifiers ?? {}).sort(([left], [right]) => left.localeCompare(right))) {
    parts.push(`${name}=${value}`);
  }
  return parts.join(' · ');
}

function readingKeyIdentity(key: SemanticReadingKey): string {
  return [
    key.dimension,
    key.subject_kind,
    key.subject_id,
    key.concept_id,
    key.group_id ?? '',
    ...Object.entries(key.qualifiers ?? {})
      .sort(([left], [right]) => left.localeCompare(right))
      .flat(),
  ].join(':');
}

function healthReadingValue(reading: CollectiveHealthReading): string {
  if (reading.value === null || reading.reading_kind === 'unknown') {
    return t('game.info_panel.region.semantic_context.unknown_value');
  }
  return String(reading.value);
}

function canonicalEntries(values: Record<string, number>): Array<[string, number]> {
  return Object.entries(values).sort(([left], [right]) => left.localeCompare(right));
}

function percentText(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function tileRefsText(tileRefs: Array<[number, number]>): string {
  return tileRefs.map(([x, y]) => `(${x}, ${y})`).join(' · ');
}

function locationText(location: [number, number]): string {
  return `(${location[0]}, ${location[1]})`;
}

function spiritualEffectEntries(
  effects: Record<string, number | string | boolean | null>,
): Array<[string, string]> {
  return Object.entries(effects).map(([key, value]) => [key, String(value)]);
}

function spiritualEffectText(effects: Record<string, number | string | boolean | null>): string {
  return spiritualEffectEntries(effects).map(([key, value]) => `${key}: ${value}`).join(' · ');
}

function spiritualDensitiesText(densities: Record<string, number>): string {
  return Object.entries(densities).map(([key, value]) => `${key}: ${value}`).join(' · ');
}

function spiritualGroundingText(status: string): string {
  return t(
    status === 'grounded'
      ? 'game.info_panel.region.spiritual_ecology.grounding.grounded'
      : 'game.info_panel.region.spiritual_ecology.grounding.unknown',
  );
}

function spiritualSourceEventIds(): string[] {
  return spiritualEcology.value?.source_event_ids ?? [];
}

function spiritualStateRefs(): string[] {
  return spiritualEcology.value?.state_refs ?? [];
}

function collectiveHealthSourceEventIds(): string[] {
  return collectiveHealth.value?.source_event_ids ?? [];
}

function collectiveHealthStateRefs(): string[] {
  return collectiveHealth.value?.state_refs ?? [];
}
</script>

<template>
  <div class="region-detail">
    <SecondaryPopup 
      :item="secondaryItem" 
      @close="closeSecondaryDetail" 
    />

    <!-- Info -->
    <div class="section">
      <div class="section-title">
        <span class="section-title-icon" :style="{ '--icon-url': `url(${getRegionTypeIcon()})` }" aria-hidden="true"></span>
        {{ data.type_name }}
      </div>
      <div class="type-note">
        <span class="inline-icon" :style="{ '--icon-url': `url(${messageCircleIcon})` }" aria-hidden="true"></span>
        {{ getRegionTypeExplanation() }}
      </div>
      <div class="desc">{{ data.desc }}</div>

      <!-- Population -->
      <div class="population-container" v-if="data.population !== undefined && data.population_capacity !== undefined">
        <div class="section-title">{{ t('game.population') }}</div>
        <div class="population-bar">
          <div
            class="fill"
            :style="{
              width: `${Math.min(100, (data.population / data.population_capacity) * 100)}%`,
              backgroundColor: getPopulationBarColor(data.population / data.population_capacity),
            }"
          ></div>
          <div class="text">{{ formatPopulationRatioText(data.population, data.population_capacity, t, locale) }}</div>
        </div>
      </div>

      <!-- Urban state -->
      <section v-if="hasCityStateFacts" class="city-state">
        <div class="section-title">{{ t('game.info_panel.region.city_state.title') }}</div>
        <div v-if="cityState?.districts.length" class="city-state__group">
          <h3 class="subheading">{{ t('game.info_panel.region.city_state.districts') }}</h3>
          <article v-for="district in cityState.districts" :key="district.id" class="fact-card">
            <div class="fact-card__header">
              <strong>{{ district.id }}</strong>
              <span>{{ district.kind }}</span>
            </div>
            <div class="semantic-meta">
              {{ t('game.info_panel.region.city_state.population_weight', { value: percentText(district.population_weight) }) }}
            </div>
            <div v-if="district.tile_refs.length" class="semantic-meta">
              {{ t('game.info_panel.region.city_state.tiles', { value: tileRefsText(district.tile_refs) }) }}
            </div>
          </article>
        </div>
        <div v-if="cityState?.assets.length" class="city-state__group">
          <h3 class="subheading">{{ t('game.info_panel.region.city_state.assets') }}</h3>
          <article v-for="asset in cityState.assets" :key="asset.id" class="fact-card">
            <div class="fact-card__header">
              <strong>{{ asset.id }}</strong>
              <span>{{ asset.district_id }}</span>
            </div>
            <div class="fact-card__capabilities">
              {{ asset.capability_ids.join(' · ') }}
            </div>
            <div class="fact-card__values">
              <span>{{ t('game.info_panel.region.city_state.capacity', { value: asset.capacity }) }}</span>
              <span>{{ t('game.info_panel.region.city_state.quality', { value: percentText(asset.quality) }) }}</span>
              <span>{{ t('game.info_panel.region.city_state.integrity', { value: percentText(asset.integrity) }) }}</span>
            </div>
          </article>
        </div>
        <section v-if="hasUrbanServiceFacts" class="city-state__group urban-services" data-testid="region-urban-services">
          <h3 class="subheading">{{ t('game.info_panel.region.city_state.urban_services') }}</h3>
          <div v-if="cityState?.service_demands.length" class="urban-services__section">
            <strong class="city-state__label">{{ t('game.info_panel.region.city_state.service_demands') }}</strong>
            <div class="canonical-state__groups">
              <article v-for="demand in cityState.service_demands" :key="demand.capability_id" class="fact-card canonical-map">
                <strong>{{ demand.capability_id }}</strong>
                <span>{{ t('game.info_panel.region.city_state.demand_per_population', { value: demand.demand_per_population }) }}</span>
              </article>
            </div>
          </div>
          <div v-if="cityState?.population_groups.length" class="urban-services__section">
            <strong class="city-state__label">{{ t('game.info_panel.region.city_state.population_groups') }}</strong>
            <div class="city-state__groups">
              <article v-for="group in cityState.population_groups" :key="group.id" class="fact-card">
                <div class="fact-card__header">
                  <strong>{{ group.id }}</strong>
                  <span>{{ t('game.info_panel.region.city_state.group_population_weight', { value: percentText(group.population_weight) }) }}</span>
                </div>
                <div v-if="Object.keys(group.service_priority_weights).length" class="urban-services__priorities">
                  <span class="city-state__label">{{ t('game.info_panel.region.city_state.priorities') }}</span>
                  <div v-for="[capabilityId, priority] in canonicalEntries(group.service_priority_weights)" :key="`${group.id}:${capabilityId}`" class="canonical-map__row">
                    <span>{{ capabilityId }}</span>
                    <span>{{ t('game.info_panel.region.city_state.priority_weight', { value: priority }) }}</span>
                  </div>
                </div>
              </article>
            </div>
          </div>
        </section>
        <div v-if="hasGovernanceFacts" class="city-state__group">
          <h3 class="subheading">{{ t('game.info_panel.region.city_state.governance') }}</h3>
          <article class="fact-card">
            <div v-if="cityState?.governance.controller_kind && cityState.governance.controller_id" class="fact-card__header">
              <span>{{ t('game.info_panel.region.city_state.controller') }}</span>
              <strong>{{ cityState.governance.controller_kind }}:{{ cityState.governance.controller_id }}</strong>
            </div>
            <div class="semantic-meta">
              {{ t('game.info_panel.region.city_state.administrative_capacity', { value: cityState?.governance.administrative_capacity }) }}
            </div>
          </article>
        </div>
      </section>
      
      <!-- Sect Jump Button -->
      <div v-if="data.sect_id" class="actions">
         <button class="btn primary" @click="jumpToSect(data.sect_id!)">{{ t('game.info_panel.region.view_sect') }}</button>
      </div>
    </div>

    <div class="section regional-context" v-if="hasRegionalContext">
      <div class="section-title">{{ t('game.info_panel.region.regional_context_title') }}</div>
      <div v-if="data.dao_tradition" class="dao-tradition">
        <span>{{ t('game.info_panel.region.dao_tradition') }}</span>
        <strong>{{ t(`game.info_panel.region.dao_traditions.${data.dao_tradition}`) }}</strong>
      </div>
      <section v-if="hasEconomyFacts" class="semantic-subsection canonical-state" data-testid="region-economy">
        <h3 class="subheading">{{ t('game.info_panel.region.economy.title') }}</h3>
        <div class="canonical-state__groups">
          <article v-for="group in economyGroups" :key="group.key" class="fact-card canonical-map">
            <strong>{{ t(`game.info_panel.region.economy.${group.key}`) }}</strong>
            <div v-for="[conceptId, value] in canonicalEntries(group.values)" :key="conceptId" class="canonical-map__row">
              <span>{{ conceptId }}</span>
              <span>{{ value }}</span>
            </div>
          </article>
        </div>
      </section>
      <section v-if="hasInfrastructureFacts" class="semantic-subsection canonical-state" data-testid="region-infrastructure">
        <h3 class="subheading">{{ t('game.info_panel.region.infrastructure.title') }}</h3>
        <div class="canonical-state__groups">
          <article v-for="group in infrastructureGroups" :key="group.key" class="fact-card canonical-map">
            <strong>{{ t(`game.info_panel.region.infrastructure.${group.key}`) }}</strong>
            <div v-for="[conceptId, value] in canonicalEntries(group.values)" :key="conceptId" class="canonical-map__row">
              <span>{{ conceptId }}</span>
              <span>{{ value }}</span>
            </div>
          </article>
        </div>
      </section>
      <section v-if="activeHazards.length" class="semantic-subsection" data-testid="region-active-hazards">
        <h3 class="subheading">{{ t('game.info_panel.region.semantic_context.hazards_title') }}</h3>
        <article v-for="hazard in activeHazards" :key="`${hazard.kind}:${hazard.region_id}`" class="semantic-condition">
          <div class="semantic-condition__header">
            <strong>{{ t(`game.info_panel.region.semantic_context.hazards.${hazard.kind}`) }}</strong>
            <span>{{ t('game.info_panel.region.semantic_context.risk', { value: Math.round(hazard.activation_risk * 100) }) }}</span>
          </div>
          <div class="semantic-meta">
            {{ t('game.info_panel.region.semantic_context.started_month', { month: hazard.started_month }) }}
          </div>
          <div v-if="hazardEventIds(hazard).length" class="semantic-events">
            <div v-for="eventId in hazardEventIds(hazard)" :key="eventId" class="semantic-event">
              <span class="semantic-event__id">{{ t('game.info_panel.region.semantic_context.source_event', { id: eventId }) }}</span>
              <button
                type="button"
                class="semantic-event__why"
                :data-testid="`region-hazard-causal-event-${eventId}`"
                :data-event-id="eventId"
                @click="openCausalDetail(eventId)"
              >
                {{ t('game.world_journal.why_button') }}
              </button>
            </div>
          </div>
        </article>
      </section>
      <section v-if="activeSemanticConditions.length" class="semantic-subsection">
        <h3 class="subheading">{{ t('game.info_panel.region.semantic_context.conditions_title') }}</h3>
        <article v-for="condition in activeSemanticConditions" :key="condition.id" class="semantic-condition">
          <div class="semantic-condition__header">
            <strong>{{ condition.label }}</strong>
            <span>{{ t('game.info_panel.region.semantic_context.intensity', { value: condition.intensity }) }}</span>
          </div>
          <div class="semantic-meta">
            {{ t('game.info_panel.region.semantic_context.started_month', { month: condition.started_month }) }}
            <span>· {{ t('game.info_panel.region.semantic_context.definition', { id: condition.definition_id }) }}</span>
          </div>
          <div v-if="conditionEventIds(condition).length" class="semantic-events">
            <div v-for="eventId in conditionEventIds(condition)" :key="eventId" class="semantic-event">
              <span class="semantic-event__id">{{ t('game.info_panel.region.semantic_context.source_event', { id: eventId }) }}</span>
              <button
                type="button"
                class="semantic-event__why"
                :data-testid="`region-condition-causal-event-${condition.id}-${eventId}`"
                :data-event-id="eventId"
                @click="openCausalDetail(eventId)"
              >
                {{ t('game.world_journal.why_button') }}
              </button>
            </div>
          </div>
        </article>
      </section>

      <section v-if="semanticReadings.length" class="semantic-subsection">
        <h3 class="subheading">{{ t('game.info_panel.region.semantic_context.readings_title') }}</h3>
        <article v-for="reading in semanticReadings" :key="readingKeyIdentity(reading.key)" class="semantic-reading">
          <div class="semantic-reading__header">
            <strong>{{ reading.key.concept_id }}</strong>
            <span class="semantic-reading__value">
              {{ readingValue(reading) }} <span class="semantic-reading__unit">{{ reading.unit }}</span>
            </span>
          </div>
          <div class="semantic-meta">
            {{ readingKeyText(reading.key) }}
          </div>
          <div class="semantic-reading__badges">
            <span>{{ t(`game.info_panel.region.semantic_context.availability.${reading.availability}`) }}</span>
            <span>{{ t(`game.info_panel.region.semantic_context.reading_kind.${reading.reading_kind}`) }}</span>
            <span v-if="reading.confidence !== null && reading.confidence !== undefined">
              {{ t('game.info_panel.region.semantic_context.confidence', { value: Math.round(reading.confidence * 100) }) }}
            </span>
          </div>
          <div v-if="reading.derived_from.length" class="semantic-reading__provenance">
            <span class="semantic-reading__provenance-label">
              {{ t('game.info_panel.region.semantic_context.derived_from') }}:
            </span>
            <ul>
              <li v-for="input in reading.derived_from" :key="readingKeyText(input)">
                {{ readingKeyText(input) }}
              </li>
            </ul>
          </div>
          <div
            v-if="reading.state_refs.length"
            class="semantic-reading__provenance"
            data-testid="region-reading-state-refs"
          >
            <span class="semantic-reading__provenance-label">
              {{ t('game.info_panel.region.semantic_context.state_refs') }}:
            </span>
            <ul>
              <li v-for="stateRef in reading.state_refs" :key="stateRef">
                {{ stateRef }}
              </li>
            </ul>
          </div>
          <div v-if="reading.source_event_ids.length" class="semantic-events">
            <div v-for="eventId in reading.source_event_ids" :key="eventId" class="semantic-event">
              <span class="semantic-event__id">{{ t('game.info_panel.region.semantic_context.source_event', { id: eventId }) }}</span>
              <button
                type="button"
                class="semantic-event__why"
                :data-testid="`region-reading-causal-event-${eventId}`"
                :data-event-id="eventId"
                @click="openCausalDetail(eventId)"
              >
                {{ t('game.world_journal.why_button') }}
              </button>
            </div>
          </div>
        </article>
      </section>

      <section v-if="spiritualEcology" class="semantic-subsection spiritual-ecology">
        <h3 class="subheading">{{ t('game.info_panel.region.spiritual_ecology.title') }}</h3>
        <article class="fact-card">
          <div class="fact-card__header">
            <strong>{{ t('game.info_panel.region.spiritual_ecology.grounding_label') }}</strong>
            <span>{{ spiritualGroundingText(spiritualEcology.grounding_status) }}</span>
          </div>
          <div v-if="spiritualEcology.essence" class="spiritual-fact">
            <strong>{{ t('game.info_panel.region.spiritual_ecology.essence') }}</strong>
            <span>{{ spiritualEcology.essence.type }} · {{ spiritualEcology.essence.density }}</span>
            <span v-if="Object.keys(spiritualEcology.essence.densities).length" class="semantic-meta">
              {{ t('game.info_panel.region.spiritual_ecology.densities') }}: {{ spiritualDensitiesText(spiritualEcology.essence.densities) }}
            </span>
          </div>
          <div v-if="spiritualEcology.formations.length" class="spiritual-fact-list">
            <strong>{{ t('game.info_panel.region.spiritual_ecology.formations') }}</strong>
            <div v-for="formation in spiritualEcology.formations" :key="formation.id" class="spiritual-observation">
              <span>{{ formation.id }} · {{ formation.type }}</span>
              <span class="semantic-meta">
                {{ t('game.info_panel.region.spiritual_ecology.started_month', { value: formation.started_month }) }}
                <template v-if="formation.expires_month !== null">
                  · {{ t('game.info_panel.region.spiritual_ecology.expires_month', { value: formation.expires_month }) }}
                </template>
              </span>
              <span v-if="spiritualEffectEntries(formation.effects).length" class="semantic-meta">
                {{ t('game.info_panel.region.spiritual_ecology.effects') }}:
                {{ spiritualEffectText(formation.effects) }}
              </span>
            </div>
          </div>
          <div v-if="spiritualEcology.graves.length" class="spiritual-fact-list">
            <strong>{{ t('game.info_panel.region.spiritual_ecology.graves') }}</strong>
            <div v-for="grave in spiritualEcology.graves" :key="grave.id" class="spiritual-observation">
              <span>{{ grave.name }} · {{ grave.id }}</span>
              <span class="semantic-meta">
                {{ t('game.info_panel.region.spiritual_ecology.location', { value: locationText(grave.location) }) }}
                · {{ t('game.info_panel.region.spiritual_ecology.created_month', { value: grave.created_month }) }}
                <template v-if="grave.expires_month !== null">
                  · {{ t('game.info_panel.region.spiritual_ecology.expires_month', { value: grave.expires_month }) }}
                </template>
              </span>
            </div>
          </div>
          <div v-if="spiritualEcology.treasures.length" class="spiritual-fact-list">
            <strong>{{ t('game.info_panel.region.spiritual_ecology.treasures') }}</strong>
            <div v-for="treasure in spiritualEcology.treasures" :key="treasure.id" class="spiritual-observation">
              <span>{{ treasure.name }} · {{ treasure.id }}</span>
              <span class="semantic-meta">
                {{ t('game.info_panel.region.spiritual_ecology.location', { value: locationText(treasure.location) }) }}
                · {{ t('game.info_panel.region.spiritual_ecology.created_month', { value: treasure.created_month }) }}
                <template v-if="treasure.expires_month !== null">
                  · {{ t('game.info_panel.region.spiritual_ecology.expires_month', { value: treasure.expires_month }) }}
                </template>
              </span>
            </div>
          </div>
          <div v-if="spiritualEcology.celestial_context" class="spiritual-fact-list">
            <strong>{{ t('game.info_panel.region.spiritual_ecology.celestial_context') }}</strong>
            <span>{{ spiritualEcology.celestial_context.name }}</span>
            <span v-if="spiritualEcology.celestial_context.description" class="semantic-meta">
              {{ spiritualEcology.celestial_context.description }}
            </span>
          </div>
          <div v-if="spiritualStateRefs().length" class="semantic-reading__provenance">
            <span class="semantic-reading__provenance-label">
              {{ t('game.info_panel.region.spiritual_ecology.state_refs') }}:
            </span>
            {{ spiritualStateRefs().join(' · ') }}
          </div>
          <div v-if="spiritualSourceEventIds().length" class="semantic-events">
            <div v-for="eventId in spiritualSourceEventIds()" :key="eventId" class="semantic-event">
              <span class="semantic-event__id">{{ t('game.info_panel.region.semantic_context.source_event', { id: eventId }) }}</span>
              <button
                type="button"
                class="semantic-event__why"
                :data-testid="`region-spiritual-causal-event-${eventId}`"
                :data-event-id="eventId"
                @click="openCausalDetail(eventId)"
              >
                {{ t('game.world_journal.why_button') }}
              </button>
            </div>
          </div>
        </article>
      </section>

      <section v-if="collectiveHealth" class="semantic-subsection collective-health">
        <h3 class="subheading">{{ t('game.info_panel.region.collective_health.title') }}</h3>
        <article class="fact-card">
          <div class="fact-card__header">
            <strong>{{ t('game.info_panel.region.collective_health.grounding_label') }}</strong>
            <span>{{ spiritualGroundingText(collectiveHealth.grounding_status) }}</span>
          </div>
          <div class="collective-health__readings">
            <div v-for="item in collectiveHealthReadings" :key="item.key" class="health-reading">
              <div class="health-reading__header">
                <span>{{ t(`game.info_panel.region.collective_health.${item.key}`) }}</span>
                <strong>{{ healthReadingValue(item.reading) }} {{ item.reading.unit }}</strong>
              </div>
              <div class="semantic-meta">
                {{ t(`game.info_panel.region.semantic_context.availability.${item.reading.availability}`) }}
                · {{ t(`game.info_panel.region.semantic_context.reading_kind.${item.reading.reading_kind}`) }}
              </div>
            </div>
          </div>
          <div v-if="collectiveHealth.injuries.length" class="spiritual-fact-list">
            <strong>{{ t('game.info_panel.region.collective_health.injuries') }}</strong>
            <span v-for="injury in collectiveHealth.injuries" :key="injury.avatar_id">
              {{ injury.avatar_id }} · {{ injury.severity }} ·
              {{ t('game.info_panel.region.collective_health.hp_lost', { value: injury.hp_lost }) }}
            </span>
          </div>
          <div v-if="collectiveHealth.healing_assets.length" class="spiritual-fact-list">
            <strong>{{ t('game.info_panel.region.collective_health.healing_assets') }}</strong>
            <span v-for="asset in collectiveHealth.healing_assets" :key="asset.asset_id">
              {{ asset.asset_id }} · {{ asset.capability_ids.join(' · ') }} ·
              {{ t('game.info_panel.region.collective_health.capacity', { value: asset.capacity }) }}
            </span>
          </div>
          <div v-if="collectiveHealthStateRefs().length" class="semantic-reading__provenance">
            <span class="semantic-reading__provenance-label">
              {{ t('game.info_panel.region.collective_health.state_refs') }}:
            </span>
            {{ collectiveHealthStateRefs().join(' · ') }}
          </div>
          <div v-if="collectiveHealthSourceEventIds().length" class="semantic-events">
            <div v-for="eventId in collectiveHealthSourceEventIds()" :key="eventId" class="semantic-event">
              <span class="semantic-event__id">{{ t('game.info_panel.region.semantic_context.source_event', { id: eventId }) }}</span>
              <button
                type="button"
                class="semantic-event__why"
                :data-testid="`region-health-causal-event-${eventId}`"
                :data-event-id="eventId"
                @click="openCausalDetail(eventId)"
              >
                {{ t('game.world_journal.why_button') }}
              </button>
            </div>
          </div>
        </article>
      </section>

      <div v-if="semanticContext && !activeHazards.length && !activeSemanticConditions.length && !semanticReadings.length && !spiritualEcology && !collectiveHealth" class="empty-hint">
        {{ t('game.info_panel.region.semantic_context.empty') }}
      </div>
    </div>

    <!-- Essence -->
    <div class="section" v-if="data.essence">
      <div class="section-title">
        <span class="section-title-icon" :style="{ '--icon-url': `url(${gemIcon})` }" aria-hidden="true"></span>
        {{ t('game.info_panel.region.essence_title') }}
      </div>
      <div class="essence-info">
        {{ t('game.info_panel.region.essence_info', { type: formatEssenceType(data.essence.type), density: data.essence.density }) }}
      </div>
    </div>

    <!-- Formation -->
    <div class="section" v-if="data.formation">
      <div class="section-title">
        <span class="section-title-icon" :style="{ '--icon-url': `url(${sparkleIcon})` }" aria-hidden="true"></span>
        {{ data.formation.name }}
      </div>
      <div class="formation-info">
        <div>{{ t('game.info_panel.region.formation_remaining', { months: data.formation.remaining_months }) }}</div>
        <div v-if="data.formation.effect_desc">{{ data.formation.effect_desc }}</div>
      </div>
    </div>

    <!-- Host (洞府主人) -->
    <div class="section" v-if="data.type === 'cultivate'">
      <div class="section-title">{{ t('game.info_panel.region.sections.host') }}</div>
      <RelationRow 
        v-if="data.host"
        :name="data.host.name"
        :meta="t('game.info_panel.region.host_meta')"
        @click="jumpToAvatar(data.host.id)"
      />
      <div v-else class="empty-hint">{{ t('game.info_panel.region.no_host') }}</div>
    </div>

    <!-- Animals -->
    <div class="section" v-if="data.animals?.length">
      <div class="section-title">{{ t('game.info_panel.region.sections.animals') }}</div>
      <div class="list">
        <EntityRow 
          v-for="animal in data.animals"
          :key="animal.name"
          :item="animal"
          compact
          @click="showDetail(animal)"
        />
      </div>
    </div>

    <!-- Plants -->
    <div class="section" v-if="data.plants?.length">
      <div class="section-title">
        <span class="section-title-icon" :style="{ '--icon-url': `url(${leafIcon})` }" aria-hidden="true"></span>
        {{ t('game.info_panel.region.sections.plants') }}
      </div>
      <div class="list">
        <EntityRow 
          v-for="plant in data.plants"
          :key="plant.name"
          :item="plant"
          compact
          @click="showDetail(plant)"
        />
      </div>
    </div>

    <!-- Lodes -->
    <div class="section" v-if="data.lodes?.length">
      <div class="section-title">
        <span class="section-title-icon" :style="{ '--icon-url': `url(${gemIcon})` }" aria-hidden="true"></span>
        {{ t('game.info_panel.region.sections.lodes') }}
      </div>
      <div class="list">
        <EntityRow 
          v-for="lode in data.lodes"
          :key="lode.name"
          :item="lode"
          compact
          @click="showDetail(lode)"
        />
      </div>
    </div>

    <!-- Store Items -->
    <div class="section" v-if="data.store_items?.length">
      <div class="section-title">
        <span class="section-title-icon" :style="{ '--icon-url': `url(${packageIcon})` }" aria-hidden="true"></span>
        {{ t('game.info_panel.region.sections.market') }}
      </div>
      <div class="list">
        <EntityRow 
          v-for="item in data.store_items"
          :key="item.id || item.name"
          :item="item"
          :meta="t('game.info_panel.region.price_meta', { price: item.price })"
          compact
          @click="showDetail(item)"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.region-detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
  overflow-y: auto;
  position: relative;
}

.section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: bold;
  color: #666;
  text-transform: uppercase;
  border-bottom: 1px solid #333;
  padding-bottom: 4px;
}

.desc {
  font-size: 13px;
  line-height: 1.5;
  color: #ccc;
}

.type-note {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 12px;
  color: #a8d8c0;
  line-height: 1.5;
}

.section-title-icon,
.inline-icon {
  display: inline-block;
  width: 1em;
  height: 1em;
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

.essence-info {
  font-size: 13px;
  color: #88fdc4;
}

.formation-info {
  font-size: 13px;
  color: #d8c27a;
  line-height: 1.5;
}

.regional-context { color: #c9d7e8; }
.dao-tradition { display: flex; justify-content: space-between; gap: 12px; padding-bottom: 8px; border-bottom: 1px solid color-mix(in srgb, currentColor 18%, transparent); }
.dao-tradition strong { color: var(--panel-accent-strong); text-align: right; }
.subheading { color: #8fb3d9; font-size: 11px; margin-top: 3px; }
.semantic-subsection { display: flex; flex-direction: column; gap: 6px; }
.semantic-condition, .semantic-reading { display: flex; flex-direction: column; gap: 5px; padding: 8px; border: 1px solid rgba(143, 179, 217, 0.18); border-radius: 4px; background: rgba(255, 255, 255, 0.025); }
.semantic-condition__header, .semantic-reading__header { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; font-size: 12px; line-height: 1.45; }
.semantic-condition__header strong, .semantic-reading__header strong { color: #e0e8f1; overflow-wrap: anywhere; }
.semantic-condition__header span, .semantic-reading__value { color: #ffd666; flex: 0 0 auto; }
.semantic-reading__value { text-align: right; }
.semantic-reading__unit { color: #9db6cf; }
.semantic-meta { color: #8d9eaf; font-size: 10px; line-height: 1.4; overflow-wrap: anywhere; }
.semantic-reading__badges { display: flex; flex-wrap: wrap; gap: 4px; }
.semantic-reading__badges span { padding: 2px 5px; border-radius: 999px; background: rgba(143, 179, 217, 0.12); color: #b9cbe0; font-size: 10px; }
.semantic-reading__provenance { color: #b9cbe0; font-size: 10px; line-height: 1.4; overflow-wrap: anywhere; }
.semantic-reading__provenance-label { color: #8d9eaf; }
.semantic-reading__provenance ul { margin: 3px 0 0; padding-left: 16px; }
.semantic-reading__provenance li + li { margin-top: 2px; }
.semantic-events { display: flex; flex-direction: column; gap: 4px; }
.semantic-event { display: flex; align-items: center; justify-content: space-between; gap: 8px; min-height: 30px; }
.semantic-event__id { color: #9db6cf; font-size: 10px; overflow-wrap: anywhere; }
.semantic-event__why { min-height: 30px; padding: 4px 9px; border: 1px solid rgba(197, 166, 107, 0.5); border-radius: 999px; background: rgba(85, 63, 27, 0.28); color: #f1dfb9; font-size: 10px; cursor: pointer; }
.semantic-event__why:hover, .semantic-event__why:focus-visible { background: rgba(110, 83, 37, 0.48); }
.city-state { margin-top: 10px; gap: 8px; }
.city-state__group { display: flex; flex-direction: column; gap: 6px; }
.city-state__groups { display: flex; flex-direction: column; gap: 6px; }
.city-state__label { color: #8fb3d9; font-size: 10px; line-height: 1.35; }
.urban-services { gap: 8px; }
.urban-services__section { display: flex; flex-direction: column; gap: 5px; }
.urban-services__priorities { display: flex; flex-direction: column; gap: 3px; }
.fact-card { display: flex; flex-direction: column; gap: 5px; padding: 8px; border: 1px solid rgba(143, 179, 217, 0.18); border-radius: 4px; background: rgba(255, 255, 255, 0.025); }
.fact-card__header { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; font-size: 12px; line-height: 1.45; }
.fact-card__header strong { color: #e0e8f1; overflow-wrap: anywhere; }
.fact-card__header span { color: #9db6cf; overflow-wrap: anywhere; text-align: right; }
.fact-card__capabilities { color: #b9cbe0; font-size: 10px; line-height: 1.4; overflow-wrap: anywhere; }
.fact-card__values { display: flex; flex-wrap: wrap; gap: 5px 10px; color: #c9d7e8; font-size: 10px; }
.spiritual-fact, .spiritual-fact-list { display: flex; flex-wrap: wrap; gap: 6px; color: #c9d7e8; font-size: 11px; line-height: 1.4; }
.spiritual-fact strong, .spiritual-fact-list strong { color: #8fb3d9; }
.spiritual-fact-list { flex-direction: column; gap: 2px; }
.spiritual-fact-list span { overflow-wrap: anywhere; }
.spiritual-observation { display: flex; flex-direction: column; gap: 2px; }
.collective-health__readings { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px; }
.health-reading { display: flex; flex-direction: column; gap: 3px; padding: 6px; border: 1px solid rgba(143, 179, 217, 0.14); border-radius: 3px; background: rgba(255, 255, 255, 0.02); }
.health-reading__header { display: flex; flex-direction: column; gap: 2px; font-size: 10px; line-height: 1.35; }
.health-reading__header span { color: #9db6cf; overflow-wrap: anywhere; }
.health-reading__header strong { color: #e0e8f1; overflow-wrap: anywhere; }
.canonical-state__groups { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px; }
.canonical-map > strong { color: #8fb3d9; font-size: 10px; line-height: 1.35; }
.canonical-map__row { display: flex; justify-content: space-between; gap: 8px; font-size: 10px; line-height: 1.35; }
.canonical-map__row span:first-child { color: #b9cbe0; overflow-wrap: anywhere; }
.canonical-map__row span:last-child { color: #e0e8f1; flex: 0 0 auto; text-align: right; }

.empty-hint {
  font-size: 12px;
  color: #666;
  font-style: italic;
}

.list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.actions {
  margin-top: 8px;
}

.btn {
  width: 100%;
  padding: 6px 12px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.05);
  color: #ccc;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.2s;
}

.btn:hover {
  background: rgba(255, 255, 255, 0.1);
}

.btn.primary {
  background: #177ddc;
  color: white;
  border: none;
}

.btn.primary:hover {
  background: #1890ff;
}

.population-container {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.population-bar {
  height: 16px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  position: relative;
  overflow: hidden;
}

.population-bar .fill {
  height: 100%;
  transition: width 0.3s ease, background-color 0.3s ease;
}

.population-bar .text {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  color: white;
  text-shadow: 0 1px 2px rgba(0,0,0,0.5);
}
</style>
