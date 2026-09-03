import type { InfrastructureSiteStatus, InfrastructureSiteSummary } from '@/types/core'

export const INFRASTRUCTURE_SITE_TILE_SIZE = 64

const STATUS_COLORS: Record<InfrastructureSiteStatus, number> = {
  active: 0x79d68b,
  impaired: 0xf0b35b,
  destroyed: 0xd86666,
}

export interface InfrastructureSiteRenderItem {
  id: string
  name: string
  kind: string
  status: InfrastructureSiteStatus
  color: number
  clickable: boolean
  position: { x: number; y: number }
}

export function buildInfrastructureSiteRenderPlan(
  sites: InfrastructureSiteSummary[],
  visible: boolean,
): InfrastructureSiteRenderItem[] {
  if (!visible) return []

  return sites.map(site => ({
    id: site.id,
    name: site.name,
    kind: site.kind,
    status: site.status,
    color: STATUS_COLORS[site.status],
    clickable: site.clickable,
    position: {
      x: site.x * INFRASTRUCTURE_SITE_TILE_SIZE + INFRASTRUCTURE_SITE_TILE_SIZE / 2,
      y: site.y * INFRASTRUCTURE_SITE_TILE_SIZE + INFRASTRUCTURE_SITE_TILE_SIZE / 2,
    },
  }))
}

export function infrastructureSiteStatusColor(status: InfrastructureSiteStatus): number {
  return STATUS_COLORS[status]
}
