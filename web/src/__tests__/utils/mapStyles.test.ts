import { describe, it, expect } from 'vitest'
import {
  getLabelCounterScale,
  getRegionTextMetrics,
  getRegionTextStyle,
  getRegionTier,
  isTierVisibleAtScale,
  usesCompactMapLabels
} from '@/utils/mapStyles'
import { MAP_GOLD, MAP_JADE, MAP_LABEL_TEXT_RESOLUTION, MAP_PAPER } from '@/constants/mapTheme'

describe('mapStyles', () => {
  describe('usesCompactMapLabels', () => {
    it('should treat zh and ja as compact-script locales', () => {
      expect(usesCompactMapLabels('zh-CN')).toBe(true)
      expect(usesCompactMapLabels('zh-TW')).toBe(true)
      expect(usesCompactMapLabels('ja-JP')).toBe(true)
      expect(usesCompactMapLabels('en-US')).toBe(false)
    })

    it('prefers the actual label script when content and UI locales differ', () => {
      expect(usesCompactMapLabels('zh-CN', 'Cidade Qingyun')).toBe(false)
      expect(usesCompactMapLabels('pt-BR', '青云城')).toBe(true)
    })
  })

  describe('tier hierarchy', () => {
    it('maps the canonical region taxonomy onto four distinct tiers', () => {
      expect(getRegionTier('city').tier).toBe('settlement')
      expect(getRegionTier('sect').tier).toBe('power')
      expect(getRegionTier('normal').tier).toBe('territory')
      expect(getRegionTier('cultivate').tier).toBe('site')
    })

    it('falls back to the territory tier for an unknown type', () => {
      expect(getRegionTier('unknown').tier).toBe('territory')
      expect(getRegionTier('').tier).toBe('territory')
    })

    it('orders on-screen size strictly by importance', () => {
      const city = getRegionTextMetrics('city', 'en-US').screenSize
      const sect = getRegionTextMetrics('sect', 'en-US').screenSize
      const wild = getRegionTextMetrics('normal', 'en-US').screenSize
      const site = getRegionTextMetrics('cultivate', 'en-US').screenSize

      // The old design gave every type 64-70px, i.e. no hierarchy at all.
      expect(city).toBeGreaterThan(sect)
      expect(sect).toBeGreaterThan(wild)
      expect(wild).toBeGreaterThan(site)
    })

    it('separates tiers by weight and colour, not only by size', () => {
      expect(getRegionTextStyle('city').fill).toBe(MAP_PAPER[100])
      expect(getRegionTextStyle('city').fontWeight).toBe('bold')
      expect(getRegionTextStyle('sect').fill).toBe(MAP_GOLD[300])
      expect(getRegionTextStyle('normal').fill).toBe(MAP_PAPER[300])
      expect(getRegionTextStyle('normal').fontWeight).toBe('normal')
      expect(getRegionTextStyle('cultivate').fill).toBe(MAP_JADE[300])
    })

    it('tracks wilderness names wider than settlement names', () => {
      const wild = getRegionTextMetrics('normal', 'en-US').letterSpacing
      const city = getRegionTextMetrics('city', 'en-US').letterSpacing
      expect(wild).toBeGreaterThan(city)
    })

    it('gives compact scripts a size bonus and less tracking', () => {
      const latin = getRegionTextMetrics('normal', 'en-US')
      const compact = getRegionTextMetrics('normal', 'zh-CN')
      expect(compact.screenSize).toBeGreaterThan(latin.screenSize)
      expect(compact.letterSpacing).toBeLessThan(latin.letterSpacing)
    })
  })

  describe('rasterization', () => {
    it('rasterizes glyphs above the target size so counter-scaling downsamples', () => {
      const metrics = getRegionTextMetrics('city', 'en-US')
      expect(metrics.fontSize).toBe(Math.round(metrics.screenSize * MAP_LABEL_TEXT_RESOLUTION))
      expect(metrics.fontSize).toBeGreaterThan(metrics.screenSize)
    })

    it('drops the heavy glyph outline wherever a plate is drawn', () => {
      // City/sect/site labels get a plate; wilderness names keep a hairline.
      expect(getRegionTextStyle('city').stroke).toEqual(
        expect.objectContaining({ width: 0 })
      )
      expect(getRegionTextStyle('normal').stroke).toEqual(
        expect.objectContaining({ width: 3 })
      )
    })
  })

  describe('getLabelCounterScale', () => {
    it('holds a label at a constant on-screen size as zoom changes', () => {
      // Halving the zoom must double the counter-scale.
      const atOne = getLabelCounterScale(1)
      const atHalf = getLabelCounterScale(0.5)
      expect(atHalf).toBeCloseTo(atOne * 2, 5)
    })

    it('clamps instead of producing a degenerate scale', () => {
      expect(getLabelCounterScale(0)).toBeGreaterThan(0)
      expect(getLabelCounterScale(Number.NaN)).toBeGreaterThan(0)
      expect(getLabelCounterScale(0.0001)).toBeLessThanOrEqual(6 / MAP_LABEL_TEXT_RESOLUTION)
    })
  })

  describe('isTierVisibleAtScale', () => {
    it('always shows settlements and powers, and reveals lesser tiers on zoom-in', () => {
      expect(isTierVisibleAtScale('city', 0.1)).toBe(true)
      expect(isTierVisibleAtScale('sect', 0.1)).toBe(true)
      expect(isTierVisibleAtScale('normal', 0.1)).toBe(false)
      expect(isTierVisibleAtScale('cultivate', 0.1)).toBe(false)

      expect(isTierVisibleAtScale('normal', 0.5)).toBe(true)
      expect(isTierVisibleAtScale('cultivate', 0.5)).toBe(false)
      expect(isTierVisibleAtScale('cultivate', 1)).toBe(true)
    })
  })
})
