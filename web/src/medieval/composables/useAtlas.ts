import { computed, onMounted, onUnmounted, ref, watch, type Ref } from 'vue'
import { useElementSize } from '@vueuse/core'
import type { Application, Container } from 'pixi.js'
import { useObserverStore } from '../stores/world'
import { mapProjection } from '../mappers'

const terrainColors: Record<string, number> = { plain: 0x465244, grassland: 0x4b5b44, forest: 0x263e35,
  mountain: 0x666b65, water: 0x264b5d, sea: 0x183c51, desert: 0x837052, snow: 0xa9b5b0, swamp: 0x3b5046 }
export const governmentColors: Record<string, number> = { auren: 0xd7b979, valedouro: 0x72bcb1, escarlia: 0xb598d7 }
export function useAtlas(host: Ref<HTMLElement | null>) {
  const store = useObserverStore(), { width, height } = useElementSize(host)
  const layer = ref<'terrain' | 'political' | 'food'>('political')
  const showRoutes = ref(true), showSites = ref(true), unavailable = ref(false), zoom = ref(1)
  const projection = computed(() => store.snapshot ? mapProjection(store.snapshot.map) : null)
  let app: Application | null = null, root: Container | null = null, cancelled = false
  let panX = 0, panY = 0
  let pixi: typeof import('pixi.js') | null = null
  const cell = 40
  function transform() {
    const map = store.snapshot?.map
    if (!app || !root || !map || !width.value || !height.value) return
    app.renderer.resize(width.value, height.value)
    const scale = Math.min(width.value / (map.width * cell), height.value / (map.height * cell)) * zoom.value
    root.scale.set(scale)
    root.position.set((width.value - map.width * cell * scale) / 2 + panX, (height.value - map.height * cell * scale) / 2 + panY)
    app.render()
  }
  function fit() { zoom.value = 1; panX = 0; panY = 0; transform() }
  function zoomBy(value: number) { zoom.value = Math.max(1, Math.min(3, zoom.value + value)); transform() }
  function draw() {
    const snapshot = store.snapshot, p = projection.value
    if (!pixi || !root || !app || !snapshot || !p) return
    root.removeChildren().forEach(c => c.destroy())
    const ground = new pixi.Graphics(), lines = new pixi.Graphics(), markers = new pixi.Graphics()
    root.addChild(ground, lines, markers)
    const settlementByRegion = new Map(snapshot.society.settlements.map(s => [s.region_id, s]))
    for (const tile of p.cells) {
      const x = tile.x * cell, y = tile.y * cell, place = settlementByRegion.get(tile.regionId)
      ground.rect(x, y, cell, cell).fill(terrainColors[tile.terrain] ?? 0x465244)
      if (layer.value !== 'terrain' && tile.terrain !== 'water' && tile.terrain !== 'sea' && place) {
        const color = layer.value === 'food' ? (place.missing_food ? 0xd87965 : 0x8ab890) : (governmentColors[place.administrator_id ?? ''] ?? 0x9caba6)
        ground.rect(x, y, cell, cell).fill({ color, alpha: .2 })
      }
      if (tile.terrain === 'mountain') {
        ground.poly([x + 7,y + 32,x + 20,y + 9,x + 34,y + 32]).fill({ color: 0xb6b7a7, alpha: .3 })
        ground.moveTo(x + 20,y + 9).lineTo(x + 25,y + 28).stroke({ color: 0x303f3c, width: 1 })
      }
      if (tile.terrain === 'forest') for (const [dx,dy] of [[12,16],[29,27]]) ground.circle(x + dx,y + dy,6).fill({ color: 0x77966b, alpha: .3 })
      const rows = snapshot.map.region_rows
      if (tile.x === 0 || rows[tile.y][tile.x - 1] !== tile.regionId) lines.moveTo(x,y).lineTo(x,y + cell).stroke({ color: 0xdbc8a1, width: 1, alpha: .35 })
      if (tile.y === 0 || rows[tile.y - 1][tile.x] !== tile.regionId) lines.moveTo(x,y).lineTo(x + cell,y).stroke({ color: 0xdbc8a1, width: 1, alpha: .35 })
    }
    if (showRoutes.value) for (const route of p.routes) {
      lines.moveTo(route.from[0] * cell, route.from[1] * cell).lineTo(route.to[0] * cell, route.to[1] * cell)
        .stroke({ color: route.capacity <= 0 ? 0xe87969 : route.mode === 'river' ? 0x96d8e2 : 0xdacba4, width: route.mode === 'river' ? 3 : 2, alpha: .7 })
    }
    if (showSites.value) for (const site of snapshot.map.sites) {
      const [x,y] = site.cell_refs[0]
      markers.poly([(x+.5)*cell,(y+.3)*cell,(x+.7)*cell,(y+.5)*cell,(x+.5)*cell,(y+.7)*cell,(x+.3)*cell,(y+.5)*cell])
        .fill(site.enabled && site.integrity > 0 ? 0xaccec2 : 0xdb806f)
    }
    for (const s of snapshot.society.settlements) {
      const x = (s.center[0] + .5)*cell, y = (s.center[1] + .5)*cell
      const selected = store.selection?.kind === 'settlement' && store.selection.id === s.id
      markers.circle(x,y,selected ? 14 : 10).fill(0x182a27).stroke({ color: selected ? 0xffe4ae : governmentColors[s.administrator_id ?? ''] ?? 0xffffff, width: selected ? 3 : 2 })
      if (s.kind === 'city') markers.rect(x-4,y-5,8,10).fill(0xe8d9b8)
      else markers.circle(x,y,3).fill(0xe8d9b8)
      const label = new pixi.Text({ text: s.name, style: { fontFamily: 'Georgia', fontSize: 16, fill: 0xf8edda,
        stroke: { color: 0x172722, width: 4 }, fontWeight: selected ? 'bold' : 'normal' } })
      label.anchor.set(.5,0); label.position.set(x,y+18); root.addChild(label)
    }
    transform()
  }
  let drag: { x: number; y: number; moved: boolean } | null = null
  function down(e: PointerEvent) { if (e.button !== 0) return; drag = { x: e.clientX, y: e.clientY, moved: false }; host.value?.setPointerCapture(e.pointerId) }
  function move(e: PointerEvent) { if (!drag) return; const dx=e.clientX-drag.x,dy=e.clientY-drag.y
    if (Math.abs(dx)+Math.abs(dy)>3) drag.moved=true
    if (drag.moved) { panX+=dx;panY+=dy;transform() }; drag.x=e.clientX;drag.y=e.clientY }
  function up(e: PointerEvent) {
    if (drag && !drag.moved && root && host.value && store.snapshot) {
      const box=host.value.getBoundingClientRect(),x=Math.floor((e.clientX-box.left-root.x)/root.scale.x/cell),y=Math.floor((e.clientY-box.top-root.y)/root.scale.y/cell)
      const region=store.snapshot.map.region_rows[y]?.[x]
      const s=store.snapshot.society.settlements.find(s=>s.region_id===region)
      if(s) store.selection={kind:'settlement',id:s.id}
    }
    drag=null
  }
  onMounted(async () => {
    if (!('WebGLRenderingContext' in globalThis)) { unavailable.value=true; return }
    try {
      pixi = await import('pixi.js')
      if (cancelled) return
      const candidate = new pixi.Application()
      await candidate.init({ backgroundAlpha: 0, antialias: true, autoStart: false, resolution: Math.min(devicePixelRatio,2), autoDensity: true })
      if (cancelled) { candidate.destroy(true); return }
      app=candidate; root=new pixi.Container(); app.stage.addChild(root)
      host.value?.appendChild(app.canvas); app.canvas.setAttribute('aria-hidden','true')
      draw()
    } catch { unavailable.value=true }
  })
  watch([width,height,zoom],transform)
  watch([projection,layer,showRoutes,showSites,()=>store.selection],draw)
  onUnmounted(() => { cancelled=true; app?.destroy(true,{children:true});app=null;root=null })
  return { layer, showRoutes, showSites, unavailable, fit, zoomBy, down, move, up }
}
