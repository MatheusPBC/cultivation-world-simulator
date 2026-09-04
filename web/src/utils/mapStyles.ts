import type { TextStyleOptions } from 'pixi.js';
import {
  MAP_LABEL_SCALE_CLAMP,
  MAP_LABEL_TEXT_RESOLUTION,
  resolveLabelTier,
  type MapLabelTier
} from '@/constants/mapTheme';

type RegionTextMetrics = {
  /** On-screen size in CSS px, held constant across zoom levels. */
  screenSize: number;
  /** World-space size the glyph texture is rasterized at. */
  fontSize: number;
  lineHeight: number;
  letterSpacing: number;
};

/**
 * Compact scripts (Chinese, Japanese) carry more meaning per glyph and need
 * less tracking, but a slightly larger optical size to stay legible.
 */
const COMPACT_SCRIPT_PATTERN = /[\u2e80-\u2fff\u3040-\u30ff\u3400-\u9fff\uf900-\ufaff]/u;
const LATIN_SCRIPT_PATTERN = /\p{Script=Latin}/u;

export function usesCompactMapLabels(locale: string, text?: string): boolean {
  if (text) {
    return COMPACT_SCRIPT_PATTERN.test(text) && !LATIN_SCRIPT_PATTERN.test(text);
  }
  return locale.startsWith('zh') || locale.startsWith('ja');
}

const COMPACT_SIZE_BONUS = 1.5;

export function getRegionTier(type: string): MapLabelTier {
  return resolveLabelTier(type);
}

export function getRegionTextMetrics(type: string, locale: string, text?: string): RegionTextMetrics {
  const tier = resolveLabelTier(type);
  const compact = usesCompactMapLabels(locale, text);
  const screenSize = tier.screenSize + (compact ? COMPACT_SIZE_BONUS : 0);
  const fontSize = Math.round(screenSize * MAP_LABEL_TEXT_RESOLUTION);

  return {
    screenSize,
    fontSize,
    lineHeight: Math.round(fontSize * (compact ? 1.18 : 1.28)),
    // Compact scripts get a fraction of the Latin tracking: CJK is already wide.
    letterSpacing: Math.round(tier.letterSpacing * (compact ? 0.45 : 1) * MAP_LABEL_TEXT_RESOLUTION)
  };
}

/**
 * Pixi text style for a region label.
 *
 * Legibility comes from a plate drawn behind the text (see `MAP_LABEL_PLATE`),
 * not from a heavy glyph outline. The previous 4–5px black stroke plus drop
 * shadow muddied every name and still failed over busy tiles.
 */
export function getRegionTextStyle(type: string, locale = 'zh-CN', text?: string): Partial<TextStyleOptions> {
  const tier = resolveLabelTier(type);
  const metrics = getRegionTextMetrics(type, locale, text);

  return {
    fontFamily: tier.fontFamily,
    fontSize: metrics.fontSize,
    fontWeight: tier.fontWeight,
    fontStyle: tier.fontStyle,
    lineHeight: metrics.lineHeight,
    letterSpacing: metrics.letterSpacing,
    fill: tier.fill,
    align: 'center',
    whiteSpace: 'pre',
    // A hairline casing keeps names readable where a plate is not drawn
    // (territory tier) without the old outline weight.
    stroke: { color: 0x0b0e0d, width: tier.plate ? 0 : 3, join: 'round' }
  };
}

/**
 * Scale that holds a label at its nominal on-screen size regardless of zoom.
 *
 * The glyph texture is rasterized `MAP_LABEL_TEXT_RESOLUTION` times larger than
 * the target, so this normally downsamples — which stays crisp — instead of
 * blowing up a small texture.
 */
export function getLabelCounterScale(viewportScale: number): number {
  if (!Number.isFinite(viewportScale) || viewportScale <= 0) {
    return 1 / MAP_LABEL_TEXT_RESOLUTION;
  }
  const raw = 1 / (viewportScale * MAP_LABEL_TEXT_RESOLUTION);
  return Math.min(
    MAP_LABEL_SCALE_CLAMP.max / MAP_LABEL_TEXT_RESOLUTION,
    Math.max(MAP_LABEL_SCALE_CLAMP.min / MAP_LABEL_TEXT_RESOLUTION, raw)
  );
}

/** Whether a tier is disclosed at the given viewport zoom. */
export function isTierVisibleAtScale(type: string, viewportScale: number): boolean {
  return viewportScale >= resolveLabelTier(type).minScale;
}
