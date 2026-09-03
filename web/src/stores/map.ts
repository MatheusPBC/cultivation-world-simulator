import { defineStore } from 'pinia';
import { ref, shallowRef } from 'vue';
import type { InfrastructureSiteSummary, MapMatrix, PhysicalGeographySnapshot, POISummary, RegionSummary, RouteSummary } from '../types/core';
import type { InfrastructureSiteDTO, InfrastructureSiteUpdateDTO, MapRenderConfigDTO, POIUpdateDTO, RouteUpdateDTO } from '../types/api';
import { worldApi } from '../api';
import { normalizeMapRenderConfig } from '../api/mappers/world';
import { logWarn } from '../utils/appError';

export const useMapStore = defineStore('map', () => {
  const mapData = shallowRef<MapMatrix>([]);
  const territoryRows = shallowRef<number[][]>([]);
  const routes = shallowRef<RouteSummary[]>([]);
  const geography = shallowRef<PhysicalGeographySnapshot>({ elevationRows: [], waterBodies: [] });
  const regions = shallowRef<Map<string | number, RegionSummary>>(new Map());
  const pois = shallowRef<Map<string, POISummary>>(new Map());
  const infrastructureSites = shallowRef<Map<string, InfrastructureSiteSummary>>(new Map());
  const renderConfig = ref<MapRenderConfigDTO>(normalizeMapRenderConfig());
  const mapId = ref('classic');
  const mapName = ref('');
  const presetVersion = ref(1);
  const isLoaded = ref(false);
  let preloadMapPromise: Promise<void> | null = null;
  let preloadMapRequestId = 0;

  async function preloadMap() {
    if (isLoaded.value && mapData.value.length > 0) return;
    if (preloadMapPromise) return preloadMapPromise;

    const requestId = ++preloadMapRequestId;
    preloadMapPromise = (async () => {
      const mapRes = await worldApi.fetchMap();
      if (requestId !== preloadMapRequestId) return;

      mapData.value = mapRes.data;
      territoryRows.value = mapRes.territoryRows;
      routes.value = mapRes.routes;
      geography.value = mapRes.geography;
      mapId.value = mapRes.mapId;
      mapName.value = mapRes.mapName;
      presetVersion.value = mapRes.presetVersion;
      renderConfig.value = normalizeMapRenderConfig(mapRes.renderConfig);
      const regionMap = new Map<string | number, RegionSummary>();
      mapRes.regions.forEach(r => regionMap.set(r.id, r));
      regions.value = regionMap;
      const poiMap = new Map<string, POISummary>();
      (mapRes.pois ?? []).forEach(p => poiMap.set(p.id, p));
      pois.value = poiMap;
      const siteMap = new Map<string, InfrastructureSiteSummary>();
      mapRes.infrastructureSites.forEach(site => siteMap.set(site.id, site));
      infrastructureSites.value = siteMap;
      isLoaded.value = true;
    })()
      .catch((e) => {
        logWarn('MapStore preload map', e);
        throw e;
      })
      .finally(() => {
        if (requestId === preloadMapRequestId) {
          preloadMapPromise = null;
        }
      });

    return preloadMapPromise;
  }

  async function refreshPois() {
    const mapRes = await worldApi.fetchMap();
    const poiMap = new Map<string, POISummary>();
    (mapRes.pois ?? []).forEach(poi => poiMap.set(poi.id, poi));
    pois.value = poiMap;
  }

  function reset() {
    preloadMapRequestId++;
    preloadMapPromise = null;
    mapData.value = [];
    territoryRows.value = [];
    routes.value = [];
    geography.value = { elevationRows: [], waterBodies: [] };
    regions.value = new Map();
    pois.value = new Map();
    infrastructureSites.value = new Map();
    renderConfig.value = normalizeMapRenderConfig();
    mapId.value = 'classic';
    mapName.value = '';
    presetVersion.value = 1;
    isLoaded.value = false;
  }

  function applyPoiUpdates(updates: POIUpdateDTO[] | undefined) {
    if (!Array.isArray(updates) || updates.length === 0) return;
    const next = new Map(pois.value);
    updates.forEach((update) => {
      if (update.op === 'remove') {
        next.delete(String(update.id));
      } else if (update.op === 'upsert' && update.poi) {
        next.set(String(update.poi.id), {
          ...update.poi,
          id: String(update.poi.id),
          icon_key: update.poi.icon_key ?? '',
          clickable: update.poi.clickable ?? true,
        });
      }
    });
    pois.value = next;
  }

  function mapInfrastructureSite(site: InfrastructureSiteDTO): InfrastructureSiteSummary {
    return {
      id: String(site.id),
      kind: site.kind,
      name: site.name,
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
    };
  }

  function applyInfrastructureSiteUpdates(updates: InfrastructureSiteUpdateDTO[] | undefined) {
    if (!Array.isArray(updates) || updates.length === 0) return;
    const next = new Map(infrastructureSites.value);
    updates.forEach(update => {
      if (update.op === 'remove') next.delete(String(update.id));
      else next.set(String(update.site.id), mapInfrastructureSite(update.site));
    });
    infrastructureSites.value = next;
  }

  function applyRouteUpdates(updates: RouteUpdateDTO[] | undefined) {
    if (!Array.isArray(updates) || updates.length === 0) return;
    const updatesById = new Map(updates.map(update => [String(update.id), update]));
    routes.value = routes.value.map((route) => {
      const update = updatesById.get(route.id);
      if (!update) return route;
      return {
        ...route,
        operationalCapacity: update.operational_capacity,
        dependencySiteIds: [...update.dependency_site_ids],
      };
    });
  }

  return {
    mapData,
    territoryRows,
    routes,
    geography,
    regions,
    pois,
    infrastructureSites,
    renderConfig,
    mapId,
    mapName,
    presetVersion,
    isLoaded,
    preloadMap,
    refreshPois,
    applyPoiUpdates,
    applyInfrastructureSiteUpdates,
    applyRouteUpdates,
    reset
  };
});
