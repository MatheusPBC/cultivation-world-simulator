import { describe, expect, it } from 'vitest';
import {
  buildVisibleRegionLabels,
  estimateRegionLabelSize,
  formatRegionDisplayName,
  getRegionPriority
} from '@/components/game/utils/mapLabels';
import type { RegionSummary } from '@/types/core';

function createRegion(overrides: Partial<RegionSummary>): RegionSummary {
  return {
    id: String(overrides.id ?? '1'),
    name: overrides.name ?? 'Test Region',
    type: overrides.type ?? 'normal',
    x: overrides.x ?? 0,
    y: overrides.y ?? 0,
    sect_id: overrides.sect_id,
    sect_name: overrides.sect_name,
    sect_color: overrides.sect_color,
    sect_is_active: overrides.sect_is_active,
    sub_type: overrides.sub_type
  };
}

describe('mapLabels', () => {
  it('wraps English map labels into at most two lines', () => {
    expect(formatRegionDisplayName('Purple Bamboo Secluded Realm', 'en-US')).toBe(
      'Purple Bamboo\nSecluded Realm'
    );
  });

  it('keeps Chinese labels on a single line', () => {
    expect(formatRegionDisplayName('紫竹幽境', 'zh-CN')).toBe('紫竹幽境');
  });

  it('wraps Latin toponyms even when the interface locale is CJK', () => {
    expect(formatRegionDisplayName('Falésias do Mar Sereno de Nanling', 'zh-CN', 'city'))
      .toContain('\n');
  });

  it('lets a city name run wider before wrapping than a cultivation site', () => {
    const city = formatRegionDisplayName('Qingyun Riverside Market', 'en-US', 'city');
    const site = formatRegionDisplayName('Qingyun Riverside Market', 'en-US', 'cultivate');
    expect(city.split('\n')[0].length).toBeLessThanOrEqual(15);
    expect(site.split('\n')[0].length).toBeLessThanOrEqual(16);
  });

  it('estimates the label footprint in on-screen pixels', () => {
    const compactSize = estimateRegionLabelSize('紫竹幽境', 'normal', 'zh-CN');
    const latinSize = estimateRegionLabelSize('Purple Bamboo\nSecluded Realm', 'normal', 'en-US');

    // Screen-space, not the old ~64px world-space font: a four-glyph CJK name
    // occupies tens of pixels, not hundreds.
    expect(compactSize.width).toBeGreaterThan(40);
    expect(compactSize.width).toBeLessThan(140);
    expect(latinSize.height).toBeGreaterThan(compactSize.height);
  });

  it('ranks the canonical region taxonomy by cartographic importance', () => {
    expect(getRegionPriority(createRegion({ type: 'city' }))).toBeGreaterThan(
      getRegionPriority(createRegion({ type: 'sect' }))
    );
    expect(getRegionPriority(createRegion({ type: 'sect' }))).toBeGreaterThan(
      getRegionPriority(createRegion({ type: 'normal' }))
    );
    expect(getRegionPriority(createRegion({ type: 'normal' }))).toBeGreaterThan(
      getRegionPriority(createRegion({ type: 'cultivate' }))
    );
  });

  it('resolves a contested spot in favour of the more important place', () => {
    const labels = buildVisibleRegionLabels(
      [
        createRegion({ id: 'normal', type: 'normal', name: 'Purple Bamboo Secluded Realm', x: 10, y: 10 }),
        createRegion({ id: 'city', type: 'city', name: 'Qingyun City', x: 10, y: 10 })
      ],
      'en-US',
      { viewportScale: 1 }
    );

    // The city keeps the anchor; the wilderness name is displaced, not stacked.
    expect(labels[0]?.id).toBe('city');
    expect(labels[0]?.labelX).toBe((10 * 64) + (64 / 2));
    expect(labels[0]?.labelY).toBe((10 * 64) + (64 * 1.5));
    const wilderness = labels.find((label) => label.id === 'normal');
    if (wilderness) {
      expect(
        wilderness.labelX !== labels[0]?.labelX || wilderness.labelY !== labels[0]?.labelY
      ).toBe(true);
    }
  });

  it('keeps separated labels visible', () => {
    const labels = buildVisibleRegionLabels(
      [
        createRegion({ id: 'a', type: 'city', name: 'Qingyun City', x: 2, y: 2 }),
        createRegion({ id: 'b', type: 'sect', name: 'Echo Valley', x: 12, y: 8 })
      ],
      'en-US',
      { viewportScale: 1 }
    );

    expect(labels.map((label) => label.id)).toEqual(['a', 'b']);
  });

  it('tags each label with its tier so the renderer can style it', () => {
    const labels = buildVisibleRegionLabels(
      [
        createRegion({ id: 'a', type: 'city', name: 'Qingyun', x: 2, y: 2 }),
        createRegion({ id: 'b', type: 'cultivate', sub_type: 'cave', name: 'Golden Grotto', x: 14, y: 9 })
      ],
      'en-US',
      { viewportScale: 1 }
    );

    expect(labels.find((label) => label.id === 'a')?.tier).toBe('settlement');
    expect(labels.find((label) => label.id === 'b')?.tier).toBe('site');
  });

  describe('level of detail', () => {
    const regions = [
      createRegion({ id: 'city', type: 'city', name: 'Qingyun City', x: 4, y: 4 }),
      createRegion({ id: 'sect', type: 'sect', name: 'Echo Valley', x: 20, y: 4 }),
      createRegion({ id: 'wild', type: 'normal', name: 'Western Quicksand', x: 36, y: 4 }),
      createRegion({ id: 'cave', type: 'cultivate', name: 'Golden Grotto', x: 52, y: 4 })
    ];

    it('shows only the loudest tiers when the whole world is on screen', () => {
      const ids = buildVisibleRegionLabels(regions, 'en-US', { viewportScale: 0.24 })
        .map((label) => label.id);
      expect(ids).toContain('city');
      expect(ids).toContain('sect');
      expect(ids).not.toContain('wild');
      expect(ids).not.toContain('cave');
    });

    it('reveals the remaining tiers as the player zooms in', () => {
      const ids = buildVisibleRegionLabels(regions, 'en-US', { viewportScale: 1 })
        .map((label) => label.id);
      expect(ids).toEqual(expect.arrayContaining(['city', 'sect', 'wild', 'cave']));
    });
  });

  it('drops a label that cannot be placed rather than overlapping a better one', () => {
    const crowded = Array.from({ length: 6 }, (_, index) =>
      createRegion({
        id: `wild-${index}`,
        type: 'normal',
        name: 'Western Quicksand Reach',
        x: 10,
        y: 10
      })
    );

    const labels = buildVisibleRegionLabels(crowded, 'en-US', { viewportScale: 1 });
    expect(labels.length).toBeLessThan(crowded.length);
  });

  it('can be asked to keep every label when overlap is acceptable', () => {
    const crowded = Array.from({ length: 6 }, (_, index) =>
      createRegion({ id: `wild-${index}`, type: 'normal', name: 'Western Quicksand Reach', x: 10, y: 10 })
    );

    const labels = buildVisibleRegionLabels(crowded, 'en-US', {
      viewportScale: 1,
      dropOnCollision: false
    });
    expect(labels).toHaveLength(crowded.length);
  });

  it('also avoids overlap for compact-script locales', () => {
    const labels = buildVisibleRegionLabels(
      [
        createRegion({ id: 'a', type: 'sect', name: '修罗血池', x: 10, y: 22 }),
        createRegion({ id: 'b', type: 'normal', name: '西域流沙', x: 10, y: 22 })
      ],
      'ja-JP',
      { viewportScale: 1, dropOnCollision: false }
    );

    expect(labels).toHaveLength(2);
    expect(
      labels[1]?.labelX !== labels[0]?.labelX || labels[1]?.labelY !== labels[0]?.labelY
    ).toBe(true);
  });
});
