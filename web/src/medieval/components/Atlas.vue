<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useObserverStore } from '../stores/world'
import { useAtlas } from '../composables/useAtlas'
const { t }=useI18n(), store=useObserverStore(), host=ref<HTMLElement|null>(null)
const {layer,showRoutes,showSites,unavailable,fit,zoomBy,down,move,up}=useAtlas(host)
</script>
<template>
  <section class="atlas" :aria-label="t('map')">
    <div class="map-toolbar">
      <div class="segmented"><button v-for="key in (['political','terrain','food'] as const)" :key="key" :aria-pressed="layer===key" @click="layer=key">{{ t(key) }}</button></div>
      <label class="check"><input v-model="showRoutes" type="checkbox" />{{t('routes')}}</label>
      <label class="check"><input v-model="showSites" type="checkbox" />{{t('sites')}}</label>
    </div>
    <div ref="host" class="map-canvas" @pointerdown="down" @pointermove="move" @pointerup="up" @pointercancel="up">
      <p v-if="unavailable" role="status" class="map-fallback">{{t('mapUnavailable')}}</p>
    </div>
    <div class="map-bottom"><span>{{t('topology')}}</span><div class="zoom-controls"><button :aria-label="t('zoomOut')" @click="zoomBy(-.25)">−</button><button @click="fit">{{t('fit')}}</button><button :aria-label="t('zoomIn')" @click="zoomBy(.25)">+</button></div></div>
    <div class="legend"><span class="auren">Auren</span><span class="valedouro">Valedouro</span><span class="escarlia">Escárlia</span></div>
  </section>
  <nav class="settlement-list" :aria-label="t('settlements')"><button v-for="s in store.snapshot!.society.settlements" :key="s.id" :data-settlement="s.id" :aria-pressed="store.selection?.id===s.id" @click="store.selection={kind:'settlement',id:s.id}">{{s.name}}<span v-if="s.missing_food" class="shortage-mark"> · {{t('missing')}}</span></button></nav>
</template>
