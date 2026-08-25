import { describe, expect, it } from 'vitest'

import { formatCultivationText, humanizeIdentifier } from '@/utils/cultivationText'

const labels: Record<string, string> = {
  'realms.QI_REFINEMENT': 'Refinamento de Qi',
  'realms.FOUNDATION_ESTABLISHMENT': 'Estabelecimento da Fundação',
  'realms.CORE_FORMATION': 'Formação do Núcleo',
  'realms.NASCENT_SOUL': 'Alma Nascente',
  'game.ranking.stages.early': 'Inicial',
  'game.ranking.stages.middle': 'Intermediário',
  'game.ranking.stages.late': 'Avançado',
}

const t = (key: string) => labels[key] ?? key

describe('formatCultivationText', () => {
  it.each([
    ['core_formationearly_stage', 'Formação do Núcleo Inicial'],
    ['core_formation_early_stage', 'Formação do Núcleo Inicial'],
    ['nascent_soullate_stage', 'Alma Nascente Avançado'],
    ['FOUNDATION_ESTABLISHMENT middle_stage', 'Estabelecimento da Fundação Intermediário'],
  ])('normalizes %s', (raw, expected) => {
    expect(formatCultivationText(raw, t)).toBe(expected)
  })

  it('never exposes an unknown snake_case identifier unchanged', () => {
    expect(formatCultivationText('custom_hidden_realm', t)).toBe('Custom Hidden Realm')
  })
})

describe('humanizeIdentifier', () => {
  it('humanizes snake case and camel case identifiers', () => {
    expect(humanizeIdentifier('sect_mission_start_headquarter')).toBe('Sect Mission Start Headquarter')
    expect(humanizeIdentifier('MoveToDirection')).toBe('Move To Direction')
  })
})
