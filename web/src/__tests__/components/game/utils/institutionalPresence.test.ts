import { describe, expect, it } from 'vitest'
import { buildInstitutionalPresenceRenderPlan } from '@/components/game/utils/institutionalPresence'

const region = { id: 301, name: 'Tianhe', x: 0, y: 0, type: 'city' }

describe('institutional presence render plan', () => {
  it('renders only governed urban regions and keeps governance color above sect overlap', () => {
    const plan = buildInstitutionalPresenceRenderPlan([
      {
        regionId: 301,
        regionName: 'Tianhe',
        regionType: 'city',
        tileCount: 2,
        governance: { controllerKind: 'dynasty', controllerId: '1', administrativeCapacity: 0.75 },
        sectInfluences: [{ sectId: 8, sectName: 'Azure', color: '#4DD0E1', ownedTileCount: 1, share: 0.5 }],
        dominantSectId: 8,
      },
      {
        regionId: 302,
        regionName: 'Wild',
        regionType: 'wilderness',
        tileCount: 1,
        governance: { controllerKind: 'dynasty', controllerId: '1', administrativeCapacity: 1 },
        sectInfluences: [],
        dominantSectId: null,
      },
      {
        regionId: 303,
        regionName: 'Unclaimed',
        regionType: 'city',
        tileCount: 1,
        governance: null,
        sectInfluences: [],
        dominantSectId: null,
      },
    ], [region], [[301, 301]], true)

    expect(plan).toHaveLength(1)
    expect(plan[0]).toMatchObject({
      regionId: 301,
      governanceColor: 0xd9aa45,
      cells: [[0, 0], [1, 0]],
    })
    expect(plan[0].governanceAlpha).toBeCloseTo(0.31)
    expect(plan[0].influenceMarkers).toEqual([{ color: 0x4dd0e1, share: 0.5 }])
  })

  it('uses the governed sect color only when that sect is the controller', () => {
    const plan = buildInstitutionalPresenceRenderPlan([{
      regionId: 301,
      regionName: 'Tianhe',
      regionType: 'city',
      tileCount: 1,
      governance: { controllerKind: 'sect', controllerId: '8', administrativeCapacity: 0 },
      sectInfluences: [{ sectId: 8, sectName: 'Azure', color: '#4DD0E1', ownedTileCount: 1, share: 1 }],
      dominantSectId: 8,
    }], [region], [[301]], true)

    expect(plan[0].governanceColor).toBe(0x4dd0e1)
    expect(buildInstitutionalPresenceRenderPlan([], [region], [[301]], false)).toEqual([])
  })

  it('clamps visual intensity and refuses a footprint from another world revision', () => {
    const presence = [{
      regionId: 301,
      regionName: 'Tianhe',
      regionType: 'city',
      tileCount: 2,
      governance: { controllerKind: 'dynasty', controllerId: '1', administrativeCapacity: 3 },
      sectInfluences: [],
      dominantSectId: null,
    }]

    expect(buildInstitutionalPresenceRenderPlan(presence, [region], [[301, 301]], true)[0]
      .governanceAlpha).toBeCloseTo(0.38)
    expect(buildInstitutionalPresenceRenderPlan(presence, [region], [[301]], true)).toEqual([])
  })
})
