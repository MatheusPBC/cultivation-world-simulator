import { describe, it, expect } from 'vitest'
import {
  appraisalStrengthClass,
  appraisalStrengthI18nKey,
  classifyAppraisalStrength,
} from '@/utils/appraisalStrength'

describe('appraisalStrength', () => {
  it('classifies at the exact spec boundaries', () => {
    expect(classifyAppraisalStrength(0.65)).toBe('strong')
    expect(classifyAppraisalStrength(0.6499)).toBe('moderate')
    expect(classifyAppraisalStrength(0.35)).toBe('moderate')
    expect(classifyAppraisalStrength(0.3499)).toBe('weak')
    expect(classifyAppraisalStrength(0.15)).toBe('weak')
  })

  it('keeps label key and css class derived from the same bucket', () => {
    for (const weight of [1, 0.65, 0.5, 0.35, 0.2, 0.15, 0]) {
      const bucket = classifyAppraisalStrength(weight)
      expect(appraisalStrengthI18nKey(weight)).toBe(
        `game.info_panel.avatar.memories.strength.${bucket}`,
      )
      expect(appraisalStrengthClass(weight)).toBe(`is-${bucket}`)
    }
  })
})
