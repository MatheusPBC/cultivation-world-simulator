/**
 * "Tinta e Jade" — the Pixi half of the design system.
 *
 * Mirrors `@/styles/tokens.css` as numeric literals so the map and the HUD share
 * one palette. Change both together.
 *
 * The map is read as a survey drawing: terrain is *ground* (low contrast, tinted
 * into one tonal family), and structure — coast, borders, routes, sites, powers,
 * names — is *figure*, drawn with ink weights on top of it.
 */

export const MAP_INK = Object.freeze({
  void: 0x08090a,
  deep: 0x0b0e0d,
  base: 0x151a18,
  raised: 0x1a201e,
})

export const MAP_PAPER = Object.freeze({
  100: 0xf2ece0,
  200: 0xded7c8,
  300: 0xcdc6b6,
  500: 0x9d968a,
})

export const MAP_GOLD = Object.freeze({
  200: 0xf3e3bd,
  300: 0xecd6a4,
  400: 0xd9b877,
  600: 0x8a6f3c,
})

export const MAP_JADE = Object.freeze({
  300: 0x9ccfc1,
  400: 0x6fb3a3,
  600: 0x2f6d63,
})

export const MAP_CINNABAR = Object.freeze({
  300: 0xd9765e,
  400: 0xc0553f,
})

/**
 * Multiplicative tints applied per terrain sprite.
 *
 * The tile art is deliberately saturated pixel art; multiplying it by a
 * desaturated hue of the same family keeps every biome distinguishable while
 * collapsing the whole terrain layer into one tonal range, so it stops
 * competing with labels, routes and characters. No art asset is modified.
 */
export const TERRAIN_TINT: Record<string, number> = Object.freeze({
  PLAIN: 0xb9bda2,
  GRASSLAND: 0xa8b795,
  FARM: 0xc4bc90,
  FOREST: 0x7f9a84,
  RAINFOREST: 0x6e8f7a,
  BAMBOO: 0x9fb58e,
  SWAMP: 0x8a9184,
  DESERT: 0xc9b48d,
  GOBI: 0xbdae93,
  MOUNTAIN: 0x9a9a95,
  SNOW_MOUNTAIN: 0xd2d8da,
  GLACIER: 0xc6d3d8,
  TUNDRA: 0xb0b6ac,
  VOLCANO: 0xa8836f,
  ISLAND: 0xb3bda4,
  CITY: 0xc3b699,
  SECT: 0xb6b0a4,
})

/** Fallback tint for terrain kinds a future preset may add. */
export const TERRAIN_TINT_DEFAULT = 0xb2b4a6

export const WATER_TINT = Object.freeze({
  sea: 0x5f8f92,
  water: 0x7fb0ac,
})

/**
 * Opacity of the per-cell colour wash laid over the tinted tile art.
 *
 * The tint alone only darkens: multiplying a violet swamp tile by a grey-green
 * keeps it violet. Compositing the biome's target colour on top at this alpha
 * pulls the hue itself into the palette while the pixel detail still reads
 * through the remaining transparency.
 */
export const TERRAIN_WASH_ALPHA = 0.46

export const MAP_SURFACE = Object.freeze({
  /** Ink veil laid over terrain to push it into the background. */
  veilColor: MAP_INK.deep,
  veilAlpha: 0.24,
  /** Edge vignette: keeps the eye inside the surveyed world. */
  vignetteColor: MAP_INK.void,
  vignetteAlpha: 0.5,
  vignetteBands: 7,
  /** Depth of the vignette as a fraction of the shorter map axis. */
  vignetteDepth: 0.085,
})

export const MAP_COAST = Object.freeze({
  /** Dark casing under the shore, so the landmass reads as a drawn outline. */
  casingColor: 0x121a1c,
  casingWidth: 5,
  casingAlpha: 0.5,
  inkColor: MAP_PAPER[200],
  inkWidth: 1.75,
  inkAlpha: 0.5,
})

export const MAP_BORDER = Object.freeze({
  casingColor: 0x0f1412,
  casingWidth: 3.5,
  casingAlpha: 0.34,
  inkColor: MAP_PAPER[300],
  inkWidth: 1.25,
  inkAlpha: 0.34,
})

export const MAP_ROUTE = Object.freeze({
  casingColor: 0x101614,
  casingAlpha: 0.55,
  /** Overland trade road. */
  landColor: MAP_GOLD[400],
  /** Ferry / river crossing. */
  waterColor: MAP_JADE[400],
  /** Disabled or fully choked. */
  severedColor: MAP_CINNABAR[400],
  /** Route width in world px, before the capacity term. */
  minWidth: 2.5,
  maxWidthBonus: 3.5,
  nodeRadius: 5,
  /** Dash geometry for water modes and severed routes. */
  dashLength: 26,
  dashGap: 16,
})

export const MAP_WATER_BODY = Object.freeze({
  /** Flow traces are the only water-body decoration: sparse, jade, thin. */
  flowColor: MAP_JADE[300],
  flowAlpha: 0.5,
  flowWidth: 2,
  /** Draw a trace every Nth cell so rivers read as current, not as fill. */
  flowSampleStride: 5,
  flowLength: 16,
})

export const MAP_SELECTION = Object.freeze({
  hoverFill: MAP_PAPER[100],
  hoverFillAlpha: 0.07,
  hoverStrokeColor: MAP_PAPER[200],
  hoverStrokeAlpha: 0.55,
  hoverStrokeWidth: 2,
  selectedFill: MAP_GOLD[400],
  selectedFillAlpha: 0.13,
  selectedStrokeColor: MAP_GOLD[200],
  selectedStrokeAlpha: 0.95,
  selectedStrokeWidth: 3,
  selectedCasingColor: 0x0f1412,
  selectedCasingWidth: 6.5,
  selectedCasingAlpha: 0.55,
})

export const MAP_SITE = Object.freeze({
  /** Sites are engraved survey marks, not colored pins. */
  casingColor: 0x0f1412,
  plateColor: MAP_INK.base,
  markColor: MAP_PAPER[200],
  activeAccent: MAP_JADE[300],
  impairedAccent: MAP_GOLD[300],
  destroyedAccent: MAP_CINNABAR[300],
  radius: 11,
})

export const MAP_SECT = Object.freeze({
  /**
   * Sect territory keeps the organization's own color — that is canonical
   * identity — but at a fraction of its former weight, expressed as a hatch
   * plus a thin double border rather than a flat 38%-alpha slab.
   */
  fillAlpha: 0.14,
  hatchAlpha: 0.2,
  hatchSpacing: 14,
  hatchWidth: 2,
  casingColor: 0x0f1412,
  casingWidth: 4,
  casingAlpha: 0.42,
  borderWidth: 1.75,
  borderAlpha: 0.85,
  /** How far the sect color is mixed toward paper for the border. */
  borderLift: 0.45,
})

/**
 * Label tiers, keyed by the canonical `RegionSummary.type` taxonomy the map
 * query actually returns (`city`, `sect`, `normal`, `cultivate`).
 *
 * `screenSize` is the on-screen size in CSS px. Labels are counter-scaled
 * against the viewport zoom so they stay at this size at every zoom level —
 * that is what makes them legible at fit-zoom, where the old fixed world-space
 * sizes collapsed to ~15px.
 *
 * `minScale` is the viewport zoom below which the tier is hidden. Progressive
 * disclosure keeps the fit-zoom view readable instead of drawing all 44 names
 * at once.
 */
export type MapLabelTierName = 'settlement' | 'power' | 'territory' | 'site'

export interface MapLabelTier {
  tier: MapLabelTierName
  /** Higher wins a collision and is drawn first. */
  priority: number
  screenSize: number
  fontWeight: 'normal' | 'bold'
  fontFamily: string
  fontStyle: 'normal' | 'italic'
  letterSpacing: number
  fill: number
  alpha: number
  /** Dark plate behind the text; territory names rely on tracking instead. */
  plate: boolean
  minScale: number
  /** Latin wrap target in characters. */
  wrapTarget: number
}

const DISPLAY_SERIF =
  '"Songti SC", "Source Han Serif SC", "Noto Serif CJK SC", "Noto Serif", Georgia, "Times New Roman", serif'
const UI_SANS =
  '"HarmonyOS Sans", "PingFang SC", "Noto Sans CJK SC", system-ui, -apple-system, "Segoe UI", sans-serif'

export const MAP_LABEL_TIERS: Record<MapLabelTierName, MapLabelTier> = Object.freeze({
  /** Cities: the settled world. Loudest, always visible. */
  settlement: Object.freeze({
    tier: 'settlement',
    priority: 4,
    screenSize: 15,
    fontWeight: 'bold',
    fontFamily: DISPLAY_SERIF,
    fontStyle: 'normal',
    letterSpacing: 1,
    fill: MAP_PAPER[100],
    alpha: 1,
    plate: true,
    minScale: 0,
    wrapTarget: 15,
  }),
  /** Sects: the powers. Gold, because a sect seat is a locus of player focus. */
  power: Object.freeze({
    tier: 'power',
    priority: 3,
    screenSize: 13,
    fontWeight: 'bold',
    fontFamily: DISPLAY_SERIF,
    fontStyle: 'normal',
    letterSpacing: 0.5,
    fill: MAP_GOLD[300],
    alpha: 1,
    plate: true,
    minScale: 0,
    wrapTarget: 16,
  }),
  /** Wilderness territory: wide-tracked and quiet, the way region names read on a survey sheet. */
  territory: Object.freeze({
    tier: 'territory',
    priority: 2,
    screenSize: 11.5,
    fontWeight: 'normal',
    fontFamily: UI_SANS,
    fontStyle: 'normal',
    letterSpacing: 3.4,
    fill: MAP_PAPER[300],
    alpha: 0.82,
    plate: false,
    minScale: 0.42,
    wrapTarget: 18,
  }),
  /** Cultivation caves and ruins: opportunities. Smallest, revealed on zoom-in. */
  site: Object.freeze({
    tier: 'site',
    priority: 1,
    screenSize: 11,
    fontWeight: 'normal',
    fontFamily: UI_SANS,
    fontStyle: 'italic',
    letterSpacing: 0.4,
    fill: MAP_JADE[300],
    alpha: 0.95,
    plate: true,
    minScale: 0.62,
    wrapTarget: 16,
  }),
})

/** Canonical region type -> label tier. */
export const REGION_TYPE_TIER: Record<string, MapLabelTierName> = Object.freeze({
  city: 'settlement',
  sect: 'power',
  normal: 'territory',
  cultivate: 'site',
})

export function resolveLabelTier(regionType: string): MapLabelTier {
  return MAP_LABEL_TIERS[REGION_TYPE_TIER[regionType] ?? 'territory']
}

export const MAP_LABEL_PLATE = Object.freeze({
  color: MAP_INK.deep,
  alpha: 0.68,
  paddingX: 7,
  paddingY: 3,
  radius: 2,
})

/**
 * Text is rasterized at `screenSize * TEXT_RESOLUTION` device px so that
 * counter-scaling never upsamples a small glyph texture.
 */
export const MAP_LABEL_TEXT_RESOLUTION = 3

/** Bounds for the label counter-scale, so labels never vanish or overwhelm. */
export const MAP_LABEL_SCALE_CLAMP = Object.freeze({ min: 0.55, max: 6 })
