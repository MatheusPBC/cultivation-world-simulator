import { describe, expect, it } from 'vitest'
import { buildInfrastructureSiteRenderPlan } from '@/components/game/utils/infrastructureSites'
import type { InfrastructureSiteSummary } from '@/types/core'

function site(status: InfrastructureSiteSummary['status']): InfrastructureSiteSummary {
  return {
    id: `site:${status}`,
    kind: 'bridge',
    name: 'Ponte',
    cellRefs: [[2, 3]],
    regionIds: [1, 2],
    routeIds: [],
    waterBodyIds: [],
    capabilityIds: [],
    ownerRef: null,
    maintainerRef: null,
    integrity: status === 'active' ? 1 : 0.3,
    enabled: status !== 'destroyed',
    status,
    x: 2,
    y: 3,
    clickable: true,
    lastEventId: null,
  }
}

describe('infrastructure site projection', () => {
  it('projects each status with a stable tile position and distinct marker color', () => {
    const plan = buildInfrastructureSiteRenderPlan([
      site('active'),
      site('impaired'),
      site('destroyed'),
    ], true)

    expect(plan).toHaveLength(3)
    expect(plan.map(item => item.position)).toEqual([
      { x: 160, y: 224 },
      { x: 160, y: 224 },
      { x: 160, y: 224 },
    ])
    expect(new Set(plan.map(item => item.color)).size).toBe(3)
    expect(plan.map(item => item.status)).toEqual(['active', 'impaired', 'destroyed'])
  })

  it('does not project hidden sites', () => {
    expect(buildInfrastructureSiteRenderPlan([site('active')], false)).toEqual([])
  })
})
