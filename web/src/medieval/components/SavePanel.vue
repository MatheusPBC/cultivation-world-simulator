<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useSaves } from '../composables/useSaves'
import { calendar,formatNumber } from '../mappers'
const emit=defineEmits<{close:[]}>(),{t}=useI18n()
const {store,files,error,name,overwrite,confirmation,saved,container,refresh,save,load,keyboard}=useSaves(()=>emit('close'))
const setContainer=(element:unknown)=>{container.value=element as HTMLElement|null}
</script>
<template>
  <div class="modal-scrim"><section :ref="setContainer" class="save-panel panel" role="dialog" aria-modal="true" aria-labelledby="saves-title" @keydown="keyboard">
    <div class="section-heading"><h2 id="saves-title">{{t('saves')}}</h2><button data-testid="close-saves" :disabled="store.busy" @click="emit('close')">{{t('close')}}</button></div>
    <p v-if="error||store.error" role="alert" class="notice error">{{(error||store.error)?.message}}</p>
    <form v-if="store.snapshot" data-testid="save-world" @submit.prevent="save">
      <label>{{t('saveName')}}<input v-model="name" name="save_id" pattern="[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}" maxlength="64" required /></label><p class="muted">{{t('saveHelp')}}</p>
      <label v-if="files.some(f=>f.save_id===name)" class="check"><input v-model="overwrite" type="checkbox" required />{{t('overwrite')}}</label>
      <button class="primary" :disabled="store.busy">{{t('save')}}</button><span v-if="saved" role="status">{{t('saved')}}</span>
    </form>
    <div v-if="confirmation" class="load-confirm"><p>{{t('loadConfirm')}}</p><strong>{{confirmation.save_id}} · {{calendar(confirmation.day??0)}}</strong><div class="button-row"><button data-testid="confirm-load" :disabled="store.busy" class="primary" @click="load">{{t('confirmLoad')}}</button><button :disabled="store.busy" @click="confirmation=null">{{t('cancel')}}</button></div></div>
    <div class="section-heading"><h3>{{t('load')}}</h3><button :disabled="store.busy" @click="refresh">{{t('refresh')}}</button></div>
    <p v-if="!files.length" class="muted">{{t('noSaves')}}</p>
    <div class="save-list"><article v-for="f in files" :key="f.save_id" class="save-row"><div><strong>{{f.save_id}}</strong><small>{{f.compatible?calendar(f.day??0):t('incompatible')}} · {{formatNumber(f.size_bytes/1024)}} KB</small></div><button :data-load="f.save_id" :disabled="!f.compatible||store.busy||store.status?.paused===false" @click="confirmation=f">{{t('load')}}</button></article></div>
  </section></div>
</template>
