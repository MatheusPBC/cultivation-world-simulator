import { computed, ref, shallowRef } from 'vue'
import type { Viewport } from 'pixi-viewport'

/**
 * Shared handle on the Pixi viewport.
 *
 * The zoom level is real interface state: label level-of-detail, the zoom
 * readout and the zoom buttons all need it, and previously the only way to
 * reach the viewport was a `window.__viewport` global. This keeps one reactive
 * source instead.
 *
 * The Pixi instance itself is held in a `shallowRef` so it never enters Vue's
 * deep reactive proxy.
 */

const viewportRef = shallowRef<Viewport | null>(null)
const scale = ref(1)
const fitScale = ref(1)

/** Zoom ceiling. Beyond this the pixel tiles break down into mush. */
const MAX_SCALE = 3
/** Multiplier applied per zoom-button press. */
const ZOOM_STEP = 1.45

export function useMapViewport() {
  function register(viewport: Viewport | null) {
    viewportRef.value = viewport
    if (viewport) syncScale()
  }

  function syncScale() {
    const viewport = viewportRef.value
    if (!viewport) return
    scale.value = viewport.scaled
  }

  function setFitScale(value: number) {
    if (Number.isFinite(value) && value > 0) fitScale.value = value
  }

  function zoomBy(factor: number) {
    const viewport = viewportRef.value
    if (!viewport) return
    const next = Math.min(MAX_SCALE, Math.max(fitScale.value, viewport.scaled * factor))
    viewport.setZoom(next, true)
    syncScale()
  }

  function zoomIn() {
    zoomBy(ZOOM_STEP)
  }

  function zoomOut() {
    zoomBy(1 / ZOOM_STEP)
  }

  /** Reset to the zoom that shows the whole world, recentred. */
  function fit() {
    const viewport = viewportRef.value
    if (!viewport) return
    viewport.setZoom(fitScale.value, true)
    viewport.moveCenter(viewport.worldWidth / 2, viewport.worldHeight / 2)
    syncScale()
  }

  /** Centre the view on a world-space point without changing zoom. */
  function centerOn(x: number, y: number) {
    const viewport = viewportRef.value
    if (!viewport) return
    viewport.animate({ position: { x, y }, time: 240 })
  }

  const canZoomIn = computed(() => scale.value < MAX_SCALE - 1e-4)
  const canZoomOut = computed(() => scale.value > fitScale.value + 1e-4)

  /**
   * Zoom expressed against the fit-the-world baseline, so "100%" means "the
   * whole world is on screen" rather than an arbitrary pixel ratio.
   */
  const zoomPercent = computed(() => {
    if (fitScale.value <= 0) return 100
    return Math.round((scale.value / fitScale.value) * 100)
  })

  return {
    viewport: viewportRef,
    scale,
    fitScale,
    maxScale: MAX_SCALE,
    register,
    syncScale,
    setFitScale,
    zoomIn,
    zoomOut,
    zoomBy,
    fit,
    centerOn,
    canZoomIn,
    canZoomOut,
    zoomPercent,
  }
}
