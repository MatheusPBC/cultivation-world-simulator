import type { EntityRef, MapView, ObservatoryView } from '../types/medieval-api'
import { ApiError } from './api'

export function acceptSnapshot(data: ObservatoryView): ObservatoryView {
  if (!data.world || !data.status || !Array.isArray(data.society?.settlements)
      || !Array.isArray(data.economy?.stocks) || !Array.isArray(data.map?.region_rows)
      || !Array.isArray(data.economy?.payrolls) || !Array.isArray(data.governance?.tax_policies)
      || !Array.isArray(data.economy?.expansions) || !Array.isArray(data.economy?.expansion_blueprints)
      || !Array.isArray(data.research?.projects) || !Array.isArray(data.research?.technologies)
      || !Array.isArray(data.research?.knowledge)
      || !Array.isArray(data.governance?.objectives) || !Array.isArray(data.governance?.plans)) {
    throw new ApiError('INVALID_RESPONSE', 'O retrato do mundo está incompleto.')
  }
  const stocks = new Set(data.economy.stocks.map(s => s.id))
  const resources = new Set(data.economy.resources.map(r => r.id))
  if (data.governance.objectives.some(o => !stocks.has(o.stock_id) || !resources.has(o.resource_id)
      || !Number.isInteger(o.target_quantity) || o.target_quantity < 0)) {
    throw new ApiError('INVALID_RESPONSE', 'O plano de abastecimento está incompleto.')
  }
  return data
}
export function mapProjection(map: MapView) {
  const centers = new Map(map.settlements.map(s => [s.region_id, [s.center[0] + .5, s.center[1] + .5] as [number, number]]))
  const cells = map.geography.terrain_rows.flatMap((row, y) => row.map((terrain, x) => ({
    x, y, terrain, regionId: map.region_rows[y][x], elevation: map.geography.elevation_rows[y][x],
  })))
  const routes = map.routes.map(({ route, operational_capacity }) => ({
    id: route.id, from: centers.get(route.endpoint_region_ids[0])!,
    to: centers.get(route.endpoint_region_ids[1])!, mode: route.mode,
    capacity: operational_capacity, enabled: route.enabled,
  })).filter(r => r.from && r.to)
  return { cells, routes }
}
export function entityName(snapshot: ObservatoryView, ref: EntityRef | null): string {
  if (!ref) return 'Sem responsável'
  const registries = [...snapshot.society.polities, ...snapshot.society.organizations,
    ...snapshot.society.characters, ...snapshot.society.settlements, ...snapshot.map.sites]
  return registries.find(x => x.id === ref.id)?.name ?? ref.id
}
export const formatNumber = (n: number) => new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 }).format(n)
export const calendar = (day: number) => 'Ano ' + (Math.floor(day / 360) + 1) + ' · mês ' + (Math.floor(day % 360 / 30) + 1) + ' · dia ' + (day % 30 + 1)
