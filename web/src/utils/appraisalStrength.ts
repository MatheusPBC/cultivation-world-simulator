/**
 * 个人解读（EventAppraisal）当前影响力的定性分级。
 *
 * 单一真源：标签文案与配色 class 都从这里派生，避免阈值在组件之间
 * 各写一份而失去同步。阈值见 docs/specs/personal-appraisal-politics.md
 * （"Query and UI"）：strong >= 0.65、moderate >= 0.35、weak >= 0.15。
 *
 * 后端 `Memórias marcantes` 查询已经用同一个 0.15 下限过滤，所以正常
 * 情况下不会出现低于 weak 的条目；这里仍然把 0.15 以下归入 weak，
 * 保证任意输入都有确定结果。
 */
export type AppraisalStrength = 'strong' | 'moderate' | 'weak'

export const APPRAISAL_STRENGTH_STRONG_MIN = 0.65
export const APPRAISAL_STRENGTH_MODERATE_MIN = 0.35
export const APPRAISAL_STRENGTH_WEAK_MIN = 0.15

export function classifyAppraisalStrength(effectiveWeight: number): AppraisalStrength {
  if (effectiveWeight >= APPRAISAL_STRENGTH_STRONG_MIN) return 'strong'
  if (effectiveWeight >= APPRAISAL_STRENGTH_MODERATE_MIN) return 'moderate'
  return 'weak'
}

/** i18n key 后缀，与 game.info_panel.avatar.memories.strength.* 对应。 */
export function appraisalStrengthI18nKey(effectiveWeight: number): string {
  return `game.info_panel.avatar.memories.strength.${classifyAppraisalStrength(effectiveWeight)}`
}

/** 组件内的配色 class，与标签保持同一分级。 */
export function appraisalStrengthClass(effectiveWeight: number): string {
  return `is-${classifyAppraisalStrength(effectiveWeight)}`
}
