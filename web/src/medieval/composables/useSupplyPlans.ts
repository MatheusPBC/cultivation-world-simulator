import { computed } from 'vue'
import { useObserverStore } from '../stores/world'
import { calendar, entityName } from '../mappers'

const sameRef = (left: { kind: string; id: string }, right: { kind: string; id: string }) =>
  left.kind === right.kind && left.id === right.id

export function useSupplyPlans() {
  const store = useObserverStore()
  const plans = computed(() => {
    const data = store.snapshot!
    return data.governance.objectives.map(objective => {
      const settlement = data.society.settlements.find(s => s.id === objective.settlement_id)!
      const stockId = objective.stock_id
      const stock = data.economy.stocks.find(s => s.id === stockId)!
      const resource = data.economy.resources.find(r => r.id === objective.resource_id)!
      const plan = data.governance.plans.find(p => p.objective_id === objective.id)
      const pending = plan
        ? data.economy.pending_orders.filter(o => plan.order_ids.includes(o.id))
        : []
      const reports = data.governance.reports.filter(r => r.recipient_ref.kind === objective.actor_ref.kind
        && r.recipient_ref.id === objective.actor_ref.id && r.kind === 'offer' && r.resource_id === resource.id)
        .map(r => ({ ...r, publisherName: entityName(data, r.publisher_ref) }))
      const placeName = (stockRef: string) => {
        const placeId = data.economy.stocks.find(s => s.id === stockRef)?.location_id
        return data.society.settlements.find(s => s.id === placeId)?.name ?? placeId ?? stockRef
      }
      const orders = pending.map(order => ({
        order,
        sourceName: placeName(order.source_id),
        destinationName: placeName(order.destination_id),
        firstDecisionId: order.decision_ids[0] ?? null,
        routeSegments: order.route_ids.map(routeId => {
          const route = data.map.routes.find(item => item.route.id === routeId)
          const endpointNames = route?.route.endpoint_region_ids.map(regionId =>
            data.society.settlements.find(s => s.region_id === regionId)?.name ?? String(regionId)) ?? []
          return {
            id: routeId,
            name: endpointNames.length ? endpointNames.join(' — ') : routeId,
            reports: data.governance.route_reports
              .filter(report => report.route_id === routeId && sameRef(report.recipient_ref, objective.actor_ref))
              .map(report => ({ ...report, observedOn: calendar(report.observed_day) })),
          }
        }),
      }))
      return { objective, plan, settlement, resource, stockId, owner: entityName(data, objective.actor_ref),
        target: objective.target_quantity, stored: stock.goods[resource.id] ?? 0,
        transit: pending.reduce((sum, o) => sum + o.quantity - o.delivered_quantity, 0), reports, orders }
    })
  })
  return { plans, source: (id: string) => { store.focusEventId = id } }
}
