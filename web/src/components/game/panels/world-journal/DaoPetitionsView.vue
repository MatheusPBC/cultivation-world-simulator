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
        <p v-if="petition.response_content" class="response"><span>{{ t('game.world_journal.dao.response') }}</span>{{ petition.response_content }}</p>
        <p v-if="petition.favor_expires_month" class="favor-expiry">{{ t('game.world_journal.dao.favor_until', { month: petition.favor_expires_month }) }}</p>
        <button v-if="petition.response_event_id" class="why" type="button" @click="emit('why', petition.response_event_id)">{{ t('game.world_journal.dao.response_why') }}</button>
      </article>
    </section>
  </section>
</template>

<style scoped>
.dao-view{--ink:#eee7d8;--muted:#aca493;--line:#39342b;--gold:#c8a96a;--jade:#78cbb1;padding:24px;color:var(--ink);background:#121211}.dao-view header{padding-bottom:18px;border-bottom:1px solid var(--line)}header span,.petition-meta{color:var(--gold);font-size:11px;letter-spacing:.09em;text-transform:uppercase}h3{margin:7px 0;font-size:25px}h4{margin:0;color:var(--ink);font-size:15px}header p,.petition p{color:var(--muted);line-height:1.55}.petition{padding:20px 0;border-bottom:1px solid var(--line)}.history{margin-top:28px;padding-top:20px;border-top:1px solid var(--line)}.history-item{padding:15px 0}.response{margin-top:12px!important;padding-left:12px;border-left:2px solid var(--jade);color:var(--ink)!important}.response span{display:block;margin-bottom:4px;color:var(--jade);font-size:11px;letter-spacing:.08em;text-transform:uppercase}.favor-expiry{margin:10px 0 0;color:var(--gold)!important;font-size:13px}.actions{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.actions button,.why{min-height:44px;border:1px solid var(--line);background:#1b1916;color:var(--ink);font:inherit;cursor:pointer}.actions .favor{border-color:var(--gold);color:var(--gold)}.why{margin-top:10px;border:0;color:var(--jade);text-align:left}.state{padding:32px 0;color:var(--muted)}button:focus-visible{outline:2px solid var(--gold);outline-offset:2px}@media(max-width:600px){.dao-view{padding:16px}.actions{grid-template-columns:1fr}.actions button{min-height:48px}}
</style>
