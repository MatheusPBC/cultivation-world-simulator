import type { DetailResponseDTO, InfrastructureSiteDetailDTO, RouteDetailDTO } from '@/types/api';
import type { AvatarDetail, InfrastructureSiteDetail, POIDetail, RegionDetail, RouteDetail, SectDetail } from '@/types/core';
import type { SelectionType } from '@/stores/ui';

type DetailDomainByType<T extends SelectionType> =
  T extends 'avatar'
    ? AvatarDetail
    : T extends 'region'
      ? RegionDetail
      : T extends 'sect'
      ? SectDetail
        : T extends 'poi'
          ? POIDetail
          : T extends 'site'
            ? InfrastructureSiteDetail
            : RouteDetail;

/**
 * 将 /api/v1/query/detail 返回的 DTO 归一化为前端领域模型。
 *
 * 当前后端已经直接返回接近领域结构的对象，因此这里主要负责：
 * - 根据调用方的 target.type 缩小联合类型
 * - 保留未来在此处做兼容映射的扩展点
 */
export function mapDetailDTOToDomain(
  dto: DetailResponseDTO,
  targetType: 'avatar',
): AvatarDetail;
export function mapDetailDTOToDomain(
  dto: DetailResponseDTO,
  targetType: 'region',
): RegionDetail;
export function mapDetailDTOToDomain(
  dto: DetailResponseDTO,
  targetType: 'sect',
): SectDetail;
export function mapDetailDTOToDomain(
  dto: DetailResponseDTO,
  targetType: 'poi',
): POIDetail;
export function mapDetailDTOToDomain(
  dto: DetailResponseDTO,
  targetType: 'site',
): InfrastructureSiteDetail;
export function mapDetailDTOToDomain(
  dto: DetailResponseDTO,
  targetType: 'route',
): RouteDetail;
export function mapDetailDTOToDomain<T extends SelectionType>(
  dto: DetailResponseDTO,
  targetType: T,
): DetailDomainByType<T>;
export function mapDetailDTOToDomain(
  dto: DetailResponseDTO,
  _targetType: SelectionType,
): AvatarDetail | RegionDetail | SectDetail | POIDetail | InfrastructureSiteDetail | RouteDetail {
  if (_targetType === 'site') {
    const site = dto as InfrastructureSiteDetailDTO;
    return {
      id: site.id,
      name: site.name,
      kind: site.kind,
      cellRefs: site.cell_refs.map(cell => [...cell] as [number, number]),
      regionIds: [...site.region_ids],
      routeIds: [...site.route_ids],
      waterBodyIds: [...site.water_body_ids],
      capabilityIds: [...site.capability_ids],
      ownerRef: site.owner_ref ? { ...site.owner_ref } : null,
      maintainerRef: site.maintainer_ref ? { ...site.maintainer_ref } : null,
      integrity: site.integrity,
      enabled: site.enabled,
      status: site.status,
      x: site.x,
      y: site.y,
      clickable: site.clickable,
      lastEventId: site.last_event_id,
      ...(site.desc === undefined ? {} : { desc: site.desc }),
      ...(site.source_event_ids === undefined ? {} : { sourceEventIds: [...site.source_event_ids] }),
    };
  }
  if (_targetType === 'route') {
    return mapRouteDetail(dto);
  }
  return dto as AvatarDetail | RegionDetail | SectDetail | POIDetail;
}

function mapRouteDetail(dto: DetailResponseDTO): RouteDetail {
  const route = isRecord(dto) ? dto as Partial<RouteDetailDTO> : null;
  if (
    typeof route?.id !== 'string' || route.id.length === 0
    || typeof route.mode !== 'string' || route.mode.length === 0
    || !isRegionPair(route.endpoint_region_ids)
    || !isFiniteNonNegative(route.capacity)
    || !isFiniteNonNegative(route.operational_capacity)
    || !isFiniteUnitInterval(route.quality)
    || typeof route.enabled !== 'boolean'
    || route.operational_capacity > route.capacity * route.quality
    || !isIdentifierArray(route.allowed_resource_ids)
    || !isIdentifierArray(route.dependency_site_ids)
    || !isIdentifierArray(route.source_event_ids)
  ) {
    throw new Error('Invalid route detail payload');
  }

  return {
    id: route.id,
    endpointRegionIds: [...route.endpoint_region_ids] as [number, number],
    mode: route.mode,
    capacity: route.capacity,
    operationalCapacity: route.operational_capacity,
    quality: route.quality,
    enabled: route.enabled,
    allowedResourceIds: [...route.allowed_resource_ids],
    dependencySiteIds: [...route.dependency_site_ids],
    sourceEventIds: [...route.source_event_ids],
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function isRegionPair(value: unknown): value is [number, number] {
  return Array.isArray(value)
    && value.length === 2
    && value.every(item => Number.isInteger(item) && item > 0)
    && value[0] !== value[1];
}

function isFiniteNonNegative(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0;
}

function isFiniteUnitInterval(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 1;
}

function isIdentifierArray(value: unknown): value is string[] {
  return Array.isArray(value)
    && value.every(item => typeof item === 'string' && item.length > 0)
    && new Set(value).size === value.length;
}
