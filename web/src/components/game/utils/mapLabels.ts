import type { RegionSummary } from '@/types/core';
import { resolveLabelTier, type MapLabelTierName } from '@/constants/mapTheme';
import {
  getRegionTextMetrics,
  isTierVisibleAtScale,
  usesCompactMapLabels
} from '@/utils/mapStyles';

const TILE_SIZE = 64;
const AVG_LATIN_GLYPH_WIDTH_RATIO = 0.62;
const AVG_COMPACT_GLYPH_WIDTH_RATIO = 0.98;
const LABEL_BOX_PADDING_X = 8;
const LABEL_BOX_PADDING_Y = 4;
const LABEL_COLLISION_PADDING = 9;
const SPATIAL_BUCKET_SIZE = 256;

export type MapRegionLabel = RegionSummary & {
  displayName: string;
  labelX: number;
  labelY: number;
  priority: number;
  tier: MapLabelTierName;
};

type LabelBounds = {
  left: number;
  top: number;
  right: number;
  bottom: number;
};

type LabelPlacement = {
  labelX: number;
  labelY: number;
  bounds: LabelBounds;
};

export type RegionLabelSize = {
  width: number;
  height: number;
};

type AcceptedLabel = {
  label: MapRegionLabel;
  bounds: LabelBounds;
};

export function getRegionPriority(region: RegionSummary): number {
  return resolveLabelTier(region.type).priority;
}

function splitLatinWords(name: string): string[] {
  return name
    .trim()
    .split(/\s+/)
    .filter(Boolean);
}

function truncateWithEllipsis(text: string, maxChars: number): string {
  if (text.length <= maxChars) return text;
  return `${text.slice(0, Math.max(1, maxChars - 1)).trimEnd()}…`;
}

/**
 * Wraps a name to at most two lines. The wrap target is per-tier: a city name
 * gets to stay wide, a cultivation site wraps sooner, so the label block scales
 * with the label's importance.
 */
export function formatRegionDisplayName(
  name: string,
  locale: string,
  type = 'normal'
): string {
  if (usesCompactMapLabels(locale, name)) {
    return name;
  }

  const wrapTarget = resolveLabelTier(type).wrapTarget;
  const words = splitLatinWords(name);
  if (words.length <= 1) {
    return truncateWithEllipsis(name, wrapTarget);
  }

  let firstLine = '';
  let secondLineWords: string[] = [];

  for (const word of words) {
    const candidate = firstLine ? `${firstLine} ${word}` : word;
    if (candidate.length <= wrapTarget || firstLine.length === 0) {
      firstLine = candidate;
      continue;
    }
    secondLineWords = words.slice(words.indexOf(word));
    break;
  }

  if (secondLineWords.length === 0) {
    return firstLine;
  }

  const secondLine = truncateWithEllipsis(secondLineWords.join(' '), wrapTarget);
  return `${firstLine}\n${secondLine}`;
}

/**
 * Label footprint in *screen* px.
 *
 * Labels are counter-scaled to hold a constant on-screen size, so collision has
 * to be resolved in screen space too. Callers convert to world units with the
 * current viewport scale.
 */
export function estimateRegionLabelSize(
  displayName: string,
  type: string,
  locale: string
): RegionLabelSize {
  const metrics = getRegionTextMetrics(type, locale, displayName);
  const lines = displayName.split('\n');
  const maxChars = Math.max(...lines.map((line) => line.length), 1);
  const compact = usesCompactMapLabels(locale, displayName);
  const widthRatio = compact ? AVG_COMPACT_GLYPH_WIDTH_RATIO : AVG_LATIN_GLYPH_WIDTH_RATIO;
  const perGlyph = metrics.screenSize * widthRatio + metrics.letterSpacing / 3;

  return {
    width: maxChars * perGlyph + LABEL_BOX_PADDING_X * 2,
    height: lines.length * (metrics.screenSize * (compact ? 1.18 : 1.28)) + LABEL_BOX_PADDING_Y * 2
  };
}

function estimateLabelPlacement(
  region: RegionSummary,
  displayName: string,
  locale: string,
  worldScale: number,
  offsetX = 0,
  offsetY = 0
): LabelPlacement {
  const screen = estimateRegionLabelSize(displayName, region.type, locale);
  // Convert the screen footprint into world units for collision in map space.
  const width = screen.width * worldScale;
  const height = screen.height * worldScale;
  const labelX = region.x * TILE_SIZE + TILE_SIZE / 2 + offsetX;
  const labelY = region.y * TILE_SIZE + TILE_SIZE * 1.5 + offsetY;
  const pad = LABEL_COLLISION_PADDING * worldScale;

  return {
    labelX,
    labelY,
    bounds: {
      left: labelX - width / 2 - pad,
      right: labelX + width / 2 + pad,
      top: labelY - height / 2 - pad,
      bottom: labelY + height / 2 + pad
    }
  };
}

function intersects(a: LabelBounds, b: LabelBounds): boolean {
  return !(a.right < b.left || a.left > b.right || a.bottom < b.top || a.top > b.bottom);
}

function getBucketKey(x: number, y: number): string {
  return `${x},${y}`;
}

function getBoundsBucketRange(bounds: LabelBounds) {
  return {
    minX: Math.floor(bounds.left / SPATIAL_BUCKET_SIZE),
    maxX: Math.floor(bounds.right / SPATIAL_BUCKET_SIZE),
    minY: Math.floor(bounds.top / SPATIAL_BUCKET_SIZE),
    maxY: Math.floor(bounds.bottom / SPATIAL_BUCKET_SIZE)
  };
}

function findCollision(
  bounds: LabelBounds,
  spatialIndex: Map<string, AcceptedLabel[]>
): AcceptedLabel | undefined {
  const range = getBoundsBucketRange(bounds);

  for (let x = range.minX; x <= range.maxX; x += 1) {
    for (let y = range.minY; y <= range.maxY; y += 1) {
      const bucket = spatialIndex.get(getBucketKey(x, y));
      if (!bucket) continue;

      const hit = bucket.find((entry) => intersects(entry.bounds, bounds));
      if (hit) {
        return hit;
      }
    }
  }

  return undefined;
}

function addToSpatialIndex(entry: AcceptedLabel, spatialIndex: Map<string, AcceptedLabel[]>) {
  const range = getBoundsBucketRange(entry.bounds);

  for (let x = range.minX; x <= range.maxX; x += 1) {
    for (let y = range.minY; y <= range.maxY; y += 1) {
      const key = getBucketKey(x, y);
      const bucket = spatialIndex.get(key);
      if (bucket) {
        bucket.push(entry);
      } else {
        spatialIndex.set(key, [entry]);
      }
    }
  }
}

function getPlacementOffsets(
  region: RegionSummary,
  locale: string,
  worldScale: number
): Array<[number, number]> {
  const metrics = getRegionTextMetrics(region.type, locale, region.name);
  const stepX = Math.round(metrics.screenSize * 3.2 * worldScale);
  const stepY = Math.round(metrics.screenSize * 1.6 * worldScale);

  return [
    [0, 0],
    [0, stepY],
    [0, -stepY],
    [stepX, 0],
    [-stepX, 0],
    [stepX, stepY],
    [-stepX, stepY],
    [stepX, -stepY],
    [-stepX, -stepY],
    [0, stepY * 2],
    [0, -stepY * 2],
    [stepX * 2, 0],
    [-stepX * 2, 0],
    [stepX, stepY * 2],
    [-stepX, stepY * 2],
    [stepX, -stepY * 2],
    [-stepX, -stepY * 2],
    [stepX * 2, stepY],
    [stepX * 2, -stepY],
    [-stepX * 2, stepY],
    [-stepX * 2, -stepY],
    [0, stepY * 3],
    [0, -stepY * 3],
    [stepX * 3, 0],
    [-stepX * 3, 0]
  ];
}

export interface BuildLabelOptions {
  /**
   * Current viewport zoom. Drives both tier disclosure (LOD) and the world-space
   * size of each label's collision box. Defaults to 1 (world units == screen px).
   */
  viewportScale?: number;
  /**
   * When true, a label that cannot find a free placement is dropped instead of
   * being stacked on top of a higher-priority name. This is what keeps the
   * fit-zoom view readable.
   */
  dropOnCollision?: boolean;
}

/**
 * Chooses which region names to draw and where.
 *
 * Ordering is by canonical tier priority (city > sect > territory > site), so a
 * contested spot always resolves in favour of the more important place. Tiers
 * below their `minScale` are not considered at all.
 */
export function buildVisibleRegionLabels(
  regions: RegionSummary[],
  locale: string,
  options: BuildLabelOptions = {}
): MapRegionLabel[] {
  const viewportScale = options.viewportScale ?? 1;
  const dropOnCollision = options.dropOnCollision ?? true;
  const worldScale = viewportScale > 0 ? 1 / viewportScale : 1;

  const sortedRegions = [...regions]
    .filter((region) => isTierVisibleAtScale(region.type, viewportScale))
    .sort((a, b) => {
      const priorityDiff = getRegionPriority(b) - getRegionPriority(a);
      if (priorityDiff !== 0) return priorityDiff;

      const nameLengthDiff = a.name.length - b.name.length;
      if (nameLengthDiff !== 0) return nameLengthDiff;

      return String(a.id).localeCompare(String(b.id));
    });

  const accepted: AcceptedLabel[] = [];
  const spatialIndex = new Map<string, AcceptedLabel[]>();

  for (const region of sortedRegions) {
    const tier = resolveLabelTier(region.type);
    const displayName = formatRegionDisplayName(region.name, locale, region.type);
    const placements = getPlacementOffsets(region, locale, worldScale).map(
      ([offsetX, offsetY]) =>
        estimateLabelPlacement(region, displayName, locale, worldScale, offsetX, offsetY)
    );

    const freePlacement = placements.find(
      (placement) => !findCollision(placement.bounds, spatialIndex)
    );

    if (!freePlacement && dropOnCollision) {
      continue;
    }

    const chosenPlacement = freePlacement ?? placements[0];

    const entry: AcceptedLabel = {
      label: {
        ...region,
        displayName,
        labelX: chosenPlacement.labelX,
        labelY: chosenPlacement.labelY,
        priority: tier.priority,
        tier: tier.tier
      },
      bounds: chosenPlacement.bounds
    };

    accepted.push(entry);
    addToSpatialIndex(entry, spatialIndex);
  }

  return accepted.map((entry) => entry.label);
}
