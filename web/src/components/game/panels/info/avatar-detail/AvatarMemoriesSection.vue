<script setup lang="ts">
import { computed } from 'vue'
import type { PersonalAppraisalEntry } from '@/types/core'
import { appraisalStrengthClass } from '@/utils/appraisalStrength'

const props = withDefaults(
  defineProps<{
    appraisals?: PersonalAppraisalEntry[]
    title: string
    emptyText: string
    strengthLabelFor: (weight: number) => string
  }>(),
  {
    // 详情 payload 可能来自缓存或部分响应，缺字段时必须安全降级，
    // 不能让整个角色面板因为读取 undefined.length 而崩掉。
    appraisals: () => [],
  },
)

const emit = defineEmits<{
  (e: 'open-source', sourceEventId: string): void
}>()

const entries = computed<PersonalAppraisalEntry[]>(() =>
  Array.isArray(props.appraisals) ? props.appraisals : [],
)

function openSource(entry: PersonalAppraisalEntry) {
  emit('open-source', entry.source_event_id)
}
</script>

<template>
  <div class="section memories-section" v-if="entries.length">
    <div class="section-title">
      <slot name="icon" />
      {{ title }}
    </div>

    <ul class="memories-list">
      <li v-for="entry in entries" :key="entry.appraisal_id" class="memory-row">
        <button type="button" class="memory-item" @click="openSource(entry)">
          <span class="memory-line memory-line--top">
            <span class="memory-emoji" aria-hidden="true">{{ entry.emotion.emoji }}</span>
            <span class="memory-focus">{{ entry.focus_avatar_name }}</span>
            <span class="memory-strength" :class="appraisalStrengthClass(entry.effective_weight)">
              {{ props.strengthLabelFor(entry.effective_weight) }}
            </span>
          </span>
          <span class="memory-summary">{{ entry.summary }}</span>
          <span class="memory-line memory-line--meta">
            <span class="memory-emotion-name">{{ entry.emotion.name }}</span>
            <span class="memory-date">{{ entry.source_event_date }}</span>
          </span>
        </button>
      </li>
    </ul>
  </div>
  <div class="section memories-section" v-else>
    <div class="section-title">
      <slot name="icon" />
      {{ title }}
    </div>
    <div class="empty-row">{{ emptyText }}</div>
  </div>
</template>

<style scoped>
.section {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: bold;
  color: #9f9380;
  border-bottom: 1px solid rgba(175, 148, 105, 0.32);
  padding-bottom: 4px;
  margin-bottom: 4px;
  letter-spacing: 0.02em;
}

.empty-row {
  padding: 6px 8px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.03);
  color: #777;
  font-size: 12px;
}

.memories-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
  list-style: none;
  margin: 0;
  padding: 0;
}

.memory-row {
  min-width: 0;
}

/* Full-row tap target, >=44px tall, no fixed width so it never forces
   horizontal overflow on a narrow viewport. */
.memory-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 100%;
  min-width: 0;
  min-height: 44px;
  padding: 8px 10px;
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.03);
  color: #ccc;
  text-align: left;
  cursor: pointer;
  font: inherit;
  transition: background 0.15s ease;
}

.memory-item:hover,
.memory-item:focus-visible {
  background: rgba(255, 255, 255, 0.07);
}

.memory-line {
  display: flex;
  align-items: baseline;
  gap: 6px;
  min-width: 0;
}

.memory-line--top {
  flex-wrap: wrap;
}

.memory-emoji {
  flex: 0 0 auto;
}

.memory-focus {
  flex: 1 1 auto;
  min-width: 0;
  font-size: 12px;
  font-weight: 600;
  color: #ddd;
  overflow-wrap: anywhere;
}

.memory-strength {
  flex: 0 0 auto;
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 999px;
  white-space: nowrap;
  background: rgba(255, 255, 255, 0.08);
  color: #aaa;
}

.memory-strength.is-strong {
  background: rgba(220, 80, 80, 0.22);
  color: #ff9a9a;
}

.memory-strength.is-moderate {
  background: rgba(220, 160, 60, 0.2);
  color: #e6c07b;
}

.memory-strength.is-weak {
  background: rgba(255, 255, 255, 0.08);
  color: #999;
}

.memory-summary {
  font-size: 12px;
  line-height: 1.5;
  color: #bbb;
  min-width: 0;
  overflow-wrap: anywhere;
  white-space: normal;
}

.memory-line--meta {
  font-size: 10px;
  color: #777;
  justify-content: space-between;
  flex-wrap: wrap;
}

.memory-date {
  overflow-wrap: anywhere;
}
</style>
