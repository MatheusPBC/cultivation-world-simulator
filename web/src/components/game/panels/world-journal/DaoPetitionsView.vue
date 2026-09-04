<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { DaoPetitionsResponseDTO } from '@/types/api'

defineProps<{ petitions: DaoPetitionsResponseDTO | null; loading: boolean; error: boolean; respondingId: string | null }>()
const emit = defineEmits<{ retry: []; answer: [id: string, response: 'silence' | 'sign' | 'favor']; why: [eventId: string] }>()
const { t } = useI18n()

function traditionLabel(tradition: string): string {
  return t(`game.info_panel.region.dao_traditions.${tradition}`)
}

function initiatorLabel(kind: string): string {
  return t(`game.world_journal.dao.initiator.${kind}`)
}

function statusLabel(status: string): string {
  return t(`game.world_journal.dao.status.${status}`)
}
</script>

<template>
  <section class="dao-view" data-testid="dao-petitions">
    <header><span>{{ t('game.world_journal.dao.eyebrow') }}</span><h3>{{ t('game.world_journal.dao.title') }}</h3><p>{{ t('game.world_journal.dao.description') }}</p></header>
    <p v-if="loading" class="state">{{ t('game.world_journal.dao.loading') }}</p>
    <p v-else-if="error" class="state"><button type="button" @click="emit('retry')">{{ t('game.world_journal.dao.retry') }}</button></p>
    <p v-else-if="!petitions?.pending.length && !petitions?.history.length" class="state">{{ t('game.world_journal.dao.empty') }}</p>
    <div v-if="petitions?.pending.length" class="pending-list">
      <article v-for="petition in petitions.pending" :key="petition.id" class="petition">
        <div class="petition-meta">{{ traditionLabel(petition.tradition) }} · {{ initiatorLabel(petition.initiator_kind) }}<template v-if="petition.initiator_name"> · {{ petition.initiator_name }}</template></div>
        <p>{{ petition.content }}</p>
        <p class="rite-evidence">{{ t('game.world_journal.dao.rite_evidence', { count: petition.rite_event_ids.length }) }}</p>
        <div class="actions">
          <button type="button" :disabled="respondingId === petition.id" @click="emit('answer', petition.id, 'silence')">{{ t('game.world_journal.dao.silence') }}</button>
          <button type="button" :disabled="respondingId === petition.id" @click="emit('answer', petition.id, 'sign')">{{ t('game.world_journal.dao.sign') }}</button>
          <button class="favor" type="button" :disabled="respondingId === petition.id" @click="emit('answer', petition.id, 'favor')">{{ t('game.world_journal.dao.favor') }}</button>
        </div>
        <button v-if="petition.motivated_event_ids[0]" class="why" type="button" @click="emit('why', petition.motivated_event_ids[0])">{{ t('game.world_journal.why_button') }}</button>
      </article>
    </div>
    <section v-if="petitions?.history.length" class="history" data-testid="dao-petition-history">
      <h4>{{ t('game.world_journal.dao.history') }}</h4>
      <article v-for="petition in petitions.history" :key="petition.id" class="petition history-item">
        <div class="petition-meta">{{ statusLabel(petition.status) }} · {{ traditionLabel(petition.tradition) }} · {{ initiatorLabel(petition.initiator_kind) }}<template v-if="petition.initiator_name"> · {{ petition.initiator_name }}</template></div>
        <p>{{ petition.content }}</p>
        <p class="rite-evidence">{{ t('game.world_journal.dao.rite_evidence', { count: petition.rite_event_ids.length }) }}</p>
        <p v-if="petition.response_content" class="response"><span>{{ t('game.world_journal.dao.response') }}</span>{{ petition.response_content }}</p>
        <p v-if="petition.favor_expires_month" class="favor-expiry">{{ t('game.world_journal.dao.favor_until', { month: petition.favor_expires_month }) }}</p>
        <button v-if="petition.response_event_id" class="why" type="button" @click="emit('why', petition.response_event_id)">{{ t('game.world_journal.dao.response_why') }}</button>
      </article>
    </section>
  </section>
</template>

<style scoped>
/*
 * Dao petitions: an audience record. Already editorial in shape, but it carried
 * its own five-value palette and a 25px title, which is oversized inside a
 * ~380px column. Now on the shared tokens at the panel's compact scale.
 */
.dao-view {
  padding: var(--s-6);
  color: var(--text-secondary);
  background: var(--surface-panel);
  font-family: var(--font-ui);
}

.dao-view header {
  padding-bottom: var(--s-5);
  border-bottom: 1px solid var(--rule);
}

/* Eyebrow and per-petition meta share one tracked, gold caption style. */
header span,
.petition-meta {
  color: var(--accent);
  font-size: 10px;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
}

h3 {
  margin: var(--s-3) 0;
  color: var(--text-primary);
  font-family: var(--font-display);
  font-size: 17px;
  font-weight: 400;
  line-height: 1.3;
}

h4 {
  margin: 0 0 var(--s-3);
  color: var(--text-muted);
  font-size: 10px;
  font-weight: 400;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
}

header p,
.petition p {
  color: var(--text-secondary);
  font-size: var(--t-md);
  line-height: 1.6;
}

.petition {
  padding: var(--s-6) 0;
  border-bottom: 1px solid var(--rule-soft);
}

.history {
  margin-top: var(--s-7);
  padding-top: var(--s-6);
  border-top: 1px solid var(--rule);
}

.history-item {
  padding: var(--s-5) 0;
}

/* Heaven's answer is a quotation from the world itself. */
.response {
  margin-top: var(--s-5) !important;
  padding-left: var(--s-5);
  border-left: 2px solid var(--jade-600);
  color: var(--text-primary) !important;
  font-family: var(--font-display);
}

.response span {
  display: block;
  margin-bottom: var(--s-1);
  color: var(--jade-300);
  font-family: var(--font-ui);
  font-size: 10px;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
}

.favor-expiry {
  margin: var(--s-4) 0 0;
  color: var(--accent-strong) !important;
  font-family: var(--font-numeric);
  font-size: var(--t-sm);
  font-variant-numeric: tabular-nums;
}

.rite-evidence {
  margin: var(--s-4) 0 !important;
  color: var(--jade-300) !important;
  font-family: var(--font-numeric);
  font-size: var(--t-xs);
  font-variant-numeric: tabular-nums;
}

/*
 * Three canonical responses. Silence and sign are equals; favor is the
 * committing choice, so it alone carries the gold.
 */
.actions {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--s-3);
}

.actions button,
.why {
  min-height: 36px;
  border: 1px solid var(--rule);
  border-radius: var(--r-1);
  background: transparent;
  color: var(--text-secondary);
  font: inherit;
  font-family: var(--font-ui);
  font-size: var(--t-sm);
  cursor: pointer;
  transition: color var(--motion-fast), background var(--motion-fast),
    border-color var(--motion-fast);
}

.actions button:hover:not(:disabled) {
  color: var(--text-primary);
  background: var(--surface-raised);
}

.actions button:disabled {
  color: var(--paper-700);
  cursor: not-allowed;
}

.actions .favor {
  border-color: var(--gold-600);
  color: var(--accent-strong);
}

.actions .favor:hover:not(:disabled) {
  background: var(--accent-wash);
  border-color: var(--accent);
}

.why {
  margin-top: var(--s-4);
  min-height: 28px;
  padding: 0 var(--s-3);
  border: 0;
  border-bottom: 1px solid var(--jade-600);
  border-radius: 0;
  color: var(--jade-300);
  font-size: var(--t-xs);
  text-align: left;
}

.why:hover {
  color: var(--paper-100);
  border-bottom-color: var(--jade-400);
}

.state {
  padding: var(--s-7) 0;
  color: var(--text-muted);
  font-size: var(--t-sm);
  font-style: italic;
}

button:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring);
}

@media (max-width: 600px) {
  .dao-view {
    padding: var(--s-6) var(--s-5);
  }

  .actions {
    grid-template-columns: 1fr;
  }

  .actions button,
  .why {
    min-height: 48px;
  }
}
</style>
