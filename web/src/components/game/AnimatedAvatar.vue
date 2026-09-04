<script setup lang="ts">
import { useTextures } from './composables/useTextures'
import { ref, watch, computed } from 'vue'
import { Graphics, Rectangle, type TextStyle } from 'pixi.js'
import type { AvatarSummary } from '../../types/core'
import { useSharedTicker } from './composables/useSharedTicker'
import { useAudio } from '../../composables/useAudio'
import { useUiStore } from '../../stores/ui'
import { useMapViewport } from './composables/useMapViewport'
import { MAP_GOLD, MAP_INK, MAP_PAPER } from '../../constants/mapTheme'

const props = defineProps<{
  avatar: AvatarSummary
  tileSize: number
  offset?: { x: number; y: number }
}>()

const emit = defineEmits<{
  (e: 'select', payload: { type: 'avatar'; id: string; name?: string }): void
}>()

const { availableAvatars, ensureAvatarTexture } = useTextures()
const uiStore = useUiStore()
const { scale: viewportScale } = useMapViewport()

const isSelected = computed(() => (
  uiStore.selectedTarget?.type === 'avatar' && uiStore.selectedTarget.id === props.avatar.id
))
const isEmphasized = computed(() => isHovered.value || isSelected.value)

// Target position (grid coordinates)
const targetX = ref(props.avatar.x)
const targetY = ref(props.avatar.y)

// Current render position (pixel coordinates)
// Initial position includes offset immediately to avoid "jumping" on spawn if possible,
// but props.offset might be undefined initially.
const initialOffsetX = props.offset?.x ?? 0
const initialOffsetY = props.offset?.y ?? 0
const currentX = ref((props.avatar.x + initialOffsetX) * props.tileSize + props.tileSize / 2)
const currentY = ref((props.avatar.y + initialOffsetY) * props.tileSize + props.tileSize / 2)
const isHovered = ref(false)

// Watch for prop updates (server ticks)
watch(() => [props.avatar.x, props.avatar.y], ([newX, newY]) => {
    targetX.value = newX
    targetY.value = newY
})

useSharedTicker((delta) => {
    const offsetX = props.offset?.x ?? 0
    const offsetY = props.offset?.y ?? 0
    
    const destX = (targetX.value + offsetX) * props.tileSize + props.tileSize / 2
    const destY = (targetY.value + offsetY) * props.tileSize + props.tileSize / 2
    
    const speed = 0.1 * delta
    
    if (Math.abs(destX - currentX.value) > 1) {
        currentX.value += (destX - currentX.value) * speed
    } else {
        currentX.value = destX
    }
    
    if (Math.abs(destY - currentY.value) > 1) {
        currentY.value += (destY - currentY.value) * speed
    } else {
        currentY.value = destY
    }
    
    // Emoji bobbing animation
    emojiTime += delta * 0.05
    emojiBob.value = Math.sin(emojiTime) * 5
})

let emojiTime = 0
const emojiBob = ref(0)

function getTexture() {
  const gender = (props.avatar.gender || 'male').toLowerCase()
  let pid = props.avatar.pic_id
  
  // Fallback logic if pic_id is missing
  if (!pid) {
     const raceKey = String(props.avatar.race || 'human').toLowerCase()
     const library = availableAvatars.value[raceKey] || availableAvatars.value.human
     const list = library?.[gender === 'female' ? 'female' : 'male']
     if (list && list.length > 0) {
         let hash = 0
         const str = props.avatar.id || props.avatar.name || 'default'
         for (let i = 0; i < str.length; i++) {
            hash = str.charCodeAt(i) + ((hash << 5) - hash)
         }
         pid = list[Math.abs(hash) % list.length]
     } else {
         pid = 1
     }
  }

  return ensureAvatarTexture(gender, pid, props.avatar.realm, props.avatar.race)
}

function getScale() {
  const tex = getTexture()
  if (!tex) return 1
  return (props.tileSize * 4.2) / Math.max(tex.width, tex.height)
}

function getAvatarSpriteScale() {
  return getScale() * (isEmphasized.value ? 1.05 : 1)
}

const drawFallback = (g: Graphics) => {
    g.clear()
    const radius = props.tileSize * (isEmphasized.value ? 0.56 : 0.5)
    g.circle(0, 0, radius)
    g.fill({ color: props.avatar.gender === 'female' ? 0xffaaaa : 0xaaaaff })
    g.stroke({ width: isEmphasized.value ? 4 : 2, color: isEmphasized.value ? MAP_GOLD[300] : MAP_INK.void })
}

/*
 * Character names sit on the same plate system as map labels, in paper rather
 * than a per-avatar hue: eleven differently-coloured 56px names with a 4px
 * black outline were the noisiest layer on the map, and the colour carried no
 * meaning a player could read.
 */
const NAME_FONT_SIZE = 34
/** On-screen size the name is held at, independent of zoom. */
const NAME_TARGET_SCREEN_SIZE = 12

/*
 * Same counter-scale as the region labels: the glyph texture is rasterized
 * large and scaled down, so the name stays readable at fit-zoom without
 * becoming a billboard when the player zooms in.
 */
const nameScale = computed(() => {
  const scale = viewportScale.value
  if (!Number.isFinite(scale) || scale <= 0) return 1
  return Math.min(1, Math.max(0.25, NAME_TARGET_SCREEN_SIZE / (NAME_FONT_SIZE * scale)))
})

const nameStyle = computed<TextStyle>(() => ({
    fontFamily: '"HarmonyOS Sans", "PingFang SC", "Noto Sans CJK SC", system-ui, sans-serif',
    fontSize: NAME_FONT_SIZE,
    fontWeight: isEmphasized.value ? 'bold' : 'normal',
    fill: isSelected.value ? MAP_GOLD[200] : MAP_PAPER[100],
    align: 'center',
    letterSpacing: 0.5,
}))

const drawNamePlate = (g: Graphics) => {
    g.clear()
    const label = props.avatar.name ?? ''
    if (!label) return
    // Rough advance width; the plate only has to sit behind the glyphs.
    const width = label.length * NAME_FONT_SIZE * 0.72 + 16
    const height = NAME_FONT_SIZE * 1.34
    g.roundRect(-width / 2, 0, width, height, 3)
      .fill({ color: MAP_INK.deep, alpha: isEmphasized.value ? 0.86 : 0.7 })
    if (isSelected.value) {
        g.roundRect(-width / 2, 0, width, height, 3)
          .stroke({ width: 1.5, color: MAP_GOLD[400], alpha: 0.9 })
    }
}

/**
 * Contact shadow and footing ring. Without a base the portraits read as
 * stickers pasted onto the terrain rather than figures standing at a place.
 */
const drawGroundAnchor = (g: Graphics) => {
    g.clear()
    const radiusX = props.tileSize * 0.58
    const radiusY = props.tileSize * 0.2
    g.ellipse(0, 0, radiusX, radiusY).fill({ color: MAP_INK.void, alpha: 0.42 })
    if (isSelected.value) {
        g.ellipse(0, 0, radiusX * 1.35, radiusY * 1.35)
          .stroke({ width: 3, color: MAP_GOLD[300], alpha: 0.95 })
        g.ellipse(0, 0, radiusX * 1.35, radiusY * 1.35)
          .fill({ color: MAP_GOLD[400], alpha: 0.12 })
    }
}

const hoverRingAlpha = computed(() => isHovered.value && !isSelected.value ? 0.72 : 0)
const hoverRingScale = computed(() => isHovered.value ? 1.04 : 0.92)
const interactionHitArea = computed(() =>
    new Rectangle(
        -props.tileSize * 1.35,
        -props.tileSize * 3.9,
        props.tileSize * 2.7,
        props.tileSize * 4.55,
    ),
)

const drawHoverRing = (g: Graphics) => {
    g.clear()
    if (!isHovered.value || isSelected.value) return
    const radiusX = props.tileSize * 0.82
    const radiusY = props.tileSize * 0.34
    g.ellipse(0, 0, radiusX, radiusY)
    g.fill({ color: MAP_PAPER[200], alpha: 0.1 })
    g.stroke({ width: 2.5, color: MAP_PAPER[100], alpha: 0.7 })
}

function handlePointerTap() {
    useAudio().play('select')
    emit('select', {
        type: 'avatar',
        id: props.avatar.id,
        name: props.avatar.name
    })
}

const emojiStyle: TextStyle = {
    fontFamily: '"Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji", sans-serif',
    fontSize: 70,
    align: 'center',
}

const drawEmojiBg = (g: Graphics) => {
    g.clear()
    
    const w = 80
    const h = 80
    const r = 16
    const halfW = w / 2
    const halfH = h / 2
    
    // 1. Draw all fills first (to cover background)
    g.beginPath()
    g.roundRect(-halfW, -halfH, w, h, r)
    g.fill({ color: 0xffffff, alpha: 1.0 })
    
    // Tail fill
    g.beginPath()
    g.moveTo(-halfW + 10, halfH)     // Start at bottom-left area of body
    g.lineTo(-halfW - 10, halfH + 20) // Point pointing down-left
    g.lineTo(-halfW, halfH - 10)      // Back to left edge of body
    g.closePath()
    g.fill({ color: 0xffffff, alpha: 1.0 })

    // 2. Draw Strokes (Outlines)
    // We draw the bubble body stroke
    g.roundRect(-halfW, -halfH, w, h, r)
    g.stroke({ width: 3, color: 0x000000, alpha: 1.0 })
    
    // We draw the tail stroke
    g.beginPath()
    g.moveTo(-halfW + 10, halfH)
    g.lineTo(-halfW - 10, halfH + 20)
    g.lineTo(-halfW, halfH - 10)
    g.stroke({ width: 3, color: 0x000000, alpha: 1.0 })

    // 3. Clean up the intersection with a white patch
    // We fill a small polygon over the line where tail meets body
    g.beginPath()
    g.moveTo(-halfW + 8, halfH - 2)   // Inside body, near bottom
    g.lineTo(-halfW - 2, halfH - 12)  // Inside body, near left
    g.lineTo(-halfW - 8, halfH + 16)  // Towards tail tip (but not all the way)
    g.lineTo(-halfW + 8, halfH + 2)   // Towards tail base
    g.closePath()
    g.fill({ color: 0xffffff, alpha: 1.0 })
}
</script>

<template>
  <container 
    :x="currentX" 
    :y="currentY" 
    :z-index="Math.floor(currentY)"
    :alpha="isEmphasized ? 1 : 0.94"
    :hitArea="interactionHitArea"
    event-mode="static"
    cursor="pointer"
    @pointerenter="isHovered = true"
    @pointerover="isHovered = true"
    @pointermove="isHovered = true"
    @mouseenter="isHovered = true"
    @mouseover="isHovered = true"
    @pointerleave="isHovered = false"
    @pointerout="isHovered = false"
    @mouseleave="isHovered = false"
    @mouseout="isHovered = false"
    @pointertap="handlePointerTap"
  >
    <graphics
      :key="`${avatar.id}-ground-${isSelected ? 'sel' : 'base'}`"
      :y="tileSize * 0.18"
      event-mode="none"
      @effect="drawGroundAnchor"
    />

    <graphics
      v-if="isHovered && !isSelected"
      :key="`${avatar.id}-hover-ring`"
      :y="tileSize * 0.18"
      :alpha="hoverRingAlpha"
      :scale="hoverRingScale"
      event-mode="none"
      @effect="drawHoverRing"
    />

    <sprite
      v-if="getTexture()"
      :key="`${avatar.id}-${isEmphasized ? 'hover' : 'normal'}`"
      :texture="getTexture()"
      :anchor-x="0.5"
      :anchor-y="0.9" 
      :scale="getAvatarSpriteScale()"
      event-mode="none"
    />
    
    <graphics
      v-else
      :key="`${avatar.id}-${isHovered ? 'hover-fallback' : 'normal-fallback'}`"
      event-mode="none"
      @effect="drawFallback"
    />

    <!-- Emoji Bubble -->
    <container
      v-if="avatar.action_emoji"
      :x="tileSize * 0.6"
      :y="(getTexture() ? -tileSize * 3.5 : -tileSize * 1.2) + emojiBob"
      :z-index="100"
      event-mode="none"
    >
        <graphics event-mode="none" @effect="drawEmojiBg" />
        <text
            :text="avatar.action_emoji"
            :style="emojiStyle"
            :anchor="0.5"
            :scale="1.0"
            event-mode="none"
        />
    </container>

    <container :y="isEmphasized ? 6 : 10" :scale="nameScale" event-mode="none">
      <graphics
        :key="`${avatar.id}-name-plate-${isSelected ? 'sel' : isHovered ? 'hover' : 'base'}`"
        event-mode="none"
        @effect="drawNamePlate"
      />
      <text
        :key="`${avatar.id}-name-${isSelected ? 'sel' : isHovered ? 'hover' : 'base'}`"
        :text="avatar.name"
        :style="nameStyle"
        :anchor-x="0.5"
        :anchor-y="0"
        :y="4"
        event-mode="none"
      />
    </container>
  </container>
</template>
