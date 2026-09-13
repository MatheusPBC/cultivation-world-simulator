import type { EntityRef, MapView, ObservatoryView } from '../types/medieval-api'
import { ApiError } from './api'

export function acceptSnapshot(data: ObservatoryView): ObservatoryView {
  if (!data.world || !data.status || !Array.isArray(data.society?.settlements)
      || !Array.isArray(data.economy?.stocks) || !Array.isArray(data.map?.region_rows)
      || !Array.isArray(data.map?.sites)
      || !Array.isArray(data.economy?.payrolls) || !Array.isArray(data.governance?.tax_policies)
      || !Array.isArray(data.economy?.expansions) || !Array.isArray(data.economy?.expansion_blueprints)
      || !Array.isArray(data.economy?.repairs) || !Array.isArray(data.economy?.repair_blueprints)
      || !Array.isArray(data.research?.projects) || !Array.isArray(data.research?.technologies)
      || !Array.isArray(data.research?.knowledge) || !Array.isArray(data.governance?.reports)
      || !Array.isArray(data.diplomacy?.proposals) || !Array.isArray(data.diplomacy?.obligations)
      || !Array.isArray(data.diplomacy?.notices)
      || !Array.isArray(data.governance?.objectives) || !Array.isArray(data.governance?.plans)
      || !Array.isArray(data.governance?.route_reports) || !Array.isArray(data.governance?.fiscal_route_reports)
      || !Array.isArray(data.governance?.site_reports)
      || !Array.isArray(data.economy?.customs_checkpoints) || !Array.isArray(data.economy?.cargo_manifests)
      || !Array.isArray(data.governance?.customs_notices)) {
    throw new ApiError('INVALID_RESPONSE', 'O retrato do mundo está incompleto.')
  }
  if (data.governance.tax_policies.some(p => !Number.isInteger(p.export_rate_permille)
      || p.export_rate_permille < 0 || p.export_rate_permille > 1000
      || (p.export_policy_event_id !== null && typeof p.export_policy_event_id !== 'string'))
      || data.governance.reports.some(r => !Number.isInteger(r.export_rate_permille)
        || r.export_rate_permille < 0 || r.export_rate_permille > 1000
        || (r.export_policy_event_id !== null && typeof r.export_policy_event_id !== 'string')
        || (r.export_collector_ref !== null && (typeof r.export_collector_ref !== 'object'
          || r.export_collector_ref.kind !== 'polity'
          || typeof r.export_collector_ref.id !== 'string' || !r.export_collector_ref.id)))) {
    throw new ApiError('INVALID_RESPONSE', 'A política de exportação está incompleta.')
  }
  if (data.map.sites.some(s => typeof s.service_suspended !== 'boolean')
      || data.governance.site_reports.some(r => typeof r.service_suspended !== 'boolean')) {
    throw new ApiError('INVALID_RESPONSE', 'O estado de serviço da instalação está incompleto.')
  }
  if (data.governance.fiscal_route_reports.some(report =>
      typeof report.id !== 'string' || !report.id
      || typeof report.recipient_ref !== 'object' || report.recipient_ref === null
      || typeof report.recipient_ref.kind !== 'string' || typeof report.recipient_ref.id !== 'string' || !report.recipient_ref.id
      || typeof report.publisher_ref !== 'object' || report.publisher_ref === null
      || typeof report.publisher_ref.kind !== 'string' || typeof report.publisher_ref.id !== 'string' || !report.publisher_ref.id
      || typeof report.route_id !== 'string' || !report.route_id
      || !Number.isInteger(report.observed_day) || report.observed_day < 0
      || typeof report.checkpoint_id !== 'string' || !report.checkpoint_id
      || typeof report.fee_per_bulk !== 'number' || !Number.isFinite(report.fee_per_bulk) || report.fee_per_bulk <= 0
      || (report.channel !== 'administrative_fiscal_route_report' && report.channel !== 'fiscal_route_bulletin')
      || typeof report.event_id !== 'string' || !report.event_id)) {
    throw new ApiError('INVALID_RESPONSE', 'O relatório fiscal da rota está incompleto.')
  }
  if (data.economy.customs_checkpoints.some(checkpoint =>
      typeof checkpoint.id !== 'string' || !checkpoint.id
      || typeof checkpoint.site_id !== 'string' || !checkpoint.site_id
      || typeof checkpoint.operator_ref !== 'object' || checkpoint.operator_ref === null
      || typeof checkpoint.operator_ref.kind !== 'string' || typeof checkpoint.operator_ref.id !== 'string' || !checkpoint.operator_ref.id
      || typeof checkpoint.account_id !== 'string' || !checkpoint.account_id
      || typeof checkpoint.staff_group_id !== 'string' || !checkpoint.staff_group_id
      || !Number.isInteger(checkpoint.staff_count) || checkpoint.staff_count < 1
      || typeof checkpoint.fee_per_bulk !== 'number' || !Number.isFinite(checkpoint.fee_per_bulk) || checkpoint.fee_per_bulk < 0
      || !Number.isInteger(checkpoint.started_day) || checkpoint.started_day < 0
      || !Number.isInteger(checkpoint.last_staffed_day) || checkpoint.last_staffed_day < checkpoint.started_day
      || !Number.isInteger(checkpoint.inspection_day) || checkpoint.inspection_day < checkpoint.started_day
      || !Number.isInteger(checkpoint.inspection_slots_used) || checkpoint.inspection_slots_used < 0
      || (checkpoint.last_event_id !== null && typeof checkpoint.last_event_id !== 'string'))
      || data.governance.customs_notices.some(notice =>
        typeof notice.id !== 'string' || !notice.id
        || typeof notice.parcel_id !== 'string' || !notice.parcel_id
        || typeof notice.checkpoint_id !== 'string' || !notice.checkpoint_id
        || typeof notice.order_id !== 'string' || !notice.order_id
        || typeof notice.recipient_ref !== 'object' || notice.recipient_ref === null
        || typeof notice.recipient_ref.kind !== 'string' || typeof notice.recipient_ref.id !== 'string' || !notice.recipient_ref.id
        || typeof notice.resource_id !== 'string' || !notice.resource_id
        || typeof notice.quantity !== 'number' || !Number.isFinite(notice.quantity) || notice.quantity <= 0
        || (notice.fee !== null && (typeof notice.fee !== 'number' || !Number.isFinite(notice.fee) || notice.fee <= 0))
        || !Number.isInteger(notice.learned_day) || notice.learned_day < 0
        || !['presented', 'fee_due', 'detected', 'cleared', 'evaded_undetected'].includes(notice.state)
        || typeof notice.event_id !== 'string' || !notice.event_id
        || typeof notice.state_event_id !== 'string' || !notice.state_event_id
        || (notice.manifest_id !== null && (typeof notice.manifest_id !== 'string' || !notice.manifest_id))
        || notice.channel !== 'direct_customs_notice')) {
    throw new ApiError('INVALID_RESPONSE', 'O registro de fiscalização aduaneira está incompleto.')
  }
  if (data.economy.cargo_manifests.some(manifest =>
      typeof manifest.id !== 'string' || !manifest.id
      || typeof manifest.checkpoint_id !== 'string' || !manifest.checkpoint_id
      || typeof manifest.parcel_id !== 'string' || !manifest.parcel_id
      || typeof manifest.order_id !== 'string' || !manifest.order_id
      || typeof manifest.owner_ref !== 'object' || manifest.owner_ref === null
      || typeof manifest.owner_ref.kind !== 'string' || typeof manifest.owner_ref.id !== 'string' || !manifest.owner_ref.id
      || typeof manifest.resource_id !== 'string' || !manifest.resource_id
      || typeof manifest.quantity !== 'number' || !Number.isFinite(manifest.quantity) || manifest.quantity <= 0
      || !Number.isInteger(manifest.declared_day) || manifest.declared_day < 0
      || typeof manifest.event_id !== 'string' || !manifest.event_id)) {
    throw new ApiError('INVALID_RESPONSE', 'O manifesto de carga está incompleto.')
  }
  if (data.economy.parcels.some(parcel =>
      (parcel.stage !== 'waiting' && parcel.stage !== 'traveling' && parcel.stage !== 'unloading' && parcel.stage !== 'held')
      || (parcel.held_checkpoint_id !== null && typeof parcel.held_checkpoint_id !== 'string')
      || (parcel.held_notice_id !== null && typeof parcel.held_notice_id !== 'string'))) {
    throw new ApiError('INVALID_RESPONSE', 'O estado da carga está incompleto.')
  }
  if (!Array.isArray(data.society.migrations) || !Array.isArray(data.economy.migration_provisions)
      || !Array.isArray(data.governance.settlement_reports)
      || data.society.settlements.some(s => !Number.isInteger(s.population) || !Number.isInteger(s.present_population))
      || data.society.migrations.some(m => typeof m.initial_destination_id !== 'string'
        || !Array.isArray(m.initial_route_ids) || typeof m.returning !== 'boolean')
      || data.economy.migration_provisions.some(p => (p.consumed_day !== null && !Number.isInteger(p.consumed_day))
        || (p.consumed_event_id !== null && typeof p.consumed_event_id !== 'string'))) {
    throw new ApiError('INVALID_RESPONSE', 'O retrato das migrações está incompleto.')
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
