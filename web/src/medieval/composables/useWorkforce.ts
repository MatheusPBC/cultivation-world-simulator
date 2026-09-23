import { computed } from 'vue'
import { useObserverStore } from '../stores/world'
import { entityName } from '../mappers'
import type { WorkforceKind } from '../../types/medieval-api'

export function useWorkforce() {
  const store = useObserverStore()
  const data = computed(() => store.snapshot!)
  const settlementName = (id: string) => data.value.society.settlements.find(item => item.id === id)?.name ?? id
  const group = (id: string) => data.value.society.population_groups.find(item => item.id === id)
  const workLocation = (kind: WorkforceKind, id: string) => {
    if (kind === 'military_recruitment') {
      const name = settlementName(id)
      return { siteName: name, settlementName: name, siteId: undefined }
    }
    const siteId = kind === 'facility'
      ? data.value.economy.facilities.find(item => item.id === id)?.site_id
      : kind === 'repair'
        ? data.value.economy.repairs.find(item => item.id === id)?.site_id
        : kind === 'research'
          ? data.value.research.projects.find(item => item.id === id)?.site_id
          : data.value.economy.customs_checkpoints.find(item => item.id === id)?.site_id
    const site = siteId ? data.value.map.sites.find(item => item.id === siteId) : undefined
    const settlement = site?.region_ids
      .map(regionId => data.value.society.settlements.find(item => item.region_id === regionId))
      .find(Boolean)
    return { siteName: site?.name ?? id, settlementName: settlement?.name ?? '—', siteId }
  }
  const demandReports = computed(() => data.value.governance.workforce_demand_reports.map(report => ({
    report,
    sponsorName: entityName(data.value, report.sponsor_ref),
    location: workLocation(report.work_kind, report.work_id),
  })).sort((a, b) => b.report.observed_day - a.report.observed_day || a.report.id.localeCompare(b.report.id)))
  const offers = computed(() => data.value.governance.workforce_offer_notices.map(notice => {
    const source = group(notice.source_group_id)
    const demand = data.value.governance.workforce_demand_reports.find(item => item.id === notice.demand_id)
    return { notice, demand, group: source, settlement: source ? settlementName(source.settlement_id) : '—', sponsorName: entityName(data.value, notice.sponsor_ref),
      location: demand ? workLocation(demand.work_kind, demand.work_id) : null }
  }).sort((a, b) => b.notice.observed_day - a.notice.observed_day || a.notice.id.localeCompare(b.notice.id)))
  const transitions = computed(() => data.value.society.workforce_transitions.map(transition => {
    const source = group(transition.source_group_id), target = group(transition.target_group_id)
    return { transition, source, target, sourceSettlement: source ? settlementName(source.settlement_id) : '—', sponsorName: entityName(data.value, transition.sponsor_ref), location: workLocation(transition.work_kind, transition.work_id) }
  }).sort((a, b) => a.transition.due_day - b.transition.due_day || a.transition.id.localeCompare(b.transition.id)))
  const source = (id: string) => { store.focusEventId = id }
  return { data, demandReports, offers, transitions, source }
}
